"""
schemas.py — Pydantic v2 validation schemas for the HTTP DMS Server.

Validates all inbound POST payloads before they touch the database.
Pydantic raises ValidationError with field-level detail on any invalid input,
which routes.py catches and returns as a structured HTTP 400 response.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SensorTestResultSchema(BaseModel):
    """
    Validates the JSON body of a POST / request.

    All fields are required. Types are coerced automatically by Pydantic
    (e.g. integer strings → int, ISO-8601 strings → datetime).
    """

    # Sensor identity
    sensor_sn: str = Field(..., min_length=1, max_length=100, description="Sensor serial number")
    model: str = Field(..., min_length=1, max_length=50, description="Sensor model (e.g. A400)")
    sensor_mac: str = Field(default="", max_length=50)
    #sensor_mac: str = Field(..., min_length=1, max_length=50, description="Sensor MAC address")

    # Quality scores
    image_quality: int = Field(..., alias="quality_score_afiq", ge=0, description="Image quality score")
    nfiq2_score: int = Field(..., alias="nfiq_score", ge=0, description="NFIQ2 quality score")
    verification_score: int = Field(..., ge=0, description="Biometric verification score")
    minutiae_count: Optional[int] = 0
    lfd_status: Optional[str] = "Unknown"

    # Work order & traceability
    part_number: str = Field(default="", max_length=100)
    work_order: str = Field(..., min_length=1, max_length=100, description="Manufacturing work order")
    tester_id: str = Field(..., min_length=1, max_length=50, description="Tester or station ID")

    timestamp: datetime = Field(..., description="ISO-8601 test execution timestamp")

    # Optional image fields
    image_name: Optional[str] = Field(None, max_length=255, description="Name of the image file")
    image_format: Optional[str] = Field(None, max_length=10, description="Format of the image (e.g. png, jpg)")
    image: Optional[str] = Field(None, description="Base64 encoded fingerprint image")
    fingerprint_image: Optional[str] = Field(None, description="Base64 encoded fingerprint image alternative key")
    fingerprint: Optional[str] = Field(None, description="Base64 encoded fingerprint image alternative key")
    image_data: Optional[str] = Field(None, description="Base64 encoded fingerprint image alternative key")
    base64_image: Optional[str] = Field(None, description="Base64 encoded fingerprint image alternative key")

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)