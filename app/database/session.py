from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import db_manager

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous context manager returning a database session transaction scope.
    
    Guarantees:
    - Clean transaction commits on block completion.
    - Automatic rolls back on database exceptions/failures.
    - Sockets are closed and returned to the pool in the finally block.
    """
    session = db_manager.session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
