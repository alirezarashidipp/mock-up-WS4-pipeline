import csv
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile


def read_records(path, optional=False):
    if not path.exists():
        if optional:
            return [], ""
        return [], f"{path.name} is missing. Run the classification pipeline first."
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return rows, ""


def is_evidence_column(name):
    return re.fullmatch(r"evidence_[1-9]\d*_column", name) is not None


def append_record(path, record):
    record = {name: "" if value is None else str(value) for name, value in record.items()}
    if not record.get("INCIDENT_ID", "").strip():
        return False, "Every record requires a nonempty INCIDENT_ID."
    rows, _ = read_records(path, optional=True)
    if rows:
        different_columns = set(rows[0]) ^ set(record)
        if any(not is_evidence_column(name) for name in different_columns):
            return False, f"{path.name} belongs to a different schema. Use a new batch folder."
        # Keep existing evidence columns and fill unused cells.
        for row in rows:
            for name in record:
                row.setdefault(name, "")
        for name in rows[0]:
            record.setdefault(name, "")
    for row in rows:
        if row["INCIDENT_ID"] == record["INCIDENT_ID"]:
            if row == record:
                return True, ""
            return False, f"{path.name} already contains a different decision for this INCIDENT_ID."
    rows.append(record)
    write_records(path, rows)
    return True, ""


def write_records(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False)
    try:
        with temporary as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary.name, path)
    finally:
        Path(temporary.name).unlink(missing_ok=True)
