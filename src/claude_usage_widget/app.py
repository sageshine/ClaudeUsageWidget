import threading
import tkinter as tk
from datetime import datetime

from . import config as config_module
from . import credential_store
from .api_client import AuthError, fetch_usage_with_retry
from .autostart import disable_autostart, enable_autostart
from .detail_panel import DetailPanel
from .logging_setup import get_logger
from .settings_ui import SettingsDialog
from .tray import build_tray_icon, make_icon_image
from .widget import CharacterWidget
from .widget_state import Mood, resolve_state

logger = get_logger()


class App:
    def __init__(self):
        self.config = config_module.load_config()
        self._first_run = not config_module.config_path().exists()

        self.root = tk.Tk()
        self.root.withdraw()

        pos = tuple(self.config.get("widget_position") or [100, 100])
        self.widget = CharacterWidget(self.root, pos, self._on_widget_move, self._on_widget_right_click)
        self.detail_panel = DetailPanel(self.root, self._manual_refresh, self._open_settings, self.quit)
        self.settings_dialog = SettingsDialog(self.root, self.config, self._on_settings_saved)
        self.tray_icon = build_tray_icon(Mood.SETUP_NEEDED, self._toggle_widget, self._open_settings, self.quit)

        self._notified_auth_error = False
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

        if self._first_run:
            self._open_settings()

        # NOTE: this very first fetch runs synchronously, before root.mainloop() has started.
        # That's a deliberate exception to the "never fetch on the Tk thread" rule applied
        # everywhere else below: at this point the window is still withdrawn, no event loop is
        # pumping yet, and no user interaction is possible, so there's nothing for a blocking
        # call to freeze. Doing it in the background instead would mean the window briefly shows
        # a SETUP_NEEDED placeholder that re-renders moments later -- extra complexity for a
        # one-time startup delay that's already bounded by fetch_usage_with_retry's own
        # retry/backoff ceiling. Kept as documented tech debt rather than changed.
        self._refresh_and_reschedule()

    def _fetch_result(self):
        session_key = credential_store.load_session_key()
        org_id = self.config.get("org_id")
        if not session_key or not org_id:
            return None
        try:
            return fetch_usage_with_retry(session_key, org_id)
        except Exception as exc:  # AuthError 또는 재시도 소진 후 TransientError
            logger.error("usage fetch failed: %s", exc)
            return exc

    def _refresh_and_reschedule(self):
        """Synchronous fetch + apply + reschedule. Only safe to call before the Tk event loop
        is running (see the comment in __init__) -- everywhere else, use
        _refresh_and_reschedule_cancel_old()/_background_refresh() instead, which do the fetch
        on a background thread."""
        result = self._fetch_result()
        state = resolve_state(result, self.config["thresholds"])
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
        independently fetches, then would independently call _schedule_next_refresh(), and
        whichever's Timer loses that overwrite race becomes an orphaned, uncancellable Timer
        that still fires later. To prevent that, every trigger of a refresh -- the periodic
        Timer firing (my_generation left as None here, so it self-assigns the next generation
        right below) and _refresh_and_reschedule_cancel_old() (which pre-assigns my_generation
        before spawning this thread) -- gets its own generation number. Only the refresh holding
        the *current* generation number when its fetch completes is allowed to apply its result
        and reschedule; any older, superseded refresh silently discards its result instead. This
        also doubles as the quit() guard: quit() bumps nothing but sets self._quitting, checked
        in the same locked block, so a refresh that finishes fetching after quit() never touches
        self.root (which quit() is busy destroying)."""
        if my_generation is None:
            with self._timer_lock:
                self._refresh_generation += 1
                my_generation = self._refresh_generation
        result = self._fetch_result()
        state = resolve_state(result, self.config["thresholds"])
        with self._timer_lock:
            if self._quitting or my_generation != self._refresh_generation:
                # Superseded by a newer refresh (or the app is shutting down) -- discard this
                # result silently. The newer refresh (or nothing, if quitting) owns applying
                # state and rescheduling from here.
                return
        self.root.after(0, self._apply_state, state)
        self._schedule_next_refresh()

    def _manual_refresh(self):
        self._refresh_and_reschedule_cancel_old()

    def _apply_state(self, state):
        self.widget.apply_state(state)
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
        y = self.widget.top.winfo_y() + CharacterWidget.SIZE
        self.detail_panel.show_at(x, y)

    def _open_settings(self):
        """May be invoked from the pystray background thread (tray menu item "설정") as well as
        the Tk main thread (detail panel's settings button). Marshal onto the main thread via
        root.after so Tk widgets are only ever touched from the thread that owns them -- same
        pattern quit() uses."""
        self.root.after(0, self.settings_dialog.show)

    def _on_settings_saved(self, values):
        if values["session_key"]:
            credential_store.save_session_key(values["session_key"])
        self.config["org_id"] = values["org_id"]
        self.config["refresh_interval_seconds"] = values["refresh_interval_seconds"]
        self.config["thresholds"] = values["thresholds"]
        self.config["show_credit"] = values["show_credit"]
        self.config["autostart_enabled"] = values["autostart_enabled"]
        config_module.save_config(self.config)

        if values["autostart_enabled"]:
            enable_autostart()
        else:
            disable_autostart()

        self._refresh_and_reschedule_cancel_old()

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
