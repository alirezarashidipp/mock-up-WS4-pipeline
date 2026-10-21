import json
import os
from pathlib import Path

import yaml
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.data_preparation.prepare_fields import prepare_fields
from app.llm.llm_connection import llm_connection
from app.models import Classification
from app.llm.save_csv import save_result


def classify_rows(rows, definitions, output_file):
    if not rows:
        return 1
    if any(path.exists() for path in (output_file, output_file.parent / "FINAL.csv")):
        print("Batch files already exist. Choose a new output folder to preserve earlier results.")
        return 1
    missing = set(rows[0]) - {"INCIDENT_ID"} - definitions.keys()
    if missing:
        print("Add definitions for: " + ", ".join(sorted(missing)))
        return 1
    prompt_file = Path(__file__).resolve().parents[2] / "prompts/classification.yml"
    prompt = yaml.safe_load(prompt_file.read_text(encoding="utf-8"))["system"]

    with llm_connection() as (client, model):
        for row in rows:
            fields = prepare_fields(row, definitions)
            try:
                result = classify_row(client, model, fields, prompt)
            except (OpenAIError, ValidationError) as error:
                save_result(output_file, row, None, fields, prompt, type(error).__name__)
                print(f"Stopped: {type(error).__name__}. Earlier results are saved.")
                return 1
            saved = save_result(output_file, row, result, fields, prompt)
            if not saved or result is None:
                print("Stopped. Check the saved results.")
                return 1
            print(f"Saved incident {row['INCIDENT_ID']}")
    print(f"Output: {output_file}")
    return 0


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
