"""create test_results table

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-18 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Creates the test_results table with all columns, indexes, and constraints."""
    op.create_table(
        "test_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier (UUID v4) for the test result"
        ),
        sa.Column("device_id", sa.String(50), nullable=False, comment="Identifier of the device under test"),
        sa.Column("serial_number", sa.String(100), nullable=False, comment="Unique manufacture serial number of the device"),
        sa.Column("operator", sa.String(100), nullable=False, comment="Name or ID of the production operator running the test"),
        sa.Column("machine", sa.String(100), nullable=False, comment="Testing station machine name"),
        sa.Column("firmware", sa.String(50), nullable=False, comment="Firmware version flashed on the device"),
        sa.Column("result", sa.String(10), nullable=False, comment="Overall test result (PASS or FAIL)"),
        sa.Column("execution_time", sa.Float(), nullable=False, comment="Duration of the test run in seconds"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, comment="Device timestamp when the test was run"),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="The full raw JSON payload from the socket connection"),
        sa.Column("client_ip", sa.String(45), nullable=False, comment="IP address of the client connection that submitted this log"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, comment="Timestamp when the server received the test result"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="Record creation timestamp"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, comment="Record update timestamp"),
    )

    # Create performance indexes
    op.create_index("ix_test_results_device_id", "test_results", ["device_id"])
    op.create_index("ix_test_results_serial_number", "test_results", ["serial_number"])
    op.create_index("ix_test_results_result", "test_results", ["result"])
    op.create_index("ix_test_results_timestamp", "test_results", ["timestamp"])


def downgrade() -> None:
    """Drops the test_results table and all its indexes."""
    op.drop_index("ix_test_results_timestamp", table_name="test_results")
    op.drop_index("ix_test_results_result", table_name="test_results")
    op.drop_index("ix_test_results_serial_number", table_name="test_results")
    op.drop_index("ix_test_results_device_id", table_name="test_results")
    op.drop_table("test_results")
