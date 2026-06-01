import logging
import logging.config
from pathlib import Path

from app.structured_logger import init_csv_log

Path("logs").mkdir(exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(status)s %(error)s",
        },
        "console": {
            "format": "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 10_485_760,
            "backupCount": 5,
            "formatter": "json",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "app": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

def setup_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    init_csv_log()