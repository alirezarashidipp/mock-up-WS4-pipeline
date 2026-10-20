import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.csv_files import append_record, read_records
from app.models import Classification, InputField
from app.save_csv import COLUMNS


FINAL_COLUMNS = {"FINAL_CLASS", "USER_REASON", "REVIEW_ACTION", "REVIEW_DATE", "STATUS"}


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    final_class: Literal["HSBC", "SUPPLIER"]
    user_reason: str = Field(min_length=1, max_length=2000)


def cleaned_values(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in COLUMNS or key == "INCIDENT_ID"}


def review_action(llm_class: str, final_class: str) -> str:
    if llm_class == "UNDECIDED":
        return "RESOLVED_UNDECIDED"
    if llm_class == final_class:
        return "CONFIRMED"
    return "CORRECTED"


def valid_result(row: dict) -> bool:
    values = {name: row[name] or None for name in Classification.model_fields}
    values["supporting_evidence"] = json.loads(row["supporting_evidence"])
    result = Classification.model_validate(values)
    payload = [InputField.model_validate(field) for field in json.loads(row["llm_input"])]
    sent_values = {field.name: field.value for field in payload}
    source = {name: value for name, value in cleaned_values(row).items() if name != "INCIDENT_ID"}
    if len(sent_values) != len(payload) or sent_values != source or not row["llm_prompt"].strip():
        return False
    if result.classification == "UNDECIDED":
        if not (result.uncertainty_reason or "").strip():
            return False
    elif not result.supporting_evidence or result.uncertainty_reason is not None:
        return False
    return all(e.quote.strip() and e.quote in sent_values.get(e.column, "") for e in result.supporting_evidence)


def load_results(path: Path) -> tuple[list, str]:
    try:
        rows, error = read_records(path)
        if error:
            return [], error
        if not set(COLUMNS) <= set(rows[0]) or FINAL_COLUMNS & set(rows[0]):
            return [], "Results use an older or invalid schema. Generate a new batch with input snapshots."
        for row in rows:
            if row["processing_status"] == "failed":
                continue
            if row["processing_status"] != "success" or not valid_result(row):
                return [], "A model result or its input snapshot is invalid."
        return rows, ""
    except (OSError, csv.Error, KeyError, TypeError, ValueError):
        return [], "Could not read or validate LLM_OUTPUT.csv."


def load_final(output_dir: Path) -> tuple[list, str]:
    try:
        rows, error = read_records(output_dir / "FINAL.csv", optional=True)
        if error:
            return [], error
        for row in rows:
            if not (set(COLUMNS) | FINAL_COLUMNS) <= set(row):
                return [], "FINAL.csv uses an older or invalid schema. Keep it in its original batch folder."
            if row["STATUS"] != "FINALIZED" or row["FINAL_CLASS"] not in ("HSBC", "SUPPLIER"):
                return [], "FINAL.csv contains an invalid final decision."
            if not row["USER_REASON"].strip() or len(row["USER_REASON"]) > 2000:
                return [], "Every final decision requires a user reason."
            date = datetime.fromisoformat(row["REVIEW_DATE"].replace("Z", "+00:00"))
            if date.tzinfo is None or row["REVIEW_ACTION"] != review_action(row["classification"], row["FINAL_CLASS"]):
                return [], "A final decision has an invalid date or review action."
            source = {key: value for key, value in row.items() if key not in FINAL_COLUMNS}
            if row["processing_status"] != "success" or not valid_result(source):
                return [], "A finalized model result or its input snapshot is invalid."
        return rows, ""
    except (OSError, csv.Error, KeyError, TypeError, ValueError):
        return [], "Could not read or validate FINAL.csv."


