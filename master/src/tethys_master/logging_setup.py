"""structlog setup for Tethys master.

Cite: structlog v24 (https://www.structlog.org/en/stable/)
Trace: parent plan section 6.1 (structured logging)
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", fmt: str = "plain") -> None:
    """Configure structlog + stdlib logging.

    Args:
        level: logging level name (DEBUG / INFO / WARNING / ERROR / CRITICAL).
        fmt: 'plain' for human-readable, 'json' for machine-parseable.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]
    if fmt == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", level=log_level, stream=sys.stderr)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger.

    Args:
        name: logger name (module path).
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
