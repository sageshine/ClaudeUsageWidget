from claude_usage_widget import logging_setup, config


def test_get_logger_writes_to_appdata_log_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # 모듈이 이미 핸들러를 캐싱하지 않도록 로거 이름을 초기화
    logging_setup._reset_for_tests()

    logger = logging_setup.get_logger()
    logger.info("hello widget")
    for handler in logger.handlers:
        handler.flush()

    log_file = config.config_dir() / "log.txt"
    assert log_file.exists()
    assert "hello widget" in log_file.read_text(encoding="utf-8")
