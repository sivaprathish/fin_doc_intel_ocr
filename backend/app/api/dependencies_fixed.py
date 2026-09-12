from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService
from app.services.extraction_service import StructuredExtractionService
from app.services.financial_validation_service import FinancialValidationService
from app.services.image_conversion_service import ImageConversionService
from app.services.file_validation_service import FileValidationService
from app.services.paddle_ocr_service import PaddleOCRService


def get_repository(db: Session = Depends(get_db)):
    return DocumentRepository(db)


@lru_cache
def get_paddle_ocr_service():
    return PaddleOCRService()


@lru_cache
def get_extraction_service():
    settings = get_settings()
    return StructuredExtractionService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        attempts=2,
    )


@lru_cache
def get_financial_validation_service():
    settings = get_settings()
    return FinancialValidationService(
        settings.financial_abs_tolerance, settings.financial_rel_tolerance
    )


@lru_cache
def get_file_validation_service():
    settings = get_settings()
    return FileValidationService(
        max_pages=settings.max_page_count, max_bytes=settings.max_file_bytes
    )


@lru_cache
def get_image_conversion_service():
    validator = get_file_validation_service()
    return ImageConversionService(validator)


def get_document_service(
    repository: DocumentRepository = Depends(get_repository),
    paddle_ocr: PaddleOCRService = Depends(get_paddle_ocr_service),
    extractor: StructuredExtractionService = Depends(get_extraction_service),
    financial: FinancialValidationService = Depends(get_financial_validation_service),
    validator: FileValidationService = Depends(get_file_validation_service),
    converter: ImageConversionService = Depends(get_image_conversion_service),
):
    return DocumentService(
        repository=repository,
        settings=get_settings(),
        validator=validator,
        converter=converter,
        ocr=paddle_ocr,
        extractor=extractor,
        financial=financial,
    )