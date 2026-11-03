"""The single incident dashboard: inspect proposals and review three ordered steps."""

import csv
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.incidents import (
    ENGAGEMENT_FILE, RESULTS_FILE, SUPPLIERS_FILE,
    get_incident, read_incidents, row_version, source_fields,
)
from app.linking.candidates import explain_candidate_match, find_candidates, normalize_name
from app.linking.linking import catalog_hash, read_engagements
from app.review import (
    classification_complete, effective_classification, effective_supplier_name,
    normalize_supplier_search, read_supplier_catalog, refresh_engagements, review_complete,
    save_review, search_supplier_catalog, supplier_complete,
)


ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="HSBC Incident Review", docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = RESULTS_FILE
app.state.suppliers_file = SUPPLIERS_FILE
app.state.engagements_file = ENGAGEMENT_FILE
app.state.demo = False


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(min_length=1, strict=True)
    version: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    target: Literal["classification", "supplier", "engagement"]
    decision: Literal["approved", "disagree"]
    classification: Literal["", "HSBC", "SUPPLIER", "UNCERTAIN"] = ""
    supplier_name: str = Field(default="", strict=True)
    engagement_id: str = Field(default="", strict=True)
    reason: str = Field(default="", max_length=2000, strict=True)


class RefreshLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


def read_evidence_columns(row):
    return [name.strip() for name in row.get("evidence_column", "").split(",") if name.strip()]


def next_action(row):
    """Describe the first unfinished stage without changing review decisions."""
    if row["processing_status"] == "pending":
        stage = "processing"
        title = "Await incident processing"
        description = "Classification has not completed. Human review will unlock afterwards."
    elif not classification_complete(row):
        stage = "classification"
        title = "Review classification"
        description = "Approve the model class, or choose a corrected class and explain why."
        if row["processing_status"] == "failed":
            title = "Resolve classification"
            description = "Processing failed. Choose HSBC or Supplier with a reason to resolve it manually."
        elif effective_classification(row) == "UNCERTAIN":
            title = "Resolve uncertain classification"
            description = "Choose HSBC or Supplier with a reason. Later steps remain locked."
    elif review_complete(row):
        stage = "complete"
        title = "Review complete"
        if row["reviewed_classification"] == "HSBC":
            description = "HSBC classification is reviewed. Supplier and engagement review are not applicable."
        elif row["reviewed_engagement_id"]:
            description = "Classification, supplier name and the selected engagement have been reviewed."
        else:
            description = "Review is complete without an accepted engagement."
    elif not supplier_complete(row):
        stage = "supplier"
        title = "Review supplier name"
        description = "Approve the usable model name, or choose a catalog base name with a reason."
    else:
        stage = "engagement"
        title = "Review engagement"
        description = "Explicitly approve a proposal, or choose another match or no link with a reason."
        if row["link_status"] == "RUNNING":
            title = "Await engagement suggestions"
            description = "Engagement finding is running. Wait for it to finish before deciding."
        elif row["link_status"] in ("PENDING", "FAILED"):
            title = "Find engagements"
            description = "Run or retry engagement finding. If a current lookup is available, you can also review its matches manually with a reason."
    return {"stage": stage, "title": title, "description": description}


def overview_text(counts):
    return (
        f"Saved incidents: {counts['total']}. "
        f"Successfully classified: {counts['classified']}; "
        f"awaiting processing: {counts['pending']}; "
        f"processing failures: {counts['failed']}. "
        f"Reviews remaining: {counts['review_pending']}. "
        f"Human-confirmed links: {counts['human_linked']}."
    )


def describe_incident(row):
    """Add the display fields needed for one incident card."""
    incident = dict(row)
    incident.update(
        incident_id=row["INCIDENT_ID"],
        summary=row.get("INCIDENT_SHORT_DESCRIPTION", ""),
        review_version=row_version(row),
        effective_classification=effective_classification(row),
        effective_supplier_name=effective_supplier_name(row),
        classification_complete=classification_complete(row),
        supplier_complete=supplier_complete(row),
        review_complete=review_complete(row),
        next_action=next_action(row),
        input_fields=[{"name": name, "value": value} for name, value in source_fields(row).items()],
        evidence_column=read_evidence_columns(row),
    )
    return incident


def count_incidents(incidents):
    """Count original model results and the current review state separately."""
    counts = {
        "total": len(incidents),
        "classified": 0,
        "HSBC": 0,
        "SUPPLIER": 0,
        "UNCERTAIN": 0,
        "failed": 0,
        "pending": 0,
        "review_pending": 0,
        "review_complete": 0,
        "human_linked": 0,
    }
    for target in ("classification", "supplier", "engagement"):
        for status in ("approved", "disagree", "pending", "not_applicable"):
            counts[f"{target}_{status}"] = 0
    bottlenecks = {stage: 0 for stage in ("processing", "classification", "supplier", "engagement", "complete")}

    for incident in incidents:
        if incident["processing_status"] == "success":
            counts["classified"] += 1
            counts[incident["classification"]] += 1
        else:
            counts[incident["processing_status"]] += 1

        if incident["review_complete"]:
            counts["review_complete"] += 1
            if incident["reviewed_engagement_id"]:
                counts["human_linked"] += 1
        else:
            counts["review_pending"] += 1

        for target in ("classification", "supplier", "engagement"):
            status = incident[target + "_review_status"]
            counts[f"{target}_{status}"] += 1
        stage = incident["next_action"]["stage"]
        bottlenecks[stage] += 1
    return counts, bottlenecks


