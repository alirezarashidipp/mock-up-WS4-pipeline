from app.csv_files import append_record
from app.models import Classification


COLUMNS = ["INCIDENT_ID", *Classification.model_fields, "processing_status", "error"]


def save_result(path, row, result, error=""):
    record = dict(row)
    for name in COLUMNS:
        if name != "INCIDENT_ID":
            record[name] = ""
    record["processing_status"] = "failed"
    record["error"] = error or "Invalid model output"

    if result is not None:
        values = result.model_dump()
        values["evidence_column"] = ", ".join(result.evidence_column)
        record.update(values)
        record["processing_status"] = "success"
        record["error"] = ""

    saved, message = append_record(path, record)
    if not saved:
        print(message)
        return {}
    return record
