import csv
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.csv_files import write_records
from app.human_review.pipeline import OUTPUT_FILE, REVIEW_LOCK, apply_review, read_rows, review_version
from app.ui.engagement_dashboard import group_engagements


ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = ROOT / "data/mockup/ENG_ALL.csv"
app = FastAPI(title="HSBC Human Review", docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = OUTPUT_FILE
app.state.catalog_file = CATALOG_FILE
app.state.demo = False


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    INCIDENT_ID: str = Field(min_length=1, strict=True)
    target: Literal["classification", "link"]
    decision: Literal["confirmed", "rejected"]
    reason: str = Field(max_length=2000, strict=True)
    version: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


def count_reviews(rows):
    counts = {
        "review_classification_confirmed": 0,
        "review_classification_pending": 0,
        "review_classification_rejected": 0,
        "review_classification_not_applicable": 0,
        "review_link_confirmed": 0,
        "review_link_pending": 0,
        "review_link_rejected": 0,
        "review_link_invalidated": 0,
        "review_link_not_applicable": 0,
    }
    for row in rows:
        classification_status = row["hitl_classification"]
        link_status = row["hitl_link"]
        counts[f"review_classification_{classification_status}"] += 1
        counts[f"review_link_{link_status}"] += 1
    return counts


def read_engagement_catalog(path):
    if path is None:
        return [], "Only engagements referenced by saved model proposals are shown."
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, strict=True)
            columns = reader.fieldnames or []
            if "ENGAGEMENT_ID" not in columns or len(columns) != len(set(columns)):
                raise ValueError
            if any(not name.strip() for name in columns):
                raise ValueError
            rows = list(reader)
        identifiers = set()
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise ValueError
            engagement_id = row["ENGAGEMENT_ID"]
            if not engagement_id.strip() or engagement_id in identifiers:
                raise ValueError
            identifiers.add(engagement_id)
        return rows, "All ENG_ALL.csv engagements plus saved proposal IDs absent from the catalog. Saved proposal details are preserved."
    except FileNotFoundError:
        return [], "ENG_ALL.csv is missing. Only engagements referenced by saved model proposals are shown."
    except (OSError, UnicodeError, csv.Error, ValueError):
        return [], "ENG_ALL.csv could not be read or has invalid columns, rows, or IDs. Only saved model proposal engagements are shown."


def include_catalog_engagements(proposals, catalog):
    engagements = {item["engagement_id"]: item for item in proposals}
    for fields in catalog:
        engagement_id = fields["ENGAGEMENT_ID"]
        if engagement_id in engagements:
            continue
        company = fields.get("THIRD_PARTY_NAME") or fields.get("THIRD_PARTY_NORMALISED_NAME") or "Unknown company"
        engagements[engagement_id] = {
            "engagement_id": engagement_id,
            "name": fields.get("ENGAGEMENT_NAME") or engagement_id,
            "company": company,
            "fields": dict(fields),
            "incidents": [],
        }
    return sorted(engagements.values(), key=lambda item: (item["company"].casefold(), item["name"].casefold()))


def build_review_data(rows, catalog_file=None):
    incidents = []
    excluded_ids = set()
    for row in rows:
        incident = dict(row)
        incident["review_version"] = review_version(row)
        incidents.append(incident)
        if row["hitl_link"] in ("rejected", "invalidated"):
            excluded_ids.add(row["INCIDENT_ID"])
    data = group_engagements(incidents, excluded_ids)
    proposals = group_engagements(incidents)
    catalog, scope_note = read_engagement_catalog(catalog_file)
    data["all_incidents"] = incidents
    data["all_engagements"] = include_catalog_engagements(proposals["engagements"], catalog)
    data["engagement_scope_note"] = scope_note
    data["counts"].update(count_reviews(rows))
    supplier_linked = proposals["counts"]["linked_incidents"]
    data["counts"]["supplier_model_linked_incidents"] = supplier_linked
    data["counts"]["supplier_without_model_link_incidents"] = data["counts"]["eligible_incidents"] - supplier_linked
    data["counts"]["total_engagements"] = len(data["all_engagements"])
    data["human_review"] = True
    data["source_file"] = "HUMAN_REVIEW.csv"
    return data


def get_review_data(path, catalog_file=None):
    if not path.exists():
        return {"error": "HUMAN_REVIEW.csv is missing. Run python -m app.human_review.pipeline first.", "human_review": True}
    try:
        rows, _ = read_rows(path, reviewed=True)
        return build_review_data(rows, catalog_file)
    except ValueError as error:
        return {"error": str(error), "human_review": True}
    except (OSError, UnicodeError, csv.Error):
        return {"error": "Could not read HUMAN_REVIEW.csv. Check its columns and UTF-8 encoding.", "human_review": True}


def incident_route(data, incident_id):
    for group, incidents in data["unlinked_groups"].items():
        if any(row["INCIDENT_ID"] == incident_id for row in incidents):
            return "#" + urlencode({"view": "unlinked", "group": group, "incident": incident_id})
    for engagement in data["engagements"]:
        if any(row["INCIDENT_ID"] == incident_id for row in engagement["incidents"]):
            return "#" + urlencode({"engagement": engagement["engagement_id"], "incident": incident_id})
    return "#"


@app.middleware("http")
async def local_requests(request: Request, call_next):
    host = request.headers.get("host")
    if host not in ("127.0.0.1:8768", "localhost:8768"):
        return JSONResponse({"error": "Use http://127.0.0.1:8768."}, status_code=403)
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
    return FileResponse(ROOT / "frontend/engagements/index.html")


@app.get("/api/engagements")
def engagement_data():
    with REVIEW_LOCK:
        data = get_review_data(app.state.results_file, app.state.catalog_file)
    data["demo"] = app.state.demo
    return JSONResponse(data, status_code=400 if "error" in data else 200)


@app.post("/api/review")
def save_review(decision: ReviewDecision):
    with REVIEW_LOCK:
        try:
            rows, _ = read_rows(app.state.results_file, reviewed=True)
            for index, row in enumerate(rows):
                if row["INCIDENT_ID"] == decision.INCIDENT_ID:
                    break
            else:
                return JSONResponse({"error": "This incident is not in HUMAN_REVIEW.csv. Refresh the dashboard."}, status_code=404)
            if review_version(row) != decision.version:
                return JSONResponse({"error": "This incident changed after you opened it. Refresh before saving another decision."}, status_code=409)
            rows[index] = apply_review(row, decision.target, decision.decision, decision.reason)
            write_records(app.state.results_file, rows)
            data = build_review_data(rows, app.state.catalog_file)
            data["review_route"] = incident_route(data, decision.INCIDENT_ID)
            data["demo"] = app.state.demo
            return JSONResponse(data)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=422)
        except (OSError, UnicodeError, csv.Error):
            return JSONResponse({"error": "Could not save HUMAN_REVIEW.csv. Check the file and refresh before retrying."}, status_code=400)


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8768, access_log=False)
