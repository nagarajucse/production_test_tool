import asyncio
import logging
import os
import sys

from app.config.settings import settings
from app.utils.logging import setup_logging
from app.server.tcp import Server
from app.database.connection import db_manager
from app.services.test_result_service import TestResultService


async def main() -> None:
    """
    Production server bootstrap.

    Startup sequence:
    1. Logging
    2. Database connection pool
    3. TCP server bind
    4. Serve until shutdown signal

    Shutdown sequence (triggered by Ctrl+C / SIGTERM):
    1. TCP listener socket closed
    2. Active client tasks drained (5s grace)
    3. Database pool disposed
    """
    setup_logging()
    logger = logging.getLogger("app")

    logger.info("=" * 60)
    logger.info("Production Test Management System")
    logger.info("PID: %d | Host: %s | Port: %d", os.getpid(), settings.SERVER_HOST, settings.SERVER_PORT)
    logger.info("=" * 60)

    # Initialize the database connection pool
    db_manager.initialize()

    # Provision schema — creates test_results table if it doesn't exist yet.
    # Safe to call on every startup (IF NOT EXISTS semantics).
    await db_manager.create_tables()

    # Inject the real business service as the RequestProcessor
    processor = TestResultService()

    server = Server(
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        processor=processor,
    )

    await server.start()

    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        # Triggered when asyncio.run() cancels main() on KeyboardInterrupt (Windows)
        pass
    finally:
        await server.stop()
        await db_manager.close()
        logger.info("Server process PID:%d fully terminated.", os.getpid())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # asyncio.run() on Windows raises KeyboardInterrupt after cancelling main()
        # The finally block in main() will have already executed cleanup
        sys.exit(0)
