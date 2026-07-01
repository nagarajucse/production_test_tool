# DMS HTTP Server — Production Test Management System

A production-ready **HTTP DMS (Data Management Server)** built with Flask and
Waitress that receives fingerprint sensor test results from manufacturing clients
over HTTP POST, validates payloads, stores them in PostgreSQL, and returns
structured JSON responses.

---

## Architecture

```
[Production Testing Client]
         │  HTTP POST / (JSON)
         ▼
┌──────────────────────────────┐
│      Flask HTTP Server       │  server/app.py + routes.py
│   POST /  →  route handler   │  Content-Type guard, JSON parse, IP extraction
└──────────────┬───────────────┘
               │  (http_status, response_dict)
               ▼
┌──────────────────────────────┐
│       Service Layer          │  server/services.py
│   Validate → Map → Persist   │  Pydantic validation, ORM mapping, error taxonomy
└──────┬──────────────┬────────┘
       ▼              ▼
┌────────────┐  ┌──────────────────────────┐
│  Pydantic  │  │    SQLAlchemy ORM        │
│  schemas   │  │  SensorTestResult model  │
│ schemas.py │  │  models.py + database.py │
└────────────┘  └─────────────┬────────────┘
                               │
                          PostgreSQL
                    (sensor_test_results)
```

### Separation of Concerns

| Layer | File | Responsibility |
|-------|------|---------------|
| Entry point | `app.py` | App factory, error handlers, server startup |
| Routing | `routes.py` | HTTP concerns only — parse, IP, timing, delegate |
| Business Logic | `services.py` | Validate, map, persist, error taxonomy |
| Validation | `schemas.py` | Pydantic field rules, type enforcement |
| Persistence | `database.py` | Engine, connection pool, session scope |
| ORM Model | `models.py` | `sensor_test_results` table definition |
| Config | `config.py` | Settings from environment variables |
| Logging | `logger.py` | Rotating file handlers |
| Utilities | `utils.py` | IP extraction, timing helpers |

---

## Project Structure

```
server/
├── app.py              # Flask app factory + Waitress entry point
├── config.py           # Pydantic settings loaded from .env
├── database.py         # SQLAlchemy sync engine + get_db() session manager
├── models.py           # SensorTestResult ORM model → sensor_test_results table
├── schemas.py          # Pydantic validation schema + error formatter
├── routes.py           # Flask Blueprint — POST /
├── services.py         # Business orchestration — validate, persist, respond
├── logger.py           # Rotating log setup (http_server.log, http_error.log)
├── utils.py            # IP extraction, elapsed_ms helper
├── requirements.txt    # Pinned dependencies
├── .env.example        # Configuration template
└── logs/               # Auto-created rotating log files
    ├── http_server.log # All events at LOG_LEVEL
    └── http_error.log  # ERROR+ events only
```

---

## Requirements

- Python 3.10+
- PostgreSQL 14+ with database `test_manager` created

---

## Quick Start

### 1. Create the PostgreSQL Database

Connect with `psql` or pgAdmin and run:

```sql
CREATE DATABASE test_manager;
```

Or from the command line:

```bash
psql -U postgres -c "CREATE DATABASE test_manager;"
```

### 2. Configure Environment

Copy the template and edit your values:

```bash
# From the PROJECT ROOT directory (d:\production_test_tool\)
copy .env.example .env
```

