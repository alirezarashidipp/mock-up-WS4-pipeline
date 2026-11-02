import csv
import hashlib
import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.llm_connection import llm_connection
from app.linking.candidates import find_candidates


ROOT = Path(__file__).resolve().parents[2]
PROMPT_FILE = ROOT / "prompts" / "linking.yml"
NAME_COLUMNS = ("THIRD_PARTY_NAME", "THIRD_PARTY_NORMALISED_NAME")


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


def load_max_candidates():
    load_dotenv(ROOT / ".env")
    try:
        limit = int(os.getenv("LINK_MAX_CANDIDATES", "70"))
    except ValueError:
        raise ValueError("LINK_MAX_CANDIDATES must be a positive integer.") from None
    if limit < 1:
        raise ValueError("LINK_MAX_CANDIDATES must be a positive integer.")
    return limit


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
    }
    for number in range(1, 6):
        result[f"link_{number}_engagement_id"] = ""
        result[f"link_{number}_reason"] = ""
        result[f"link_{number}_evidence_strength"] = ""
    return result


def validate_engagements(engagements):
    seen_ids = set()
    if engagements and not isinstance(engagements[0], dict):
        raise ValueError("Engagement rows must be dictionaries.")
    expected_columns = set(engagements[0]) if engagements else set()
    if any(not isinstance(name, str) or not name.strip() for name in expected_columns):
        raise ValueError("Engagement column names must be nonblank text.")
    for row in engagements:
        if not isinstance(row, dict) or set(row) != expected_columns:
            raise ValueError("Engagement rows must have consistent columns.")
        if "ENGAGEMENT_ID" not in row or not set(NAME_COLUMNS).intersection(row):
            raise ValueError("Engagements need ENGAGEMENT_ID and a supplier name column.")
        if any(not isinstance(value, str) for value in row.values()):
            raise ValueError("Engagement fields must contain text.")
        engagement_id = row["ENGAGEMENT_ID"]
        if not engagement_id.strip() or engagement_id in seen_ids:
            raise ValueError("Engagement IDs must be nonblank and unique.")
        seen_ids.add(engagement_id)


def read_engagements(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []
        if not columns or any(not name.strip() for name in columns) or len(columns) != len(set(columns)):
            raise ValueError("ENG_ALL.csv needs nonblank, unique column names.")
        if "ENGAGEMENT_ID" not in columns or not set(NAME_COLUMNS).intersection(columns):
            raise ValueError("ENG_ALL.csv needs ENGAGEMENT_ID and a supplier name column.")
        rows = list(reader)
    validate_engagements(rows)
    return rows


def catalog_hash(engagements):
    content = json.dumps(engagements, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def response_schema():
    schema = EngagementSuggestions.model_json_schema()
    remove_schema_limits(schema)
    return schema


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


def incident_context(incident):
    fields = {}
    for name, value in incident.items():
        if name in ("INCIDENT_ID", "linked_engagement_id", "processing_status", "error", "row_revision"):
            continue
        if name.startswith(("link_", "hitl_", "review_", "reviewed_", "classification_review_", "supplier_review_", "engagement_review_", "workflow_", "ENG_")):
            continue
        fields[name] = "" if value is None else str(value)
    return fields


def validate_suggestions(result, candidates):
    if not result.reason.strip():
        raise ValueError("The linking decision requires a reason.")
    candidate_ids = {row["ENGAGEMENT_ID"] for row in candidates}
    suggestion_ids = set()
    for suggestion in result.suggestions:
        if suggestion.engagement_id not in candidate_ids or suggestion.engagement_id in suggestion_ids:
            raise ValueError("Each suggestion must identify a different supplied candidate.")
        if not suggestion.reason.strip():
            raise ValueError("Every engagement suggestion requires a reason.")
        suggestion_ids.add(suggestion.engagement_id)
    if not result.suggestions:
        if result.selected_engagement_id is not None:
            raise ValueError("An empty suggestion list cannot have a selected engagement.")
        return
    if result.selected_engagement_id not in suggestion_ids:
        raise ValueError("The selected engagement must be one of the suggestions.")
    strongest_score = max(suggestion.evidence_strength for suggestion in result.suggestions)
    selected = next(suggestion for suggestion in result.suggestions if suggestion.engagement_id == result.selected_engagement_id)
    if selected.evidence_strength != strongest_score:
        raise ValueError("The default engagement must have the strongest evidence score.")


def request_suggestions(incident, candidates, supplier_name):
    instructions = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    if not isinstance(instructions, dict) or not isinstance(instructions.get("system"), str):
        raise ValueError("The linking prompt needs system instructions.")
    payload = LinkInput(supplier_name=supplier_name, incident=incident_context(incident), engagements=candidates)
    messages = [
        {"role": "system", "content": instructions["system"]},
        {"role": "user", "content": "<link_request>\n" + payload.model_dump_json() + "\n</link_request>"},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "EngagementSuggestions", "strict": True, "schema": response_schema()},
    }
    with llm_connection() as (client, model):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=response_format,
            store=False,
        )
    if not response.choices:
        raise ValueError("The linking response was empty.")
    choice = response.choices[0]
    if choice.finish_reason != "stop" or choice.message.refusal or not choice.message.content:
        raise ValueError("The linking response was refused, empty, or incomplete.")
    result = EngagementSuggestions.model_validate_json(choice.message.content)
    validate_suggestions(result, candidates)
    return result


def find_engagements(incident, engagements, supplier_name, max_candidates=70):
    """Search, request up to five suggestions, and return flat fields without saving."""
    link = empty_link(supplier_name)
    try:
        if type(max_candidates) is not int or max_candidates < 1:
            raise ValueError("max_candidates must be a positive integer.")
        validate_engagements(engagements)
        link["link_catalog_hash"] = catalog_hash(engagements)
        matches = find_candidates(supplier_name, engagements, max_candidates=None)
        candidates = matches[:max_candidates]
        link["link_match_count"] = len(matches)
        link["link_candidate_count"] = len(candidates)
        link["link_suggestion_count"] = 0
        if not candidates:
            link["link_status"] = "NO_MATCH"
            link["link_reason"] = "No engagement supplier names match the supplied base name."
            return link
        result = request_suggestions(incident, candidates, supplier_name)
    except (OpenAIError, ValidationError, ValueError, OSError, yaml.YAMLError) as error:
        link["link_status"] = "FAILED"
        link["link_reason"] = "Engagement suggestions could not be prepared. Check link_error."
        link["link_error"] = type(error).__name__
        return link

    link["link_reason"] = result.reason
    link["link_suggestion_count"] = len(result.suggestions)
    link["link_status"] = "READY" if result.suggestions else "NO_MATCH"
    link["linked_engagement_id"] = result.selected_engagement_id or ""
    link["link_confidence"] = 0
    for number, suggestion in enumerate(result.suggestions, start=1):
        link[f"link_{number}_engagement_id"] = suggestion.engagement_id
        link[f"link_{number}_reason"] = suggestion.reason
        link[f"link_{number}_evidence_strength"] = suggestion.evidence_strength
        if suggestion.engagement_id == result.selected_engagement_id:
            link["link_confidence"] = suggestion.evidence_strength
    return link
