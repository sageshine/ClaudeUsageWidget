import logging

from .config import config_dir

_LOGGER_NAME = "claude_usage_widget"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = config_dir() / "log.txt"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _reset_for_tests() -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
