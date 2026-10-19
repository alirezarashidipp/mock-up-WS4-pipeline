import json
from pathlib import Path

from app.csv_files import append_record
from app.models import Classification


COLUMNS = ["ROW_ID", *Classification.model_fields, "processing_status", "review_status", "error"]


def save_result(path: Path, row: dict, result: Classification | None, error: str = "") -> dict:
    record = dict(row)
    record.update({name: "" for name in COLUMNS if name != "ROW_ID"})
    record.update(processing_status="failed", review_status="Not processed", error=error)
    if result is not None:
        record.update(result.model_dump())
        record["supporting_evidence"] = json.dumps(record["supporting_evidence"], ensure_ascii=False)
        record["processing_status"] = "success"
        record["review_status"] = "Needs Human Review" if record["classification"] == "UNDECIDED" else "Pending Review"
    saved, message = append_record(path, record)
    if not saved:
        print(message)
        return {}
    return record
