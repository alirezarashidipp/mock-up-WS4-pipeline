# HSBC Incident Classification Demo

A small Python 3.11 mock-up with CSV storage, structured LLM responses, and two independent FastAPI screens.

```text
RAW.csv -> Read -> Rename -> Clean -> CLEAN.csv
CLEAN.csv + Definitions + Prompt -> LLM (one row per request) -> LLM_OUTPUT.csv
LLM_OUTPUT.csv -> User review -> FINAL.csv
FINAL.csv -> Independent dashboard
```

## Setup

Run from the project root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Place your UTF-8 source CSV at `data/mockup/RAW.csv`.
- Create `.env` using [.env.example](.env.example) if it does not already exist. Keep credentials local.
- Select `LLM_PROVIDER=openai` or `azure` and fill the corresponding settings. `LLM_TEMPERATURE` is optional; leave it blank for the model default.
- Names: [fields/columns.yaml](fields/columns.yaml). Short definitions: [fields/definitions.yml](fields/definitions.yml). Instructions: [prompts/classification.yml](prompts/classification.yml).

## Run

| Step | PowerShell command | Result |
| --- | --- | --- |
| 1. Prepare | `.\.venv\Scripts\python.exe -m app.data_preparation.pipeline` | `data/run/CLEAN.csv` |
| 2. Classify | `.\.venv\Scripts\python.exe -m app.llm.pipeline` | `data/run/LLM_OUTPUT.csv`, including inputs and model results |
| 3. Review | `.\.venv\Scripts\python.exe -m app.ui.review_app` | [Review UI](http://127.0.0.1:8765/); user decisions saved to `data/run/FINAL.csv` |
| 4. Dashboard | `.\.venv\Scripts\python.exe -m app.ui.dashboard_app` | [Dashboard](http://127.0.0.1:8766/); reads `FINAL.csv` only |

Finish classification before reviewing. Run each UI in its own terminal; stop with Ctrl+C. Refresh the dashboard to reread FINAL.csv.

All model outcomes (`HSBC`, `SUPPLIER`, `UNDECIDED`) await a user's final class and reason. FINAL.csv preserves the original result plus the user decision and UTC date. Neither UI calls the model; the dashboard needs no other process running.

Frontend files are separate: `frontend/review/` and `frontend/dashboard/`. Both use the shared `frontend/style.css` and logo artwork in `frontend/pictures/`.

Existing batch outputs are preserved. Move earlier outputs aside or configure a new batch folder before rerunning the pipelines. CSV files and credentials are excluded from Git.

## Stage documentation

- [Data preparation](docs/data_preparation.md)
- [LLM requests and output](docs/llm.md)
- [Review and final decisions](docs/review_app.md)
- [Independent dashboard](docs/dashboard_app.md)

AI agents: follow [AGENTS.md](AGENTS.md) and read the relevant stage document before changing code.
