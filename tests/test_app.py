import threading
from datetime import datetime, timezone

from claude_usage_widget import app as app_module
from claude_usage_widget import config as config_module
from claude_usage_widget.models import CreditInfo, LimitInfo, ScopedLimit, UsageSnapshot
from claude_usage_widget.widget_state import Mood, WidgetState


class _FakeWidget:
    def __init__(self):
        self.destroyed = False

    def apply_state(self, state, thresholds):
        pass

    def destroy(self):
        self.destroyed = True


class _FakeTop:
    def winfo_x(self):
        return 100

    def winfo_y(self):
        return 200


class _FakeDetailPanel:
    def render(self, rows, updated_text):
        pass


class _FakeTrayIcon:
    def __init__(self):
        self.icon = None
        self.notify_calls = []

    def notify(self, message):
        self.notify_calls.append(message)


def test_on_settings_saved_persists_config_and_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    saved = {}
    monkeypatch.setattr(app_module.credential_store, "save_session_key", lambda v: saved.setdefault("session_key", v))
    monkeypatch.setattr(app_module, "enable_autostart", lambda: saved.setdefault("autostart", "enabled"))
    monkeypatch.setattr(app_module, "disable_autostart", lambda: saved.setdefault("autostart", "disabled"))

    instance = app_module.App.__new__(app_module.App)
    instance.config = config_module.load_config()
    instance._timer = None
    instance._notified_auth_error = False
    instance._refresh_and_reschedule_cancel_old = lambda: saved.setdefault("rescheduled", True)

    instance._on_settings_saved({
        "session_key": "secret-token",
        "org_id": "org-42",
        "refresh_interval_seconds": 120,
        "thresholds": {"warning": 50, "danger": 80},
        "show_credit": True,
        "autostart_enabled": True,
        "widget_style": "tetris",
        "headline_metric": "max",
    })

    assert saved["session_key"] == "secret-token"
    assert saved["autostart"] == "enabled"
    assert saved["rescheduled"] is True
    assert instance.config["org_id"] == "org-42"
    assert instance.config["thresholds"] == {"warning": 50, "danger": 80}

    reloaded = config_module.load_config()
    assert reloaded["org_id"] == "org-42"


def test_on_settings_saved_disables_autostart_when_unchecked(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    saved = {}
    save_session_key_calls = []
    monkeypatch.setattr(
        app_module.credential_store, "save_session_key", lambda v: save_session_key_calls.append(v)
    )
    monkeypatch.setattr(app_module, "enable_autostart", lambda: saved.setdefault("autostart", "enabled"))
    monkeypatch.setattr(app_module, "disable_autostart", lambda: saved.setdefault("autostart", "disabled"))

    instance = app_module.App.__new__(app_module.App)
    instance.config = config_module.load_config()
    instance._timer = None
    instance._notified_auth_error = False
    instance._refresh_and_reschedule_cancel_old = lambda: None

    instance._on_settings_saved({
        "session_key": None,
        "org_id": "org-42",
        "refresh_interval_seconds": 120,
        "thresholds": {"warning": 50, "danger": 80},
        "show_credit": False,
        "autostart_enabled": False,
        "widget_style": "tetris",
        "headline_metric": "max",
    })

    assert saved["autostart"] == "disabled"
    # session_key was None, so save_session_key must not have been called at all.
    assert save_session_key_calls == []


def test_on_settings_saved_swaps_widget_when_style_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "save_session_key", lambda v: None)
    monkeypatch.setattr(app_module, "enable_autostart", lambda: None)
    monkeypatch.setattr(app_module, "disable_autostart", lambda: None)

    instance = app_module.App.__new__(app_module.App)
    instance.config = config_module.load_config()
    instance.config["widget_style"] = "tetris"
    instance._timer = None
    instance._notified_auth_error = False
    instance._refresh_and_reschedule_cancel_old = lambda: None

    old_widget = _FakeWidget()
    old_widget.top = _FakeTop()
    instance.widget = old_widget

    built_positions = []

    def fake_build_widget(pos):
        built_positions.append(pos)
        new_widget = _FakeWidget()
        new_widget.top = _FakeTop()
        return new_widget

    instance._build_widget = fake_build_widget

    instance._on_settings_saved({
        "session_key": None,
        "org_id": "org-42",
        "refresh_interval_seconds": 120,
        "thresholds": {"warning": 50, "danger": 80},
        "show_credit": False,
        "autostart_enabled": False,
        "widget_style": "hourglass",
        "headline_metric": "max",
    })

    assert instance.config["widget_style"] == "hourglass"
    assert built_positions == [(100, 200)]
    assert instance.widget is not old_widget
    # widget.destroy() 여야 한다 -- top.destroy()만 하면 위젯이 돌리던 after
    # 애니메이션 루프가 살아남아 사라진 캔버스를 건드린다.
    assert old_widget.destroyed is True


