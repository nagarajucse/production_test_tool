"""
create_tables.py
----------------
One-shot utility to create all SQLAlchemy-mapped tables in PostgreSQL.

Use this when the Alembic CLI is not available on the system PATH.
This is equivalent to running: python -m alembic upgrade head

Usage:
    python create_tables.py

Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS semantics.
"""
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from app.config.settings import settings
from app.database.base import Base

# Import all models so their Table definitions are registered on Base.metadata
import app.models.test_result  # noqa: F401


async def create_all_tables() -> None:
    """Creates all mapped tables that do not yet exist in the database."""
    print(f"Connecting to: {settings.DATABASE_URL}")

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
        connect_args={"ssl": False},
    )

    try:
        async with engine.begin() as conn:
            print("\nCreating tables...")
            await conn.run_sync(Base.metadata.create_all)
            print("\n[OK] All tables created successfully.")

        # List tables that now exist
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name;"
                )
            )
            rows = result.fetchall()
            print("\nTables in database:")
            for row in rows:
                print(f"  - {row[0]}")

    except Exception as e:
        print(f"\n[ERROR] Failed to create tables: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_all_tables())
