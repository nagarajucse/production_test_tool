"""
services.py — Business logic orchestration for the HTTP DMS Server.

The service layer is the single authoritative location for all business rules.
Routes delegate entirely to this layer; they never touch ORM models directly.

Responsibilities:
  1. Validate the incoming raw dict via Pydantic schema
  2. Map validated data to the ORM model
  3. Persist via the database session context manager
  4. Return a structured outcome tuple: (http_status_code, response_dict)

Error taxonomy:
  - ValidationError  → HTTP 400  (client fault — bad payload)
  - IntegrityError   → HTTP 500  (DB constraint violation — unexpected)
  - OperationalError → HTTP 500  (DB unavailable — infrastructure fault)
  - Exception        → HTTP 500  (unexpected — logged with full traceback)

No stack traces or internal error details are ever returned to the client.
"""

import base64
import logging
import time
from typing import Any, Dict, Tuple

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from database import get_db
from models import SensorTestResult
from schemas import SensorTestResultSchema, format_validation_errors

logger = logging.getLogger("dms.services")


class TestResultService:
    """
    Orchestrates the full lifecycle of a sensor test result submission:
    parse → validate → map → persist → respond.

    Instantiated once per Flask application and reused across requests.
    Contains no mutable instance state — thread-safe by design.
    """

    def store_test_result(
        self,
        client_ip: str,
        raw_data: Dict[str, Any],
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Validates and persists a sensor test result payload.

        Args:
            client_ip: The originating client IP address (from utils.get_client_ip).
            raw_data:  The parsed JSON dictionary from the HTTP request body.

        Returns:
            A tuple of (http_status_code, response_body_dict):
              - (200, {"status": "success", "message": "Data stored successfully"})
              - (400, {"status": "error",   "message": "...", "errors": [...]})
              - (500, {"status": "error",   "message": "..."})
        """
        start = time.monotonic()

        # ------------------------------------------------------------------
        # Step 1: Pydantic schema validation
        # Catches missing fields, wrong types, empty strings, bad timestamps.
        # ------------------------------------------------------------------
        try:
            validated: SensorTestResultSchema = SensorTestResultSchema(**raw_data)
        except ValidationError as exc:
            errors = format_validation_errors(exc.errors())
            logger.warning(
                "Validation failed for client %s — %d error(s): %s",
                client_ip,
                len(errors),
                errors,
            )
            return 400, {
                "status": "error",
                "message": "Payload validation failed.",
                "errors": errors,
            }

        # ------------------------------------------------------------------
        # Step 2: Map validated schema → ORM model
        # Extract and decode the fingerprint image from any of the standard payload fields.
        # ------------------------------------------------------------------
        image_b64 = (
            validated.image
            or validated.fingerprint_image
            or validated.fingerprint
            or validated.image_data
            or validated.base64_image
        )
        image_name = validated.image_name
        image_format = validated.image_format

        fingerprint_image_bytes = None
        if image_b64:
            if image_b64.startswith("data:image"):
                try:
                    prefix, data_part = image_b64.split(",", 1)
                    if not image_format:
                        if "/" in prefix:
                            parts = prefix.split(";")[0].split("/")
                            if len(parts) > 1:
                                image_format = parts[1]
                    image_b64 = data_part
                except Exception:
                    pass

            try:
                fingerprint_image_bytes = base64.b64decode(image_b64)
            except Exception as e:
                logger.warning("Failed to decode base64 image: %s", e)

        if fingerprint_image_bytes and not image_format:
            image_format = "png"

        record = SensorTestResult(
            sensor_sn=validated.sensor_sn,
            model=validated.model,
            sensor_mac=validated.sensor_mac,
            quality_score_afiq=validated.quality_score_afiq,
            nfiq_score=validated.nfiq_score,
            minutiae_count=validated.minutiae_count,
            verification_score=validated.verification_score,
            part_number=validated.part_number,
            work_order=validated.work_order,
            tester_id=validated.tester_id,
            timestamp=validated.timestamp,
            client_ip=client_ip,
            image_name=image_name,
            image_format=image_format,
            fingerprint_image=fingerprint_image_bytes,
        )

        # ------------------------------------------------------------------
        # Step 3: Persist within a transactional session scope.
        # get_db() auto-commits on success, auto-rollbacks on any exception.
        # ------------------------------------------------------------------
        try:
            with get_db() as session:
                session.add(record)
                session.flush()  # populate server-generated id before commit

                elapsed = round((time.monotonic() - start) * 1000, 2)
                logger.info(
                    "Record saved — sensor_sn=%s model=%s work_order=%s id=%s "
                    "client_ip=%s response_time=%sms",
                    record.sensor_sn,
                    record.model,
                    record.work_order,
                    record.id,
                    client_ip,
                    elapsed,
                )

            return 200, {
                "status": "success",
                "message": "Data stored successfully",
            }

        except IntegrityError as exc:
            logger.error(
                "Database integrity violation for client %s sensor_sn=%s: %s",
                client_ip,
                validated.sensor_sn,
                exc,
                exc_info=True,
            )
            return 500, {
                "status": "error",
                "message": "A database integrity error occurred. Please contact support.",
            }

        except OperationalError as exc:
            logger.error(
                "Database connection unavailable for client %s: %s",
                client_ip,
                exc,
                exc_info=True,
            )
            return 500, {
                "status": "error",
                "message": "Database is currently unavailable. Please retry in a moment.",
            }

        except Exception as exc:
            logger.exception(
                "Unexpected error persisting record for client %s: %s",
                client_ip,
                exc,
            )
            return 500, {
                "status": "error",
                "message": "An internal server error occurred.",
            }
