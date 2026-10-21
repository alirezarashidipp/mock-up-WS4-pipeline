import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.csv_files import append_record, read_records
from app.llm.save_csv import COLUMNS, RESULT_COLUMNS
from app.models import Classification, InputField


FINAL_COLUMNS = {"FINAL_CLASS", "USER_REASON", "REVIEW_ACTION", "REVIEW_DATE", "STATUS"}


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    final_class: Literal["HSBC", "SUPPLIER"]
    user_reason: str = Field(min_length=1, max_length=2000)


def cleaned_values(row):
    metadata = set(COLUMNS) | FINAL_COLUMNS
    metadata.remove("INCIDENT_ID")
    return {name: value for name, value in row.items() if name not in metadata}


def read_input_fields(row, definitions):
    fields = []
    for name, value in cleaned_values(row).items():
        if name != "INCIDENT_ID":
            field = InputField(name=name, description=definitions[name], value=value)
            fields.append(field.model_dump())
    return fields


def read_evidence(row):
    evidence = []
    for number in range(1, 6):
        column = row[f"evidence_{number}_column"]
        quote = row[f"evidence_{number}_quote"]
        if column or quote:
            evidence.append({"column": column, "quote": quote})
    return evidence


def review_action(llm_class, final_class):
    if llm_class == "UNDECIDED":
        return "RESOLVED_UNDECIDED"
    if llm_class == final_class:
        return "CONFIRMED"
    return "CORRECTED"


def valid_result(row):
    values = {name: row[name] or None for name in RESULT_COLUMNS}
    values["supporting_evidence"] = read_evidence(row)
    result = Classification.model_validate(values)
    input_values = cleaned_values(row)
    del input_values["INCIDENT_ID"]
    if not row["llm_prompt"].strip():
        return False
    if result.classification == "UNDECIDED":
        if not (result.uncertainty_reason or "").strip():
            return False
    elif not result.supporting_evidence or result.uncertainty_reason is not None:
        return False
    for evidence in result.supporting_evidence:
        if not evidence.quote.strip() or evidence.quote not in input_values.get(evidence.column, ""):
            return False
    return True


def load_batch(results_file, output_dir):
    final_file = output_dir / "FINAL.csv"
    if results_file.resolve() == final_file.resolve():
        return [], [], "Model results and final decisions must be separate files."

    try:
        rows, error = read_records(results_file)
        if error:
            return [], [], error
        finalized, error = read_records(final_file, optional=True)
        if error:
            return [], [], error

        if not rows or not set(COLUMNS) <= set(rows[0]) or FINAL_COLUMNS & set(rows[0]):
            return [], [], "Generate a new LLM_OUTPUT.csv with separate evidence columns."
        for row in rows:
            if row["processing_status"] == "failed":
                continue
            if row["processing_status"] != "success" or not valid_result(row):
                return [], [], "A model result or its input snapshot is invalid."

        by_id = {row["INCIDENT_ID"]: row for row in rows}
        for saved in finalized:
            current = by_id.get(saved["INCIDENT_ID"])
            if current is None or set(saved) != set(current) | FINAL_COLUMNS:
                return [], [], "FINAL.csv belongs to a different batch."
            original = {name: saved[name] for name in current}
            if original != current or current["processing_status"] != "success":
                return [], [], "A finalized incident changed. Use a separate batch folder."
            if saved["STATUS"] != "FINALIZED" or saved["FINAL_CLASS"] not in ("HSBC", "SUPPLIER"):
                return [], [], "FINAL.csv contains an invalid final decision."
            if not saved["USER_REASON"].strip() or len(saved["USER_REASON"]) > 2000:
                return [], [], "Every final decision requires a user reason."
            date = datetime.fromisoformat(saved["REVIEW_DATE"].replace("Z", "+00:00"))
            action = review_action(current["classification"], saved["FINAL_CLASS"])
            if date.tzinfo is None or saved["REVIEW_ACTION"] != action:
                return [], [], "A final decision has an invalid date or review action."
    except (OSError, csv.Error, KeyError, TypeError, ValueError):
        return [], [], "Could not read or validate the review CSV files."
    return rows, finalized, ""


def row_version(row):
    contents = json.dumps(row, sort_keys=True)
    return hashlib.sha256(contents.encode()).hexdigest()


def get_review_data(results_file, output_dir):
    rows, finalized, error = load_batch(results_file, output_dir)
    if error:
        return {"error": error}
    definitions_file = Path(__file__).resolve().parents[2] / "fields/definitions.yml"
    try:
        definitions = yaml.safe_load(definitions_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return {"error": "Could not read fields/definitions.yml."}
    decisions = {row["INCIDENT_ID"]: row for row in finalized}
    records = []
    counts = {"pending": 0, "finalized": len(finalized), "undecided": 0, "failed": 0}
    for row in rows:
        if row["processing_status"] == "failed":
            counts["failed"] += 1
            continue
        decision = decisions.get(row["INCIDENT_ID"], {})
        if not decision:
            counts["pending"] += 1
            if row["classification"] == "UNDECIDED":
                counts["undecided"] += 1
        result = {name: row[name] for name in RESULT_COLUMNS}
        result["supporting_evidence"] = read_evidence(row)
        records.append({
            "incident_id": row["INCIDENT_ID"],
            "version": row_version(row),
            "input": cleaned_values(row),
            "model_input": read_input_fields(row, definitions),
            "prompt": row["llm_prompt"],
            "result": result,
            "review_status": "FINALIZED" if decision else "PENDING_REVIEW",
            "final_class": decision.get("FINAL_CLASS", ""),
            "user_reason": decision.get("USER_REASON", ""),
            "review_action": decision.get("REVIEW_ACTION", ""),
            "review_date": decision.get("REVIEW_DATE", ""),
        })
    return {"records": records, "counts": counts}


def submit_review(results_file, output_dir, decision):
    reason = decision.user_reason.strip()
    if not reason:
        return {"error": "A reason is required for every final decision."}, 400
    rows, finalized, error = load_batch(results_file, output_dir)
    if error:
        return {"error": error}, 400
    by_id = {row["INCIDENT_ID"]: row for row in rows}
    row = by_id.get(decision.incident_id)
    finalized_ids = {row["INCIDENT_ID"] for row in finalized}
    if row is None or row["processing_status"] != "success" or decision.incident_id in finalized_ids:
        return {"error": "This incident is missing or already finalized. Reload the queue."}, 409
    if row_version(row) != decision.version:
        return {"error": "The incident changed. Reload it before deciding."}, 409
    saved = dict(row)
    saved["FINAL_CLASS"] = decision.final_class
    saved["USER_REASON"] = reason
    saved["REVIEW_ACTION"] = review_action(row["classification"], decision.final_class)
    saved["REVIEW_DATE"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    saved["STATUS"] = "FINALIZED"
    ok, error = append_record(output_dir / "FINAL.csv", saved)
    if not ok:
        return {"error": error}, 409
    return {"message": "Final decision saved to FINAL.csv."}, 200
