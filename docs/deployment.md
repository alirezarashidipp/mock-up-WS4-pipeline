# Local demo

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_pipeline.ps1
.\run_frontend.ps1
```

Configure .env and a source CSV matching fields/columns.yaml before the first command. The pipeline makes model calls and writes CLEAN.csv and LLM_OUTPUT.csv. Wait for it to finish, then start the frontend. Open http://127.0.0.1:8765/ for review and http://127.0.0.1:8765/dashboard for finalized decisions. The frontend makes no model calls. The dashboard is initially empty until the user saves a decision.

For a manual real model run, configure .env and set INPUT_FILE and OUTPUT_FILE in app/main.py:

```powershell
.\run_pipeline.ps1
.\run_frontend.ps1
```

The default raw input is data/mockup/RAW.csv; outputs go in data/run/. A new run creates CLEAN.csv and LLM_OUTPUT.csv. Existing batch outputs are preserved; choose a new output folder for another batch. Review and dashboard make no model calls.

The provider, model/deployment, temperature, credentials, and optional proxy settings are described in .env.example and README.md. Stop and restart the pipeline after changing them.

Run one worker locally and finish classification before review. Stop with Ctrl+C. The target is Python 3.11; the existing virtual environment is Python 3.14. Offline checks use mocked model responses.
