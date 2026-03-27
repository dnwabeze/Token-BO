import logging
import sys
from pathlib import Path

LOG_FILE = Path("data/bot.log")


def setup_logger(name: str = "trend_bot", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler — rotates at 5 MB, keeps 3 backups
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except Exception:
        pass  # If file logging fails, console logging still works

    return logger


logger = setup_logger()
