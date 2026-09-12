from enum import Enum
from pydantic import Field
from app.schemas.common import StrictModel


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FileValidation(StrictModel):
    file_type: str
    is_supported: bool
    is_readable: bool
    page_count: int = Field(ge=1, le=3)
    status: str


class ValidationCheck(StrictModel):
    name: str
    formula: str
    period: str | None = None
    operands: dict[str, float | None] = Field(default_factory=dict)
    calculated_value: float | None = None
    reported_value: float | None = None
    variance: float | None = None
    status: CheckStatus
    message: str | None = None


class FinancialValidation(StrictModel):
    checks: list[ValidationCheck] = Field(default_factory=list)
    overall_status: CheckStatus
    issues: list[str] = Field(default_factory=list)

