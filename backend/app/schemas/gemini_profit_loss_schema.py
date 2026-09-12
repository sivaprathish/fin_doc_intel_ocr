from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeminiPeriodValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str = Field(
        description="Period heading exactly as printed, such as 31-Mar-18."
    )
    value: float | None = Field(
        description=(
            "Numeric value for this period. Parentheses represent negative values. "
            "Null only when no value is printed."
        )
    )
    raw_value: str | None = Field(
        description=(
            "Value exactly as printed, including commas or parentheses."
        )
    )


class GeminiFinancialLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str = Field(
        description=(
            "Statement section such as INCOME, EXPENDITURE, PROFIT, "
            "APPROPRIATIONS or EARNINGS_PER_SHARE."
        )
    )
    label: str = Field(
        description="Financial line-item label exactly as printed."
    )
    schedule: str | None = Field(
        default=None,
        description="Schedule or note number when printed.",
    )
    values: list[GeminiPeriodValue] = Field(
        description="One value for each visible reporting period."
    )


class GeminiProfitLossExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_name: str | None = Field(
        default=None,
        description="Company or reporting entity name.",
    )
    statement_title: str | None = Field(
        default=None,
        description="Financial statement title.",
    )
    reporting_date: str | None = Field(
        default=None,
        description="Reporting date or year-end heading.",
    )
    currency: str | None = Field(
        default=None,
        description="ISO currency code, such as INR.",
    )
    unit: str | None = Field(
        default=None,
        description="Printed scale such as thousands, millions or crores.",
    )
    periods: list[str] = Field(
        default_factory=list,
        description="Reporting periods in displayed order.",
    )
    line_items: list[GeminiFinancialLineItem] = Field(
        default_factory=list,
        description="Every financial line item with its values for every period.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Short extraction warnings; empty when none.",
    )
