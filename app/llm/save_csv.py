from app.csv_files import append_record
from app.models import Classification


COLUMNS = ["INCIDENT_ID", *Classification.model_fields, "processing_status", "error"]


def save_result(path, row, result, error=""):
    record = dict(row)
    record.update({name: "" for name in COLUMNS if name != "INCIDENT_ID"})
    record.update(processing_status="failed", error=error or "Invalid model output")
    if result is not None:
        record.update(result.model_dump(exclude={"supporting_evidence"}))
        record["supporting_evidence"] = ", ".join(result.supporting_evidence)
        record.update(processing_status="success", error="")
    saved, message = append_record(path, record)
    if not saved:
        print(message)
        return {}
    return record
