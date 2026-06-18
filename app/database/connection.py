import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from app.config.settings import settings

logger = logging.getLogger("app")

class DatabaseConnectionManager:
    """
    Manages the lifecycle of the SQLAlchemy asynchronous connection engine and session factory.
    Integrates production-ready connection pool sizing, idle recycling, and pre-pings.
    """
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker[AsyncSession]] = None

    def initialize(self) -> None:
        """
        Initializes the async engine and session factory.
        Pool parameters are optimized for multi-client concurrency.
        """
        if self._engine:
            logger.debug("Database Connection Manager already initialized.")
            return

        logger.info("Initializing database connection engine...")
        try:
            self._engine = create_async_engine(
                self.database_url,
                pool_size=20,            # Pre-allocated connection pool size
                max_overflow=10,         # Max overflow connections beyond pool size
                pool_timeout=30.0,       # Socket checkout timeout (seconds)
                pool_recycle=1800,       # Recycle connections after 30 minutes to prevent stale pools
                pool_pre_ping=True,      # Auto-test connection state before checkout
                echo=False,              # Set to True for verbose SQL debugging
            )
            self._session_maker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False   # Keep objects detached from session usable post-commit
            )
            logger.info("Database connection engine successfully initialized.")
        except Exception as e:
            logger.error("Failed to initialize database engine: %s", str(e), exc_info=e)
            raise

    @property
    def session_maker(self) -> async_sessionmaker[AsyncSession]:
        """Exposes the session maker factory."""
        if not self._session_maker:
            raise RuntimeError("DatabaseConnectionManager is not initialized. Invoke initialize() first.")
        return self._session_maker

    async def create_tables(self) -> None:
        """
        Creates all SQLAlchemy-mapped tables that do not yet exist in the database.
        Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS semantics.
        Called once at server startup to ensure the schema is provisioned.
        """
        if not self._engine:
            raise RuntimeError("DatabaseConnectionManager not initialized. Call initialize() first.")

        # Import lazily here to avoid circular imports
        from app.database.base import Base
        import app.models.test_result  # noqa: F401 — registers TestResult on Base.metadata

        logger.info("Running schema provisioning (CREATE TABLE IF NOT EXISTS)...")
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Schema provisioning complete. All tables are ready.")
        except Exception as e:
            logger.error("Schema provisioning failed: %s", e, exc_info=e)
            raise

    async def close(self) -> None:
        """Disposes the connection pool cleanly on graceful shutdown."""
        if self._engine:
            logger.info("Disposing database connection pool...")
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
            logger.info("Database connection pool successfully disposed.")


# Global database manager instance
db_manager = DatabaseConnectionManager(settings.DATABASE_URL)
