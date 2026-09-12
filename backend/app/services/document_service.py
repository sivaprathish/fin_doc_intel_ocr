import logging
from datetime import datetime, timezone
from app.core.config import Settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentResponse, DocumentType, ProcessingMetadata
from app.services.financial_validation_service import FinancialValidationService
from app.services.extraction_service import ExtractionError, StructuredExtractionService
from app.services.file_validation_service import FileValidationService
from app.services.image_conversion_service import ImageConversionService
from app.services.paddle_ocr_service import PaddleOCRService
from app.utils.file_utils import safe_document_name

log = logging.getLogger(__name__)


def validate_required_extraction(document_type, extraction):
    type_name = getattr(document_type, "value", str(document_type))

    if type_name == "balance_sheet":
        if not extraction.periods:
            raise ExtractionError("Balance-sheet periods were not extracted.")
        if not extraction.financial_line_items:
            raise ExtractionError("Balance-sheet financial rows were not extracted.")

    if type_name == "invoice":
        if not extraction.document_fields and not extraction.invoice_line_items:
            raise ExtractionError("No invoice fields or line items were extracted.")


class DocumentService:
    def __init__(self, repository: DocumentRepository, settings: Settings,
                 validator=None, converter=None, ocr=None, extractor=None, financial=None):
        self.repository = repository
        self.settings = settings
        self.validator = validator or FileValidationService(
            max_pages=settings.max_page_count, max_bytes=settings.max_file_bytes)
        self.converter = converter or ImageConversionService(self.validator)
        self.ocr = ocr or PaddleOCRService()
        self.extractor = extractor or StructuredExtractionService(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            attempts=2,
        )
        self.financial = financial or FinancialValidationService(
            settings.financial_abs_tolerance, settings.financial_rel_tolerance)

    def process(self, data: bytes, filename: str, content_type: str | None,
                document_type: DocumentType):
        started = datetime.now(timezone.utc)
        safe_name = safe_document_name(filename)
        log.info("Processing started document=%s type=%s", safe_name, document_type.value)
        validation_dict = self.validator.validate(data, safe_name, content_type)
        pages = self.converter.convert(data, safe_name, content_type)
        ocr_pages = self.ocr.transcribe(pages)
        for page in ocr_pages:
            log.info(
                "OCR OUTPUT page=%s:\n%s",
                page["page_number"],
                page["ocr_text"],
            )
        extraction = self.extractor.extract(document_type, ocr_pages)
        if document_type.value == "invoice":
            self._validate_invoice_completeness(extraction)
        validate_required_extraction(document_type, extraction)
        financial_result = self.financial.validate(document_type, extraction)
        completed = datetime.now(timezone.utc)
        metadata = ProcessingMetadata(
            ocr_used=True, started_at=started, completed_at=completed,
            processing_time_ms=max(0, int((completed - started).total_seconds() * 1000)),
            page_count=len(pages), model_id=self.settings.gemini_model)
        response = DocumentResponse(
            document_name=safe_name, document_type=document_type, processing_status="PASS",
            file_validation=validation_dict, extracted_data=extraction,
            validation=financial_result, processing_metadata=metadata)
        payload = response.model_dump(mode="json")
        self.repository.create_document(
            document_name=safe_name, document_type=document_type.value,
            processing_status=response.processing_status,
            file_validation_json=payload["file_validation"],
            extracted_data_json=payload["extracted_data"],
            validation_json=payload["validation"],
            processing_metadata_json=payload["processing_metadata"])
        log.info("Processing completed document=%s duration_ms=%s",
                 safe_name, metadata.processing_time_ms)
        return response

    @staticmethod
    def record_to_response(record):
        return DocumentResponse.model_validate({
            "document_name": record.document_name,
            "document_type": record.document_type,
            "processing_status": record.processing_status,
            "file_validation": record.file_validation_json,
            "extracted_data": record.extracted_data_json,
            "validation": record.validation_json,
            "processing_metadata": record.processing_metadata_json,
        })

    @staticmethod
    def _field_value(extraction, field_name: str):
        field = extraction.document_fields.get(field_name)

        if field is None:
            return None

        return getattr(field, "value", None)

    @classmethod
    def _validate_invoice_completeness(cls, extraction) -> None:
        core_fields = [
            cls._field_value(extraction, "invoice_number"),
            cls._field_value(extraction, "vendor_name"),
            cls._field_value(extraction, "invoice_date"),
        ]

        has_core_field = any(
            value not in (None, "")
            for value in core_fields
        )

        if not has_core_field:
            raise ExtractionError(
                "Invoice extraction contains no usable header fields."
            )
