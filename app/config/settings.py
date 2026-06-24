import os
import sys
from typing import Any, Dict
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

# Load environmental variables from .env file if it exists
load_dotenv()

class Settings(BaseModel):
    """
    Application Settings configuration class.
    Parses and validates environment variables.
    """
    # Server Configuration
    SERVER_HOST: str = Field(
        default="0.0.0.0", 
        description="IP address for the TCP server to listen on"
    )
    SERVER_PORT: int = Field(
        default=5000, 
        description="Port for the TCP server to bind to"
    )
    SERVER_TIMEOUT_SECONDS: float = Field(
        default=30.0, 
        description="Inactivity timeout in seconds before closing client socket"
    )
    SERVER_MAX_PACKET_SIZE_BYTES: int = Field(
        default=1048576, 
        description="Maximum allowed payload size per JSON packet (in bytes)"
    )
    SERVER_MAX_CONNECTIONS: int = Field(
        default=1000, 
        description="Maximum allowed concurrent client connections"
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/test_manager",
        description="Asynchronous PostgreSQL connection string"
    )

    # Logging Configuration
    LOG_LEVEL: str = Field(
        default="INFO", 
        description="Standard logging severity level"
    )
    LOG_DIR: str = Field(
        default="logs", 
        description="Directory directory path to save log files"
    )
    LOG_MAX_BYTES: int = Field(
        default=10485760, 
        description="Max log size in bytes before rotating"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=5, 
        description="Number of historical rotated logs to keep"
    )


def load_settings() -> Settings:
    """
    Reads configuration from OS environment variables and instantiates the validated Settings model.
    Falls back to Pydantic defaults if variables are missing or empty.
    
    If configuration validation fails, prints a descriptive traceback to stderr and exits immediately.
    """
    raw_data: Dict[str, str] = {}
    for field_name in Settings.model_fields:
        env_value = os.environ.get(field_name)
        if env_value is not None and env_value.strip() != "":
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
    except ValidationError as e:
        # Write to sys.stderr before logging is initialized
        print(f"CRITICAL CONFIGURATION ERROR: Invalid environment variables configuration:\n{e}", file=sys.stderr)
        sys.exit(1)


# Global settings instance loaded on import
settings = load_settings()
