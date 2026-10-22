from app.csv_files import append_record
from app.models import Classification


RESULT_COLUMNS = [name for name in Classification.model_fields if name != "supporting_evidence"]
EVIDENCE_COLUMNS = [f"evidence_{number}_column" for number in range(1, 11)]
COLUMNS = ["INCIDENT_ID", *RESULT_COLUMNS, *EVIDENCE_COLUMNS, "processing_status", "error"]


def save_result(path, row, result, error=""):
    record = dict(row)
    record.update({name: "" for name in COLUMNS if name != "INCIDENT_ID"})
    record.update(processing_status="failed", error=error or "Invalid model output")
    if result is not None:
        record.update(result.model_dump(exclude={"supporting_evidence"}))
        for number, column_name in enumerate(result.supporting_evidence, start=1):
            record[f"evidence_{number}_column"] = column_name
        record.update(processing_status="success", error="")
    saved, message = append_record(path, record)
    if not saved:
        print(message)
        return {}
    return record