def test_on_settings_saved_does_not_swap_widget_when_style_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "save_session_key", lambda v: None)
    monkeypatch.setattr(app_module, "enable_autostart", lambda: None)
    monkeypatch.setattr(app_module, "disable_autostart", lambda: None)

    instance = app_module.App.__new__(app_module.App)
    instance.config = config_module.load_config()
    instance.config["widget_style"] = "tetris"
    instance._timer = None
    instance._notified_auth_error = False
    instance._refresh_and_reschedule_cancel_old = lambda: None

    old_widget = _FakeWidget()
    old_widget.top = _FakeTop()
    instance.widget = old_widget
    instance._build_widget = lambda pos: (_ for _ in ()).throw(AssertionError("should not rebuild"))

    instance._on_settings_saved({
        "session_key": None,
        "org_id": "org-42",
        "refresh_interval_seconds": 120,
        "thresholds": {"warning": 50, "danger": 80},
        "show_credit": False,
        "autostart_enabled": False,
        "widget_style": "tetris",
        "headline_metric": "max",
    })

    assert instance.widget is old_widget
    assert old_widget.destroyed is False


def test_fetch_result_returns_none_when_credentials_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "load_session_key", lambda: None)

    instance = app_module.App.__new__(app_module.App)
    instance.config = {"org_id": None}

    assert instance._fetch_result() is None


def test_fetch_result_returns_exception_when_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "load_session_key", lambda: "key")

    def raise_error(session_key, org_id):
        raise app_module.AuthError("expired")

    monkeypatch.setattr(app_module, "fetch_usage_with_retry", raise_error)

    instance = app_module.App.__new__(app_module.App)
    instance.config = {"org_id": "org-1"}

    result = instance._fetch_result()
    assert isinstance(result, app_module.AuthError)


def test_apply_state_notifies_once_on_auth_error_then_resets():
    instance = app_module.App.__new__(app_module.App)
    instance.config = {"thresholds": {"warning": 50, "danger": 80}}
    instance.widget = _FakeWidget()
    instance.detail_panel = _FakeDetailPanel()
    instance.tray_icon = _FakeTrayIcon()
    instance._notified_auth_error = False

    auth_error_state = WidgetState(
        mood=Mood.AUTH_ERROR,
        headline_percent=0,
        tooltip="재로그인이 필요해요",
        detail_rows=[("sessionKey가 만료되었거나 유효하지 않아요.", None)],
    )

    # Applying the same AUTH_ERROR state twice in a row should only notify once.
    instance._apply_state(auth_error_state)
    instance._apply_state(auth_error_state)
    assert len(instance.tray_icon.notify_calls) == 1
    assert instance._notified_auth_error is True

    # A subsequent non-AUTH_ERROR state resets the dedup flag.
    calm_state = WidgetState(
        mood=Mood.CALM,
        headline_percent=10,
        tooltip="세션 10%",
        detail_rows=[("현재 세션", 10)],
    )
    instance._apply_state(calm_state)
    assert instance._notified_auth_error is False
    assert len(instance.tray_icon.notify_calls) == 1

    # ...so a later AUTH_ERROR state notifies again.
    instance._apply_state(auth_error_state)
    assert len(instance.tray_icon.notify_calls) == 2
    assert instance._notified_auth_error is True


class _FakeRoot:
    """Stand-in for the real Tk root: .after() just calls the function immediately, since
    there's no real event loop pumping in these tests."""

    def after(self, delay, func, *args):
        func(*args)


class _FakeThread:
    """Stand-in for threading.Thread that records what it would have run instead of actually
    starting a background thread -- lets tests drive _background_refresh() invocations
    synchronously, in whatever order they want, to simulate overlapping refreshes without any
    real threads or timing."""

    instances = []

    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args
        _FakeThread.instances.append(self)

    def start(self):
        pass  # deliberately does not run target; the test calls it manually