Edit `.env`:

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/test_manager
LOG_LEVEL=INFO
```

### 3. Install Dependencies

```bash
# From the server/ directory
cd server
pip install -r requirements.txt
```

### 4. Run the Server

```bash
# From the server/ directory
python app.py
```

Expected startup output in `logs/http_server.log`:

```
2026-06-19T05:30:00+0000 [INFO    ] [dms.app] ============================================================
2026-06-19T05:30:00+0000 [INFO    ] [dms.app] DMS HTTP Server — Production Test Management System
2026-06-19T05:30:00+0000 [INFO    ] [dms.app] PID: 12345 | Host: 0.0.0.0 | Port: 5000
2026-06-19T05:30:00+0000 [INFO    ] [dms.database] Running schema provisioning (CREATE TABLE IF NOT EXISTS)...
2026-06-19T05:30:00+0000 [INFO    ] [dms.database] Schema provisioning complete — all tables are ready.
2026-06-19T05:30:00+0000 [INFO    ] [dms.app] Starting Waitress WSGI server on 0.0.0.0:5000 (threads=8)...
```

---

## API Reference

### `POST /`

Receives a fingerprint sensor test result, validates it, and stores it in PostgreSQL.

#### Request

```
POST / HTTP/1.1
Host: <SERVER_IP>:5000
Content-Type: application/json
```

#### Request Body

```json
{
    "sensor_sn": "A400202401010111111",
    "model": "A400",
    "image_quality": 81,
    "nfiq2_score": 81,
    "verification_score": 333,
    "part_number": "1.17-A400-0001",
    "work_order": "MO-1-2025-0211",
    "tester_id": "1034",
    "timestamp": "2026-06-19T05:27:43Z",
    "sensor_mac": "3130313131313131"
}
```

#### Field Specification

| Field | Type | Required | Constraints |
|-------|------|----------|------------|
| `sensor_sn` | string | ✅ | non-empty, max 100 chars |
| `model` | string | ✅ | non-empty, max 50 chars |
| `image_quality` | integer | ✅ | 0–100 |
| `nfiq2_score` | integer | ✅ | 0–100 |
| `verification_score` | integer | ✅ | >= 0 |
| `part_number` | string | ✅ | non-empty, max 100 chars |
| `work_order` | string | ✅ | non-empty, max 100 chars |
| `tester_id` | string | ✅ | non-empty, max 50 chars |
| `timestamp` | string | ✅ | ISO-8601 format |
| `sensor_mac` | string | ✅ | hex characters only, max 50 chars |

#### Response: Success (HTTP 200)

```json
{
    "status": "success",
    "message": "Data stored successfully"
}
```

#### Response: Validation Error (HTTP 400)

```json
{
    "status": "error",
    "message": "Payload validation failed.",
    "errors": [
        "sensor_sn: field required",
        "nfiq_score: Input should be less than or equal to 100"
    ]
}
```

#### Response: Server Error (HTTP 500)

```json
{
    "status": "error",
    "message": "An internal server error occurred."
}
```

#### Response: Payload Too Large (HTTP 413)

```json
{
    "status": "error",
    "message": "Payload too large. Maximum allowed size is 1024 KB."
}
```

---

## Testing the API

### Python `requests` (recommended)

```python
import requests

payload = {
    "sensor_sn": "A400202401010111111",
    "model": "A400",
    "image_quality": 81,
    "nfiq2_score": 81,
    "verification_score": 333,
    "part_number": "1.17-A400-0001",
    "work_order": "MO-1-2025-0211",
    "tester_id": "1034",
    "timestamp": "2026-06-19T05:27:43Z",
    "sensor_mac": "3130313131313131"
}

response = requests.post("http://localhost:5000/", json=payload)
print(response.status_code, response.json())
```

### cURL

```bash
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_sn": "A400202401010111111",
    "model": "A400",
    "image_quality": 81,
    "nfiq2_score": 81,
    "verification_score": 333,
    "part_number": "1.17-A400-0001",
    "work_order": "MO-1-2025-0211",
    "tester_id": "1034",
    "timestamp": "2026-06-19T05:27:43Z",
    "sensor_mac": "3130313131313131"
  }'
```

### Test Validation Rejection

```bash
# Missing required field
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{"sensor_sn": "A400-001"}'
# → HTTP 400 with errors list

# Wrong Content-Type
curl -X POST http://localhost:5000/ \
  -H "Content-Type: text/plain" \
  -d 'hello'
# → HTTP 400
```

---

## Verifying Database Records

Connect with `psql` or pgAdmin:

```sql
-- View all stored test results (latest first)
SELECT id, sensor_sn, model, image_quality, nfiq2_score,
       work_order, tester_id, received_at
