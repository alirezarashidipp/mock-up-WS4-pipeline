from threading import Lock

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.llm.pipeline import OUTPUT_FILE, ROOT
from app.ui.review_store import ReviewDecision, get_review_data, submit_review


app = FastAPI(title="HSBC Incident Review", docs_url=None, redoc_url=None, openapi_url=None)
app.state.results_file = OUTPUT_FILE
app.state.output_dir = OUTPUT_FILE.parent
app.state.demo = False
review_lock = Lock()  # One local worker serializes CSV writes.


@app.middleware("http")
async def local_requests(request: Request, call_next):
    host = request.headers.get("host")
    if host not in ("127.0.0.1:8765", "localhost:8765"):
        return JSONResponse({"error": "Use http://127.0.0.1:8765."}, status_code=403)
    if request.method == "POST":
        origin = request.headers.get("origin")
        local_origin = str(request.base_url).rstrip("/")
        if origin != local_origin:
            return JSONResponse({"error": "Submit decisions from this local application."}, status_code=403)
        content_type = request.headers.get("content-type", "").split(";")[0]
        if content_type != "application/json":
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
def review_page():
    return FileResponse(ROOT / "frontend/review/index.html")


@app.get("/api/review")
def review_data():
    with review_lock:
        data = get_review_data(app.state.results_file, app.state.output_dir)
    data["demo"] = app.state.demo
    status = 400 if "error" in data else 200
    return JSONResponse(data, status_code=status)


@app.post("/api/review")
def save_decision(decision: ReviewDecision):
    with review_lock:
        data, status = submit_review(app.state.results_file, app.state.output_dir, decision)
    return JSONResponse(data, status_code=status)


app.mount("/assets", StaticFiles(directory=ROOT / "frontend"), name="assets")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)
