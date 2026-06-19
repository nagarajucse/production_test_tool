"""
app.py — Flask application factory and server entry point.

This module:
  1. Loads config and initialises logging
  2. Creates and configures the Flask application (create_app)
  3. Registers all blueprints
  4. Registers global error handlers (400, 404, 405, 413, 500)
  5. Tests the PostgreSQL connection and provisions the schema on startup
  6. Starts Waitress (Windows) or Gunicorn (Linux) depending on the platform

Security hardening:
  - Debug mode: ALWAYS off in production
  - MAX_CONTENT_LENGTH: limits request body to prevent memory exhaustion (DoS)
  - Stack traces: never sent to clients — all exceptions return generic JSON
  - JSON_SORT_KEYS=False: avoids revealing implementation details via key ordering

Deployment:
  - Windows: python app.py  (uses Waitress — production-grade WSGI on Windows)
  - Linux:   gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"

Common startup failure causes:
  - waitress not installed    → pip install waitress
  - PostgreSQL not reachable  → check DATABASE_URL and that postgres is running
  - asyncpg in DATABASE_URL   → must use postgresql:// not postgresql+asyncpg://
"""

import logging
import os
import sys
from typing import Tuple

# ---------------------------------------------------------------------------
# All imports wrapped in try/except so startup failures produce clear messages
# instead of a silent exit.
# ---------------------------------------------------------------------------
try:
    from flask import Flask, Response, jsonify
    from sqlalchemy import text
except ImportError as _e:
    print(f"FATAL: Missing dependency — {_e}", flush=True)
    print("Run:  pip install flask sqlalchemy psycopg2-binary", flush=True)
    sys.exit(1)

try:
    from config import settings
except Exception as _e:
    print(f"FATAL: Failed to load config — {_e}", flush=True)
    sys.exit(1)

try:
    from logger import setup_logging
except Exception as _e:
    print(f"FATAL: Failed to import logger — {_e}", flush=True)
    sys.exit(1)

try:
    from database import create_tables
except Exception as _e:
    print(f"FATAL: Failed to import database — {_e}", flush=True)
    sys.exit(1)

try:
    from routes import api_bp
except Exception as _e:
    print(f"FATAL: Failed to import routes — {_e}", flush=True)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Initialise logging — after all imports succeed, before anything else runs.
# Logging is module-level so it persists for the lifetime of the process.
# ---------------------------------------------------------------------------
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR,
    max_bytes=settings.LOG_MAX_BYTES,
    backup_count=settings.LOG_BACKUP_COUNT,
)

_app_logger = logging.getLogger("dms.app")


