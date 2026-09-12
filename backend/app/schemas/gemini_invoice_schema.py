from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeminiInvoiceLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        description="Complete product or service description."
    )
    quantity: float | None = Field(
        default=None,
        description="Explicitly printed quantity; null when unavailable."
    )
    unit_price: float | None = Field(
        default=None,
        description="Explicitly printed unit price; null when unavailable."
    )
    amount: float | None = Field(
        default=None,
        description="Explicitly printed line amount; null when unavailable."
    )


class GeminiInvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = Field(
        default=None,
        description="Seller, merchant or supplier name."
    )
    vendor_address: str | None = Field(
        default=None,
        description="Seller address."
    )
    invoice_number: str | None = Field(
        default=None,
        description="Invoice, receipt or transaction number."
    )
    invoice_date: str | None = Field(
        default=None,
        description="Invoice or transaction date exactly as printed."
    )
    invoice_time: str | None = Field(
        default=None,
        description="Invoice or transaction time exactly as printed."
    )
    customer_name: str | None = Field(
        default=None,
        description="Customer name."
    )
    currency: str | None = Field(
        default=None,
        description="ISO currency code inferred from printed symbol, such as MYR."
    )
    subtotal: float | None = Field(
        default=None,
        description="Subtotal or amount before tax."
    )
    tax_amount: float | None = Field(
        default=None,
        description="Explicit total tax or GST amount."
    )
    discount: float | None = Field(
        default=None,
        description="Explicit discount amount."
    )
    total_amount: float | None = Field(
        default=None,
        description="Final invoice total or total sales."
    )
    cash_paid: float | None = Field(
        default=None,
        description="Cash tendered or amount paid."
    )
    change: float | None = Field(
        default=None,
        description="Change returned to customer."
    )
    balance_due: float | None = Field(
        default=None,
        description="Remaining balance due."
    )
    line_items: list[GeminiInvoiceLineItem] = Field(
        default_factory=list,
        description="Every visible product or service row."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Short extraction warnings; empty when none."
    )