FROM sensor_test_results
ORDER BY received_at DESC
LIMIT 20;

-- Filter by sensor serial number
SELECT * FROM sensor_test_results
WHERE sensor_sn = 'A400202401010111111';

-- Filter by work order
SELECT sensor_sn, model, nfiq2_score, verification_score, received_at
FROM sensor_test_results
WHERE work_order = 'MO-1-2025-0211'
ORDER BY received_at;

-- Count results per model
SELECT model, COUNT(*) as total_tests
FROM sensor_test_results
GROUP BY model
ORDER BY total_tests DESC;

-- Retrieve fingerprint image details
SELECT sensor_sn, image_name, image_format
FROM sensor_test_results
WHERE sensor_sn = 'A400202401010111111';
```

---

## Deployment

### Windows — Waitress (Production)

Waitress is a production-grade pure-Python WSGI server. It is the recommended
choice for Windows where Gunicorn is not supported.

```bash
# Run directly (Waitress starts automatically on Windows)
python app.py

# Or with explicit Waitress CLI
waitress-serve --host=0.0.0.0 --port=5000 --threads=8 "app:create_app()"
```

**Run as a Windows Service** (optional):

Use NSSM (Non-Sucking Service Manager) to register as a Windows service:

```bash
nssm install DMS-Server "C:\Python311\python.exe" "D:\production_test_tool\server\app.py"
nssm set DMS-Server AppDirectory "D:\production_test_tool\server"
nssm start DMS-Server
```

### Linux — Gunicorn (Production)

```bash
# Install Gunicorn
pip install gunicorn

# Run with 4 worker processes (set to 2 * CPU cores + 1)
gunicorn -w 4 -b 0.0.0.0:5000 \
  --timeout 30 \
  --access-logfile logs/gunicorn_access.log \
  --error-logfile logs/gunicorn_error.log \
  "app:create_app()"
```

**Systemd service** (`/etc/systemd/system/dms-server.service`):

```ini
[Unit]
Description=DMS HTTP Server
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/opt/production_test_tool/server
ExecStart=/opt/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
Restart=always
RestartSec=5
EnvironmentFile=/opt/production_test_tool/.env

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable dms-server
systemctl start dms-server
systemctl status dms-server
```

---

## Log Files

| File | Contents |
|------|----------|
| `logs/http_server.log` | All events: startup, requests, inserts, errors |
| `logs/http_error.log` | ERROR and CRITICAL events only |

Log format:
```
2026-06-19T05:27:43+0000 [INFO    ] [dms.routes] Incoming POST / from 10.174.99.100
2026-06-19T05:27:43+0000 [INFO    ] [dms.services] Record saved — sensor_sn=A400202401010111111 model=A400 id=...
2026-06-19T05:27:43+0000 [INFO    ] [dms.routes] POST / completed for 10.174.99.100 — HTTP 200 response_time=12.4ms
```

All log files rotate at 10 MB, with 5 historical backups retained.

---

## Connection Pooling

| Parameter | Value | Reason |
|-----------|-------|--------|
| `pool_size=20` | 20 persistent connections | Pre-allocated — eliminates per-request connect overhead |
| `max_overflow=10` | +10 burst connections | Handles traffic spikes |
| `pool_timeout=30` | 30s checkout wait | Prevents indefinite hangs when pool is exhausted |
| `pool_recycle=1800` | Recycle after 30 min | Avoids stale PostgreSQL connections |
| `pool_pre_ping=True` | Health check on checkout | Survives network interruptions automatically |

---

## Security Features

| Feature | Implementation |
|---------|---------------|
| SQL Injection prevention | SQLAlchemy ORM — no string concatenation ever |
| Input validation | Pydantic with strict types, min/max lengths, range checks |
| Oversized request rejection | Flask `MAX_CONTENT_LENGTH` → HTTP 413 |
| Stack trace hiding | Global error handlers return generic messages only |
| Debug mode | Always `False` — hardcoded, not configurable |
| Secrets management | Environment variables only — never in source code |
| Unknown field rejection | Pydantic `extra="forbid"` |
