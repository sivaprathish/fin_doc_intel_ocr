from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from app.api.dependencies import get_document_service, get_repository
from app.core.config import get_settings
from app.schemas.document import DocumentListItem, DocumentResponse, DocumentType

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/process", response_model=DocumentResponse)
async def process_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    service=Depends(get_document_service),
):
    settings = get_settings()
    data = await file.read(settings.max_file_bytes + 1)
    try:
        return service.process(data, file.filename or "", file.content_type, document_type)
    finally:
        await file.close()


@router.get("", response_model=list[DocumentListItem])
def list_documents(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repository=Depends(get_repository),
):
    return repository.list_documents(limit=limit, offset=offset)


@router.get("/{document_name}", response_model=DocumentResponse)
def get_document(document_name: str, repository=Depends(get_repository)):
    record = repository.get_latest_by_name(document_name)
    if not record:
        raise HTTPException(status_code=404, detail={
            "code": "DOCUMENT_NOT_FOUND", "message": "No processed document was found with that name."})
    from app.services.document_service import DocumentService
    return DocumentService.record_to_response(record)

