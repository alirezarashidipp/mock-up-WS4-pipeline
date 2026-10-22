import csv
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = ROOT / "data/run/LLM_OUTPUT.csv"
app = FastAPI(title="HSBC Incident Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = RESULTS_FILE
app.state.demo = False


def get_dashboard_data(path):
    rows = []
    try:
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))

        counts = {"total": 0, "HSBC": 0, "SUPPLIER": 0, "failed": 0}
        records = []
        for row in rows:
            if row["processing_status"] == "failed":
                counts["failed"] += 1
                continue
            if row["processing_status"] != "success":
                return {"error": "LLM_OUTPUT.csv contains an invalid processing status."}
            classification = row["classification"]
            if classification not in ("HSBC", "SUPPLIER"):
                return {"error": "Classification must be HSBC or SUPPLIER. Generate new binary results."}
            record = {
                "incident_id": row["INCIDENT_ID"],
                "summary": row.get("INCIDENT_SHORT_DESCRIPTION", ""),
                "classification": classification,
                "input": {name: value for name, value in row.items() if name.isupper()},
                "supporting_evidence": [],
            }
            for name in ("key_root_cause", "decision_rationale", "llm_confidence", "supplier_name",
                         "supplier_product_or_service", "supplier_action_or_failure",
                         "supplier_causal_explanation", "supplier_accountability_reason", "supplier_more_info"):
                record[name] = row.get(name, "")
            for name, value in row.items():
                if name.startswith("evidence_") and name.endswith("_column") and value:
                    record["supporting_evidence"].append(value)
            records.append(record)
            counts[classification] += 1
        counts["total"] = len(records)
        return {"records": records, "counts": counts}
    except (OSError, UnicodeError, csv.Error, KeyError, TypeError):
        return {"error": "Could not read LLM_OUTPUT.csv. Check its columns and UTF-8 encoding, or generate a new batch with supplier details."}


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if request.headers.get("host") not in ("127.0.0.1:8766", "localhost:8766"):
        return JSONResponse({"error": "Use http://127.0.0.1:8766."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.get("/")
def dashboard_page():
    return FileResponse(ROOT / "frontend/dashboard/index.html")


@app.get("/api/dashboard")
def dashboard_data():
    data = get_dashboard_data(app.state.results_file)
    data["demo"] = app.state.demo
    status = 400 if "error" in data else 200
    return JSONResponse(data, status_code=status)


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
