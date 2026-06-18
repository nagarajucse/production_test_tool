import asyncio
import sys

from app.config.settings import settings
from app.utils.logging import setup_logging
from app.server.tcp import Server, DummyRequestProcessor

async def main() -> None:
    """
    Main entrypoint bootstrapper for the TCP Server.
    Initializes logging, injects dependencies, starts the listener,
    and handles graceful termination signals.
    """
    # 1. Initialize logging configurations
    setup_logging()

    # 2. Instantiate request processor (mock implementation for Step 2)
    processor = DummyRequestProcessor()

    # 3. Create the Server instance
    server = Server(
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        processor=processor
    )

    # 4. Start listener socket
    await server.start()

    # 5. Serve requests until interupted
    try:
        await server.serve_forever()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTCP Server shutdown triggered by Ctrl+C.")
        sys.exit(0)
