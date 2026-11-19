"""Structured JSON logging. Never log emails, passwords, chat contents or prompts (PRD §6.8, S7)."""

import logging
import sys

import structlog

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str = "app"):
    configure_logging()
    return structlog.get_logger(name)

