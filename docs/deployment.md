# Run locally

Install requirements once from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Prepare RAW.csv into CLEAN.csv, then classify CLEAN.csv into LLM_OUTPUT.csv:

```powershell
.\.venv\Scripts\python.exe -m app.data_preparation.pipeline
.\.venv\Scripts\python.exe -m app.llm.pipeline
```

Set INPUT_FILE and CLEAN_FILE in app/data_preparation/pipeline.py, and INPUT_FILE and OUTPUT_FILE in app/llm/pipeline.py. The source CSV must match fields/columns.yaml. Configure .env before the LLM step. Preparation makes no model calls. Existing output CSVs are preserved; use a new output folder for a new batch.

After classification, start review in one terminal:

```powershell
.\run_review_app.ps1
```

Open http://127.0.0.1:8765/. Users confirm or change the LLM decision, give a reason, and save to FINAL.csv.

Start the dashboard in another terminal:

```powershell
.\run_dashboard_app.ps1
```

Open http://127.0.0.1:8766/. This independent app reads FINAL.csv only and shows three counts and a small table. Set FINAL_FILE in app/dashboard_app.py if using a different batch folder. It works without the review process or LLM_OUTPUT.csv. Click Refresh to reload saved decisions.

Both apps make no model calls. Run one worker per app, keep output CSVs closed in Excel, and stop each app with Ctrl+C in its terminal. The target is Python 3.11; the existing virtual environment is Python 3.14.
