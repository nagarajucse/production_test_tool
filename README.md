# Production Test Management System — Phase 1

A high-performance, enterprise-grade **asynchronous TCP server** that receives JSON test result packets from manufacturing floor desktop clients, validates them, and persists them to PostgreSQL.

---

## Architecture

```
[Desktop Testing Client]
         │  TCP Socket (newline-framed JSON)
         ▼
┌─────────────────────────┐
│   Presentation Layer    │  app/server/tcp.py
│   AsyncIO TCP Server    │  ConnectionHandler, Server
└──────────┬──────────────┘
           │  RequestProcessor Protocol (Dependency Injection)
           ▼
┌─────────────────────────┐
│    Service Layer        │  app/services/test_result_service.py
│  Business Orchestration │  JSON parse → Pydantic validate → business rules → persist
└──────────┬──────────────┘
           │
    ┌──────┴────────────────────────────┐
    ▼                                   ▼
┌──────────────────┐     ┌─────────────────────────────┐
│ Pydantic Schemas │     │     Repository Layer        │
│ app/schemas/     │     │  app/repositories/          │
│ Validate fields  │     │  SQLAlchemy queries only     │
└──────────────────┘     └──────────────┬──────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │      Database Layer         │
                         │  app/database/ + app/models │
                         │  AsyncEngine, Session scope │
                         └──────────────┬──────────────┘
                                        │
                                  PostgreSQL
```

### Why Clean Architecture?

| Principle | Application |
|---|---|
| **Single Responsibility** | TCP server only handles bytes; service only handles business logic; repository only handles SQL |
| **Dependency Inversion** | TCP server depends on `RequestProcessor` Protocol, not `TestResultService` directly |
| **Open/Closed** | New packet types require only new schemas and services — TCP layer unchanged |
| **Repository Pattern** | Isolates SQLAlchemy from business logic; repositories can be swapped for mock implementations in tests |
| **Service Layer** | Centralises business rules (e.g. duplicate pass detection); keeps them out of both TCP and DB code |

---

## Project Structure

```
production-test-server/
├── app/
│   ├── config/
│   │   └── settings.py          # Pydantic config, loaded from .env
│   ├── database/
│   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   ├── connection.py        # AsyncEngine + connection pooling
│   │   └── session.py           # Async session context manager (commit/rollback/close)
│   ├── models/
│   │   └── test_result.py       # TestResult ORM model → test_results table
│   ├── repositories/
│   │   └── test_result_repository.py   # save, get_by_id, get_by_serial_number, exists
│   ├── schemas/
│   │   └── test_result.py       # Pydantic validation schemas (TestResultCreateSchema)
│   ├── server/
│   │   ├── tcp.py               # asyncio TCP Server, ConnectionHandler, RequestProcessor
│   ├── services/
│   │   └── test_result_service.py      # Business orchestrator, implements RequestProcessor
│   └── utils/
│       └── logging.py           # Rotating log handlers: server.log, error.log, connections.log
├── migrations/
│   ├── env.py                   # Alembic async migration environment
│   ├── script.py.mako           # Migration file template
│   └── versions/
│       └── 0001_initial.py      # Creates test_results table with all indexes
├── tests/
│   ├── test_tcp_server.py       # TCP server integration tests (11 tests)
│   └── test_database_layer.py   # Repository and service layer unit tests
├── logs/                        # Auto-created rotating log files
├── alembic.ini                  # Alembic configuration
├── requirements.txt             # Pinned production dependencies
├── .env.example                 # Configuration template
├── run_server.py                # Production server entry point
└── README.md
```

---

## Configuration

Copy `.env.example` to `.env` and adjust for your environment:

```bash
copy .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Network interface to bind |
| `SERVER_PORT` | `5000` | TCP port |
| `SERVER_TIMEOUT_SECONDS` | `30.0` | Client inactivity timeout |
| `SERVER_MAX_PACKET_SIZE_BYTES` | `1048576` | Max JSON packet size (1 MB) |
| `SERVER_MAX_CONNECTIONS` | `1000` | Max concurrent connections |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL async connection string |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `LOG_DIR` | `logs` | Log file directory |
| `LOG_MAX_BYTES` | `10485760` | Log rotation size (10 MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of archived log files |

---

## How to Install PostgreSQL

### Windows
1. Download from https://www.postgresql.org/download/windows/
2. Install with default settings (remember the `postgres` password)
3. Open **pgAdmin** or **psql** to manage databases

### Docker (Recommended for Development)
```bash
docker run -d --name postgres-test \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=test_manager \
  -p 5432:5432 \
  postgres:16
```

---

## How to Create the Database

Connect using `psql` or pgAdmin and run:

```sql
CREATE DATABASE test_manager;
```

Or using `psql`:
```bash
psql -U postgres -c "CREATE DATABASE test_manager;"
```

---

## How to Run Alembic Migrations

Alembic is installed as part of the project dependencies. Run migrations from the project root:

```bash
# Apply all pending migrations (creates test_results table)
python -m alembic upgrade head

