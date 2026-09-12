from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.document import DocumentRecord


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_document(self, *, document_name, document_type, processing_status,
                        file_validation_json, extracted_data_json, validation_json,
                        processing_metadata_json):
        record = DocumentRecord(
            document_name=document_name, document_type=document_type,
            processing_status=processing_status,
            file_validation_json=file_validation_json,
            extracted_data_json=extracted_data_json,
            validation_json=validation_json,
            processing_metadata_json=processing_metadata_json,
        )
        try:
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            return record
        except Exception:
            self.session.rollback()
            raise

    def get_latest_by_name(self, document_name):
        statement = (select(DocumentRecord)
                     .where(DocumentRecord.document_name == document_name)
                     .order_by(DocumentRecord.created_at.desc(), DocumentRecord.id.desc())
                     .limit(1))
        return self.session.scalar(statement)

    def list_documents(self, limit=100, offset=0):
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)
        statement = (select(DocumentRecord)
                     .order_by(DocumentRecord.created_at.desc(), DocumentRecord.id.desc())
                     .offset(offset).limit(limit))
        return list(self.session.scalars(statement))

