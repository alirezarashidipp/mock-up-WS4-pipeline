import argparse
from contextlib import asynccontextmanager
from threading import Lock

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app.main import OUTPUT_FILE, ROOT
from app.review_store import ReviewDecision, get_review_data, submit_review, sync_human_review


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app.state.results_file.exists():
        app.state.sync_error = sync_human_review(app.state.results_file, app.state.output_dir).get("error")
    yield


app = FastAPI(title="HSBC Incident Review", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = OUTPUT_FILE
app.state.output_dir = OUTPUT_FILE.parent
app.state.demo = False
app.state.sync_error = None
review_lock = Lock()  # One local worker serializes CSV writes.


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if request.headers.get("host") not in ("127.0.0.1:8765", "localhost:8765"):
        return JSONResponse({"error": "Use http://127.0.0.1:8765."}, status_code=403)
    if request.method == "POST":
        if request.headers.get("origin") != str(request.base_url).rstrip("/"):
            return JSONResponse({"error": "Submit decisions from this local application."}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"error": "Expected JSON."}, status_code=415)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.exception_handler(OSError)
async def save_error(request: Request, error: OSError):
    return JSONResponse({"error": "Could not access the CSV files. Close them in Excel and reload."}, status_code=500)


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend/index.html")


@app.get("/style.css")
def stylesheet():
    return FileResponse(ROOT / "frontend/style.css")


@app.get("/app.js")
def javascript():
    return FileResponse(ROOT / "frontend/app.js")


@app.get("/api/review")
def review_data():
    with review_lock:
        data = {"error": app.state.sync_error} if app.state.sync_error else get_review_data(app.state.results_file, app.state.output_dir)
    return JSONResponse({"demo": app.state.demo, **data}, status_code=400 if "error" in data else 200)


@app.post("/api/reload")
def reload_data():
    with review_lock:
        synced = sync_human_review(app.state.results_file, app.state.output_dir)
        app.state.sync_error = synced.get("error")
        data = synced if "error" in synced else get_review_data(app.state.results_file, app.state.output_dir)
    return JSONResponse({"demo": app.state.demo, **data}, status_code=400 if "error" in data else 200)


@app.post("/api/review")
def save_decision(decision: ReviewDecision):
    with review_lock:
        data, status = submit_review(app.state.results_file, app.state.output_dir, decision)
    return JSONResponse(data, status_code=status)


def main():
    parser = argparse.ArgumentParser(description="Review a manually generated classification CSV.")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        app.state.results_file = ROOT / "data/mockup/LLM_OUTPUT.csv"
        app.state.output_dir = ROOT / "data/mockup"
        app.state.demo = True
    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)


if __name__ == "__main__":
    main()
