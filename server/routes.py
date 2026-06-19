"""
routes.py — Flask Blueprint defining the HTTP DMS Server API endpoints.

Endpoints:
  POST /          — Accepts a JSON test result payload, validates it via
                    Pydantic, persists it to PostgreSQL, returns confirmation.
  GET  /health    — Health check; returns server status and DB connectivity.

All responses are structured JSON with a 'status' field ('ok' or 'error').
All exceptions are caught and returned as structured errors — no raw tracebacks
are ever sent to clients.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from database import get_db
from models import SensorTestResult
from schemas import SensorTestResultSchema

logger = logging.getLogger("dms.routes")

api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# POST / — Ingest a sensor test result
# ---------------------------------------------------------------------------

@api_bp.route("/", methods=["POST"])
def ingest_test_result() -> tuple[Response, int]:
    """
    Accepts a JSON payload containing fingerprint sensor test result data,
    validates it, and persists it to the database.

    Request:
        Content-Type: application/json
        Body: SensorTestResult JSON object (see schemas.py for field spec)

    Response 200:
        { "status": "ok", "message": "Test result stored.", "id": "<uuid>" }

    Response 400:
        { "status": "error", "message": "<validation detail>" }

    Response 500:
        { "status": "error", "message": "An internal server error occurred." }
    """
    client_ip: str = request.remote_addr or "unknown"
    logger.info("POST / received from %s", client_ip)

    # --- Parse JSON body ---
    payload = request.get_json(silent=True)
    if payload is None:
        logger.warning("POST / rejected — missing or non-JSON body from %s", client_ip)
        return jsonify({
            "status": "error",
            "message": "Request body must be valid JSON with Content-Type: application/json.",
        }), 400

    # --- Validate with Pydantic schema ---
    try:
        validated = SensorTestResultSchema(**payload)
    except Exception as exc:
        logger.warning("POST / validation failed from %s: %s", client_ip, exc)
        return jsonify({
            "status": "error",
            "message": f"Payload validation failed: {exc}",
        }), 400

    # --- Persist to PostgreSQL ---
    try:
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
            received_at=datetime.now(timezone.utc),
            client_ip=client_ip,
            raw_json=payload,
        )
        # Capture all values needed after session closes INSIDE the with block.
        # SQLAlchemy expires ORM attributes on commit — accessing them after
        # the session closes raises DetachedInstanceError.
        with get_db() as db:
            db.add(record)
            db.flush()  # assigns server-generated values (e.g. UUID default)
            record_id = str(record.id)
            record_sn = record.sensor_sn
            record_wo = record.work_order

        logger.info(
            "POST / stored record id=%s sensor_sn=%s work_order=%s",
            record_id, record_sn, record_wo,
        )
        return jsonify({
            "status": "ok",
            "message": "Test result stored.",
            "id": record_id,
        }), 200

    except Exception as exc:
        logger.exception("POST / database write failed from %s: %s", client_ip, exc)
        return jsonify({
            "status": "error",
            "message": "An internal server error occurred.",
        }), 500


# ---------------------------------------------------------------------------
# GET /health — Liveness + DB connectivity check
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    """
    Health check endpoint.

    Returns 200 if the server is running and PostgreSQL is reachable.
    Returns 503 if the database connection fails.

    Response 200:
        { "status": "ok", "database": "connected", "timestamp": "<iso8601>" }

    Response 503:
        { "status": "error", "database": "unreachable", "timestamp": "<iso8601>" }
    """
    from database import get_engine
    from sqlalchemy import text

    now = datetime.now(timezone.utc).isoformat()

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.debug("GET /health — database OK")
        return jsonify({
            "status": "ok",
            "database": "connected",
            "timestamp": now,
        }), 200

    except Exception as exc:
        logger.error("GET /health — database unreachable: %s", exc)
        return jsonify({
            "status": "error",
            "database": "unreachable",
            "timestamp": now,
        }), 503