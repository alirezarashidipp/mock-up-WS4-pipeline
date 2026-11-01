from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SUPPLIER_FIELDS = (
    "supplier_name",
    "supplier_product_or_service",
    "supplier_action_or_failure",
    "supplier_causal_explanation",
    "supplier_accountability_reason",
    "supplier_more_info",
)


class ColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_name: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


class InputField(BaseModel):
    name: str
    description: str = Field(min_length=1)
    value: str


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_root_cause: str | None = Field(
        min_length=1, description="The documented root cause in one sentence, or null if unknown."
    )
    supporting_evidence: list[str] = Field(
        min_length=1,
        max_length=10,
        description="One to ten standardized source column names that informed the decision; names only, without quotes."
    )
    decision_rationale: str = Field(
        min_length=1, description="A short evidence-based explanation of the accountability decision."
    )
    classification: Literal["SUPPLIER", "HSBC"] = Field(
        description="The model's assessment of the party accountable for the incident, based on available evidence."
    )
    attribution_evidence_strength: int = Field(
        ge=0,
        le=4,
        strict=True,
        json_schema_extra={"enum": [0, 1, 2, 3, 4]},
        description="Recorded evidence for the selected attribution: 0 unsupported, 1 weak, 2 moderate, 3 strong, 4 very strong. Not a probability or an engagement-link score."
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
    supplier_more_info: str | None = Field(
        description="Additional recorded supplier facts not covered by the other fields; null for HSBC or when nothing else is recorded."
    )
