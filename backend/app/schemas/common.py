from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    source_text: str | None = None
    page_number: int | None = Field(default=None, ge=1, le=3)


class ExtractedField(StrictModel):
    value: Any = None
    raw_value: str | None = None
    evidence: Evidence | None = None

