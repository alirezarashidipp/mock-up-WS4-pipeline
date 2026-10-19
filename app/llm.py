import json

from openai import OpenAI

from app.models import Classification


def classify_row(client: OpenAI, model: str, fields: list[dict], prompt: str) -> Classification | None:
    response = client.responses.parse(
        model=model,
        instructions=prompt,
        input=[{"role": "user", "content": json.dumps(fields, ensure_ascii=False)}],
        text_format=Classification,
        max_output_tokens=2000,
        store=False,
    )
    result = response.output_parsed
    if response.status != "completed" or result is None:
        return None
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
