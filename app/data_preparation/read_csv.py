import csv
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)) or any(not name.strip() for name in headers):
            print("CSV column names must be nonempty and unique.")
            return []
        rows = list(reader)

    if not rows or any(None in row or None in row.values() for row in rows):
        print("CSV needs data rows with the same number of values as headers.")
        return []
    return rows
