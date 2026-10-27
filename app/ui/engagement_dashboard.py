import csv
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = ROOT / "data/run/INC_LINKED.csv"
app = FastAPI(title="HSBC Engagement Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = RESULTS_FILE
app.state.demo = False


def get_engagement_data(path):
    rows = []
    try:
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                required = {"INCIDENT_ID", "link_status", "linked_engagement_id", "ENG_ENGAGEMENT_ID"}
                if reader.fieldnames and not required.issubset(reader.fieldnames):
                    return {"error": "INC_LINKED.csv is missing incident or engagement link columns."}
                rows = list(reader)
        groups = {}
        unlinked_groups = {"hsbc": [], "supplier": [], "other": []}
        companies = set()
        counts = {"engagements": 0, "companies": 0, "linked_incidents": 0, "unlinked_incidents": 0}
        for row in rows:
            if None in row:
                return {"error": "INC_LINKED.csv has a row with more values than columns."}
            row = {name: value or "" for name, value in row.items()}
            status = row["link_status"]
            if status in ("UNDECIDED", "NOT_APPLICABLE", "SKIPPED", "FAILED"):
                if status == "NOT_APPLICABLE" and row.get("classification") == "HSBC":
                    unlinked_groups["hsbc"].append(row)
                elif status == "UNDECIDED" and row.get("classification") == "SUPPLIER":
                    unlinked_groups["supplier"].append(row)
                else:
                    unlinked_groups["other"].append(row)
                counts["unlinked_incidents"] += 1
                continue
            if status != "MATCHED":
                return {"error": "INC_LINKED.csv contains an invalid link status."}
            engagement_id = row["linked_engagement_id"]
            if not engagement_id.strip() or engagement_id != row["ENG_ENGAGEMENT_ID"] or not row["INCIDENT_ID"].strip():
                return {"error": "A matched row has missing or inconsistent incident/engagement identifiers."}
            if engagement_id not in groups:
                fields = {name[4:]: value for name, value in row.items() if name.startswith("ENG_")}
                company = fields.get("THIRD_PARTY_NAME") or fields.get("THIRD_PARTY_NORMALISED_NAME") or ""
                groups[engagement_id] = {
                    "engagement_id": engagement_id,
                    "name": fields.get("ENGAGEMENT_NAME") or engagement_id,
                    "company": company or "Unknown company",
                    "fields": fields,
                    "incidents": [],
                }
                if company.strip():
                    companies.add(company.strip().casefold())
            groups[engagement_id]["incidents"].append(row)
            counts["linked_incidents"] += 1
        engagements = sorted(groups.values(), key=lambda group: (group["company"].casefold(), group["name"].casefold()))
        counts["engagements"] = len(engagements)
        counts["companies"] = len(companies)
        counts["hsbc_incidents"] = len(unlinked_groups["hsbc"])
        counts["supplier_unlinked_incidents"] = len(unlinked_groups["supplier"])
        counts["other_unlinked_incidents"] = len(unlinked_groups["other"])
        return {"engagements": engagements, "unlinked_groups": unlinked_groups, "counts": counts}
    except (OSError, UnicodeError, csv.Error, KeyError, TypeError):
        return {"error": "Could not read INC_LINKED.csv. Check its columns and UTF-8 encoding."}


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if request.headers.get("host") not in ("127.0.0.1:8767", "localhost:8767"):
        return JSONResponse({"error": "Use http://127.0.0.1:8767."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.get("/")
def dashboard_page():
    return FileResponse(ROOT / "frontend/engagements/index.html")


@app.get("/api/engagements")
def engagement_data():
    data = get_engagement_data(app.state.results_file)
    data["demo"] = app.state.demo
    status = 400 if "error" in data else 200
    return JSONResponse(data, status_code=status)


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8767, access_log=False)
