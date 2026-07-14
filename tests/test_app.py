from claude_usage_widget import app as app_module
from claude_usage_widget import config as config_module


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
    monkeypatch.setattr(app_module.credential_store, "save_session_key", lambda v: None)
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
