import tkinter as tk

import pytest

from claude_usage_widget import settings_ui
from claude_usage_widget.config import DEFAULT_CONFIG


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_save_calls_on_save_with_expected_values(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.session_key_var.set("  secret-token  ")
    dialog.org_id_var.set("org-1")
    dialog.interval_var.set(120)
    dialog.warning_var.set(50)
    dialog.danger_var.set(80)
    dialog.credit_var.set(True)
    dialog.autostart_var.set(True)

    dialog._save()

    assert len(saved) == 1
    result = saved[0]
    assert result["session_key"] == "secret-token"
    assert result["org_id"] == "org-1"
    assert result["refresh_interval_seconds"] == 120
    assert result["thresholds"] == {"warning": 50, "danger": 80}
    assert result["show_credit"] is True
    assert result["autostart_enabled"] is True
    dialog.top.destroy()


def test_save_rejects_warning_threshold_greater_than_or_equal_danger(root, monkeypatch):
    errors = []
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda title, msg: errors.append(msg))
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.warning_var.set(90)
    dialog.danger_var.set(80)
    dialog._save()

    assert saved == []
    assert len(errors) == 1
    dialog.top.destroy()


def test_save_shows_error_when_spinbox_has_non_numeric_input(root, monkeypatch):
    """Finding 4: a hand-typed non-numeric Spinbox value makes IntVar.get() raise tk.TclError.
    In a --windowed build that exception would otherwise vanish silently -- 저장 must instead
    show an error and leave on_save uncalled."""
    errors = []
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda title, msg: errors.append(msg))
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    def raise_tclerror():
        raise tk.TclError("expected integer, got junk")

    monkeypatch.setattr(dialog.interval_var, "get", raise_tclerror)

    dialog._save()

    assert saved == []
    assert len(errors) == 1
    assert "숫자" in errors[0]
    dialog.top.destroy()


def test_enforces_minimum_refresh_interval_of_60_seconds(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.interval_var.set(10)
    dialog._save()

    assert saved[0]["refresh_interval_seconds"] == 60
    dialog.top.destroy()


def test_headline_metric_dropdown_reflects_config_and_saves_selection(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    config = dict(DEFAULT_CONFIG)
    config["headline_metric"] = "weekly"
    dialog = settings_ui.SettingsDialog(root, config, on_save=saved.append)

    assert dialog.headline_metric_var.get() == settings_ui.HEADLINE_METRIC_LABELS["weekly"]

    dialog.headline_metric_var.set(settings_ui.HEADLINE_METRIC_LABELS["session"])
    dialog._save()

    assert saved[0]["headline_metric"] == "session"
    dialog.top.destroy()


def test_headline_metric_defaults_to_max_when_config_key_missing(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    config = dict(DEFAULT_CONFIG)
    config.pop("headline_metric", None)  # 예전 버전에서 쓰던 config.json
    dialog = settings_ui.SettingsDialog(root, config, on_save=saved.append)

    dialog._save()

    assert saved[0]["headline_metric"] == "max"
    dialog.top.destroy()


def test_widget_style_dropdown_reflects_config_and_saves_selection(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    config = dict(DEFAULT_CONFIG)
    config["widget_style"] = "hourglass"
    dialog = settings_ui.SettingsDialog(root, config, on_save=saved.append)

    assert dialog.widget_style_var.get() == settings_ui.WIDGET_STYLE_LABELS["hourglass"]

    dialog.widget_style_var.set(settings_ui.WIDGET_STYLE_LABELS["tetris"])
    dialog._save()

    assert saved[0]["widget_style"] == "tetris"
    dialog.top.destroy()
