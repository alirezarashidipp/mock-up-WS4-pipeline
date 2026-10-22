from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SUPPLIER_FIELDS = (
    "supplier_name",
    "supplier_product_or_service",
    "supplier_action_or_failure",
    "supplier_causal_explanation",
    "supplier_accountability_reason",
)


class ColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_name: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


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

    classification: Literal["SUPPLIER", "HSBC"] = Field(
        description="The model's assessment of the party accountable for the incident, based on available evidence."
    )
    key_root_cause: str | None = Field(
        min_length=1, description="The documented root cause in one sentence, or null if unknown."
    )
    decision_rationale: str = Field(
        min_length=1, description="A short evidence-based explanation of the accountability decision."
    )
    supporting_evidence: list[Evidence] = Field(
        description="Evidence supporting the decision, including material counterevidence."
    )
    llm_confidence: int = Field(
        ge=0, le=100, description="Self-reported confidence in the selected label from 0 to 100, not measured accuracy."
    )
    supplier_name: str | None = Field(
        description="For SUPPLIER, the responsible supplier or actor named in the record, or Unknown; null for HSBC."
    )
    supplier_product_or_service: str | None = Field(
        description="For SUPPLIER, the related product, service, or infrastructure recorded, or Unknown; null for HSBC."
    )
    supplier_action_or_failure: str | None = Field(
        description="For SUPPLIER, the recorded action, defect, or omission, or Unknown; null for HSBC."
    )
    supplier_causal_explanation: str | None = Field(
        description="For SUPPLIER, how the recorded supplier action caused the incident or impact, or Unknown; null for HSBC."
    )
    supplier_accountability_reason: str | None = Field(
        description="For SUPPLIER, why the record supports assigning responsibility to this actor, or Unknown; null for HSBC."
    )
