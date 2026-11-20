"""Logging configuration for the Devecoop MCP server.

stdout is reserved for the MCP stdio transport, so every log record must go to
stderr.
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide logging to write to stderr.

    Args:
        level: Log level name, for example ``INFO`` or ``DEBUG``.

    Raises:
        ValueError: If ``level`` is not a valid logging level name.
    """
    numeric_level = logging.getLevelNamesMapping().get(level.upper())
    if numeric_level is None:
        raise ValueError(f"Unsupported log level: {level!r}")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    for existing_handler in root.handlers[:]:
        root.removeHandler(existing_handler)
    root.addHandler(handler)
    root.setLevel(numeric_level)
