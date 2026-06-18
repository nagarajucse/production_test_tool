from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class TestItemSchema(BaseModel):
    """
    Validates individual sub-test results nested inside the main payload.
    """
    name: str = Field(..., min_length=1, max_length=100, description="The name of the test case")
    status: str = Field(..., description="Status result of the test case: PASS, FAIL, ERROR")
    value: Optional[str] = Field(None, max_length=255, description="Measured parameter value or OK status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"PASS", "FAIL", "ERROR"}
        upper_v = v.upper().strip()
        if upper_v not in valid_statuses:
            raise ValueError(f"Sub-test status must be one of: {valid_statuses}")
        return upper_v


class TestResultCreateSchema(BaseModel):
    """
    Validates the primary test result record payload.
    """
    device_id: str = Field(..., min_length=1, max_length=50)
    serial_number: str = Field(..., min_length=1, max_length=100)
    operator: str = Field(..., min_length=1, max_length=100)
    machine: str = Field(..., min_length=1, max_length=100)
    firmware: str = Field(..., min_length=1, max_length=50)
    result: str = Field(..., description="Overall test verdict: PASS or FAIL")
    execution_time: float = Field(..., ge=0.0, description="Test execution time in seconds")
    timestamp: datetime = Field(..., description="ISO 8601 formatted timestamp of the test event")
    tests: List[TestItemSchema] = Field(default_factory=list, description="Array of nested sub-test item results")

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        valid_results = {"PASS", "FAIL"}
        upper_v = v.upper().strip()
        if upper_v not in valid_results:
            raise ValueError(f"Overall test result must be one of: {valid_results}")
        return upper_v
