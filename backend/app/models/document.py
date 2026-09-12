from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    file_validation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    extracted_data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    processing_metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
