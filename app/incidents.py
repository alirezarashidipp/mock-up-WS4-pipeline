"""One incident snapshot, with model proposals and separate human decisions."""

import csv
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from app.csv_files import write_records
from app.linking.linking import empty_link
from app.models import Classification


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
    validate_rows(rows, columns)
    return rows


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
        if rows and set(source_fields(rows[0])) != columns:
            raise ValueError("Source columns changed. Preserve INCIDENTS.csv and choose a fresh output.")
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


def engagement_values(row, engagements, selected_id):
    columns = {name[4:] for name in row if name.startswith("ENG_")}
    if engagements and columns != set(engagements[0]):
        raise ValueError("Engagement columns changed. Preserve this output and start a fresh batch.")
    selected = next((item for item in engagements if item["ENGAGEMENT_ID"] == selected_id), None)
    if selected_id and selected is None:
        raise ValueError("The selected engagement is no longer in the current catalog.")
    return {"ENG_" + name: selected[name] if selected else "" for name in columns}


def supplier_options(path=SUPPLIERS_FILE):
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file, strict=True))
        names = []
        for row in rows:
            if not row:
                continue
            if len(row) != 1:
                raise ValueError
            name = row[0].strip()
            if not name or (not names and name.casefold() == "supplier_name"):
                continue
            if name not in names:
                names.append(name)
        if not names:
            return [], "SUPPLIER_NAME.csv has no base names. Add names before correcting a supplier."
        return names, ""
    except FileNotFoundError:
        return [], "SUPPLIER_NAME.csv is missing. Supplier corrections require the base-name catalog."
    except (OSError, UnicodeError, csv.Error, ValueError):
        return [], "SUPPLIER_NAME.csv must be a UTF-8 CSV with one supplier-name column."


def usable_supplier_name(name):
    return (name or "").strip().casefold() not in ("", "unknown", "n/a", "n a", "none", "null", "not known", "not available")


def classification_complete(row):
    return row["classification_review_status"] in ("approved", "disagree") and row["reviewed_classification"] in ("HSBC", "SUPPLIER")


def supplier_complete(row):
    return (
        classification_complete(row)
        and row["reviewed_classification"] == "SUPPLIER"
        and row["supplier_review_status"] in ("approved", "disagree")
        and usable_supplier_name(row["reviewed_supplier_name"])
    )


def effective_classification(row):
    if row["classification_review_status"] in ("approved", "disagree"):
        return row["reviewed_classification"]
    return row["classification"] if row["processing_status"] == "success" else ""


def effective_supplier_name(row):
    if supplier_complete(row):
        return row["reviewed_supplier_name"]
    if effective_classification(row) == "SUPPLIER":
        return row.get("supplier_name", "")
    return ""


def review_complete(row):
    if not classification_complete(row):
        return False
    if row["reviewed_classification"] == "HSBC":
        return True
    return supplier_complete(row) and row["engagement_review_status"] in ("approved", "disagree")


def apply_classification_review(row, decision):
    if row["processing_status"] == "pending":
        raise ValueError("Wait for classification processing before reviewing this incident.")
    updated = dict(row)
    if decision.decision == "approved":
        if row["processing_status"] != "success" or row["classification"] not in ("HSBC", "SUPPLIER"):
            raise ValueError("Choose HSBC or SUPPLIER and explain the decision for an unresolved model result.")
        selected = row["classification"]
    else:
        selected = decision.classification
        if selected not in CLASSES:
            raise ValueError("Choose HSBC, SUPPLIER, or UNCERTAIN.")
    updated.update(REVIEW_DEFAULTS)
    updated["classification_review_status"] = decision.decision
    updated["reviewed_classification"] = selected
    updated["classification_review_reason"] = decision.reason.strip() if decision.decision == "disagree" else ""
    if selected == "SUPPLIER" and row["link_status"] == "RUNNING":
        updated.update(empty_link(status="PENDING", reason="Review changed while suggestions were running."))
    if selected != "SUPPLIER":
        status = "NOT_APPLICABLE" if selected == "HSBC" else "SKIPPED"
        updated.update(empty_link(status=status, reason="Human classification does not permit engagement linking."))
        updated.update({name: "" for name in row if name.startswith("ENG_")})
        updated["supplier_review_status"] = "not_applicable"
        updated["engagement_review_status"] = "not_applicable"
    return updated


def apply_supplier_review(row, decision, supplier_names):
    if not classification_complete(row) or row["reviewed_classification"] != "SUPPLIER":
        raise ValueError("Approve or correct Supplier classification before reviewing its name.")
    if decision.decision == "approved":
        if row["processing_status"] != "success" or row["classification"] != "SUPPLIER" or not usable_supplier_name(row.get("supplier_name", "")):
            raise ValueError("Choose a supplier base name from the catalog and give a reason.")
        name = row["supplier_name"]
    else:
        name = decision.supplier_name
        if name not in supplier_names or not usable_supplier_name(name):
            raise ValueError("Choose a supplier from the current SUPPLIER_NAME.csv catalog.")
    updated = dict(row)
    updated["supplier_review_status"] = decision.decision
    updated["reviewed_supplier_name"] = name
    updated["supplier_review_reason"] = decision.reason.strip() if decision.decision == "disagree" else ""
    updated["engagement_review_status"] = "pending"
    updated["reviewed_engagement_id"] = ""
    updated["engagement_review_reason"] = ""
    return updated
