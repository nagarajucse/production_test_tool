"""
models.py — SQLAlchemy ORM model for the HTTP DMS Server.

Maps the 'sensor_test_results' table which stores fingerprint sensor
production test records received over HTTP POST.

Table: sensor_test_results
  - Separate from the existing 'test_results' TCP server table.
  - Indexed on: sensor_sn, work_order, received_at for fast filtering queries.
  - image_name, image_format, fingerprint_image: stores normalized fingerprint preview image details.
  - UUID primary key: globally unique, avoids sequential ID enumeration.
"""

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, DateTime, Integer, String, Text, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.mysql import LONGBLOB


class Base(DeclarativeBase):
    """
    Shared declarative base for all HTTP server ORM models.
    Kept separate from the existing TCP server's Base to prevent
    accidental cross-contamination of metadata.
    """
    pass


class SensorTestResult(Base):
    """
    ORM model representing a single fingerprint sensor production test record.

    Each row corresponds to one HTTP POST payload received from a
    production testing client. The payload is validated by Pydantic
    (schemas.py) before the ORM model is constructed.

    Table: sensor_test_results
    """

    __tablename__ = "sensor_test_results"

    # Primary key — UUID v4, generated server-side
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique record identifier (UUID v4 as string)",
    )

    # --- Sensor Identity ---
    sensor_sn: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Fingerprint sensor serial number",
    )
    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Sensor model identifier (e.g. A400)",
    )
    sensor_mac: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Sensor MAC address (hex string)",
    )

    # --- Quality Scores ---
    image_quality: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Image quality score computed by the testing client",
    )
    nfiq2_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="NFIQ2 fingerprint quality score",
    )
    verification_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Biometric verification match score",
    )
    minutiae_count: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        default=0,
        comment="Number of extracted minutiae points",
    )
    lfd_status: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        default="Unknown",
        comment="Live Finger Detection status",
    )

    # --- Work Order & Traceability ---
    part_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Product part number (e.g. 1.17-A400-0001)",
    )
    work_order: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Manufacturing work order identifier (e.g. MO-1-2025-0211)",
    )
    tester_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Identifier of the production tester or station operator",
    )

    # --- Timestamps ---
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="ISO-8601 timestamp from the device at test execution time",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        comment="Server-side timestamp when the HTTP request was received",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        comment="Record creation timestamp",
    )

    # --- Network Metadata ---
    client_ip: Mapped[str] = mapped_column(
        String(45),  # max length for IPv6 addresses
        nullable=False,
        comment="IP address of the client that submitted the test result",
    )

    # --- Fingerprint Image Preview ---
    image_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of the fingerprint image file",
    )
    image_format: Mapped[str] = mapped_column(
        String(10),
        nullable=True,
        comment="Format of the image (e.g. png, jpg)",
    )
    fingerprint_image: Mapped[bytes] = mapped_column(
        LargeBinary().with_variant(LONGBLOB, "mysql"),
        nullable=True,
        comment="Decoded binary fingerprint image data",
    )

    def __repr__(self) -> str:
        return (
            f"<SensorTestResult id={self.id} sensor_sn={self.sensor_sn!r} "
            f"model={self.model!r} work_order={self.work_order!r}>"
        )


class User(Base):
    """
    ORM model representing a system user/administrator.
    
    Used for dashboard authentication and authorization.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique user identifier",
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Login username",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Werkzeug hashed password",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the user account is active",
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user has admin privileges",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        onupdate=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        comment="Record last update timestamp",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
