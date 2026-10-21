from app.csv_files import append_record
from app.models import Classification


RESULT_COLUMNS = [name for name in Classification.model_fields if name != "supporting_evidence"]
EVIDENCE_COLUMNS = []
for number in range(1, 6):
    EVIDENCE_COLUMNS.extend([f"evidence_{number}_column", f"evidence_{number}_quote"])
COLUMNS = ["INCIDENT_ID", *RESULT_COLUMNS, *EVIDENCE_COLUMNS, "llm_prompt", "processing_status", "review_status", "error"]


def save_result(path, row, result, prompt, error=""):
    record = dict(row)
    record.update({name: "" for name in COLUMNS if name != "INCIDENT_ID"})
    record.update(processing_status="failed", review_status="Not processed", error=error or "Invalid model output")
    record["llm_prompt"] = prompt
    if result is not None:
        record.update(result.model_dump(exclude={"supporting_evidence"}))
        for number, evidence in enumerate(result.supporting_evidence, start=1):
            record[f"evidence_{number}_column"] = evidence.column
            record[f"evidence_{number}_quote"] = evidence.quote
        record.update(processing_status="success", review_status="PENDING_REVIEW", error="")
    saved, message = append_record(path, record)
    if not saved:
        print(message)
        return {}
    return record
