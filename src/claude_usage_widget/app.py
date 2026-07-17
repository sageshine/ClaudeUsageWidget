import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from . import config as config_module
from . import credential_store
from .api_client import AuthError, TransientError, fetch_usage_with_retry
from .autostart import disable_autostart, enable_autostart
from .detail_panel import DetailPanel
from .hourglass_widget import HourglassWidget
from .logging_setup import get_logger
from .number_widget import NumberWidget
from .settings_ui import SettingsDialog
from .tray import build_tray_icon, make_icon_image
from .widget import CharacterWidget
from .widget_state import Mood, WidgetState, compute_widget_state, resolve_state

logger = get_logger()

_WIDGET_CLASSES = {"tetris": CharacterWidget, "hourglass": HourglassWidget, "number": NumberWidget}


class App:
    def __init__(self):
        self.config = config_module.load_config()
        self._first_run = not config_module.config_path().exists()

        self.root = tk.Tk()
        self.root.withdraw()

        pos = tuple(self.config.get("widget_position") or [100, 100])
        self.widget = self._build_widget(pos)
        self.detail_panel = DetailPanel(self.root, self._manual_refresh, self._open_settings, self.quit)
        self.settings_dialog = SettingsDialog(self.root, self.config, self._on_settings_saved)
        self.tray_icon = build_tray_icon(Mood.SETUP_NEEDED, self._toggle_widget, self._open_settings, self.quit)

        self._notified_auth_error = False
        # Last successfully-fetched snapshot, used to keep showing real numbers (instead of a
        # generic error line) in the detail panel when a subsequent refresh hits a transient
        # network failure. See _resolve_state()/_fetch_result().
        self._last_snapshot = None
        self._timer = None
        # Guards reads/writes of self._timer, self._refresh_generation and self._quitting:
        # _schedule_next_refresh() runs on whatever background thread is doing a refresh (the
        # periodic Timer's own thread, or a thread spawned by
        # _refresh_and_reschedule_cancel_old()), while _refresh_and_reschedule_cancel_old() and
        # quit() can read/cancel/mutate them from the Tk main thread at the same time.
        self._timer_lock = threading.Lock()
        # Generation counter ("epoch") used to detect and discard stale results from overlapping
        # _background_refresh() calls -- see _background_refresh()'s docstring for the full
        # explanation of the race this prevents.
        self._refresh_generation = 0
        # Set True by quit(); lets an in-flight _background_refresh() notice the app is shutting
        # down and avoid touching self.root (which quit() schedules for destruction) after the
        # fact.
        self._quitting = False

        self._handle_first_run()

        # NOTE: this very first fetch runs synchronously, before root.mainloop() has started.
        # That's a deliberate exception to the "never fetch on the Tk thread" rule applied
        # everywhere else below: at this point the window is still withdrawn, no event loop is
        # pumping yet, and no user interaction is possible, so there's nothing for a blocking
        # call to freeze. Doing it in the background instead would mean the window briefly shows
        # a SETUP_NEEDED placeholder that re-renders moments later -- extra complexity for a
        # one-time startup delay that's already bounded by fetch_usage_with_retry's own
        # retry/backoff ceiling. Kept as documented tech debt rather than changed.
        self._refresh_and_reschedule()

    def _build_widget(self, pos):
        widget_cls = _WIDGET_CLASSES.get(self.config.get("widget_style", "tetris"), CharacterWidget)
        return widget_cls(self.root, pos, self._on_widget_move, self._on_widget_right_click)

    def _fetch_result(self):
        session_key = credential_store.load_session_key()
        org_id = self.config.get("org_id")
        if not session_key or not org_id:
            return None
        try:
            snapshot = fetch_usage_with_retry(session_key, org_id)
        except Exception as exc:  # AuthError 또는 재시도 소진 후 TransientError
            logger.error("usage fetch failed: %s", exc)
            return exc
        self._last_snapshot = snapshot
        return snapshot

    def _resolve_state(self, result):
        """resolve_state() plus "last known good" fallback: on a transient fetch failure (any
        Exception other than AuthError -- i.e. the WARNING mood), if a previous fetch succeeded,
        replace the generic error row with that snapshot's real numbers so the detail panel
        keeps showing actual session/weekly percentages instead of just an error line. The
        WARNING mood/color is kept as-is so the UI still signals something's wrong."""
        show_credit = self.config.get("show_credit", False)
        metric = self.config.get("headline_metric", "max")
        state = resolve_state(result, self.config["thresholds"], show_credit, headline_metric=metric)
        if isinstance(result, Exception) and not isinstance(result, AuthError) and self._last_snapshot is not None:
            last_known = compute_widget_state(
                self._last_snapshot, self.config["thresholds"], show_credit, headline_metric=metric
            )
            state = WidgetState(
                mood=state.mood,
                headline_percent=last_known.headline_percent,
                tooltip=f"⚠ 갱신 실패, 마지막 값: {last_known.tooltip}",
                detail_rows=last_known.detail_rows,
            )
        return state

    def _refresh_and_reschedule(self):
        """Synchronous fetch + apply + reschedule. Only safe to call before the Tk event loop
        is running (see the comment in __init__) -- everywhere else, use
        _refresh_and_reschedule_cancel_old()/_background_refresh() instead, which do the fetch
        on a background thread."""
        result = self._fetch_result()
        state = self._resolve_state(result)
        self._apply_state(state)
        self._schedule_next_refresh()

    def _refresh_and_reschedule_cancel_old(self):
        """Cancel any pending periodic timer and kick off a fresh refresh on a background
        thread. Safe to call from the Tk main thread (manual refresh button, settings dialog
        save) since the actual network fetch -- which can sleep for several seconds across
        fetch_usage_with_retry's exponential backoff -- never runs on the calling thread.

        Only cancels the *pending, not-yet-fired* periodic timer, so a tick that's about to fire
        doesn't also start a redundant fetch. It does NOT try to stop an already-in-flight fetch
        thread (there's no safe way to abort a thread mid-fetch) -- instead it bumps
        self._refresh_generation so that if an older in-flight _background_refresh() finishes
        later, it recognizes it's been superseded and discards its own result. See
        _background_refresh()'s docstring for the full race this prevents."""
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._refresh_generation += 1
            my_generation = self._refresh_generation
        threading.Thread(target=self._background_refresh, args=(my_generation,), daemon=True).start()

    def _schedule_next_refresh(self):
        """Only used by _refresh_and_reschedule()'s one-time synchronous startup call (see its
        docstring) -- at that point nothing else can be concurrently touching self._timer, so a
        plain unconditional write is safe. _background_refresh() does NOT call this: it inlines
        the same create/assign/start sequence into its own freshness-check lock so the two
        happen atomically -- see its docstring for why that distinction matters."""
        interval = self.config.get("refresh_interval_seconds", 180)
        timer = threading.Timer(interval, self._background_refresh)
        timer.daemon = True
        with self._timer_lock:
            if self._quitting:
                # quit() already ran (or is running) -- don't leave a fresh Timer alive after
                # shutdown; it would just wake up later to do a pointless fetch.
                return
            self._timer = timer
        timer.start()

    def _background_refresh(self, my_generation=None):
        """Runs on a background thread (either the periodic Timer's own thread, or a thread
        spawned by _refresh_and_reschedule_cancel_old()). Performs the network fetch off the Tk
        main thread, marshals the resulting state back via root.after, and reschedules the next
        periodic tick.

        Overlapping-refresh race this guards against: nothing stops two _background_refresh()
        calls from running concurrently on different threads (e.g. the user clicks manual
        refresh twice, or saves settings while a manual refresh is still retrying via
        fetch_usage_with_retry's exponential backoff -- which can take up to ~30s). Each one
        independently fetches, then would independently want to reschedule, and whichever's
        Timer loses that overwrite race becomes an orphaned, uncancellable Timer that still
        fires later. To prevent that, every trigger of a refresh -- the periodic Timer firing
        (my_generation left as None here, so it self-assigns the next generation right below)
        and _refresh_and_reschedule_cancel_old() (which pre-assigns my_generation before
        spawning this thread) -- gets its own generation number. Only the refresh holding the
        *current* generation number when its fetch completes is allowed to create/start the next
        Timer; any older, superseded refresh silently discards its result instead.

        The freshness check and the self._timer write below happen inside a SINGLE
        `with self._timer_lock:` block -- this used to be two separate lock acquisitions (a
        check here, then an unconditional write in a later call to _schedule_next_refresh()),
        which left a check-then-act gap: a refresh could pass its freshness check, then -- before
        it reached the write -- get superseded by a newer refresh that ran to completion and
        wrote *its* Timer into self._timer, only to have the original refresh's now-stale write
        clobber it moments later, orphaning the newer Timer (unreferenced by self._timer, never
        cancellable via quit(), but still alive and due to fire later). Doing the check and the
        write in one uninterrupted critical section closes that gap: once a refresh has
        confirmed (under the lock) that it's still current, nothing can supersede it before its
        Timer is created, assigned, and started, because that all happens before the lock is
        released.

        This also doubles as the quit() guard: quit() bumps nothing but sets self._quitting,
        checked in the same locked block, so a refresh that finishes fetching after quit() never
        creates a new Timer and never touches self.root (which quit() is busy destroying)."""
        if my_generation is None:
            with self._timer_lock:
                self._refresh_generation += 1
                my_generation = self._refresh_generation
        result = self._fetch_result()
        state = self._resolve_state(result)
        interval = self.config.get("refresh_interval_seconds", 180)
        with self._timer_lock:
            if self._quitting or my_generation != self._refresh_generation:
                # Superseded by a newer refresh (or the app is shutting down) -- discard this
                # result silently, without creating a Timer or touching self.root. The newer
                # refresh (or nothing, if quitting) owns applying state and rescheduling.
                return
            timer = threading.Timer(interval, self._background_refresh)
            timer.daemon = True
            self._timer = timer
            timer.start()
        # Applying the UI state doesn't need the lock (root.after is thread-safe to call from
        # any thread) and only ever runs for the refresh that just atomically won the section
        # above, so it's fine -- and simpler -- to do it after releasing the lock.
        self.root.after(0, self._apply_state, state)

    def _manual_refresh(self):
        self._refresh_and_reschedule_cancel_old()

    def _apply_state(self, state):
        self.widget.apply_state(state, self.config["thresholds"])
        now_text = f"마지막 업데이트: {datetime.now().strftime('%H:%M')}"
        self.detail_panel.render(state.detail_rows, now_text)
        self.tray_icon.icon = make_icon_image(state.mood)

        if state.mood == Mood.AUTH_ERROR and not self._notified_auth_error:
            self._notify("재로그인이 필요해요. 설정에서 sessionKey를 다시 입력해주세요.")
            self._notified_auth_error = True
        elif state.mood != Mood.AUTH_ERROR:
            self._notified_auth_error = False

    def _notify(self, message: str):
        try:
            self.tray_icon.notify(message)
        except NotImplementedError:
            logger.info("tray notifications not supported on this platform: %s", message)

    def _on_widget_move(self, pos):
        self.config["widget_position"] = list(pos)
        config_module.save_config(self.config)

    def _on_widget_right_click(self):
        x = self.widget.top.winfo_x()
        y = self.widget.top.winfo_y() + self.widget.HEIGHT
        self.detail_panel.show_at(x, y)

    def _handle_first_run(self):
        """On the very first launch (no config.json yet), show the mandatory unofficial-API
        disclaimer before opening settings, so the user reads it before entering sessionKey."""
        if not self._first_run:
            return
        self._show_first_run_disclaimer()
        self._open_settings()

    def _show_first_run_disclaimer(self):
        messagebox.showwarning(
            "알림",
            "이 위젯은 Anthropic이 공식 지원하지 않는 claude.ai 비공식 API를 사용합니다.\n"
            "Anthropic 쪽 구현이 바뀌면 사전 공지 없이 동작이 멈출 수 있습니다.\n\n"
            "잠시 후 입력할 sessionKey 쿠키 값은 로그인 정보와 동일한 민감한 값입니다.\n"
            "Windows 자격 증명 관리자(Credential Manager)에 암호화되어 저장되며, "
            "claude.ai 외 다른 곳으로는 전송되지 않습니다.",
        )

    def _open_settings(self):
        """May be invoked from the pystray background thread (tray menu item "설정") as well as
        the Tk main thread (detail panel's settings button). Marshal onto the main thread via
        root.after so Tk widgets are only ever touched from the thread that owns them -- same
        pattern quit() uses."""
        self.root.after(0, self.settings_dialog.show)

    def _on_settings_saved(self, values):
        if values["session_key"]:
            credential_store.save_session_key(values["session_key"])
        style_changed = values["widget_style"] != self.config.get("widget_style", "tetris")

        self.config["org_id"] = values["org_id"]
        self.config["refresh_interval_seconds"] = values["refresh_interval_seconds"]
        self.config["thresholds"] = values["thresholds"]
        self.config["show_credit"] = values["show_credit"]
        self.config["autostart_enabled"] = values["autostart_enabled"]
        self.config["widget_style"] = values["widget_style"]
        self.config["headline_metric"] = values["headline_metric"]
        config_module.save_config(self.config)

        if values["autostart_enabled"]:
            enable_autostart()
        else:
            disable_autostart()

        if style_changed:
            self._swap_widget()

        self._refresh_and_reschedule_cancel_old()

    def _swap_widget(self):
        """설정에서 위젯 모양을 바꾸면, 같은 위치에 새 위젯을 만들고 기존 것은
        없앤다. 다음 새로고침이 새 위젯에 바로 상태를 반영해준다.

        widget.destroy()를 쓰는 이유: 위젯들은 저마다 canvas.after 애니메이션
        루프를 돌리고 있어서, 예약된 콜백을 취소하지 않고 창만 없애면 남은
        콜백이 사라진 캔버스를 건드리며 터진다."""
        pos = (self.widget.top.winfo_x(), self.widget.top.winfo_y())
        old_widget = self.widget
        self.widget = self._build_widget(pos)
        old_widget.destroy()

    def _toggle_widget(self):
        """Invoked from the pystray background thread (tray menu item "위젯 표시/숨김"). Marshal
        the actual Tk widget state mutation onto the main thread via root.after -- same pattern
        quit() uses -- since .state()/.deiconify()/.withdraw() must run on the thread that owns
        the Tk widget."""
        def _do_toggle():
            if self.widget.top.state() == "withdrawn":
                self.widget.top.deiconify()
            else:
                self.widget.top.withdraw()

        self.root.after(0, _do_toggle)

    def quit(self):
        with self._timer_lock:
            self._quitting = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.root.mainloop()


def main():
    app = App()
    app.run()
