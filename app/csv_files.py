import csv
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def read_records(path):
    if not path.exists():
        return [], f"{path.name} is missing. Run the classification pipeline first."
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return rows, ""


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
