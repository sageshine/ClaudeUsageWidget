from claude_usage_widget import config


def test_load_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = config.load_config()
    assert result["refresh_interval_seconds"] == 180
    assert result["thresholds"] == {"warning": 60, "danger": 85}
    assert result["autostart_enabled"] is False


def test_save_then_load_round_trips_values(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    data = config.load_config()
    data["org_id"] = "org-123"
    data["refresh_interval_seconds"] = 300
    config.save_config(data)

    reloaded = config.load_config()
    assert reloaded["org_id"] == "org-123"
    assert reloaded["refresh_interval_seconds"] == 300


def test_load_config_recovers_from_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config.config_dir()  # ensures dir exists
    config.config_path().write_text("{not valid json", encoding="utf-8")

    result = config.load_config()
    assert result["refresh_interval_seconds"] == 180
