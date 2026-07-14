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
