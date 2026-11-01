import json
import os
from pathlib import Path

import yaml
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.llm.prepare_fields import prepare_fields
from app.llm.llm_connection import llm_connection
from app.models import Classification, SUPPLIER_FIELDS
from app.llm.save_csv import save_result


PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts/classification.yml"


def classify_rows(rows, definitions, output_file):
    if not rows:
        return 1
    missing = set(rows[0]) - {"INCIDENT_ID"} - definitions.keys()
    if missing:
        print("Add definitions for: " + ", ".join(sorted(missing)))
        return 1
    prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
    prompt = yaml.safe_load(prompt_text)["system"]

    with llm_connection() as (client, model):
        for row in rows:
            fields = prepare_fields(row, definitions)
            try:
                result = classify_row(client, model, fields, prompt)
            except (OpenAIError, ValidationError) as error:
                save_result(output_file, row, None, type(error).__name__)
                print(f"Stopped: {type(error).__name__}. Earlier results are saved.")
                return 1
            saved = save_result(output_file, row, result)
            if not saved or result is None:
                print("Stopped. Check the saved results.")
                return 1
            print(f"Saved incident {row['INCIDENT_ID']}")
    print(f"Output: {output_file}")
    return 0


def classification_schema() -> dict:
    schema = Classification.model_json_schema()
    fields = list(schema["properties"].values())
    # Azure's schema subset omits these limits; Pydantic still validates them locally.
    for field in fields:
        variants = [field]
        variants.extend(field.get("anyOf", []))
        for variant in variants:
            for keyword in ("minLength", "minItems", "maxItems", "minimum", "maximum"):
                variant.pop(keyword, None)
    return schema


def classify_row(client: OpenAI, model: str, fields: list[dict], prompt: str) -> Classification | None:
    options = {}
    temperature = os.getenv("LLM_TEMPERATURE", "").strip()
    if temperature:
        options["temperature"] = float(temperature)

    payload = json.dumps(fields, ensure_ascii=False)
    schema = classification_schema()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": payload},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "Classification", "strict": True, "schema": schema},
        },
        max_completion_tokens=2000,
        store=False,
        **options,
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
    if result.classification == "UNCERTAIN" and result.attribution_evidence_strength > 2:
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
