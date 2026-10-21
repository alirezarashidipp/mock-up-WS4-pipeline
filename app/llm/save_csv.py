import json

from app.csv_files import append_record
from app.models import Classification


COLUMNS = ["INCIDENT_ID", *Classification.model_fields, "llm_input", "llm_prompt", "processing_status", "review_status", "error"]


def save_result(path, row, result, fields, prompt, error=""):
    record = dict(row)
    record.update({name: "" for name in COLUMNS if name != "INCIDENT_ID"})
    record.update(processing_status="failed", review_status="Not processed", error=error or "Invalid model output")
    record["llm_input"] = json.dumps(fields, ensure_ascii=False)
    record["llm_prompt"] = prompt
    if result is not None:
        record.update(result.model_dump())
        record["supporting_evidence"] = json.dumps(record["supporting_evidence"], ensure_ascii=False)
        record.update(processing_status="success", review_status="PENDING_REVIEW", error="")
    saved, message = append_record(path, record)
    if not saved:
        print(message)
        return {}
    return record
