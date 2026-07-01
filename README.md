# Production Test Management System

A high-performance, enterprise-grade data management system that receives fingerprint sensor test results from manufacturing floor desktop clients, validates them, and persists them to PostgreSQL.

This project consists of two core components running on a unified Database layer:
1.  **DMS HTTP Server**: A production-ready Flask + Waitress server providing REST APIs for test submission and a dashboard interface.
2.  **TCP Server**: An asynchronous TCP socket server for high-throughput, raw test data ingestion.

---

## Architecture Overview

Both servers share the same underlying architecture and database.

```
[Desktop Testing Clients]
    │                 │
    │ HTTP POST (JSON)│ TCP Socket (newline JSON)
    ▼                 ▼
┌───────────────┐ ┌──────────────────┐
│ Flask Server  │ │ AsyncIO TCP      │
│ app.py        │ │ tcp.py           │
└──────┬────────┘ └────────┬─────────┘
       │                   │
       ▼                   ▼
┌──────────────────────────────────────┐
│            Service Layer             │
│   Validate → Map → Business Rules    │
│  (Pydantic Schemas, validations)     │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│           Database Layer             │
│  SQLAlchemy ORM + Connection Pool    │
└──────────────────┬───────────────────┘
                   │
               PostgreSQL
         (test_results / sensor_test_results)
```

---

## Requirements & Setup

- Python 3.10+
- PostgreSQL 14+

### 1. Database Creation

Connect using `psql` or pgAdmin and run:
```sql
CREATE DATABASE test_manager;
```

### 2. Install Dependencies

All dependencies for both the HTTP server and the TCP server are consolidated in `requirements.txt`.

```bash
# From the project root
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and configure your settings:
```bash
copy .env.example .env
```
Key settings to update in `.env`:
- `DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/test_manager`
- `SERVER_HOST=0.0.0.0`
- `SERVER_PORT=5000`

### 4. Database Migrations (Alembic)

Run the automated migrations to provision your database schema:
```bash
python -m alembic upgrade head
```

---

## Running the Servers

### Running the HTTP DMS Server (Dashboard & API)

This is the primary production tool for the dashboard and API integration.

```bash
# Change to the server directory
cd server

# Run the Waitress production server (on Windows)
python app.py
```
*Access the dashboard at `http://localhost:5000`*

### Running the Async TCP Server (Raw socket ingestion)

If you are using raw TCP clients instead of HTTP:
```bash
# From the project root
python run_server.py
```

---

## API Reference (HTTP POST /)

Receives a fingerprint sensor test result, validates it, and stores it in PostgreSQL.

**Endpoint**: `POST /`
**Content-Type**: `application/json`

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

---

## Logs and Monitoring

Application events and connections are logged using rotating file handlers.
- **`logs/server.log`**: Standard operations and connection tracking.
- **`server/logs/http_server.log`**: HTTP server specific requests and routing logs.
- **`logs/error.log`**: Exception traces and failed payloads.