def get_review_data(results_file: Path, output_dir: Path) -> dict:
    if results_file.resolve() == (output_dir / "FINAL.csv").resolve():
        return {"error": "Model results and final decisions must be separate files."}
    rows, error = load_results(results_file)
    if error:
        return {"error": error}
    finalized, error = load_final(output_dir)
    if error:
        return {"error": error}
    by_id = {row["INCIDENT_ID"]: row for row in rows}
    for saved in finalized:
        current = by_id.get(saved["INCIDENT_ID"])
        if current is None or set(saved) != set(current) | FINAL_COLUMNS:
            return {"error": "FINAL.csv belongs to a different batch."}
        if any(saved[name] != value for name, value in current.items()):
            return {"error": "A finalized incident changed. Use a separate batch folder."}
    decisions = {row["INCIDENT_ID"]: row for row in finalized}
    records = []
    failed = pending = undecided = 0
    for row in rows:
        if row["processing_status"] == "failed":
            failed += 1
            continue
        decision = decisions.get(row["INCIDENT_ID"], {})
        if not decision:
            pending += 1
            undecided += row["classification"] == "UNDECIDED"
        records.append({
            "incident_id": row["INCIDENT_ID"],
            "version": hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
            "input": cleaned_values(row),
            "model_input": json.loads(row["llm_input"]),
            "prompt": row["llm_prompt"],
            "result": {key: row[key] for key in COLUMNS},
            "review_status": "FINALIZED" if decision else "PENDING_REVIEW",
            "final_class": decision.get("FINAL_CLASS", ""),
            "user_reason": decision.get("USER_REASON", ""),
            "review_action": decision.get("REVIEW_ACTION", ""),
            "review_date": decision.get("REVIEW_DATE", ""),
        })
    return {"records": records, "counts": {
        "pending": pending, "finalized": len(finalized), "undecided": undecided, "failed": failed,
    }}


def submit_review(results_file: Path, output_dir: Path, decision: ReviewDecision) -> tuple[dict, int]:
    reason = decision.user_reason.strip()
    if not reason:
        return {"error": "A reason is required for every final decision."}, 400
    data = get_review_data(results_file, output_dir)
    if "error" in data:
        return data, 400
    row = next((row for row in data["records"] if row["incident_id"] == decision.incident_id), None)
    if row is None or row["review_status"] != "PENDING_REVIEW":
        return {"error": "This incident is missing or already finalized. Reload the queue."}, 409
    if row["version"] != decision.version:
        return {"error": "The incident changed. Reload it before deciding."}, 409
    saved = row["input"] | row["result"] | {
        "FINAL_CLASS": decision.final_class,
        "USER_REASON": reason,
        "REVIEW_ACTION": review_action(row["result"]["classification"], decision.final_class),
        "REVIEW_DATE": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "STATUS": "FINALIZED",
    }
    ok, error = append_record(output_dir / "FINAL.csv", saved)
    if not ok:
        return {"error": error}, 409
    return {"message": "Final decision saved. The dashboard now includes this incident."}, 200


def get_dashboard_data(output_dir: Path) -> dict:
    # The dashboard reads FINAL.csv only; pending model results are never counted.
    rows, error = load_final(output_dir)
    if error:
        return {"error": error}
    counts = {"total": len(rows), "HSBC": 0, "SUPPLIER": 0,
              "CONFIRMED": 0, "CORRECTED": 0, "RESOLVED_UNDECIDED": 0}
    for row in rows:
        counts[row["FINAL_CLASS"]] += 1
        counts[row["REVIEW_ACTION"]] += 1
    percentages = {name: round(100 * counts[name] / len(rows), 1) if rows else 0 for name in ("HSBC", "SUPPLIER")}
    records = [{
        "incident_id": row["INCIDENT_ID"], "summary": row.get("INCIDENT_SHORT_DESCRIPTION", ""),
        "llm_class": row["classification"], "final_class": row["FINAL_CLASS"],
        "user_reason": row["USER_REASON"], "review_action": row["REVIEW_ACTION"],
        "review_date": row["REVIEW_DATE"],
    } for row in rows]
    return {"records": records, "counts": counts, "percentages": percentages}