def create_app() -> Flask:
    """
    Flask application factory.

    Creates a fully configured Flask application instance, suitable for both
    direct execution and WSGI server deployment (Waitress, Gunicorn).

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # --- Security & Request Hardening ---
    app.config["DEBUG"] = False          # NEVER enable debug in production
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = settings.MAX_CONTENT_LENGTH  # reject oversized bodies → HTTP 413
    app.config["JSON_SORT_KEYS"] = False

    # --- Register Blueprints ---
    app.register_blueprint(api_bp)

    # --- Global Error Handlers ---
    # These ensure ALL error responses are structured JSON,
    # regardless of where in the request lifecycle the error occurs.

    @app.errorhandler(400)
    def bad_request(error: Exception) -> Tuple[Response, int]:
        """Handles malformed requests — invalid JSON, missing Content-Type, etc."""
        _app_logger.warning("HTTP 400 Bad Request: %s", error)
        return jsonify({
            "status": "error",
            "message": "Bad request. Ensure Content-Type is application/json and payload is valid.",
        }), 400

    @app.errorhandler(404)
    def not_found(error: Exception) -> Tuple[Response, int]:
        """Handles requests to undefined endpoints."""
        _app_logger.warning("HTTP 404 Not Found: %s", error)
        return jsonify({
            "status": "error",
            "message": "Endpoint not found. The DMS server accepts POST / only.",
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error: Exception) -> Tuple[Response, int]:
        """Handles non-POST requests to /."""
        _app_logger.warning("HTTP 405 Method Not Allowed: %s", error)
        return jsonify({
            "status": "error",
            "message": "Method not allowed. Use POST /.",
        }), 405

    @app.errorhandler(413)
    def payload_too_large(error: Exception) -> Tuple[Response, int]:
        """Handles requests exceeding MAX_CONTENT_LENGTH."""
        _app_logger.warning(
            "HTTP 413 Payload Too Large — limit is %d bytes.", settings.MAX_CONTENT_LENGTH
        )
        return jsonify({
            "status": "error",
            "message": f"Payload too large. Maximum allowed size is "
                       f"{settings.MAX_CONTENT_LENGTH // 1024} KB.",
        }), 413

    @app.errorhandler(500)
    def internal_error(error: Exception) -> Tuple[Response, int]:
        """
        Catch-all for unhandled exceptions that escape route handlers.
        Stack traces are logged server-side — never exposed to the client.
        """
        _app_logger.exception("HTTP 500 Internal Server Error: %s", error)
        return jsonify({
            "status": "error",
            "message": "An internal server error occurred.",
        }), 500

    _app_logger.info(
        "Flask application created. MAX_CONTENT_LENGTH=%d bytes.",
        settings.MAX_CONTENT_LENGTH,
    )
    return app


def _start_wsgi_server(app: Flask) -> None:
    """
    Starts the best available WSGI server on the current platform.

    Priority order:
      1. Waitress (preferred — production-grade, multi-threaded, Windows-compatible)
      2. Flask built-in Werkzeug server with threaded=True (fallback — development only)

    Waitress must be installed for production deployments:
        pip install waitress
    """
    try:
        from waitress import serve as waitress_serve

        _app_logger.info(
            "Starting Waitress WSGI server on %s:%d (threads=8)...",
            settings.SERVER_HOST,
            settings.SERVER_PORT,
        )
        print(
            f"[DMS] Waitress server running on http://{settings.SERVER_HOST}:{settings.SERVER_PORT}",
            flush=True,
        )
        waitress_serve(
            app,
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            threads=8,
            connection_limit=1000,
            cleanup_interval=30,
            channel_timeout=30,
            ident="DMS-Server",
        )

    except ImportError:
        _sep = "=" * 60
        _app_logger.warning(
            "\n%s\nWARNING: Waitress is not installed.\n"
            "Falling back to Flask built-in server (development mode).\n"
            "Install for production:  pip install waitress\n%s",
            _sep, _sep,
        )
        print(
            f"[DMS] Flask dev server running on http://{settings.SERVER_HOST}:{settings.SERVER_PORT}",
            flush=True,
        )
        app.run(
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            debug=False,
            use_reloader=False,
            threaded=True,
        )


def _verify_database_connection() -> None:
    """
    Verifies that PostgreSQL is reachable BEFORE attempting schema provisioning.

    Raises:
        SystemExit(1) with a descriptive message if the connection fails.
    """
    from database import get_engine
    engine = get_engine()
    masked_url = str(engine.url).replace(str(engine.url.password or ""), "***")
    _app_logger.info("Testing PostgreSQL connection: %s", masked_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _app_logger.info("PostgreSQL connection verified successfully.")
        print("[DMS] PostgreSQL connection OK.", flush=True)
    except Exception as exc:
        _sep = "=" * 60
        msg = (
            f"\n{_sep}\n"
            f"STARTUP FAILURE — Cannot connect to PostgreSQL\n"
            f"{_sep}\n"
            f"DATABASE_URL : {masked_url}\n"
            f"Error        : {exc}\n\n"
            f"Checklist:\n"
            f"  1. Is PostgreSQL running?  ->  pg_ctl status  /  services.msc\n"
            f"  2. Does the database exist?  ->  CREATE DATABASE test_manager;\n"
            f"  3. Are credentials correct in .env?\n"
            f"  4. Is DATABASE_URL using psycopg2 format?\n"
            f"     Correct  : postgresql://user:pass@host:5432/dbname\n"
            f"     Incorrect: postgresql+asyncpg://...  (async -- not supported)\n"
            f"{_sep}"
        )
        _app_logger.critical(msg)
        print(msg, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    print("[DMS] Starting DMS HTTP Server...", flush=True)

    _app_logger.info("=" * 60)
    _app_logger.info("DMS HTTP Server — Production Test Management System")
    _app_logger.info(
        "PID: %d | Host: %s | Port: %d",
        os.getpid(), settings.SERVER_HOST, settings.SERVER_PORT,
    )
    _app_logger.info("=" * 60)

    # Step 1: Verify PostgreSQL is reachable.
    _verify_database_connection()

    # Step 2: Provision schema (CREATE TABLE IF NOT EXISTS — idempotent).
    try:
        create_tables()
        print("[DMS] Schema provisioning complete.", flush=True)
    except Exception as exc:
        _app_logger.critical(
            "Schema provisioning failed: %s. Server cannot start.", exc, exc_info=True
        )
        print(f"[DMS] FATAL: Schema provisioning failed — {exc}", flush=True)
        sys.exit(1)

    # Step 3: Create Flask application.
    flask_app = create_app()
    _app_logger.info("Flask application created successfully.")

    # Step 4: Start WSGI server (blocks until process is killed).
    _start_wsgi_server(flask_app)