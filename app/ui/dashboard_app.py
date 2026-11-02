import csv
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.classification_review import (
    REVIEW_COLUMNS, REVIEW_FILE, REVIEW_LOCK, SUPPLIERS_FILE,
    classification_is_approved, load_reviewed_rows, ready_for_linking,
    save_review, supplier_options,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = ROOT / "data/run/LLM_OUTPUT.csv"
app = FastAPI(title="HSBC Incident Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = RESULTS_FILE
app.state.review_file = REVIEW_FILE
app.state.suppliers_file = SUPPLIERS_FILE
app.state.demo = False


class ClassificationReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    INCIDENT_ID: str = Field(min_length=1, strict=True)
    version: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    target: Literal["classification", "supplier"]
    decision: Literal["approved", "corrected", "needs_review"]
    classification: Literal["", "HSBC", "SUPPLIER"] = ""
    supplier_name: str = Field(default="", strict=True)
    reason: str = Field(default="", max_length=2000, strict=True)


def read_evidence_columns(row):
    names = []
    for column in ("evidence_column", "supporting_evidence"):
        if column in row:
            for value in (row[column] or "").split(","):
                name = value.strip()
                if name:
                    names.append(name)
            return names

    # Read older numbered columns without rewriting the saved file.
    for column, value in row.items():
        if column.startswith("evidence_") and column.endswith("_column") and value:
            names.append(value)
    return names


def get_dashboard_data(path, review_path=None, suppliers_path=None):
    rows = []
    try:
        if review_path is not None:
            rows = load_reviewed_rows(path, review_path)
        elif path.exists():
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
        counts = {"total": 0, "HSBC": 0, "SUPPLIER": 0, "UNCERTAIN": 0, "failed": 0}
        records = []
        for row in rows:
            status = row["processing_status"]
            if status not in ("success", "failed"):
                return {"error": "LLM_OUTPUT.csv contains an invalid processing status."}
            classification = row.get("classification", "")
            if status == "success":
                if classification not in ("HSBC", "SUPPLIER", "UNCERTAIN"):
                    return {"error": "Classification must be HSBC, SUPPLIER, or UNCERTAIN."}
                counts[classification] += 1
                counts["total"] += 1
            else:
                counts["failed"] += 1
            record = {
                "incident_id": row["INCIDENT_ID"],
                "summary": row.get("INCIDENT_SHORT_DESCRIPTION", ""),
                "classification": classification,
                "processing_status": status,
                "error": row.get("error", ""),
                "input": {name: value for name, value in row.items() if name.isupper()},
                "evidence_column": read_evidence_columns(row),
            }
            for name in ("key_root_cause", "decision_rationale", "attribution_evidence_strength", "supplier_name",
                         "supplier_product_or_service", "supplier_action_or_failure",
                         "supplier_causal_explanation", "supplier_accountability_reason", "supplier_more_info"):
                record[name] = row.get(name, "")
            if review_path is not None:
                record["review"] = {name: row[name] for name in REVIEW_COLUMNS}
                record["review"]["review_version"] = row["review_version"]
                record["review"]["review_stale"] = row["review_stale"]
            records.append(record)
        data = {"records": records, "counts": counts}
        if review_path is not None:
            names, note = supplier_options(suppliers_path or SUPPLIERS_FILE)
            data["supplier_names"] = names
            data["supplier_catalog_note"] = note
            approved = sum(classification_is_approved(row) for row in rows)
            data["review_counts"] = {
                "classification_approved": approved,
                "classification_pending": len(rows) - approved,
                "supplier_pending": sum(classification_is_approved(row) and row["reviewed_classification"] == "SUPPLIER" and not ready_for_linking(row) for row in rows),
                "ready_for_linking": sum(ready_for_linking(row) for row in rows),
            }
        return data
    except ValueError as error:
        return {"error": str(error)}
    except (OSError, UnicodeError, csv.Error, KeyError, TypeError):
        return {"error": "Could not read LLM_OUTPUT.csv. Check its columns and UTF-8 encoding, or generate a new batch with supplier details."}


@app.middleware("http")
async def local_requests(request: Request, call_next):
    host = request.headers.get("host")
    if host not in ("127.0.0.1:8766", "localhost:8766"):
        return JSONResponse({"error": "Use http://127.0.0.1:8766."}, status_code=403)
    if request.method == "POST":
        if request.headers.get("origin") != f"http://{host}":
            return JSONResponse({"error": "Review changes must come from this local dashboard."}, status_code=403)
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            return JSONResponse({"error": "Review changes require application/json."}, status_code=415)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    return JSONResponse({"error": "Invalid review request. Supply an incident, decision, reason, and current review version."}, status_code=422)


@app.get("/")
def dashboard_page():
    return FileResponse(ROOT / "frontend/dashboard/index.html")


@app.get("/api/dashboard")
def dashboard_data():
    with REVIEW_LOCK:
        data = get_dashboard_data(app.state.results_file, app.state.review_file, app.state.suppliers_file)
    data["demo"] = app.state.demo
    status = 400 if "error" in data else 200
    return JSONResponse(data, status_code=status)


@app.post("/api/classification-review")
def save_classification_review(decision: ClassificationReviewDecision):
    try:
        save_review(app.state.results_file, app.state.review_file, app.state.suppliers_file, decision)
    except ValueError as error:
        status = 409 if "changed after you opened" in str(error) else 422
        return JSONResponse({"error": str(error)}, status_code=status)
    except (OSError, UnicodeError, csv.Error):
        return JSONResponse({"error": "Could not save CLASSIFICATION_REVIEW.csv. Check the file and refresh before retrying."}, status_code=400)
    return dashboard_data()


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
