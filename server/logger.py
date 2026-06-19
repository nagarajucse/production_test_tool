"""
logger.py — Logging infrastructure for the HTTP DMS Server.

Configures a rotating file handler hierarchy:
  - logs/http_server.log  : All events at the configured LOG_LEVEL
  - logs/http_error.log   : ERROR and CRITICAL events only (separate for alerting)

Format: ISO-8601 timestamp | level | module | message

No console output in production — all output is directed to files.
Root logger fallback is intentionally suppressed to prevent noisy libraries
from polluting application logs.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str, log_dir: str, max_bytes: int, backup_count: int) -> None:
    """
    Initialise the 'dms' logger with rotating file handlers.

    Args:
        log_level:    Standard Python logging level string (e.g. 'INFO', 'DEBUG').
        log_dir:      Directory path where log files are stored. Created if absent.
        max_bytes:    Maximum size in bytes of a single log file before rotation.
        backup_count: Number of rotated backup files to retain.
    """
    os.makedirs(log_dir, exist_ok=True)

    numeric_level: int = getattr(logging, log_level.upper(), logging.INFO)

    # Unified log record format — matches the spec: Timestamp | Level | Module | Message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    # --- Handler: all events → http_server.log ---
    server_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "http_server.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    server_handler.setLevel(numeric_level)
    server_handler.setFormatter(formatter)

    # --- Handler: errors only → http_error.log ---
    error_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "http_error.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # --- Application logger: 'dms' namespace ---
    logger = logging.getLogger("dms")
    logger.setLevel(numeric_level)
    logger.addHandler(server_handler)
    logger.addHandler(error_handler)
    # Prevent logs from bubbling to the root logger (avoids duplicate output
    # if a consumer configures basicConfig elsewhere).
    logger.propagate = False

    # Suppress verbose output from third-party libraries (SQLAlchemy, Werkzeug)
    # so they only surface WARNING+ events in the application log.
    for noisy_lib in ("sqlalchemy.engine", "werkzeug"):
        lib_logger = logging.getLogger(noisy_lib)
        lib_logger.setLevel(logging.WARNING)

    logger.info("Logging infrastructure initialised. log_dir=%s level=%s", log_dir, log_level.upper())
