"""Shared model contracts and flat output defaults; no file or provider calls."""

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
CLASSIFICATION_CONTEXT_FIELDS = (
    "incident_country",
    "supplier_country",
    "causing_party",
    "affected_party",
    "resolving_party",
)


class InputField(BaseModel):
    name: str
    description: str = Field(min_length=1)
    value: str


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_root_cause: str | None = Field(
        min_length=1, description="The documented root cause in one sentence, or null if unknown."
    )
    evidence_column: list[str] = Field(
        description="Standardized source column names that informed the decision; names only, without source excerpts. An empty list is allowed; no fixed maximum count."
    )
    citations: list[str] = Field(
        description="Short excerpts from supplied source values, labeled with their source column. An empty list is allowed."
    )
    decision_rationale: str = Field(
        min_length=1, description="A short evidence-based explanation of the accountability decision."
    )
    classification: Literal["HSBC", "SUPPLIER", "UNCERTAIN"] = Field(
        description="HSBC or SUPPLIER when the evidence supports attribution; UNCERTAIN when responsibility cannot be determined."
    )
    attribution_evidence_strength: int = Field(
        ge=0,
        le=4,
        strict=True,
        json_schema_extra={"enum": [0, 1, 2, 3, 4]},
        description="Evidence for attributing responsibility: 0 unsupported, 1 weak, 2 moderate, 3 strong, 4 very strong. For UNCERTAIN use 0-2, not confidence in uncertainty. Not a probability."
    )
    supplier_name: str | None = Field(
        description="For SUPPLIER, the documented base supplier name (for example AXA), without legal-entity or country suffixes when the base name is clear, or Unknown; otherwise null."
    )
    supplier_product_or_service: str | None = Field(
        description="For SUPPLIER, the related product, service, or infrastructure recorded, or Unknown; otherwise null."
    )
    supplier_action_or_failure: str | None = Field(
        description="For SUPPLIER, the recorded action, defect, or omission, or Unknown; otherwise null."
    )
    supplier_causal_explanation: str | None = Field(
        description="For SUPPLIER, how the recorded supplier action caused the incident or impact, or Unknown; otherwise null."
    )
    supplier_accountability_reason: str | None = Field(
        description="For SUPPLIER, why the record supports assigning responsibility to this actor, or Unknown; otherwise null."
    )
    supplier_more_info: str | None = Field(
        description="For SUPPLIER, additional recorded facts not covered by the other fields; null for other classifications or when nothing else is recorded."
    )
    incident_country: str | None = Field(
        description="Documented country of the incident or affected service, not the supplier's headquarters. Use an unambiguous English country name; separate multiple documented countries with semicolons. Null when absent or conflicting."
    )
    supplier_country: str | None = Field(
        description="For SUPPLIER, the documented country of the involved supplier entity or service operation, not automatically the incident country or global headquarters. Use English country names separated by semicolons when multiple are documented. Otherwise null."
    )
    causing_party: str | None = Field(
        description="Actor explicitly documented as causing the incident; null when absent or conflicting. Affected or resolving actors are not automatically the cause. Separate documented joint actors with semicolons."
    )
    affected_party: str | None = Field(
        description="Actor or group explicitly documented as affected by the incident; null when absent or conflicting. Being affected does not establish accountability. Separate multiple documented actors with semicolons."
    )
    resolving_party: str | None = Field(
        description="Actor explicitly documented as restoring service or resolving the incident; null when absent or conflicting. Resolution does not establish who caused the incident. Separate multiple documented actors with semicolons."
    )


class LinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_name: str
    incident: dict[str, str]
    engagements: list[dict[str, str]]


class EngagementSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engagement_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_strength: int = Field(
        ge=1,
        le=4,
        strict=True,
        json_schema_extra={"enum": [1, 2, 3, 4]},
        description="Recorded support: 1 weak, 2 moderate, 3 strong, 4 very strong. Not a probability.",
    )


class EngagementSuggestions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[EngagementSuggestion] = Field(max_length=5)
    selected_engagement_id: str | None
    reason: str = Field(min_length=1)
    citations: list[str] = Field(
        description="Short source excerpts labeled INCIDENT.column or ENGAGEMENT_ID.column, from original values rather than earlier model summaries. An empty list is allowed."
    )


def empty_link(supplier_name="", status="PENDING", reason=""):
    result = {
        "link_supplier_name": supplier_name,
        "link_status": status,
        "linked_engagement_id": "",
        "link_reason": reason,
        "link_confidence": "",
        "link_match_count": "",
        "link_candidate_count": "",
        "link_suggestion_count": "",
        "link_error": "",
        "link_catalog_hash": "",
        "citations": "",
    }
    for number in range(1, 6):
        result[f"link_{number}_engagement_id"] = ""
        result[f"link_{number}_reason"] = ""
        result[f"link_{number}_evidence_strength"] = ""
    return result


def format_citations(citations, stage):
    """Label every line so one CSV cell can keep the two model stages separate."""
    lines = []
    for citation in citations:
        for line in citation.splitlines():
            lines.append(f"{stage}: {line}")
    return "\n".join(lines)


def remove_schema_limits(value):
    # Azure accepts the structure; Pydantic still enforces every limit locally.
    if isinstance(value, dict):
        for keyword in ("minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum"):
            value.pop(keyword, None)
        for child in value.values():
            remove_schema_limits(child)
    elif isinstance(value, list):
        for child in value:
            remove_schema_limits(child)
