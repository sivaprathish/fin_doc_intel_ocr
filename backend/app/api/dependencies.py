from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.repositories.document_repository import DocumentRepository


def get_repository(db: Session = Depends(get_db)):
    return DocumentRepository(db)


def get_document_service(repository=Depends(get_repository)):
    # Created lazily so health/list/retrieve still work if HF is temporarily unconfigured.
    from app.services.document_service import DocumentService
    return DocumentService(repository, get_settings())
