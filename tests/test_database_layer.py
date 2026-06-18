import asyncio
import datetime
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models.test_result import TestResult
from app.repositories.test_result_repository import TestResultRepository
from app.services.test_result_service import TestResultService

class TestDatabaseLayer(unittest.IsolatedAsyncioTestCase):
    """
    Test suite validating database models, repositories, and transactional services.
    Uses mock frameworks to simulate DB connections in offline development setups.
    """
    async def test_repository_save_test_result(self) -> None:
        """Verifies that the repository stages record inserts inside the active session transaction."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # Synchronous ORM method
        repository = TestResultRepository(mock_session)
        
        test_result = TestResult(
            id=uuid.uuid4(),
            device_id="DEV-100",
            serial_number="SN-TST-100",
            operator="Nagaraju",
            machine="Station-01",
            firmware="1.2.0",
            result="PASS",
            execution_time=15.6,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            raw_json={},
            client_ip="127.0.0.1"
        )
        
        saved = await repository.save_test_result(test_result)
        
        # Verify SQLAlchemy ORM interactions
        mock_session.add.assert_called_once_with(test_result)
        mock_session.flush.assert_called_once()
        self.assertEqual(saved.device_id, "DEV-100")
        self.assertEqual(saved.serial_number, "SN-TST-100")

    async def test_repository_get_by_id(self) -> None:
        """Verifies that retrieving a record by ID executes a select query and parses scalars."""
        mock_session = AsyncMock()
        repository = TestResultRepository(mock_session)
        test_id = uuid.uuid4()
        
        # Configure select execution mocks
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = TestResult(id=test_id, device_id="DEV-100")
        mock_session.execute.return_value = mock_result
        
        result = await repository.get_by_id(test_id)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, test_id)
        mock_session.execute.assert_called_once()

    async def test_service_duplicate_pass_rejection(self) -> None:
        """Verifies the business rule that devices which have already PASS-ed are rejected on resubmit."""
        service = TestResultService()
        raw_payload = {
            "device_id": "DEV-200",
            "serial_number": "SN-DUP-PASS",
            "operator": "Nagaraju",
            "machine": "Station-01",
            "firmware": "2.0.0",
            "result": "PASS",
            "execution_time": 12.0,
            "timestamp": "2026-06-18T10:22:00Z",
            "tests": []
        }
        
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        # Simulate a previous PASS result exists for the device serial number
        mock_repo.get_by_serial_number.return_value = TestResult(result="PASS", serial_number="SN-DUP-PASS")
        
        with patch("app.services.test_result_service.get_db_session") as mock_get_session, \
             patch("app.services.test_result_service.TestResultRepository", return_value=mock_repo):
            
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            response = await service.process_raw_test_result("127.0.0.1", 5000, json.dumps(raw_payload))
            
            # Assert failure return
            self.assertEqual(response["status"], "failed")
            self.assertIn("already passed", response["errors"][0])
            mock_repo.save_test_result.assert_not_called()

    async def test_service_operational_error(self) -> None:
        """Verifies that operational errors (e.g. database down) fail gracefully with a connection error."""
        service = TestResultService()
        raw_payload = {
            "device_id": "DEV-300",
            "serial_number": "SN-TST-300",
            "operator": "Nagaraju",
            "machine": "Station-01",
            "firmware": "1.0.0",
            "result": "PASS",
            "execution_time": 4.5,
            "timestamp": "2026-06-18T10:22:00Z",
            "tests": []
        }
        
        # Force the session builder to raise an OperationalError simulating server down
        with patch("app.services.test_result_service.get_db_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.side_effect = OperationalError("select", {}, Exception("Connection refused"))
            
            response = await service.process_raw_test_result("127.0.0.1", 5000, json.dumps(raw_payload))
            
            self.assertEqual(response["status"], "error")
            self.assertIn("connection unavailable", response["message"].lower())

    async def test_service_integrity_error_rollback(self) -> None:
        """Verifies that database integrity violations (e.g. constraint failure) trigger failure responses."""
        service = TestResultService()
        raw_payload = {
            "device_id": "DEV-400",
            "serial_number": "SN-TST-400",
            "operator": "Nagaraju",
            "machine": "Station-01",
            "firmware": "1.0.0",
            "result": "PASS",
            "execution_time": 2.5,
            "timestamp": "2026-06-18T10:22:00Z",
            "tests": []
        }
        
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_by_serial_number.return_value = None
        # Raise IntegrityError on save
        mock_repo.save_test_result.side_effect = IntegrityError("insert", {}, Exception("Unique violation"))
        
        with patch("app.services.test_result_service.get_db_session") as mock_get_session, \
             patch("app.services.test_result_service.TestResultRepository", return_value=mock_repo):
            
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            response = await service.process_raw_test_result("127.0.0.1", 5000, json.dumps(raw_payload))
            
            self.assertEqual(response["status"], "failed")
            self.assertIn("integrity constraint violation", response["errors"][0].lower())
