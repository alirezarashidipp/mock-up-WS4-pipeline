from pathlib import Path

import yaml
from pydantic import ValidationError

from app.csv_files import read_records
from app.incidents import (
    RESULTS_FILE, ENGAGEMENT_FILE, engagement_values, initialize_incidents,
    read_incidents, row_version, save_incident, apply_link_result,
)
from app.llm.classification import PROMPT_FILE, classify_row, classification_values, validation_error_summary
from app.llm.llm_connection import llm_connection
from app.llm.prepare_fields import prepare_fields
from app.linking.linking import empty_link, find_engagements, load_max_candidates, read_engagements


ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = ROOT / "data/run/CLEAN.csv"
DEFINITIONS_FILE = ROOT / "fields/definitions.yml"


def run_llm_pipeline():
    rows, error = read_records(INPUT_FILE)
    if error:
        print(error)
        return 1
    definitions_text = DEFINITIONS_FILE.read_text(encoding="utf-8")
    definitions = yaml.safe_load(definitions_text)
    engagements = read_engagements(ENGAGEMENT_FILE)
    max_candidates = load_max_candidates()
    return classify_incidents(rows, definitions, RESULTS_FILE, engagements, max_candidates)


def classify_incidents(rows, definitions, output_file, engagements, max_candidates=70):
    if not rows:
        return 1
    missing = set(rows[0]) - {"INCIDENT_ID"} - definitions.keys()
    if missing:
        raise ValueError("Add field definitions before classification.")
    engagement_columns = list(engagements[0]) if engagements else []
    initialize_incidents(output_file, rows, engagement_columns)
    prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
    prompt = yaml.safe_load(prompt_text)["system"]

    with llm_connection() as (client, model):
        for source in rows:
            saved = read_incidents(output_file)
            row = next(item for item in saved if item["INCIDENT_ID"] == source["INCIDENT_ID"])
            # Never rerun model work over a human decision.
            if row["classification_review_status"] != "pending":
                continue

            if row["processing_status"] != "success":
                fields = prepare_fields(source, definitions)
                row = classify_and_save(client, model, fields, prompt, row, output_file)
                if row["processing_status"] == "failed":
                    print("Stopped after saving a failed classification. Rerun to retry.")
                    return 1

            if row["classification"] == "SUPPLIER" and row["link_status"] in ("PENDING", "RUNNING", "FAILED"):
                row = link_incident(row, engagements, output_file, max_candidates)
                if row["link_status"] == "FAILED":
                    print("Stopped after saving a failed linking request. Rerun or retry in the dashboard.")
                    return 1
            print(f"Saved incident {row['INCIDENT_ID']}")
    print(f"Output: {output_file}")
    return 0


def classify_and_save(client, model, fields, prompt, row, output_file):
    result = None
    error = ""
    try:
        result = classify_row(client, model, fields, prompt)
    except ValidationError as failure:
        error = validation_error_summary(failure)
    except Exception as failure:
        # Provider error text can contain credentials or incident data.
        error = type(failure).__name__

    version = row_version(row)
    row.update(classification_values(result, error))
    if result and result.classification == "HSBC":
        apply_link_result(row, empty_link(status="NOT_APPLICABLE", reason="HSBC has no supplier engagement."))
    elif result and result.classification == "UNCERTAIN":
        apply_link_result(row, empty_link(status="SKIPPED", reason="Resolve classification before supplier review."))
    return save_incident(output_file, row, version)


def link_incident(row, engagements, output_file, max_candidates):
    version = row_version(row)
    apply_link_result(row, empty_link(row["supplier_name"], "RUNNING"))
    row.update(engagement_values(row, engagements, ""))
    row = save_incident(output_file, row, version)
    version = row_version(row)
    proposal = find_engagements(row, engagements, row["supplier_name"], max_candidates)
    apply_link_result(row, proposal)
    row.update(engagement_values(row, engagements, row["linked_engagement_id"]))
    return save_incident(output_file, row, version)


if __name__ == "__main__":
    try:
        raise SystemExit(run_llm_pipeline())
    except Exception as error:
        print(f"Stopped: {type(error).__name__}. Earlier results are preserved.")
        raise SystemExit(1) from None
