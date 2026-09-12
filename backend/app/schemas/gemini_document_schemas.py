from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeminiStrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


# ============================================================
# Invoice schemas
# ============================================================


class GeminiInvoiceLineItem(GeminiStrictModel):
    description: str | None = Field(
        description="Complete product or service description."
    )
    quantity: float | None = Field(
        description="Printed quantity; null when unavailable."
    )
    unit_price: float | None = Field(
        description="Printed unit price; null when unavailable."
    )
    amount: float | None = Field(
        description="Printed line amount; null when unavailable."
    )


class GeminiInvoiceExtraction(GeminiStrictModel):
    vendor_name: str | None
    vendor_address: str | None
    invoice_number: str | None
    invoice_date: str | None
    invoice_time: str | None
    customer_name: str | None
    currency: str | None
    subtotal: float | None
    tax_amount: float | None
    discount: float | None
    total_amount: float | None
    cash_paid: float | None
    change: float | None
    balance_due: float | None

    line_items: list[GeminiInvoiceLineItem] = Field(
        description="Every visible invoice product or service row."
    )

    warnings: list[str]


# ============================================================
# Financial-statement schemas
# ============================================================


class GeminiPeriodValue(GeminiStrictModel):
    period: str = Field(
        description=(
            "Reporting period exactly as printed, "
            "such as 31-Mar-17."
        )
    )
    value: float | None = Field(
        description=(
            "Normalized numeric value. Numbers in parentheses "
            "must be negative. Null only when no value is printed."
        )
    )
    raw_value: str | None = Field(
        description=(
            "Value exactly as printed, including commas, "
            "decimal points and parentheses."
        )
    )


class GeminiStatementLineItem(GeminiStrictModel):
    label: str = Field(
        description="Financial line-item label exactly as printed."
    )
    category: str = Field(
        description="Normalized financial-statement category."
    )
    values: list[GeminiPeriodValue] = Field(
        min_length=1,
        description=(
            "One value object for each displayed reporting period."
        ),
    )


class GeminiStatementExtraction(GeminiStrictModel):
    entity_name: str | None
    statement_title: str
    reporting_date: str | None
    currency: str | None
    unit: str | None

    periods: list[str] = Field(
        min_length=1,
        description="Reporting periods in displayed order.",
    )

    line_items: list[GeminiStatementLineItem] = Field(
        min_length=1,
        description="Every visible financial line item.",
    )

    warnings: list[str]


class GeminiBalanceSheetExtraction(GeminiStatementExtraction):
    """Structured Gemini output for balance sheets."""


class GeminiProfitLossExtraction(GeminiStatementExtraction):
    pass


class GeminiCashFlowExtraction(GeminiStatementExtraction):
    """Structured Gemini output for cash-flow statements."""
