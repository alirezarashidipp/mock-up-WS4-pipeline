import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.csv_files import append_record, read_records
from app.models import Classification
from app.save_csv import COLUMNS


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    decision: Literal["Approved", "Rejected"]
    reason_of_rejection: str = Field(default="", max_length=2000)


def cleaned_values(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in COLUMNS or key == "ROW_ID"}


def review_metadata(status: str, reason: str = "", uncertainty: str = "") -> dict:
    return {
        "STATUS": status,
        "REVIEW_DATE": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "REJECTION_REASON": reason,
        "LLM_UNCERTAINTY_REASON": uncertainty,
    }


def load_batch(results_file: Path, output_dir: Path) -> tuple[list, list, list, str]:
    approved_file = output_dir / "FINAL.csv"
    human_file = output_dir / "HUMAN_REVIEW.csv"
    if results_file.resolve() in (approved_file.resolve(), human_file.resolve()):
        return [], [], [], "Classification input must be separate from review outputs."
    try:
        rows, error = read_records(results_file)
        if error:
            return [], [], [], error
        if not set(COLUMNS) <= set(rows[0]) or "INCIDENT_SUMMARY" not in rows[0]:
            return [], [], [], "Results must include standardized input fields and the six classification fields. Run a new batch with the current prompt."
        for row in rows:
            if row["processing_status"] == "failed":
                continue
            values = {name: row[name] or None for name in Classification.model_fields}
            values["supporting_evidence"] = json.loads(row["supporting_evidence"])
            result = Classification.model_validate(values)
            if row["processing_status"] != "success":
                return [], [], [], "A classification result is inconsistent or invalid."
            if result.classification == "UNDECIDED" and not row["uncertainty_reason"].strip():
                return [], [], [], "An undecided result must explain why the model could not decide."
            if result.classification != "UNDECIDED" and (not result.supporting_evidence or result.uncertainty_reason is not None):
                return [], [], [], "A definite classification requires supporting evidence and no uncertainty reason."
        approved, error = read_records(approved_file, optional=True)
        if error:
            return [], [], [], error
        human, error = read_records(human_file, optional=True)
        if error:
            return [], [], [], error
        by_id = {row["ROW_ID"]: row for row in rows}
        if {row["ROW_ID"] for row in approved} & {row["ROW_ID"] for row in human}:
            return [], [], [], "A record cannot be both approved and in human review."
        metadata = {"STATUS", "REVIEW_DATE", "REJECTION_REASON", "LLM_UNCERTAINTY_REASON"}
        for saved in approved + human:
            current = by_id.get(saved["ROW_ID"])
            if current is None:
                return [], [], [], "Review outputs belong to a different batch or schema."
            if saved in approved:
                expected = current | {"review_status": "Approved"}
            else:
                expected = cleaned_values(current)
            if set(saved) != set(expected) | metadata or not saved["REVIEW_DATE"].strip():
                return [], [], [], "Review outputs have an invalid schema or missing date."
            if any(saved[name] != value for name, value in expected.items()):
                return [], [], [], "A previously routed record changed. Use a new batch folder."
        for saved in approved:
            if saved["STATUS"] != "USER_APPROVED" or saved["classification"] not in ("SUPPLIER", "HSBC"):
                return [], [], [], "Only a definite classification can be approved."
        for saved in human:
            current = by_id[saved["ROW_ID"]]
            automatic = saved["STATUS"] == "LLM_UNDECIDED" and current["classification"] == "UNDECIDED" and saved["LLM_UNCERTAINTY_REASON"] == current["uncertainty_reason"] and not saved["REJECTION_REASON"]
            rejected = saved["STATUS"] == "USER_REJECTED" and current["classification"] in ("SUPPLIER", "HSBC") and saved["REJECTION_REASON"].strip() and not saved["LLM_UNCERTAINTY_REASON"]
            if not (automatic or rejected):
                return [], [], [], "A human-review record has an invalid route or missing rejection reason."
        return rows, approved, human, ""
    except (OSError, csv.Error, KeyError, TypeError, ValueError):
        return [], [], [], "The current batch files could not be read or validated."


def sync_human_review(results_file: Path, output_dir: Path) -> dict:
    rows, _, human, error = load_batch(results_file, output_dir)
    if error:
        return {"error": error}
    routed = {row["ROW_ID"] for row in human}
    for row in rows:
        if row["processing_status"] == "success" and row["classification"] == "UNDECIDED" and row["ROW_ID"] not in routed:
            saved = cleaned_values(row) | review_metadata("LLM_UNDECIDED", uncertainty=row["uncertainty_reason"])
            ok, error = append_record(output_dir / "HUMAN_REVIEW.csv", saved)
            if not ok:
                return {"error": error}
    return {"message": "Uncertain classifications are in human review."}


def get_review_data(results_file: Path, output_dir: Path) -> dict:
    rows, approved, human, error = load_batch(results_file, output_dir)
    if error:
        return {"error": error}
    decisions = {row["ROW_ID"]: row for row in approved + human}
    records = []
    pending = failed = 0
    for row in rows:
        if row["processing_status"] == "failed":
            failed += 1
            continue
        decision = decisions.get(row["ROW_ID"], {})
        status = "Needs Human Review" if row["classification"] == "UNDECIDED" else "Pending Review"
        if decision:
            statuses = {"USER_APPROVED": "Approved", "USER_REJECTED": "Rejected", "LLM_UNDECIDED": "Needs Human Review"}
            status = statuses[decision["STATUS"]]
        pending += status == "Pending Review"
        records.append({
            "row_id": row["ROW_ID"],
            "version": hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
            "input": cleaned_values(row),
            "result": {key: row[key] for key in COLUMNS},
            "review_status": status,
            "review_source": decision.get("STATUS", ""),
            "review_date": decision.get("REVIEW_DATE", ""),
            "reason_of_rejection": decision.get("REJECTION_REASON", ""),
        })
    return {"records": records, "counts": {"pending": pending, "approved": len(approved), "human_review": len(human), "failed": failed}}


def submit_review(results_file: Path, output_dir: Path, decision: ReviewDecision) -> tuple[dict, int]:
    reason = decision.reason_of_rejection.strip()
    if decision.decision == "Rejected" and not reason:
        return {"error": "A rejection reason is required."}, 400
    data = get_review_data(results_file, output_dir)
    if "error" in data:
        return data, 400
    row = next((row for row in data["records"] if row["row_id"] == decision.row_id), None)
    if row is None or row["review_status"] != "Pending Review" or row["result"]["classification"] == "UNDECIDED":
        return {"error": "Only an unreviewed SUPPLIER or HSBC decision can be approved or rejected."}, 409
    if row["version"] != decision.version:
        return {"error": "This record changed. Reload it before making a decision."}, 409
    approved = decision.decision == "Approved"
    if approved:
        saved = row["input"] | row["result"] | {"review_status": "Approved"} | review_metadata("USER_APPROVED")
    else:
        saved = row["input"] | review_metadata("USER_REJECTED", reason=reason)
    target = output_dir / ("FINAL.csv" if approved else "HUMAN_REVIEW.csv")
    ok, error = append_record(target, saved)
    return ({"message": "Classification approved." if approved else "Sent to human review."}, 200) if ok else ({"error": error}, 409)
