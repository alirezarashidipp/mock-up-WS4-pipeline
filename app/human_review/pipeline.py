import csv
import hashlib
import json
from pathlib import Path
from threading import Lock

from app.classification_review import effective_classification
from app.csv_files import write_records


ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = ROOT / "data/run/INC_LINKED.csv"
OUTPUT_FILE = ROOT / "data/run/HUMAN_REVIEW.csv"
REVIEW_COLUMNS = (
    "hitl_classification",
    "hitl_classifivation_reasninb",
    "hitl_link",
    "hitl_link_reasoning",
    "hitl_linked_engagement_id",
)
REVIEW_LOCK = Lock()


def classification_is_reviewable(row):
    return effective_classification(row) in ("HSBC", "SUPPLIER", "UNCERTAIN")


def has_link_proposal(row):
    return effective_classification(row) == "SUPPLIER" and row["link_status"] == "MATCHED"


def read_rows(path, reviewed=False):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        columns = reader.fieldnames or []
        if not columns:
            return [], []
        if len(columns) != len(set(columns)) or any(not name.strip() for name in columns):
            raise ValueError(f"{path.name} has duplicate or blank column names.")
        required = {"INCIDENT_ID", "classification", "processing_status", "link_status", "linked_engagement_id", "ENG_ENGAGEMENT_ID"}
        if reviewed:
            required.update(REVIEW_COLUMNS)
        if not required.issubset(columns):
            raise ValueError(f"{path.name} is missing required incident, link, or review columns.")
        if "review_version" in columns:
            raise ValueError("review_version is reserved for the review API, not CSV storage.")
        if not reviewed and set(columns).intersection(REVIEW_COLUMNS):
            raise ValueError("The input already contains review columns. Use the original INC_LINKED.csv.")
        rows = list(reader)
    identifiers = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{path.name} contains a row with the wrong number of cells.")
        incident_id = row["INCIDENT_ID"]
        if not incident_id.strip() or incident_id in identifiers:
            raise ValueError(f"{path.name} requires nonblank, unique INCIDENT_ID values.")
        identifiers.add(incident_id)
        if row["link_status"] not in ("MATCHED", "UNDECIDED", "NOT_APPLICABLE", "SKIPPED", "FAILED"):
            raise ValueError(f"{path.name} contains an invalid model link status.")
        if row["link_status"] == "MATCHED":
            if not has_link_proposal(row) or not row["linked_engagement_id"].strip() or row["linked_engagement_id"] != row["ENG_ENGAGEMENT_ID"]:
                raise ValueError(f"{path.name} contains an invalid matched engagement.")
        if reviewed:
            validate_review(row)
    return rows, columns


def validate_review(row):
    classification = row["hitl_classification"]
    link = row["hitl_link"]
    if classification_is_reviewable(row):
        if classification not in ("pending", "confirmed", "rejected"):
            raise ValueError("Invalid classification review status.")
    elif classification != "not_applicable":
        raise ValueError("An unsuccessful classification cannot be reviewed.")
    if classification == "rejected" and not row["hitl_classifivation_reasninb"].strip():
        raise ValueError("A rejected classification requires a reason.")
    if has_link_proposal(row):
        if link not in ("pending", "confirmed", "rejected", "invalidated"):
            raise ValueError("Invalid link review status.")
        if classification == "rejected" and link != "invalidated":
            raise ValueError("Rejecting classification must invalidate its link.")
        if link == "invalidated" and classification != "rejected":
            raise ValueError("Only a rejected classification can invalidate a link.")
        if link in ("confirmed", "rejected") and classification != "confirmed":
            raise ValueError("Confirm classification before reviewing its link.")
    elif link != "not_applicable":
        raise ValueError("This incident has no engagement link to review.")
    if link == "rejected" and not row["hitl_link_reasoning"].strip():
        raise ValueError("A rejected link requires a reason.")
    expected_id = row["linked_engagement_id"] if link == "confirmed" else ""
    if row["hitl_linked_engagement_id"] != expected_id:
        raise ValueError("The effective engagement ID does not match the review decision.")


def add_review_columns(row):
    result = dict(row)
    result["hitl_classification"] = "pending" if classification_is_reviewable(row) else "not_applicable"
    result["hitl_classifivation_reasninb"] = ""
    result["hitl_link"] = "pending" if has_link_proposal(row) else "not_applicable"
    result["hitl_link_reasoning"] = ""
    result["hitl_linked_engagement_id"] = ""
    return result


def merge_reviews(source_rows, source_columns, saved_rows, saved_columns):
    expected_columns = source_columns + list(REVIEW_COLUMNS)
    if saved_columns and saved_columns != expected_columns:
        raise ValueError("HUMAN_REVIEW.csv belongs to a different schema. Use a new batch folder.")
    rows = list(saved_rows)
    saved_by_id = {row["INCIDENT_ID"]: row for row in saved_rows}
    for source in source_rows:
        saved = saved_by_id.get(source["INCIDENT_ID"])
        if saved is not None:
            if any(saved[name] != source[name] for name in source_columns):
                raise ValueError("A saved incident's source data changed. Use a new batch folder to avoid applying an old review to a new result.")
        else:
            rows.append(add_review_columns(source))
    return rows


def prepare_reviews(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    if input_file.resolve() == output_file.resolve():
        raise ValueError("Review output must be separate from INC_LINKED.csv.")
    source_rows, source_columns = read_rows(input_file)
    if not source_rows:
        return 0
    saved_rows, saved_columns = [], []
    if output_file.exists():
        saved_rows, saved_columns = read_rows(output_file, reviewed=True)
    rows = merge_reviews(source_rows, source_columns, saved_rows, saved_columns)
    if rows != saved_rows:
        write_records(output_file, rows)
    return len(rows)


def review_version(row):
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def apply_review(row, target, decision, reason):
    reason = reason.strip()
    if decision not in ("confirmed", "rejected") or target not in ("classification", "link"):
        raise ValueError("Choose a valid review target and decision.")
    if len(reason) > 2000 or (decision == "rejected" and not reason):
        raise ValueError("A rejection requires a reason of 1 to 2000 characters.")
    result = dict(row)
    if target == "classification":
        if not classification_is_reviewable(row):
            raise ValueError("There is no successful classification to review.")
        result["hitl_classification"] = decision
        result["hitl_classifivation_reasninb"] = reason if decision == "rejected" else ""
        if has_link_proposal(row) and decision == "rejected":
            result["hitl_link"] = "invalidated"
            result["hitl_link_reasoning"] = "Classification rejected; review the link again after confirming classification."
            result["hitl_linked_engagement_id"] = ""
        elif row["hitl_link"] == "invalidated":
            result["hitl_link"] = "pending"
            result["hitl_link_reasoning"] = ""
            result["hitl_linked_engagement_id"] = ""
    else:
        if row["hitl_classification"] != "confirmed" or not has_link_proposal(row):
            raise ValueError("Confirm the accepted Supplier classification with a matched engagement before reviewing its link.")
        result["hitl_link"] = decision
        result["hitl_link_reasoning"] = reason if decision == "rejected" else ""
        result["hitl_linked_engagement_id"] = row["linked_engagement_id"] if decision == "confirmed" else ""
    validate_review(result)
    return result


def main():
    try:
        with REVIEW_LOCK:
            count = prepare_reviews()
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        print(f"Human review preparation failed: {error}")
        return False
    if count:
        print(f"Human review ready: {count} incidents in {OUTPUT_FILE.name}.")
    else:
        print("No incident rows to review. Existing files were left unchanged.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
