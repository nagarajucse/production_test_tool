"""
schemas.py — Pydantic v2 validation schemas for the HTTP DMS Server.

Validates all inbound POST payloads before they touch the database.
Pydantic raises ValidationError with field-level detail on any invalid input,
which routes.py catches and returns as a structured HTTP 400 response.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class SensorTestResultSchema(BaseModel):
    """
    Validates the JSON body of a POST / request.

    All fields are required. Types are coerced automatically by Pydantic
    (e.g. integer strings → int, ISO-8601 strings → datetime).
    """

    # Sensor identity
    sensor_sn: str = Field(..., min_length=1, max_length=100, description="Sensor serial number")
    model: str = Field(..., min_length=1, max_length=50, description="Sensor model (e.g. A400)")
    sensor_mac: str = Field(..., min_length=1, max_length=50, description="Sensor MAC address")

    # Quality scores
    quality_score_afiq: int = Field(..., ge=0, description="AFIQ quality score")
    nfiq_score: int = Field(..., ge=0, description="NFIQ2 quality score")
    minutiae_count: int = Field(..., ge=0, description="Detected minutiae count")
    verification_score: int = Field(..., ge=0, description="Biometric verification score")

    # Work order & traceability
    part_number: str = Field(..., min_length=1, max_length=100, description="Product part number")
    work_order: str = Field(..., min_length=1, max_length=100, description="Manufacturing work order")
    tester_id: str = Field(..., min_length=1, max_length=50, description="Tester or station ID")

    # Timestamp from device
    timestamp: datetime = Field(..., description="ISO-8601 test execution timestamp")

    model_config = {"str_strip_whitespace": True}