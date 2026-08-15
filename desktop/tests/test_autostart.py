from claude_usage_widget import autostart


def test_enable_then_disable_autostart_round_trip():
    fake_exe = r"C:\fake\path\ClaudeUsageWidget.exe"
    try:
        assert autostart.is_autostart_enabled() is False
        autostart.enable_autostart(fake_exe)
        assert autostart.is_autostart_enabled() is True
    finally:
        autostart.disable_autostart()
    assert autostart.is_autostart_enabled() is False


def test_disable_autostart_is_safe_when_not_set():
    autostart.disable_autostart()  # 예외 없이 통과해야 함
    assert autostart.is_autostart_enabled() is False
