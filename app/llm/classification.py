import json
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from app.models import Classification, SUPPLIER_FIELDS, format_citations, remove_schema_limits


PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts/classification.yml"


def classification_values(result, error=""):
    values = {name: "" for name in Classification.model_fields}
    values["processing_status"] = "failed"
    values["error"] = error or "Invalid model output"
    if result is not None:
        values.update(result.model_dump())
        values["evidence_column"] = ", ".join(result.evidence_column)
        values["citations"] = format_citations(result.citations, "Classification")
        values["processing_status"] = "success"
        values["error"] = ""
    return values


def validation_error_summary(error: ValidationError) -> str:
    details = []
    for item in error.errors(include_input=False, include_context=False, include_url=False):
        field = item["loc"][0] if item["loc"] else "response"
        if field not in Classification.model_fields:
            field = "response"
        details.append(f"{field}: {item['type']}")
    return "ValidationError: " + "; ".join(details)


def classification_schema() -> dict:
    schema = Classification.model_json_schema()
    remove_schema_limits(schema)
    return schema

def classify_row(client: OpenAI, model: str, fields: list[dict], prompt: str) -> Classification | None:
    payload = json.dumps(fields, ensure_ascii=False)
    schema = classification_schema()
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": payload},
    ]
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "Classification", "strict": True, "schema": schema},
    }
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format=response_format,
        store=False,
    )
    result = parse_response(response)
    if result is None:
        return None
    return normalize_supplier_fields(result)


def parse_response(response) -> Classification | None:
    if not response.choices:
        return None
    choice = response.choices[0]
    if choice.finish_reason != "stop":
        return None
    message = choice.message
    if message.refusal or not message.content:
        return None
    result = Classification.model_validate_json(message.content)
    score = result.attribution_evidence_strength
    if result.classification == "UNCERTAIN" and score > 2:
        return None
    if result.classification in ("HSBC", "SUPPLIER") and score == 0:
        return None

    return result


def normalize_supplier_fields(result: Classification) -> Classification:
    if result.classification != "SUPPLIER":
        for name in SUPPLIER_FIELDS:
            setattr(result, name, None)
        return result

    for name in SUPPLIER_FIELDS:
        value = getattr(result, name)
        if value and value.strip():
            continue
        if name == "supplier_more_info":
            setattr(result, name, None)
        else:
            setattr(result, name, "Unknown")
    return result