def get_dashboard_data(path=RESULTS_FILE, suppliers_path=SUPPLIERS_FILE, engagements_path=ENGAGEMENT_FILE):
    rows = read_incidents(path)
    suppliers, supplier_note = read_supplier_catalog(suppliers_path)
    countries = {}
    for supplier in suppliers:
        for country in supplier["countries"]:
            countries.setdefault(normalize_supplier_search(country), country)
    engagement_note = ""
    try:
        read_engagements(engagements_path)
    except (OSError, UnicodeError, csv.Error, ValueError):
        engagement_note = "ENG_ALL.csv is missing or invalid. Engagement suggestions and approval require the catalog."

    incidents = [describe_incident(row) for row in rows]
    counts, bottlenecks = count_incidents(incidents)
    return {
        "incidents": incidents,
        "counts": counts,
        "supplier_catalog_count": len(suppliers),
        "supplier_countries": sorted(countries.values(), key=str.casefold),
        "overview": overview_text(counts),
        "bottlenecks": bottlenecks,
        "supplier_catalog_note": supplier_note,
        "engagement_catalog_note": engagement_note,
        "error": "",
        "demo": False,
    }


def engagement_data(row):
    engagements = read_engagements(app.state.engagements_file)
    name = row["link_supplier_name"] or effective_supplier_name(row)
    matches = find_candidates(name, engagements, None)
    normalized_name = normalize_name(name)
    explanations = []
    for engagement in matches:
        explanation = explain_candidate_match(normalized_name, engagement)
        explanation["engagement_id"] = engagement["ENGAGEMENT_ID"]
        explanations.append(explanation)
    by_id = {engagement["ENGAGEMENT_ID"]: engagement for engagement in matches}
    suggestions = []
    for number in range(1, 6):
        prefix = f"link_{number}_"
        engagement_id = row[prefix + "engagement_id"]
        if engagement_id:
            suggestions.append({
                "engagement_id": engagement_id,
                "reason": row[prefix + "reason"],
                "evidence_strength": row[prefix + "evidence_strength"],
                "engagement": by_id.get(engagement_id, {}),
            })
    stale = bool(row["link_catalog_hash"] and row["link_catalog_hash"] != catalog_hash(engagements))
    return {"review_version": row_version(row), "matches": matches, "suggestions": suggestions,
            "selected_engagement_id": row["linked_engagement_id"],
            "reviewed_engagement_id": row["reviewed_engagement_id"], "link_stale": stale,
            "match_count": len(matches), "candidate_count": row["link_candidate_count"],
            "suggestion_count": len(suggestions), "supplier_name": name,
            "matching_explanation": {"supplier_name": name, "normalized_supplier_name": normalized_name,
                                     "matches": explanations},
            "saved_engagement": {key[4:]: value for key, value in row.items() if key.startswith("ENG_")}, "error": ""}


def error_response(error):
    if isinstance(error, ValueError):
        status = 409 if "changed after you opened" in str(error) else 422
        return JSONResponse({"error": str(error)}, status_code=status)
    return JSONResponse({"error": "Could not read or save the incident files. Check UTF-8 CSV structure and file access, then refresh."}, status_code=400)


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
    if request.url.path == "/api/suppliers":
        return JSONResponse({"error": "Supplier search requires a query up to 200 characters, a country up to 100 characters, and a nonnegative offset."}, status_code=422)
    return JSONResponse({"error": "Invalid review request. Supply a decision and the current incident version."}, status_code=422)


@app.get("/")
def dashboard_page():
    return FileResponse(ROOT / "frontend/dashboard/index.html")


@app.get("/api/dashboard")
def dashboard_data():
    try:
        data = get_dashboard_data(app.state.results_file, app.state.suppliers_file, app.state.engagements_file)
        data["demo"] = app.state.demo
        return JSONResponse(data)
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        return error_response(error)


@app.get("/api/incidents/{incident_id}/engagements")
def incident_engagements(incident_id: str):
    try:
        row = get_incident(app.state.results_file, incident_id)
        return JSONResponse(engagement_data(row))
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        return error_response(error)


@app.get("/api/suppliers")
def supplier_search(
    q: str = Query(default="", max_length=200),
    country: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0),
):
    suppliers, note = read_supplier_catalog(app.state.suppliers_file)
    if note:
        return JSONResponse({"error": note}, status_code=422)
    return JSONResponse(search_supplier_catalog(suppliers, q, country, offset))


@app.post("/api/review")
def review_incident(decision: ReviewDecision):
    try:
        save_review(
            decision, app.state.results_file, app.state.suppliers_file, app.state.engagements_file
        )
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        return error_response(error)
    return dashboard_data()


@app.post("/api/incidents/{incident_id}/refresh-links")
def rerun_links(incident_id: str, request: RefreshLinks):
    try:
        row = get_incident(app.state.results_file, incident_id, request.version)
        refresh_engagements(row, app.state.results_file, app.state.engagements_file)
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        return error_response(error)
    return dashboard_data()


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
