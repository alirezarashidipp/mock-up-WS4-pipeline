from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ColumnDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_name: str = Field(min_length=1)
    new_name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class InputField(BaseModel):
    name: str
    description: str = Field(min_length=1)
    value: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: Literal["SUPPLIER", "HSBC", "UNDECIDED"] = Field(
        description="The party accountable for the incident, or UNDECIDED when attribution is unsupported."
    )
    key_root_cause: str | None = Field(
        min_length=1, description="The documented root cause in one sentence, or null if unknown."
    )
    decision_rationale: str = Field(
        min_length=1, description="A short evidence-based explanation of the accountability decision."
    )
    supporting_evidence: list[Evidence] = Field(
        max_length=5, description="Up to five exact input quotes supporting the decision, including material counterevidence."
    )
    llm_confidence: int = Field(
        ge=0, le=100, description="Self-reported confidence in the selected label from 0 to 100, not measured accuracy."
    )
    uncertainty_reason: str | None = Field(
        min_length=1, description="What prevents attribution for UNDECIDED; null for SUPPLIER or HSBC."
    )
