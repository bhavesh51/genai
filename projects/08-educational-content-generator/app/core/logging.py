"""
Project 8 – Educational Content Generator
Structured logging configuration (OpenTelemetry + JSON)
"""
import logging
import sys

from app.core.config import settings


def configure_logging():
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)
    for lib in ("pymilvus", "httpx", "httpcore", "urllib3", "redis"):
        logging.getLogger(lib).setLevel(logging.WARNING)
