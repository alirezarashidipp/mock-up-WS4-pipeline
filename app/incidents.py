"""One incident snapshot, with model proposals and separate human decisions."""

import csv
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from app.csv_files import write_records
from app.models import Classification, empty_link


ROOT = Path(__file__).resolve().parents[1]
RESULTS_FILE = ROOT / "data/run/INCIDENTS.csv"
ENGAGEMENT_FILE = ROOT / "data/mockup/ENG_ALL.csv"
SUPPLIERS_FILE = ROOT / "data/mockup/SUPPLIER_NAME.csv"
CLASSES = ("HSBC", "SUPPLIER", "UNCERTAIN")
REVIEW_DEFAULTS = {
    "classification_review_status": "pending",
    "reviewed_classification": "",
    "classification_review_reason": "",
    "supplier_review_status": "pending",
    "reviewed_supplier_name": "",
    "supplier_review_reason": "",
    "engagement_review_status": "pending",
    "reviewed_engagement_id": "",
    "engagement_review_reason": "",
}
RESULT_COLUMNS = {*Classification.model_fields, "processing_status", "error", "row_revision", *empty_link(), *REVIEW_DEFAULTS}
WRITE_LOCK = Lock()


@contextmanager
def incident_write_lock(path):
    """Serialize pipeline and dashboard writes, including separate processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with WRITE_LOCK:
        with path.with_suffix(path.suffix + ".lock").open("a+b") as file:
            if file.seek(0, os.SEEK_END) == 0:
                file.write(b"0")
                file.flush()
            file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def text_record(row):
    return {name: "" if value is None else str(value) for name, value in row.items()}


def row_version(row):
    text = json.dumps(text_record(row), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_fields(row):
    return {name: value for name, value in row.items() if name not in RESULT_COLUMNS and not name.startswith("ENG_")}


def initial_incident(source, engagement_columns=()):
    if set(source).intersection(RESULT_COLUMNS) or any(name.startswith("ENG_") for name in source):
        raise ValueError("CLEAN.csv contains reserved model or review columns.")
    row = dict(source)
    row.update({name: "" for name in Classification.model_fields})
    row.update(processing_status="pending", error="", row_revision="0")
    row.update(empty_link())
    row.update({"ENG_" + name: "" for name in engagement_columns})
    row.update(REVIEW_DEFAULTS)
    return text_record(row)


def validate_rows(rows, columns):
    if not columns or len(columns) != len(set(columns)) or any(not name.strip() for name in columns):
        raise ValueError("INCIDENTS.csv has missing, blank, or duplicate columns.")
    if not ({"INCIDENT_ID"} | RESULT_COLUMNS).issubset(columns):
        raise ValueError("INCIDENTS.csv has a different schema. Preserve it and choose a fresh output.")
    identifiers = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("INCIDENTS.csv has a row with the wrong number of cells.")
        incident_id = row["INCIDENT_ID"]
        if not incident_id.strip() or incident_id in identifiers:
            raise ValueError("Incident processing requires nonblank, unique INCIDENT_ID values.")
        identifiers.add(incident_id)
        revision = row["row_revision"]
        if not revision.isascii() or not revision.isdecimal():
            raise ValueError("INCIDENTS.csv row_revision must be a nonnegative integer.")
        if row["processing_status"] not in ("pending", "success", "failed"):
            raise ValueError("INCIDENTS.csv contains an invalid processing status.")
        if row["processing_status"] == "success" and row["classification"] not in CLASSES:
            raise ValueError("Successful classification must be HSBC, SUPPLIER, or UNCERTAIN.")
        for target in ("classification", "supplier", "engagement"):
            allowed = ("pending", "approved", "disagree", "not_applicable")
            if row[f"{target}_review_status"] not in allowed:
                raise ValueError("INCIDENTS.csv contains an invalid review status.")


def read_incidents(path=RESULTS_FILE):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        columns = reader.fieldnames or []
        rows = list(reader)
    # Older unified outputs have no citations; reads remain non-mutating.
    if "citations" not in columns:
        columns.append("citations")
        for row in rows:
            row["citations"] = ""
    validate_rows(rows, columns)
    return rows


def get_incident(path, incident_id, version=None):
    rows = read_incidents(path)
    row = next((row for row in rows if row["INCIDENT_ID"] == incident_id), None)
    if row is None:
        raise ValueError("This incident no longer exists. Refresh the dashboard.")
    if version is not None and row_version(row) != version:
        raise ValueError("This incident changed after you opened it. Refresh before saving.")
    return row


def initialize_incidents(path, sources, engagement_columns=()):
    """Add pending incidents without replacing saved results or decisions."""
    if not sources:
        return read_incidents(path)
    columns = set(sources[0])
    identifiers = set()
    pending = []
    for source in sources:
        if set(source) != columns or None in source or any(value is None for value in source.values()):
            raise ValueError("CLEAN.csv rows must have the same complete columns.")
        incident_id = source.get("INCIDENT_ID", "")
        if not incident_id.strip() or incident_id in identifiers:
            raise ValueError("Incident processing requires nonblank, unique INCIDENT_ID values.")
        identifiers.add(incident_id)
        pending.append(initial_incident(source, engagement_columns))
    with incident_write_lock(path):
        rows = read_incidents(path)
        saved_by_id = {row["INCIDENT_ID"]: row for row in rows}
        if rows and set(rows[0]) != set(pending[0]):
            raise ValueError("Incident or engagement columns changed. Preserve this output and start a fresh batch.")
        changed = False
        for new_row in pending:
            saved = saved_by_id.get(new_row["INCIDENT_ID"])
            if saved is not None:
                if source_fields(saved) != source_fields(new_row):
                    raise ValueError("A saved incident's source changed. Preserve this output and start a fresh batch.")
                continue
            rows.append(new_row)
            changed = True
        if changed:
            write_records(path, rows)
        return rows


def save_incident(path, row, expected_version):
    row = text_record(row)
    with incident_write_lock(path):
        rows = read_incidents(path)
        for index, saved in enumerate(rows):
            if saved["INCIDENT_ID"] != row.get("INCIDENT_ID"):
                continue
            if row_version(saved) != expected_version:
                raise ValueError("This incident changed after you opened it. Refresh before saving.")
            if set(saved) != set(row) or source_fields(saved) != source_fields(row):
                raise ValueError("Incident source fields and output columns cannot change during a save.")
            validate_rows([row], list(row))
            # Every write advances the version, even when the visible values repeat.
            row["row_revision"] = str(int(saved["row_revision"]) + 1)
            rows[index] = row
            write_records(path, rows)
            return row
    raise ValueError("This incident no longer exists. Refresh the dashboard.")


def apply_link_result(row, proposal):
    """Replace link citations while retaining the original classification excerpts."""
    classification_lines = []
    for line in row.get("citations", "").splitlines():
        if line.startswith("Classification: "):
            classification_lines.append(line)
    row.update(proposal)
    link_citations = proposal.get("citations", "")
    if link_citations:
        classification_lines.append(link_citations)
    row["citations"] = "\n".join(classification_lines)


def engagement_values(row, engagements, selected_id):
    columns = {name[4:] for name in row if name.startswith("ENG_")}
    if engagements and columns != set(engagements[0]):
        raise ValueError("Engagement columns changed. Preserve this output and start a fresh batch.")
    selected = next((item for item in engagements if item["ENGAGEMENT_ID"] == selected_id), None)
    if selected_id and selected is None:
        raise ValueError("The selected engagement is no longer in the current catalog.")
    return {"ENG_" + name: selected[name] if selected else "" for name in columns}
