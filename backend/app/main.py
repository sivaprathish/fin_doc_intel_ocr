import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.database import Base, engine
from app.models import DocumentRecord  # noqa: F401: registers table metadata
from app.services.extraction_service import ExtractionError
from app.services.file_validation_service import DocumentError

configure_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])
app.include_router(health_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")


@app.exception_handler(DocumentError)
async def document_error_handler(_request: Request, exc: DocumentError):
    statuses = {"UNSUPPORTED_FILE_TYPE": 415, "FILE_TYPE_MISMATCH": 415,
                "MIME_TYPE_MISMATCH": 415, "FILE_TOO_LARGE": 413,
                "PAGE_LIMIT_EXCEEDED": 400, "OCR_SERVICE_FAILED": 502}
    return JSONResponse(status_code=statuses.get(exc.code, 400), content=exc.as_dict())


@app.exception_handler(ExtractionError)
async def extraction_error_handler(_request: Request, exc: ExtractionError):
    log.error("Structured extraction failed: %s", exc)

    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "code": "STRUCTURED_EXTRACTION_FAILED",
                "message": str(exc),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {
        "code": "REQUEST_VALIDATION_FAILED",
        "message": "The request fields or document_type are invalid."}})


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {
        "code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request: Request, _exc: SQLAlchemyError):
    log.exception("Database operation failed")
    return JSONResponse(status_code=503, content={"error": {
        "code": "DATABASE_UNAVAILABLE", "message": "The persistence service is unavailable."}})


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, _exc: Exception):
    log.exception("Unexpected request failure")
    return JSONResponse(status_code=500, content={"error": {
        "code": "INTERNAL_ERROR", "message": "An unexpected processing error occurred."}})
