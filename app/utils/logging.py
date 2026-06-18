import logging
import os
from logging.handlers import RotatingFileHandler
from app.config.settings import settings

def setup_logging() -> None:
    """
    Configures the application's logging hierarchy.
    
    Layout:
    - Root Logger: Fallback logger configured to output WARNING+ to the console.
    - 'app' Logger: The namespace for all application logs. Routes:
        - Console (stdout) at LOG_LEVEL
        - logs/server.log at LOG_LEVEL
        - logs/error.log at ERROR+ (system-wide error tracking)
    - 'app.server.connections' Logger: Dedicated connection lifecycle tracker.
      Writes connection events to logs/connections.log and propagates logs
      to the parent 'app' logger to appear in the general logs and console.
    """
    # Ensure log directory exists
    os.makedirs(settings.LOG_DIR, exist_ok=True)

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Unified ISO-like format including date, time, log level, namespace, and thread context
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [%(process)d:%(threadName)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z"
    )

    # --- Handlers Initialization ---
    
    # 1. Console stream handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # 2. Rotating file handler for general system traces
    server_file_path = os.path.join(settings.LOG_DIR, "server.log")
    server_handler = RotatingFileHandler(
        filename=server_file_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    server_handler.setFormatter(formatter)
    server_handler.setLevel(log_level)

    # 3. Rotating file handler specifically filtering for errors and critical failures
    error_file_path = os.path.join(settings.LOG_DIR, "error.log")
    error_handler = RotatingFileHandler(
        filename=error_file_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # 4. Rotating file handler for client connection logs
    connections_file_path = os.path.join(settings.LOG_DIR, "connections.log")
    connections_handler = RotatingFileHandler(
        filename=connections_file_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    connections_handler.setFormatter(formatter)
    connections_handler.setLevel(log_level)

    # --- Logger Configuration ---

    # Main application logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)
    app_logger.addHandler(console_handler)
    app_logger.addHandler(server_handler)
    app_logger.addHandler(error_handler)
    # Prevent propagation up to the root logger to avoid duplicate console entries
    app_logger.propagate = False

    # Connection-specific child logger
    # Inherits app_logger's handlers, and also outputs connection lifecycle events to connections.log
    connections_logger = logging.getLogger("app.server.connections")
    connections_logger.setLevel(log_level)
    connections_logger.addHandler(connections_handler)
    # Bubble logs up to 'app' logger for console/server.log outputs
    connections_logger.propagate = True

    # Configure root logger fallback
    logging.basicConfig(level=logging.WARNING, handlers=[console_handler])
    
    app_logger.info("Logging infrastructure successfully initialized.")
