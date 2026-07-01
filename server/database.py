"""
database.py — SQLAlchemy synchronous database engine and session management.

Design decisions:
  - Synchronous engine (psycopg2): matches Flask's synchronous request model and
    the dependency list specified in the task. Avoids the complexity of mixing
    asyncio with Flask without a framework like Quart or async Flask extensions.
  - Connection pooling: QueuePool with pre-ping ensures stale connections are
    detected and recycled automatically — critical for long-running services.
  - get_db() context manager: guarantees commit on success and rollback on any
    exception, then always closes the session. No connection leaks possible.
  - Never use raw SQL strings — all queries go through ORM or Core expressions.

Usage:
    from database import get_db

    with get_db() as session:
        session.add(record)   # auto-committed on exit
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings

logger = logging.getLogger("dms.database")

# ---------------------------------------------------------------------------
# Engine — created once at module import time (singleton pattern).
# pool_pre_ping=True: tests each connection with a lightweight SELECT before
#   handing it to the application, preventing "server closed the connection
#   unexpectedly" errors after network interruptions.
# pool_recycle=1800: forces connections to be replaced after 30 minutes,
#   avoiding PostgreSQL's default idle connection timeout.
# ---------------------------------------------------------------------------
_engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,          # steady-state pool — pre-allocated for concurrency
    max_overflow=10,       # burst capacity beyond pool_size
    pool_timeout=30,       # seconds to wait for a connection before raising
    pool_recycle=1800,     # recycle connections every 30 minutes
    pool_pre_ping=True,    # validate connection health on checkout
    echo=False,            # set True only for SQL debugging — never in production
)

# Session factory — all sessions are created through this factory
_SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=_engine,
    autocommit=False,  # explicit commit required — transactions are controlled by get_db()
    autoflush=False,   # flush manually to control when SQL statements are sent
)


def get_engine() -> Engine:
    """Returns the module-level SQLAlchemy engine. Useful for table creation."""
    return _engine


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Provides a transactional database session scope.

    Guarantees:
      - A fresh session is opened for every request.
      - On success (no exception): session is flushed and committed.
      - On any exception: transaction is rolled back before re-raising.
      - Session is always closed in the finally block — no resource leaks.

    Usage:
        with get_db() as db:
            db.add(my_record)
            # commit happens automatically on context exit
    """
    session: Session = _SessionLocal()
    logger.debug("Database session opened.")
    try:
        yield session
        session.commit()
        logger.debug("Transaction committed.")
    except Exception:
        session.rollback()
        logger.debug("Transaction rolled back.")
        raise
    finally:
        session.close()
        logger.debug("Database session closed.")


def create_tables() -> None:
    """
    Creates all SQLAlchemy-mapped tables that do not yet exist in PostgreSQL.

    Uses CREATE TABLE IF NOT EXISTS semantics via SQLAlchemy's
    metadata.create_all() — safe to call on every server startup.

    The import of 'models' here is intentional: it registers all ORM model
    classes with Base.metadata before create_all() is called.
    """
    from models import Base  # noqa: F401 — triggers ORM model registration
    from sqlalchemy import text, inspect

    logger.info("Running schema provisioning (CREATE TABLE IF NOT EXISTS)...")
    try:
        insp = inspect(_engine)
        if insp.has_table('sensor_test_results'):
            columns = [col['name'] for col in insp.get_columns('sensor_test_results')]
            if 'minutiae_count' not in columns:
                logger.info("Applying schema migration to add minutiae_count and lfd_status...")
                with _engine.begin() as conn:
                    conn.execute(text("ALTER TABLE sensor_test_results ADD COLUMN minutiae_count INTEGER DEFAULT 0"))
                    conn.execute(text("ALTER TABLE sensor_test_results ADD COLUMN lfd_status VARCHAR(50) DEFAULT 'Unknown'"))
                logger.info("Schema migration successful.")
    except Exception as e:
        logger.warning("Automatic schema migration skipped or failed: %s", e)

    try:
        Base.metadata.create_all(bind=_engine)
        logger.info("Schema provisioning complete — all tables are ready.")
    except Exception as exc:
        logger.error("Schema provisioning failed: %s", exc, exc_info=True)
        raise
