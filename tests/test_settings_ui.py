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


def test_enforces_minimum_refresh_interval_of_60_seconds(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.interval_var.set(10)
    dialog._save()

    assert saved[0]["refresh_interval_seconds"] == 60
    dialog.top.destroy()
