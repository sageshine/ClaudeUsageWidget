import threading

from claude_usage_widget import app as app_module
from claude_usage_widget import config as config_module
from claude_usage_widget.widget_state import Mood, WidgetState


class _FakeWidget:
    def apply_state(self, state):
        pass


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
    })

    assert saved["autostart"] == "disabled"
    # session_key was None, so save_session_key must not have been called at all.
    assert save_session_key_calls == []


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
