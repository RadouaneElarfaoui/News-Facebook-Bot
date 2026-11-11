"""
Core — Logger
Logger structuré avec rotation de fichiers centralisée.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_ROOT_LOGGER_INITIALIZED = False


def _init_root_logger():
    global _ROOT_LOGGER_INITIALIZED
    if _ROOT_LOGGER_INITIALIZED:
        return

    root_logger = logging.getLogger("screen_drop")
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)

    # File handler centralisé (rotation 5MB, 3 backups)
    fh = RotatingFileHandler(
        LOG_DIR / "screen_drop.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)

    _ROOT_LOGGER_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger hiérarchique sous le namespace 'screen_drop'.
    Les logs sont propagés vers les handlers uniques du logger parent.
    """
    _init_root_logger()
    if name == "screen_drop" or name.startswith("screen_drop."):
        return logging.getLogger(name)
    return logging.getLogger(f"screen_drop.{name}")

