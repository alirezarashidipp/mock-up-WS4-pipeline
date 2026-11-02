"""Local human decisions before engagement linking; model output stays unchanged."""

import csv
import hashlib
import json
from pathlib import Path
from threading import Lock

from app.csv_files import write_records


ROOT = Path(__file__).resolve().parents[1]
REVIEW_FILE = ROOT / "data/run/CLASSIFICATION_REVIEW.csv"
SUPPLIERS_FILE = ROOT / "data/mockup/SUPPLIER_NAME.csv"
REVIEW_COLUMNS = (
    "classification_review_status",
    "reviewed_classification",
    "classification_review_reason",
    "supplier_review_status",
    "reviewed_supplier_name",
    "supplier_review_reason",
)
REVIEW_LOCK = Lock()


def supplier_options(path):
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
            if not name:
                continue
            if not names and name.casefold() == "supplier_name":
                continue
            if name not in names:
                names.append(name)
        if not names:
            return [], "SUPPLIER_NAME.csv has no supplier names. Supplier corrections require this catalog."
        return names, ""
    except FileNotFoundError:
        return [], "SUPPLIER_NAME.csv is missing. Add the supplier-name catalog before correcting a supplier."
    except (OSError, UnicodeError, csv.Error, ValueError):
        return [], "SUPPLIER_NAME.csv must be a UTF-8 CSV with one supplier-name column."


def read_rows(path, reviewed=False):
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        columns = reader.fieldnames or []
        if not columns:
            return [], []
        if len(columns) != len(set(columns)) or any(not name.strip() for name in columns):
            raise ValueError("Incident CSV has duplicate or blank columns.")
        required = {"INCIDENT_ID", "processing_status", "classification"}
        if reviewed:
            required.update(REVIEW_COLUMNS)
        elif set(columns).intersection(REVIEW_COLUMNS):
            raise ValueError("LLM_OUTPUT.csv contains reserved human-review columns.")
        if {"review_version", "review_stale"}.intersection(columns):
            raise ValueError("Review version and stale markers belong in the API, not source CSV columns.")
        if not required.issubset(columns):
            raise ValueError("Incident CSV is missing classification or review columns.")
        rows = list(reader)
    identifiers = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Incident CSV contains a row with the wrong number of cells.")
        incident_id = row["INCIDENT_ID"]
        if not incident_id.strip() or incident_id in identifiers:
            raise ValueError("Classification review requires nonblank, unique INCIDENT_ID values.")
        identifiers.add(incident_id)
        if row["processing_status"] not in ("success", "failed"):
            raise ValueError("LLM_OUTPUT.csv contains an invalid processing status.")
        if row["processing_status"] == "success" and row["classification"] not in ("HSBC", "SUPPLIER", "UNCERTAIN"):
            raise ValueError("Classification must be HSBC, SUPPLIER, or UNCERTAIN.")
        if reviewed:
            validate_review(row)
    return rows, columns


def empty_review():
    return {
        "classification_review_status": "pending",
        "reviewed_classification": "",
        "classification_review_reason": "",
        "supplier_review_status": "not_applicable",
        "reviewed_supplier_name": "",
        "supplier_review_reason": "",
    }


def classification_is_approved(row):
    return (
        not row.get("review_stale", False)
        and row.get("classification_review_status") in ("approved", "corrected")
        and row.get("reviewed_classification") in ("HSBC", "SUPPLIER")
    )


def usable_supplier_name(name):
    return name.strip().casefold() not in ("", "unknown", "n/a", "n a", "none", "null", "not known", "not available")


def ready_for_linking(row):
    return (
        classification_is_approved(row)
        and row["reviewed_classification"] == "SUPPLIER"
        and row.get("supplier_review_status") in ("approved", "corrected")
        and usable_supplier_name(row.get("reviewed_supplier_name", ""))
    )


def effective_classification(row):
    if "classification_review_status" in row:
        return row["reviewed_classification"] if classification_is_approved(row) else ""
    if row.get("processing_status") == "success" and row.get("classification") in ("HSBC", "SUPPLIER", "UNCERTAIN"):
        return row["classification"]
    return ""


def effective_supplier_name(row):
    if "classification_review_status" in row:
        return row["reviewed_supplier_name"] if ready_for_linking(row) else ""
    return row.get("supplier_name", "")


def validate_review(row):
    classification_status = row["classification_review_status"]
    supplier_status = row["supplier_review_status"]
    if classification_status not in ("pending", "approved", "corrected", "needs_review"):
        raise ValueError("Invalid saved classification review status.")
    if supplier_status not in ("pending", "approved", "corrected", "needs_review", "not_applicable"):
        raise ValueError("Invalid saved supplier review status.")
    for status, reason in ((classification_status, row["classification_review_reason"]), (supplier_status, row["supplier_review_reason"])):
        if len(reason) > 2000 or (status in ("corrected", "needs_review") and not reason.strip()):
            raise ValueError("A correction or unresolved review requires a reason of 1 to 2000 characters.")
        if status in ("pending", "approved", "not_applicable") and reason:
            raise ValueError("A saved approval or pending review cannot contain a rejection reason.")
    if classification_status in ("approved", "corrected"):
        if row["reviewed_classification"] not in ("HSBC", "SUPPLIER"):
            raise ValueError("A completed classification review requires HSBC or SUPPLIER.")
    elif row["reviewed_classification"]:
        raise ValueError("An unresolved classification cannot have an approved class.")
    if classification_status == "approved":
        if row["processing_status"] != "success" or row["classification"] != row["reviewed_classification"]:
            raise ValueError("A classification approval must agree with a successful model result.")
    if classification_is_approved(row) and row["reviewed_classification"] == "SUPPLIER":
        if supplier_status == "not_applicable":
            raise ValueError("Supplier classifications require a supplier-name review.")
    elif supplier_status != "not_applicable":
        raise ValueError("Supplier-name review requires an approved Supplier classification.")
    if supplier_status in ("approved", "corrected"):
        if not usable_supplier_name(row["reviewed_supplier_name"]):
            raise ValueError("An approved supplier name cannot be blank or Unknown.")
    elif row["reviewed_supplier_name"]:
        raise ValueError("An unresolved supplier review cannot have an approved supplier name.")
    if supplier_status == "approved":
        if row["processing_status"] != "success" or row["classification"] != "SUPPLIER" or row.get("supplier_name", "") != row["reviewed_supplier_name"]:
            raise ValueError("Supplier approval must agree with the original model supplier name.")


