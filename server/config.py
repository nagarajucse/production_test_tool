"""
config.py — Application configuration for the HTTP DMS Server.

Reads all runtime settings from environment variables (populated from .env
by python-dotenv). Pydantic BaseModel provides automatic type coercion and
validation, so missing or malformed variables are caught at startup — not at
runtime when the first request arrives.

Usage:
    from config import settings
    print(settings.SERVER_PORT)
"""

import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Load .env from the project root (one directory above server/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_env_path)


class Settings(BaseModel):
    """
    Validated application settings sourced from environment variables.

    All fields have sensible production defaults so the server can start
    without a .env file during local development. Secrets (DATABASE_URL)
    must always be supplied explicitly in production.
    """

    # --- HTTP Server ---
    SERVER_HOST: str = Field(
        default="0.0.0.0",
        description="Network interface for Flask/Waitress to bind on.",
    )
    SERVER_PORT: int = Field(
        default=5000,
        description="TCP port the HTTP server listens on.",
    )
    MAX_CONTENT_LENGTH: int = Field(
        default=1_048_576,  # 1 MB
        description="Maximum allowed HTTP request body size in bytes. "
                    "Requests exceeding this limit are rejected with HTTP 413.",
    )

    # --- Database ---
    DATABASE_URL: str = Field(
        default="mysql+pymysql://root:root@localhost:3306/test_manager",
        description="Synchronous database connection string (pymysql/pg8000). "
                    "Do NOT use asyncpg/aiomysql here.",
    )

    SECRET_KEY: str = Field(
        default="dev-secret-key-replace-in-prod-12345",
        description="Flask session secret key for securing cookies.",
    )


    # --- Logging ---
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Standard Python logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )
    LOG_DIR: str = Field(
        default="logs",
        description="Directory where rotating log files are written.",
    )
    LOG_MAX_BYTES: int = Field(
        default=10_485_760,  # 10 MB
        description="Maximum log file size before rotation (bytes).",
    )
    LOG_BACKUP_COUNT: int = Field(
        default=5,
        description="Number of rotated backup log files to retain.",
    )


def _load_settings() -> Settings:
    """
    Constructs a Settings instance from OS environment variables.

    Only non-empty env values are forwarded so that Pydantic's field defaults
    take effect when variables are set but empty (e.g. `SERVER_HOST=`).

    Exits the process with a descriptive error if validation fails — it is
    never safe to start the server with invalid configuration.
    """
    raw_data: Dict[str, str] = {}
    for field_name in Settings.model_fields:
        env_value = os.environ.get(field_name)
        if env_value is not None and env_value.strip():
            raw_data[field_name] = env_value.strip()

    data: Dict[str, Any] = {}

    # Process SERVER_HOST first if it exists, to potentially extract port
    if "SERVER_HOST" in raw_data:
        host_val = raw_data["SERVER_HOST"]
        if host_val.startswith("http://"):
            host_val = host_val[7:]
        elif host_val.startswith("https://"):
            host_val = host_val[8:]
        host_val = host_val.split("/")[0]

        if ":" in host_val:
            parts = host_val.split(":")
            host_val = parts[0]
            try:
                data["SERVER_PORT"] = int(parts[1])
            except ValueError:
                pass
        data["SERVER_HOST"] = host_val

    # Process all other fields
    for field_name, env_value in raw_data.items():
        if field_name == "SERVER_HOST":
            continue
        data[field_name] = env_value

    try:
        return Settings(**data)
    except ValidationError as exc:
        print(
            f"CRITICAL — Invalid server configuration:\n{exc}",
            file=sys.stderr,
        )
        sys.exit(1)


# Module-level singleton — imported everywhere as `from config import settings`
settings: Settings = _load_settings()
