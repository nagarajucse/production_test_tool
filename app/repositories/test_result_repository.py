import logging
from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.test_result import TestResult

logger = logging.getLogger("app")

class TestResultRepository:
    """
    Repository encapsulating database query and command operations for the TestResult model.
    Decoupled from transaction scoping to allow multi-repository composition.
    """
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_test_result(self, test_result: TestResult) -> TestResult:
        """
        Persists a new TestResult record in the database.
        
        Args:
            test_result: Instantiated TestResult ORM entity.
            
        Returns:
            The saved TestResult record.
        """
        self.session.add(test_result)
        # Flush to populate automatically generated fields (UUID, defaults) before transaction commit
        await self.session.flush()
        logger.info("Record staged in session database transaction (ID: %s)", test_result.id)
        return test_result

    async def get_by_id(self, id: uuid.UUID) -> Optional[TestResult]:
        """
        Retrieves a single TestResult record by its UUID key.
        
        Args:
            id: Target record UUID.
            
        Returns:
            The matching TestResult entity or None.
        """
        stmt = select(TestResult).where(TestResult.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_serial_number(self, serial_number: str) -> Optional[TestResult]:
        """
        Retrieves the latest test result record for a specific serial number.
        
        Args:
            serial_number: Target device serial string.
            
        Returns:
            The latest matching TestResult entity or None.
        """
        stmt = (
            select(TestResult)
            .where(TestResult.serial_number == serial_number)
            .order_by(TestResult.received_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def exists_by_serial_number(self, serial_number: str) -> bool:
        """
        Checks if any test result has been logged for a device serial number.
        
        Args:
            serial_number: Target device serial string.
            
        Returns:
            True if any records exist, False otherwise.
        """
        stmt = select(1).where(TestResult.serial_number == serial_number).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar() is not None
