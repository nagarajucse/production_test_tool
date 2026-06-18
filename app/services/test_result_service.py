import json
import logging
from typing import Any, Dict
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database.session import get_db_session
from app.repositories.test_result_repository import TestResultRepository
from app.models.test_result import TestResult
from app.schemas.test_result import TestResultCreateSchema

logger = logging.getLogger("app")

class TestResultService:
    """
    Orchestrator Service class executing business workflows:
    - Parses JSON payloads
    - Validates fields via Pydantic Schemas
    - Evaluates business rules (blocks duplicates of successfully passed devices)
    - Persists records using SQL Repositories
    - Returns structured outcome payloads (ACK/NACK)
    """
    async def process_raw_test_result(
        self, client_ip: str, client_port: int, raw_json_str: str
    ) -> Dict[str, Any]:
        """
        Decodes incoming connection test string, validates schema, applies policies, and persists.
        
        Args:
            client_ip: Remote network interface IP address.
            client_port: Remote network port.
            raw_json_str: Plain text from socket stream.
            
        Returns:
            Dictionary payload matching standard Success/Failure/Error JSON contracts.
        """
        # 1. Structural parse check
        try:
            raw_payload = json.loads(raw_json_str)
            if not isinstance(raw_payload, dict):
                return {
                    "status": "failed",
                    "errors": ["Payload must be a JSON object"]
                }
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "errors": ["Invalid JSON format"]
            }

        # 2. Schema check
        try:
            validated_data = TestResultCreateSchema(**raw_payload)
        except ValidationError as e:
            # Format and list errors for cleaner diagnostics
            errors = [f"{err['loc'][0] if err['loc'] else 'payload'}: {err['msg']}" for err in e.errors()]
            logger.warning("Validation failed for request from %s:%d: %s", client_ip, client_port, errors)
            return {
                "status": "failed",
                "errors": errors
            }

        # 3. Transaction boundary connection context
        try:
            async with get_db_session() as session:
                repository = TestResultRepository(session)

                # --- Business Rule: Prevent duplicate passing runs ---
                # Check if device has a prior passing history logged in DB.
                existing_record = await repository.get_by_serial_number(validated_data.serial_number)
                if existing_record and existing_record.result == "PASS":
                    logger.warning("Business rule rejection: serial '%s' has already logged a PASS status.",
                                   validated_data.serial_number)
                    return {
                        "status": "failed",
                        "errors": [f"Device with serial number '{validated_data.serial_number}' has already passed testing."]
                    }

                # 4. Map ORM Model
                test_result_model = TestResult(
                    device_id=validated_data.device_id,
                    serial_number=validated_data.serial_number,
                    operator=validated_data.operator,
                    machine=validated_data.machine,
                    firmware=validated_data.firmware,
                    result=validated_data.result,
                    execution_time=validated_data.execution_time,
                    timestamp=validated_data.timestamp,
                    raw_json=raw_payload,
                    client_ip=client_ip
                )

                saved_record = await repository.save_test_result(test_result_model)
                
                # Transaction commit executes automatically when exiting context block successfully
                logger.info("Record successfully saved. Device: %s (SN: %s) ID: %s", 
                            saved_record.device_id, saved_record.serial_number, saved_record.id)

                return {
                    "status": "success",
                    "message": "Stored Successfully",
                    "id": str(saved_record.id)
                }

        except IntegrityError as e:
            logger.error("Database constraint collision on persistence: %s", str(e))
            # Scoped rollback triggers automatically in context manager
            return {
                "status": "failed",
                "errors": ["Database integrity constraint violation occurred."]
            }
        except OperationalError as e:
            logger.error("Postgres connection pool offline or socket timeout: %s", str(e), exc_info=e)
            return {
                "status": "error",
                "message": "Database connection unavailable. Try again later."
            }
        except Exception as e:
            logger.error("Unhandled database error occurred: %s", str(e), exc_info=e)
            return {
                "status": "error",
                "message": "Internal Server Error"
            }

    async def process_request(self, ip: str, port: int, payload: str) -> str:
        """
        Adapter method implementing the RequestProcessor protocol.
        Converts the service's dictionary response to a JSON string.
        """
        result_dict = await self.process_raw_test_result(ip, port, payload)
        return json.dumps(result_dict)
