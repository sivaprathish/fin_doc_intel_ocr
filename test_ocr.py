import logging
import os
import sys
from dotenv import load_dotenv

# Add the backend directory to the sys.path so that we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.config import Settings
from app.services.document_service import DocumentService
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentType

# Load environment variables
load_dotenv()

# Configure logging to see OCR output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Mock repository that does nothing
class MockRepository(DocumentRepository):
    def create_document(self, *args, **kwargs):
        pass

    def get_document(self, *args, **kwargs):
        return None

    def list_documents(self, *args, **kwargs):
        return []

    def update_document(self, *args, **kwargs):
        pass

    def delete_document(self, *args, **kwargs):
        pass

def main():
    # Settings
    settings = Settings()
    
    # Create service with mock repository
    service = DocumentService(
        repository=MockRepository(),
        settings=settings
    )
    
    # Read sample invoice
    invoice_path = r"sample_documents\invoices\batch1-1109.jpg"
    with open(invoice_path, "rb") as f:
        data = f.read()
    
    # Process the invoice
    log.info(f"Processing invoice: {invoice_path}")
    try:
        result = service.process(
            data=data,
            filename="batch1-1109.jpg",
            content_type="image/jpeg",
            document_type=DocumentType.INVOICE
        )
        log.info(f"Processing completed. Status: {result.processing_status}")
        # Optionally print extracted data
        # print(result.extracted_data)
    except Exception as e:
        log.error(f"Processing failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()