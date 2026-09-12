from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.dependencies import get_document_service, get_repository
from app.core.config import Settings
from app.core.database import Base
from app.main import app
from app.models import DocumentRecord  # noqa: F401
from app.repositories.document_repository import DocumentRepository
from app.schemas.common import ExtractedField
from app.schemas.document import DocumentResponse, DocumentType
from app.schemas.extraction import FinancialStatementLineItem, InvoiceLineItem, StructuredExtraction
from app.schemas.validation import CheckStatus
from app.services.document_service import DocumentService
from app.services.financial_validation_service import FinancialValidationService
from app.services.extraction_service import ExtractionError, StructuredExtractionService


def field(value):
    return ExtractedField(value=value, raw_value=str(value) if value is not None else None)


def response_json(content, reason="stop"):
    return NS(output_text=content)


def minimal_extraction_json():
    return '{"document_fields":{},"periods":[],"invoice_line_items":[],"financial_line_items":[],"additional_tables":[],"warnings":[]}'


def minimal_invoice_json():
    return ('{"document_fields":{"invoice_number":{"value":"INV-001",'
            '"raw_value":"INV-001","evidence":{"source_text":"Invoice INV-001",'
            '"page_number":1}}},"periods":[],"invoice_line_items":[],'
            '"financial_line_items":[],"additional_tables":[],"warnings":[]}')


def test_structured_extraction_valid_and_retry():
    client = Mock()
    client.interactions.create.side_effect = [
        response_json("not json"),
        response_json(minimal_invoice_json()),
    ]
    result = StructuredExtractionService(client).extract(
        DocumentType.invoice, [{"page_number": 1, "ocr_text": "Invoice"}])
    assert result.document_fields["invoice_number"].value == "INV-001"
    assert client.interactions.create.call_count == 2


def test_empty_invoice_extraction_is_rejected_after_retries():
    client = Mock()
    client.interactions.create.return_value = response_json(minimal_extraction_json())
    with pytest.raises(ExtractionError, match="no invoice fields"):
        StructuredExtractionService(client, attempts=2).extract(
            DocumentType.invoice, [{"page_number": 1, "ocr_text": "Invoice INV-001"}])
    assert client.interactions.create.call_count == 2


def test_structured_extraction_rejects_trailing_text():
    client = Mock()
    client.interactions.create.return_value = response_json(minimal_extraction_json() + " extra")
    with pytest.raises(ExtractionError):
        StructuredExtractionService(client, attempts=1).extract(
            DocumentType.invoice, [{"page_number": 1, "ocr_text": "Invoice"}])


def test_parenthesized_value_is_normalized_before_validation():
    content = ('{"document_fields":{"subtotal":{"value":"(1,250.50)",'
               '"raw_value":"(1,250.50)","evidence":{"source_text":"Subtotal (1,250.50)","page_number":1}}},"periods":[],'
               '"invoice_line_items":[],"financial_line_items":[],'
               '"additional_tables":[],"warnings":[]}')
    client = Mock()
    client.interactions.create.return_value = response_json(content)
    result = StructuredExtractionService(client).extract(
        DocumentType.invoice, [{"page_number": 1, "ocr_text": "Subtotal (1,250.50)"}])
    assert result.document_fields["subtotal"].value == -1250.50


def test_invoice_financial_checks_pass():
    extraction = StructuredExtraction(document_fields={
        "subtotal": field(20), "tax_amount": field(2), "discount": field(1),
        "total_amount": field(21), "cash_paid": field(25), "change": field(4),
        "tax_included_in_total": field(False),
    }, invoice_line_items=[InvoiceLineItem(
        description=field("A"), quantity=field(2), unit_price=field(10), amount=field(20))])
    result = FinancialValidationService().validate(DocumentType.invoice, extraction)
    assert result.overall_status == CheckStatus.PASS
    assert all(check.status == CheckStatus.PASS for check in result.checks)


def test_invoice_missing_is_not_applicable_and_tax_included_is_safe():
    extraction = StructuredExtraction(document_fields={
        "total_amount": field(100), "tax_included_in_total": field(True)})
    result = FinancialValidationService().validate(DocumentType.invoice, extraction)
    assert result.overall_status == CheckStatus.NOT_APPLICABLE
    assert all(check.status == CheckStatus.NOT_APPLICABLE for check in result.checks)


def test_partial_line_items_are_not_summed():
    extraction = StructuredExtraction(document_fields={"subtotal": field(20)}, invoice_line_items=[
        InvoiceLineItem(description=field("A"), amount=field(20)),
        InvoiceLineItem(description=field("B"), amount=field(None)),
    ])
    result = FinancialValidationService().validate(DocumentType.invoice, extraction)
    subtotal_check = next(c for c in result.checks if c.name == "invoice_subtotal_check")
    assert subtotal_check.status == CheckStatus.NOT_APPLICABLE


def test_invoice_failure():
    extraction = StructuredExtraction(document_fields={
        "subtotal": field(20), "tax_amount": field(2), "discount": field(0),
        "total_amount": field(99), "tax_included_in_total": field(False)})
    result = FinancialValidationService().validate(DocumentType.invoice, extraction)
    assert result.overall_status == CheckStatus.FAIL


