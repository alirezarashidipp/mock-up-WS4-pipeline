from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.review_store import get_dashboard_data


ROOT = Path(__file__).resolve().parent.parent
FINAL_FILE = ROOT / "data/run/FINAL.csv"
app = FastAPI(title="HSBC Final Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
app.state.output_dir = FINAL_FILE.parent
app.state.demo = False


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
    return FileResponse(ROOT / "frontend/dashboard.html")


@app.get("/api/dashboard")
def dashboard_data():
    data = get_dashboard_data(app.state.output_dir)
    data["demo"] = app.state.demo
    status = 400 if "error" in data else 200
    return JSONResponse(data, status_code=status)


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
