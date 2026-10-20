import csv
import os
import tempfile
from pathlib import Path


def read_records(path: Path, optional: bool = False) -> tuple[list[dict], str]:
    if optional and not path.exists():
        return [], ""
    if not path.exists():
        return [], f"{path.name} is missing. Run the classification pipeline first."
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        headers = reader.fieldnames or []
        rows = list(reader)
    if not rows or "INCIDENT_ID" not in headers or len(headers) != len(set(headers)):
        return [], f"{path.name} requires data, unique columns, and INCIDENT_ID."
    if any(None in row or None in row.values() for row in rows):
        return [], f"{path.name} contains a malformed row."
    ids = [row["INCIDENT_ID"] for row in rows]
    if any(not value.strip() for value in ids) or len(ids) != len(set(ids)):
        return [], f"{path.name} requires unique, nonempty identifiers."
    return rows, ""


def append_record(path: Path, record: dict) -> tuple[bool, str]:
    record = {key: "" if value is None else str(value) for key, value in record.items()}
    rows, error = read_records(path, optional=True)
    if error:
        return False, error
    if rows and set(rows[0]) != set(record):
        return False, f"{path.name} belongs to a different schema. Use a new batch folder."
    previous = next((row for row in rows if row["INCIDENT_ID"] == record["INCIDENT_ID"]), None)
    if previous is not None:
        return (True, "") if previous == record else (False, f"{path.name} already contains a different decision for this INCIDENT_ID.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            writer = csv.DictWriter(file, fieldnames=list(record))
            writer.writeheader()
            writer.writerows(rows + [record])
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True, ""
