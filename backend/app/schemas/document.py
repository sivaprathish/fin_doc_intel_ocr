from datetime import datetime
from enum import Enum
from pydantic import ConfigDict, Field
from app.schemas.common import StrictModel
from app.schemas.extraction import StructuredExtraction
from app.schemas.validation import FileValidation, FinancialValidation


class DocumentType(str, Enum):
    invoice = "invoice"
    balance_sheet = "balance_sheet"
    profit_and_loss = "profit_and_loss"
    cash_flow_statement = "cash_flow_statement"


class ProcessingMetadata(StrictModel):
    ocr_used: bool
    started_at: datetime
    completed_at: datetime
    processing_time_ms: int = Field(ge=0)
    page_count: int = Field(ge=1, le=3)
    model_id: str | None = None


class DocumentResponse(StrictModel):
    document_name: str
    document_type: DocumentType
    processing_status: str
    file_validation: FileValidation
    extracted_data: StructuredExtraction
    validation: FinancialValidation
    processing_metadata: ProcessingMetadata


class DocumentListItem(StrictModel):
    id: int
    document_name: str
    document_type: str
    processing_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody

