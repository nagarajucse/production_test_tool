from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class TestResult(Base):
    """
    SQLAlchemy ORM model representing the 'test_results' table in PostgreSQL.
    Tracks production test run details, including operators, execution times,
    verdicts, and full nested payload details.
    """
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        comment="Unique identifier (UUID v4) for the test result"
    )
    device_id: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        index=True,
        comment="Identifier of the device under test"
    )
    serial_number: Mapped[str] = mapped_column(
        String(100), 
        nullable=False, 
        index=True,
        comment="Unique manufacture serial number of the device"
    )
    operator: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        comment="Name or ID of the production operator running the test"
    )
    machine: Mapped[str] = mapped_column(
        String(100), 
        nullable=False,
        comment="Testing station machine name"
    )
    firmware: Mapped[str] = mapped_column(
        String(50), 
        nullable=False,
        comment="Firmware version flashed on the device"
    )
    result: Mapped[str] = mapped_column(
        String(10), 
        nullable=False, 
        index=True,
        comment="Overall test result (PASS or FAIL)"
    )
    execution_time: Mapped[float] = mapped_column(
        Float, 
        nullable=False,
        comment="Duration of the test run in seconds"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        index=True,
        comment="Device timestamp when the test was run"
    )
    raw_json: Mapped[dict] = mapped_column(
        JSONB, 
        nullable=False,
        comment="The full raw JSON payload from the socket connection"
    )
    client_ip: Mapped[str] = mapped_column(
        String(45), 
        nullable=False,
        comment="IP address of the client connection that submitted this log"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        comment="Timestamp when the server received the test result"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        comment="Record creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False,
        comment="Record update timestamp"
    )
