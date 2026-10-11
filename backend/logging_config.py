"""Logging for the backend's own "nora.*" loggers.

uvicorn configures its own loggers; this only adds a handler for ours so their messages
have a timestamp, level and source. Never log one-time codes, passwords, tokens or
medical text (AGENTS.md).
"""

import logging

from config import settings

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging() -> None:
    logger = logging.getLogger("nora")
    if logger.handlers:  # already configured (e.g. uvicorn --reload re-imports main)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
