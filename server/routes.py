"""
routes.py — Flask Blueprint defining the HTTP DMS Server API endpoints.

Endpoints:
  POST /          — Accepts a JSON test result payload, validates it, persists to PostgreSQL.
  GET  /data      — Paginated query of all test results (for dashboard).
  GET  /stats     — Aggregate statistics for dashboard header cards.
  GET  /health    — Health check; returns server status and DB connectivity.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from database import get_db
from models import SensorTestResult
from schemas import SensorTestResultSchema

logger = logging.getLogger("dms.routes")

api_bp = Blueprint("api", __name__)
import os
from flask import send_file

@api_bp.route("/dashboard", methods=["GET"])
def serve_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    return send_file(dashboard_path, mimetype="text/html")

# ---------------------------------------------------------------------------
# POST / — Ingest a sensor test result
# ---------------------------------------------------------------------------

@api_bp.route("/", methods=["POST"])
def ingest_test_result() -> tuple[Response, int]:
    client_ip: str = request.remote_addr or "unknown"
    logger.info("POST / received from %s", client_ip)

    payload = request.get_json(silent=True)
    if payload is None:
        logger.warning("POST / rejected — missing or non-JSON body from %s", client_ip)
        return jsonify({
            "status": "error",
            "message": "Request body must be valid JSON with Content-Type: application/json.",
        }), 400

    try:
        validated = SensorTestResultSchema(**payload)
    except Exception as exc:
        logger.warning("POST / validation failed from %s: %s", client_ip, exc)
        return jsonify({
            "status": "error",
            "message": f"Payload validation failed: {exc}",
        }), 400

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
        # Capture values inside the session block to avoid DetachedInstanceError
        with get_db() as db:
            db.add(record)
            db.flush()
            record_id = str(record.id)
            record_sn = record.sensor_sn
            record_wo = record.work_order

        logger.info("POST / stored record id=%s sensor_sn=%s work_order=%s", record_id, record_sn, record_wo)
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
# GET /data — Paginated query of all test results (for dashboard)
# ---------------------------------------------------------------------------

@api_bp.route("/data", methods=["GET"])
def get_data() -> tuple[Response, int]:
    from database import get_engine
    from sqlalchemy import text as sa_text

    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(200, max(1, int(request.args.get("per_page", 50))))
        search   = request.args.get("search", "").strip()
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid pagination parameters."}), 400

    offset = (page - 1) * per_page
    where  = "WHERE (sensor_sn ILIKE :q OR work_order ILIKE :q OR tester_id ILIKE :q)" if search else ""
    params: dict = {"limit": per_page, "offset": offset}
    if search:
        params["q"] = f"%{search}%"

    sql_rows = sa_text(f"""
        SELECT id, sensor_sn, model, sensor_mac,
               quality_score_afiq, nfiq_score, minutiae_count, verification_score,
               part_number, work_order, tester_id,
               timestamp, received_at, client_ip
        FROM sensor_test_results
        {where}
        ORDER BY received_at DESC
        LIMIT :limit OFFSET :offset
    """)
    sql_count = sa_text(f"SELECT COUNT(*) FROM sensor_test_results {where}")

    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(sql_count, params).scalar()
            rows  = conn.execute(sql_rows, params).mappings().all()

        return jsonify({
            "status":   "ok",
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "rows": [
                {
                    "id":                 str(r["id"]),
                    "sensor_sn":          r["sensor_sn"],
                    "model":              r["model"],
                    "sensor_mac":         r["sensor_mac"],
                    "quality_score_afiq": r["quality_score_afiq"],
                    "nfiq_score":         r["nfiq_score"],
                    "minutiae_count":     r["minutiae_count"],
                    "verification_score": r["verification_score"],
                    "part_number":        r["part_number"],
                    "work_order":         r["work_order"],
                    "tester_id":          r["tester_id"],
                    "timestamp":          r["timestamp"].isoformat() if r["timestamp"] else None,
                    "received_at":        r["received_at"].isoformat() if r["received_at"] else None,
                    "client_ip":          r["client_ip"],
                }
                for r in rows
            ],
        }), 200

    except Exception as exc:
        logger.exception("GET /data failed: %s", exc)
        return jsonify({"status": "error", "message": "Failed to fetch data."}), 500


# ---------------------------------------------------------------------------
# GET /stats — Aggregate stats for dashboard header cards
# ---------------------------------------------------------------------------

@api_bp.route("/stats", methods=["GET"])
def get_stats() -> tuple[Response, int]:
    from database import get_engine
    from sqlalchemy import text as sa_text

    sql = sa_text("""
        SELECT
            COUNT(*)                                    AS total_records,
            COUNT(DISTINCT sensor_sn)                   AS unique_sensors,
            COUNT(DISTINCT work_order)                  AS unique_work_orders,
            ROUND(AVG(quality_score_afiq)::numeric, 1)  AS avg_quality,
            ROUND(AVG(nfiq_score)::numeric, 1)          AS avg_nfiq,
            MAX(received_at)                            AS last_received
        FROM sensor_test_results
    """)
    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(sql).mappings().one()
        return jsonify({
            "status":             "ok",
            "total_records":      row["total_records"],
            "unique_sensors":     row["unique_sensors"],
            "unique_work_orders": row["unique_work_orders"],
            "avg_quality":        float(row["avg_quality"] or 0),
            "avg_nfiq":           float(row["avg_nfiq"] or 0),
            "last_received":      row["last_received"].isoformat() if row["last_received"] else None,
        }), 200
    except Exception as exc:
        logger.exception("GET /stats failed: %s", exc)
        return jsonify({"status": "error", "message": "Failed to fetch stats."}), 500


# ---------------------------------------------------------------------------
# GET /health — Liveness + DB connectivity check
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    from database import get_engine
    from sqlalchemy import text

    now = datetime.now(timezone.utc).isoformat()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.debug("GET /health — database OK")
        return jsonify({"status": "ok", "database": "connected", "timestamp": now}), 200
    except Exception as exc:
        logger.error("GET /health — database unreachable: %s", exc)
        return jsonify({"status": "error", "database": "unreachable", "timestamp": now}), 503