import json
import os

from openai import OpenAI

from app.models import Classification


def classification_schema() -> dict:
    schema = Classification.model_json_schema()
    fields = list(schema["properties"].values()) + list(schema["$defs"]["Evidence"]["properties"].values())
    # Azure's schema subset omits these limits; Pydantic still validates them locally.
    for field in fields:
        for variant in [field, *field.get("anyOf", [])]:
            for keyword in ("minLength", "maxItems", "minimum", "maximum"):
                variant.pop(keyword, None)
    return schema


def classify_row(client: OpenAI, model: str, fields: list[dict], prompt: str) -> Classification | None:
    options = {}
    temperature = os.getenv("LLM_TEMPERATURE", "").strip()
    if temperature:
        value = float(temperature)
        if not 0 <= value <= 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2.")
        options["temperature"] = value

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(fields, ensure_ascii=False)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "Classification", "strict": True, "schema": classification_schema()},
        },
        max_completion_tokens=2000,
        store=False,
        **options,
    )
    if not response.choices:
        return None
    choice = response.choices[0]
    if choice.finish_reason != "stop" or choice.message.refusal or not choice.message.content:
        return None
    result = Classification.model_validate_json(choice.message.content)
    if result.classification != "UNDECIDED" and not result.supporting_evidence:
        return None
    if result.classification == "UNDECIDED" and not (result.uncertainty_reason or "").strip():
        return None
    if result.classification != "UNDECIDED" and result.uncertainty_reason is not None:
        return None

    values = {field["name"]: field["value"] for field in fields}
    for evidence in result.supporting_evidence:
        if not evidence.quote.strip() or evidence.quote not in values.get(evidence.column, ""):
            return None
    return result