class _FakeTimer:
    """Stand-in for threading.Timer that records creation (so tests can assert whether a new
    Timer was -- or wasn't -- scheduled) without actually waiting or firing."""

    instances = []

    def __init__(self, interval, target, args=()):
        self.interval = interval
        self.target = target
        self.args = args
        self.cancelled = False
        _FakeTimer.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


def _make_refresh_test_instance():
    instance = app_module.App.__new__(app_module.App)
    instance.config = {"thresholds": {"warning": 50, "danger": 80}, "refresh_interval_seconds": 180}
    instance._timer = None
    instance._timer_lock = threading.Lock()
    instance._refresh_generation = 0
    instance._quitting = False
    instance._last_snapshot = None
    instance.widget = _FakeWidget()
    instance.detail_panel = _FakeDetailPanel()
    instance.tray_icon = _FakeTrayIcon()
    instance._notified_auth_error = False
    instance.root = _FakeRoot()
    return instance


def test_overlapping_refresh_generations_discard_stale_result(monkeypatch):
    """Two refreshes triggered back-to-back (e.g. two manual-refresh clicks, or a manual refresh
    followed by a settings save) while the first is still "in flight" must not both win: only
    the latest-triggered refresh's result should be applied and only it should reschedule the
    next periodic timer. The older, superseded refresh must silently discard its result."""
    instance = _make_refresh_test_instance()

    _FakeThread.instances = []
    _FakeTimer.instances = []
    monkeypatch.setattr(app_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(app_module.threading, "Timer", _FakeTimer)
    monkeypatch.setattr(instance, "_fetch_result", lambda: None)

    applied_states = []
    monkeypatch.setattr(instance, "_apply_state", lambda state: applied_states.append(state))

    # Trigger #1 (e.g. first click of 새로고침) -> generation 1. Thread doesn't actually run yet.
    instance._refresh_and_reschedule_cancel_old()
    assert instance._refresh_generation == 1
    gen1_thread = _FakeThread.instances[0]

    # Trigger #2 (e.g. a second click, or settings save, while #1 is still "mid-fetch") ->
    # generation 2, and cancels the (still-None) pending periodic timer.
    instance._refresh_and_reschedule_cancel_old()
    assert instance._refresh_generation == 2
    gen2_thread = _FakeThread.instances[1]

    # Simulate #2's fetch completing first (it's the latest generation).
    gen2_thread.target(*gen2_thread.args)
    assert len(applied_states) == 1
    assert len(_FakeTimer.instances) == 1  # only #2 rescheduled

    # Simulate #1's fetch completing afterwards -- it's now stale (generation 1 != current 2)
    # and must be discarded silently: no extra _apply_state call, no extra Timer created.
    gen1_thread.target(*gen1_thread.args)
    assert len(applied_states) == 1
    assert len(_FakeTimer.instances) == 1


def test_second_trigger_after_first_writes_timer_does_not_orphan_it(monkeypatch):
    """Reproduces the gap a reviewer found in an earlier version of the fix: the freshness check
    and the self._timer write used to happen in two separate lock acquisitions (the check in
    _background_refresh(), then an unconditional write in a later call to
    _schedule_next_refresh()). That left a window, between "check passed" and "Timer written",
    during which a second trigger could run to completion -- fetch, pass its own check, and
    write its own Timer into self._timer -- only to have the first (now-stale) refresh clobber
    it moments later when it finally reached its own write. The clobbered Timer was left
    orphaned: unreferenced by self._timer, never cancellable via quit(), but still alive and due
    to fire later.

    This test simulates that interleaving by hooking root.after() (the call _background_refresh()
    makes right after its critical section, on the fresh path) to synchronously trigger and run
    a second refresh to completion before control returns to the first. With the fix, the first
    refresh's Timer is already created/assigned/started *before* root.after() is ever called, so
    when the second refresh's _refresh_and_reschedule_cancel_old() runs, it finds a real,
    still-pending Timer to cancel -- no orphan. Before the fix, this hook lands exactly in the
    gap between the first refresh's check and its (unconditional) write, so the first refresh's
    write would clobber the second refresh's Timer without ever cancelling it."""
    instance = _make_refresh_test_instance()

    _FakeThread.instances = []
    _FakeTimer.instances = []
    monkeypatch.setattr(app_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(app_module.threading, "Timer", _FakeTimer)
    monkeypatch.setattr(instance, "_fetch_result", lambda: None)

    applied_states = []
    triggered = {"done": False}

    def after_hook(delay, func, *args):
        # Apply this refresh's state first, same as the real (immediate) _FakeRoot.after would.
        func(*args)
        if triggered["done"]:
            return
        triggered["done"] = True
        # Simulate a second trigger (e.g. another manual-refresh click) arriving and running to
        # completion while the first refresh is "on its way" to reschedule.
        instance._refresh_and_reschedule_cancel_old()
        second_thread = _FakeThread.instances[-1]
        second_thread.target(*second_thread.args)

    instance._apply_state = lambda state: applied_states.append(state)
    instance.root = type("_HookRoot", (), {"after": staticmethod(after_hook)})()

    # Trigger #1 (generation 1).
    instance._refresh_and_reschedule_cancel_old()
    assert instance._refresh_generation == 1
    first_thread = _FakeThread.instances[0]

    # Run #1. Its root.after() call (see after_hook above) fires the second trigger and runs it
    # to completion before #1's own call stack unwinds.
    first_thread.target(*first_thread.args)

    assert instance._refresh_generation == 2
    assert len(_FakeTimer.instances) == 2
    first_timer, second_timer = _FakeTimer.instances

    # The second (newer) refresh must own self._timer...
    assert instance._timer is second_timer
    # ...and the first refresh's Timer must have been properly cancelled by the second trigger's
    # cancel-old logic, not silently orphaned (unreferenced and still alive).
    assert first_timer.cancelled is True
    assert second_timer.cancelled is False

    # No Timer anywhere is both unreferenced by self._timer AND still uncancelled.
    for timer in _FakeTimer.instances:
        assert timer is instance._timer or timer.cancelled

    # Both refreshes' results were applied (each was still current at the moment its own
    # root.after() fired) -- that's expected and fine; the bug this test targets is about Timer
    # bookkeeping, not about suppressing UI updates.
    assert len(applied_states) == 2


def test_background_refresh_discarded_after_quit(monkeypatch):
    """A _background_refresh() that finishes fetching after quit() has already run must not
    touch self.root (which quit() is in the process of destroying) or schedule a new Timer."""
    instance = _make_refresh_test_instance()
    instance._quitting = True
    instance._refresh_generation = 5

    _FakeTimer.instances = []
    monkeypatch.setattr(app_module.threading, "Timer", _FakeTimer)
    monkeypatch.setattr(instance, "_fetch_result", lambda: None)

    applied_states = []
    monkeypatch.setattr(instance, "_apply_state", lambda state: applied_states.append(state))

    instance._background_refresh(my_generation=5)  # matches current generation, but quitting

    assert applied_states == []
    assert _FakeTimer.instances == []


def _snapshot(session_pct=42, weekly_pct=17):
    now = datetime.now(timezone.utc)
    return UsageSnapshot(
        session=LimitInfo(percent=session_pct, resets_at=now),
        weekly_all=LimitInfo(percent=weekly_pct, resets_at=now),
        weekly_scoped=[ScopedLimit(model_name="Fable", percent=19, resets_at=now)],
        credit=CreditInfo(enabled=False, percent=0, used_dollars=0.0, limit_dollars=None),
        fetched_at=now,
    )


def test_resolve_state_passes_show_credit_from_config():
    """Finding 1: show_credit must actually reach compute_widget_state/resolve_state, not just
    sit unused in config."""
    instance = _make_refresh_test_instance()
    snapshot = _snapshot()
    snapshot.credit.enabled = True

    instance.config["show_credit"] = True
    state_on = instance._resolve_state(snapshot)
    labels_on = [row[0] for row in state_on.detail_rows]
    assert any("크레딧" in label for label in labels_on)

    instance.config["show_credit"] = False
    state_off = instance._resolve_state(snapshot)
    labels_off = [row[0] for row in state_off.detail_rows]
    assert not any("크레딧" in label for label in labels_off)


def test_transient_error_after_success_retains_last_known_numbers():
    """Finding 2: a transient fetch failure that follows a successful fetch must keep showing
    the last known real percentages in detail_rows, not just the generic error line."""
    instance = _make_refresh_test_instance()

    snapshot = _snapshot(session_pct=42, weekly_pct=17)
    state1 = instance._resolve_state(snapshot)
    assert state1.mood == Mood.CALM

    # Simulate _fetch_result() having cached the successful snapshot (as the real method does).
    instance._last_snapshot = snapshot

    state2 = instance._resolve_state(app_module.TransientError("network blip"))

    assert state2.mood == Mood.WARNING
    # 라벨엔 위젯이 따라가는 줄을 가리키는 "◀ 위젯" 표시가 붙을 수 있다
    session_row = next(row for row in state2.detail_rows if row[0].startswith("현재 세션"))
    weekly_row = next(row for row in state2.detail_rows if row[0].startswith("주간 한도 (전체 모델)"))
    assert session_row[1] == 42
    assert weekly_row[1] == 17
    # Not just the old generic single-line error message.
    assert state2.detail_rows != [("네트워크 오류로 최신 값을 가져오지 못했어요.", None)]


def test_resolve_state_passes_headline_metric_from_config():
    """Finding 1과 같은 부류: headline_metric이 config에만 있고 실제 계산까지
    전달되지 않으면 설정이 아무 일도 안 한다."""
    instance = _make_refresh_test_instance()
    snapshot = _snapshot(session_pct=9, weekly_pct=88)

    instance.config["headline_metric"] = "session"
    assert instance._resolve_state(snapshot).headline_percent == 9

    instance.config["headline_metric"] = "weekly"
    assert instance._resolve_state(snapshot).headline_percent == 88

    instance.config["headline_metric"] = "max"
    assert instance._resolve_state(snapshot).headline_percent == 88


def test_transient_error_fallback_respects_headline_metric():
    """마지막 성공값으로 되돌릴 때도 사용자가 고른 지표를 그대로 따라야 한다."""
    instance = _make_refresh_test_instance()
    instance.config["headline_metric"] = "session"
    instance._last_snapshot = _snapshot(session_pct=42, weekly_pct=88)

    state = instance._resolve_state(app_module.TransientError("network blip"))

    assert state.headline_percent == 42


def test_transient_error_without_prior_success_falls_back_to_generic_message():
    """When no snapshot has ever succeeded, there's nothing to fall back to -- keep the original
    generic error row instead of crashing or showing stale-but-fake data."""
    instance = _make_refresh_test_instance()
    assert instance._last_snapshot is None

    state = instance._resolve_state(app_module.TransientError("network blip"))

    assert state.mood == Mood.WARNING
    assert state.detail_rows == [("네트워크 오류로 최신 값을 가져오지 못했어요.", None)]


def test_fetch_result_caches_last_snapshot_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "load_session_key", lambda: "key")

    snapshot = _snapshot()
    monkeypatch.setattr(app_module, "fetch_usage_with_retry", lambda session_key, org_id: snapshot)

    instance = app_module.App.__new__(app_module.App)
    instance.config = {"org_id": "org-1"}
    instance._last_snapshot = None

    result = instance._fetch_result()

    assert result is snapshot
    assert instance._last_snapshot is snapshot


def test_handle_first_run_shows_disclaimer_then_opens_settings(monkeypatch):
    instance = app_module.App.__new__(app_module.App)
    instance._first_run = True
    calls = []
    monkeypatch.setattr(instance, "_show_first_run_disclaimer", lambda: calls.append("disclaimer"))
    monkeypatch.setattr(instance, "_open_settings", lambda: calls.append("settings"))

    instance._handle_first_run()

    assert calls == ["disclaimer", "settings"]


def test_handle_first_run_does_nothing_on_subsequent_runs(monkeypatch):
    instance = app_module.App.__new__(app_module.App)
    instance._first_run = False
    calls = []
    monkeypatch.setattr(instance, "_show_first_run_disclaimer", lambda: calls.append("disclaimer"))
    monkeypatch.setattr(instance, "_open_settings", lambda: calls.append("settings"))

    instance._handle_first_run()

    assert calls == []


def test_show_first_run_disclaimer_mentions_unofficial_api_and_session_key(monkeypatch):
    instance = app_module.App.__new__(app_module.App)
    calls = []
    monkeypatch.setattr(app_module.messagebox, "showwarning", lambda title, msg: calls.append((title, msg)))

    instance._show_first_run_disclaimer()

    assert len(calls) == 1
    _, message = calls[0]
    assert "비공식" in message
    assert "sessionKey" in message