# View migration history
python -m alembic history

# Roll back the last migration
python -m alembic downgrade -1

# Generate a new auto-migration after model changes
python -m alembic revision --autogenerate -m "describe your change"
```

### Why Alembic?
- Tracks schema version history in a `alembic_version` table
- Supports incremental upgrades and rollbacks
- Autogenerate compares live SQLAlchemy models to the current DB schema

### Why Async Engine in env.py?
Our `DATABASE_URL` uses the `asyncpg` driver. Alembic runs synchronously by default, so `env.py` wraps the migration execution in `asyncio.run()` to maintain full compatibility.

---

## How to Run the Server

```bash
# Ensure .env is configured with your DATABASE_URL
python run_server.py
```

Expected startup output:
```
2026-06-18T09:45:00+0530 [INFO] [app] Logging infrastructure successfully initialized.
2026-06-18T09:45:00+0530 [INFO] [app] Initializing database connection engine...
2026-06-18T09:45:00+0530 [INFO] [app] Database connection engine successfully initialized.
2026-06-18T09:45:00+0530 [INFO] [app] Asynchronous TCP Server successfully initialized and listening on 0.0.0.0:5000
```

---

## TCP Protocol Specification

**Transport**: Raw TCP  
**Framing**: Newline-delimited (`\n`) — one JSON object per line  
**Encoding**: UTF-8

### Request Payload
```json
{
  "device_id": "DEV-001",
  "serial_number": "SN123456789",
  "operator": "Nagaraju",
  "machine": "Station-01",
  "firmware": "1.0.5",
  "result": "PASS",
  "execution_time": 12.45,
  "timestamp": "2026-06-18T10:22:00Z",
  "tests": [
    {"name": "Fingerprint", "status": "PASS", "value": "OK"},
    {"name": "Camera", "status": "PASS", "value": "OK"}
  ]
}
```

### Response: Success
```json
{"status": "success", "message": "Stored Successfully", "id": "<uuid>"}
```

### Response: Validation Failure
```json
{"status": "failed", "errors": ["result: Input should be 'PASS' or 'FAIL'"]}
```

### Response: Server Error
```json
{"status": "error", "message": "Internal Server Error"}
```

---

## How to Test Locally

### Quick Socket Test (Python)
```python
import socket, json

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("127.0.0.1", 5000))

payload = {
    "device_id": "DEV-001", "serial_number": "SN-00001",
    "operator": "Nagaraju", "machine": "Station-01",
    "firmware": "1.0.5", "result": "PASS",
    "execution_time": 12.45, "timestamp": "2026-06-18T10:22:00Z",
    "tests": [{"name": "Camera", "status": "PASS", "value": "OK"}]
}
s.sendall((json.dumps(payload) + "\n").encode())
print(s.recv(4096).decode())
s.close()
```

### Run Automated Tests
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## How to Verify Records in PostgreSQL

```sql
-- View all test results
SELECT id, device_id, serial_number, result, received_at
FROM test_results
ORDER BY received_at DESC;

-- Filter only failed tests
SELECT serial_number, operator, machine, result, execution_time
FROM test_results
WHERE result = 'FAIL'
ORDER BY timestamp DESC;

-- Count results per device
SELECT device_id, result, COUNT(*) as total
FROM test_results
GROUP BY device_id, result
ORDER BY device_id;

-- Retrieve test results for a specific device
SELECT serial_number, device_id, operator, result
FROM test_results
WHERE serial_number = 'SN-00001';
```

---

## How Connection Pooling Works

`app/database/connection.py` configures the SQLAlchemy async engine with:

| Parameter | Value | Reason |
|---|---|---|
| `pool_size=20` | 20 persistent connections | Pre-allocated; eliminates connection overhead per request |
| `max_overflow=10` | +10 burst connections | Handles traffic spikes beyond pool_size |
| `pool_timeout=30` | 30 second checkout wait | Avoids indefinite hangs when pool is exhausted |
| `pool_recycle=1800` | Recycle after 30 minutes | Prevents stale TCP connections from PostgreSQL server |
| `pool_pre_ping=True` | Health check on checkout | Automatically reconnects to DB after network interruptions |

### Why Scoped Sessions?
`app/database/session.py` creates a new `AsyncSession` per request using an `asynccontextmanager`. This means:
- Each TCP request gets a **fresh, isolated transaction scope**
- Commits happen automatically on success
- Rollbacks happen automatically on any exception
- Sessions are always closed in the `finally` block — no connection leaks

---

## Log Files

| File | Contents |
|---|---|
| `logs/server.log` | All application events (startup, requests, errors) |
| `logs/connections.log` | Client connect/disconnect events only |
| `logs/error.log` | ERROR and CRITICAL events only |

All files rotate at 10 MB with 5 historical backups retained.
