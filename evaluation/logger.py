"""evaluation/logger.py — Logging configuration for the evaluation module."""

import logging
import sys
from pathlib import Path

# Project-root-relative log directory
LOG_DIR = Path(__file__).parent.parent / "logs"


def get_eval_logger(name: str = "evaluation", verbose: bool = False) -> logging.Logger:
    """Return a configured logger for the evaluation module.

    Creates ``logs/evaluation.log`` in the project root and also emits to
    stdout.  Calling this function multiple times for the same *name* is safe —
    handlers are only attached once.

    Args:
        name:    Logger name (default: ``"evaluation"``).
        verbose: If True, set level to DEBUG; otherwise INFO.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    # If handlers already exist, only adjust the level if needed.
    if logger.handlers:
        if verbose:
            logger.setLevel(logging.DEBUG)
            for h in logger.handlers:
                h.setLevel(logging.DEBUG)
        return logger

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    logger.propagate = False  # Don't duplicate messages to the root logger.

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — append mode so successive runs accumulate.
    fh = logging.FileHandler(str(LOG_DIR / "evaluation.log"), encoding="utf-8", mode="a")
    fh.setLevel(level)
    fh.setFormatter(fmt)

    # Console handler.
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)

    return logger