def test_balance_sheet_per_period():
    extraction = StructuredExtraction(
        periods=["2025", "2024"],
        document_fields={
            "total_assets": field({"2025": 100, "2024": 90}),
            "total_capital_and_liabilities": field({"2025": 100, "2024": 90}),
        },
        financial_line_items=[
            FinancialStatementLineItem(label="Cash", category="asset_component", values={"2025": 40, "2024": 30}),
            FinancialStatementLineItem(label="Other assets", category="asset_component", values={"2025": 60, "2024": 60}),
            FinancialStatementLineItem(label="Equity", category="capital_liability_component", values={"2025": 70, "2024": 65}),
            FinancialStatementLineItem(label="Liabilities", category="capital_liability_component", values={"2025": 30, "2024": 25}),
        ])
    result = FinancialValidationService().validate(DocumentType.balance_sheet, extraction)
    assert len(result.checks) == 6
    assert result.overall_status == CheckStatus.PASS


def test_profit_and_loss_per_period():
    values = {
        "interest_earned": 80, "other_income": 20, "total_income": 100,
        "interest_expended": 30, "operating_expenses": 20,
        "provisions_and_contingencies": 10, "total_expenditure": 60,
        "consolidated_net_profit_before_minority_interest": 40,
        "minority_interest": 5, "consolidated_net_profit_attributable_to_group": 35,
        "current_profit": 35, "brought_forward_profit": 10,
        "total_available_for_appropriation": 45,
    }
    extraction = StructuredExtraction(periods=["2025"],
        document_fields={key: field({"2025": value}) for key, value in values.items()})
    result = FinancialValidationService().validate(DocumentType.profit_and_loss, extraction)
    assert len(result.checks) == 5
    assert result.overall_status == CheckStatus.PASS


def test_cash_flow_negative_values():
    values = {
        "operating_cash_flow": 100, "investing_cash_flow": -30,
        "financing_cash_flow": -10, "fx_translation_adjustment": -5,
        "net_increase_in_cash": 55, "opening_cash": 20,
        "cash_acquired_on_amalgamation": 2, "other_cash_adjustments": 3,
        "closing_cash": 80,
    }
    extraction = StructuredExtraction(periods=["2025"],
        document_fields={key: field({"2025": value}) for key, value in values.items()})
    result = FinancialValidationService().validate(DocumentType.cash_flow_statement, extraction)
    assert result.overall_status == CheckStatus.PASS


@pytest.fixture
def repository():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield DocumentRepository(session)


def record_payload(name="same.pdf", status="PASS"):
    now = datetime.now(timezone.utc).isoformat()
    return dict(document_name=name, document_type="invoice", processing_status=status,
        file_validation_json={"file_type": "application/pdf", "is_supported": True,
                              "is_readable": True, "page_count": 1, "status": "PASS"},
        extracted_data_json={"document_fields": {}, "periods": [], "invoice_line_items": [],
                             "financial_line_items": [], "additional_tables": [], "warnings": []},
        validation_json={"checks": [], "overall_status": "NOT_APPLICABLE", "issues": []},
        processing_metadata_json={"ocr_used": True, "started_at": now, "completed_at": now,
                                  "processing_time_ms": 1, "page_count": 1, "model_id": "mock"})


def test_repository_keeps_versions_and_latest(repository):
    first = repository.create_document(**record_payload(status="PASS"))
    second = repository.create_document(**record_payload(status="FAILED"))
    assert first.id != second.id
    assert repository.get_latest_by_name("same.pdf").id == second.id
    assert len(repository.list_documents()) == 2


def test_document_workflow(repository):
    validator = Mock()
    validator.validate.return_value = {"file_type": "application/pdf", "is_supported": True,
        "is_readable": True, "page_count": 1, "status": "PASS"}
    converter = Mock()
    converter.convert.return_value = [{"page_number": 1, "native_text": "Invoice", "image_bytes": b"png"}]
    ocr = Mock()
    ocr.transcribe.return_value = [{"page_number": 1, "ocr_text": "Invoice", "native_text": "Invoice"}]
    extractor = Mock()
    extractor.extract.return_value = StructuredExtraction(
        document_fields={"invoice_number": field("INV-001")},
    )
    settings = Settings(gemini_api_key="x", gemini_model="mock")
    service = DocumentService(repository, settings, validator=validator, converter=converter,
                              ocr=ocr, extractor=extractor)
    result = service.process(b"pdf", "folder/invoice.pdf", "application/pdf", DocumentType.invoice)
    assert result.document_name == "invoice.pdf"
    assert repository.get_latest_by_name("invoice.pdf") is not None


def test_api_health_list_latest_and_process(repository):
    app.dependency_overrides[get_repository] = lambda: repository
    mock_service = Mock()
    saved = repository.create_document(**record_payload("api.pdf"))
    expected = DocumentService.record_to_response(saved)
    mock_service.process.return_value = expected
    app.dependency_overrides[get_document_service] = lambda: mock_service
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/health").status_code == 200
            assert client.get("/api/v1/documents").json()[0]["document_name"] == "api.pdf"
            assert client.get("/api/v1/documents/api.pdf").status_code == 200
            assert client.get("/api/v1/documents/missing.pdf").status_code == 404
            processed = client.post("/api/v1/documents/process",
                files={"file": ("api.pdf", b"%PDF-test", "application/pdf")},
                data={"document_type": "invoice"})
            assert processed.status_code == 200
    finally:
        app.dependency_overrides.clear()
