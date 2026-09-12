from typing import Any
from pydantic import Field, field_validator
from app.schemas.common import Evidence, ExtractedField, StrictModel


class InvoiceLineItem(StrictModel):
    description: ExtractedField
    quantity: ExtractedField = Field(default_factory=ExtractedField)
    unit_price: ExtractedField = Field(default_factory=ExtractedField)
    amount: ExtractedField = Field(default_factory=ExtractedField)
    additional_fields: dict[str, ExtractedField] = Field(default_factory=dict)
    evidence: Evidence | None = None


class FinancialStatementLineItem(StrictModel):
    label: str
    category: str | None = None
    values: dict[str, float | None] = Field(default_factory=dict)
    raw_values: dict[str, str | None] = Field(default_factory=dict)
    evidence: Evidence | None = None


class StructuredExtraction(StrictModel):
    document_fields: dict[str, ExtractedField] = Field(default_factory=dict)
    periods: list[str] = Field(default_factory=list)
    invoice_line_items: list[InvoiceLineItem] = Field(default_factory=list)
    financial_line_items: list[FinancialStatementLineItem] = Field(default_factory=list)
    additional_tables: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("periods")
    @classmethod
    def unique_periods(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("periods must be unique")
        return values