def merge_review_rows(source_rows, saved_rows):
    saved_by_id = {row["INCIDENT_ID"]: row for row in saved_rows}
    results = []
    for source in source_rows:
        saved = saved_by_id.get(source["INCIDENT_ID"])
        saved_source = None
        if saved is not None:
            saved_source = {name: value for name, value in saved.items() if name not in REVIEW_COLUMNS}
        stale = saved is not None and saved_source != source
        row = dict(source)
        row.update(empty_review())
        if saved is not None and not stale:
            for name in REVIEW_COLUMNS:
                row[name] = saved[name]
        version_data = {"source": source, "saved_review": saved}
        encoded = json.dumps(version_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        row["review_version"] = hashlib.sha256(encoded).hexdigest()
        row["review_stale"] = stale
        results.append(row)
    return results


def load_reviewed_rows(source_path, review_path):
    source_rows, _ = read_rows(source_path)
    saved_rows, _ = read_rows(review_path, reviewed=True)
    return merge_review_rows(source_rows, saved_rows)


def apply_review(row, decision, supplier_names):
    if decision.target not in ("classification", "supplier") or decision.decision not in ("approved", "corrected", "needs_review"):
        raise ValueError("Choose a valid review target and decision.")
    result = dict(row)
    reason = decision.reason.strip()
    if len(reason) > 2000 or (decision.decision in ("corrected", "needs_review") and not reason):
        raise ValueError("A correction or unresolved review requires a reason of 1 to 2000 characters.")
    if decision.target == "classification":
        result.update(empty_review())
        result["classification_review_status"] = decision.decision
        result["classification_review_reason"] = reason if decision.decision != "approved" else ""
        if decision.decision == "approved":
            if row["processing_status"] != "success" or row["classification"] not in ("HSBC", "SUPPLIER"):
                raise ValueError("Choose HSBC or SUPPLIER and explain the decision for an uncertain or failed model result.")
            result["reviewed_classification"] = row["classification"]
        elif decision.decision == "corrected":
            if decision.classification not in ("HSBC", "SUPPLIER"):
                raise ValueError("Choose the corrected classification: HSBC or SUPPLIER.")
            result["reviewed_classification"] = decision.classification
        if result["reviewed_classification"] == "SUPPLIER":
            result["supplier_review_status"] = "pending"
    else:
        if not classification_is_approved(row) or row["reviewed_classification"] != "SUPPLIER":
            raise ValueError("Approve or correct classification to Supplier before reviewing its name.")
        result["supplier_review_status"] = decision.decision
        result["supplier_review_reason"] = reason if decision.decision != "approved" else ""
        result["reviewed_supplier_name"] = ""
        if decision.decision == "approved":
            if row["processing_status"] != "success" or row["classification"] != "SUPPLIER" or not usable_supplier_name(row.get("supplier_name", "")):
                raise ValueError("Choose a supplier from the catalog when the model has no usable supplier name.")
            result["reviewed_supplier_name"] = row["supplier_name"]
        elif decision.decision == "corrected":
            if decision.supplier_name not in supplier_names or not usable_supplier_name(decision.supplier_name):
                raise ValueError("Choose a supplier from the current SUPPLIER_NAME.csv catalog.")
            result["reviewed_supplier_name"] = decision.supplier_name
    result.pop("review_version", None)
    result.pop("review_stale", None)
    validate_review(result)
    return result


def save_review(source_path, review_path, supplier_path, decision):
    if review_path.resolve() in (source_path.resolve(), supplier_path.resolve()):
        raise ValueError("Review output must be separate from model output and the supplier catalog.")
    with REVIEW_LOCK:
        source_rows, source_columns = read_rows(source_path)
        saved_rows, saved_columns = read_rows(review_path, reviewed=True)
        if saved_columns and set(saved_columns) != set(source_columns) | set(REVIEW_COLUMNS):
            raise ValueError("Review source columns changed. Preserve the old reviews and use a fresh review output.")
        rows = merge_review_rows(source_rows, saved_rows)
        row = next((row for row in rows if row["INCIDENT_ID"] == decision.INCIDENT_ID), None)
        if row is None:
            raise ValueError("This incident is no longer in LLM_OUTPUT.csv. Refresh the dashboard.")
        if row["review_version"] != decision.version:
            raise ValueError("This incident changed after you opened it. Refresh before saving another decision.")
        supplier_names, _ = supplier_options(supplier_path)
        updated = apply_review(row, decision, supplier_names)
        for index, saved in enumerate(saved_rows):
            if saved["INCIDENT_ID"] == decision.INCIDENT_ID:
                saved_rows[index] = updated
                break
        else:
            saved_rows.append(updated)
        write_records(review_path, saved_rows)
