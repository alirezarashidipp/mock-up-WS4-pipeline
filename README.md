# HSBC Incident Classification Demo

A small Python 3.11 mock-up with CSV storage, structured LLM responses, and two independent FastAPI screens.

```text
RAW.csv -> Read -> Rename -> Clean -> CLEAN.csv
CLEAN.csv + Definitions + Prompt -> LLM (one row per request) -> LLM_OUTPUT.csv
LLM_OUTPUT.csv -> User review -> FINAL.csv
FINAL.csv -> Independent dashboard
```

## Setup

Run every command from the project root in a terminal. Commands call the virtual environment's Python directly.

Create the environment once (skip the first command if `.venv` already exists):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Place your UTF-8 source CSV at `data/mockup/RAW.csv`.
- Create `.env` using [.env.example](.env.example) if it does not already exist. Keep credentials local.
- Select `LLM_PROVIDER=openai` or `azure` and fill the corresponding settings. `LLM_TEMPERATURE` is optional; leave it blank for the model default.
- Names: [fields/columns.yaml](fields/columns.yaml). Short definitions: [fields/definitions.yml](fields/definitions.yml). Instructions: [prompts/classification.yml](prompts/classification.yml).

## Run in this order

### 1. Prepare the source data

```powershell
.\.venv\Scripts\python.exe -m app.data_preparation.pipeline
```

Reads `data/mockup/RAW.csv`, renames columns, cleans values, and saves `data/run/CLEAN.csv`. Wait for completion before step 2.

### 2. Send each cleaned row to the LLM

```powershell
.\.venv\Scripts\python.exe -m app.llm.pipeline
```

Reads `CLEAN.csv`, sends one row per request with definitions and prompt, and saves inputs and responses to `data/run/LLM_OUTPUT.csv`. Wait for completion before step 3.

`app/llm/save_csv.py` saves each result immediately. CSV cells contain plain source values, model fields and separate evidence column/quote pairs, without JSON blobs. Definitions stay in `fields/definitions.yml`; review reads them from that file.

### 3. Start the review frontend

```powershell
.\.venv\Scripts\python.exe -m app.ui.review_app
```

Open [Review UI](http://127.0.0.1:8765/). Choose the final class, enter a reason, and save. The first successful decision creates `data/run/FINAL.csv`. Keep this terminal open.

### 4. Start the dashboard in a second terminal

```powershell
.\.venv\Scripts\python.exe -m app.ui.dashboard_app
```

Open [Dashboard](http://127.0.0.1:8766/). It reads `FINAL.csv` only; click Refresh after saving reviews. It can run independently and shows an empty view until final decisions exist. Stop either UI with Ctrl+C in its terminal.

All model outcomes (`HSBC`, `SUPPLIER`, `UNDECIDED`) await a user's final class and reason. FINAL.csv preserves the original result plus the user decision and UTC date. Neither UI calls the model; the dashboard needs no other process running.

Frontend files are separate: `frontend/review/` and `frontend/dashboard/`. Both use the shared `frontend/style.css` and logo artwork in `frontend/pictures/`.

Existing batch outputs are preserved. Move earlier outputs aside or configure a new batch folder before rerunning the pipelines. CSV files and credentials are excluded from Git.

## Stage documentation

- [Data preparation](docs/data_preparation.md)
- [LLM requests and output](docs/llm.md)
- [Review and final decisions](docs/review_app.md)
- [Independent dashboard](docs/dashboard_app.md)

AI agents: follow [AGENTS.md](AGENTS.md) and read the relevant stage document before changing code.

## Simple tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_frontend.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_python.py -v
```

Frontend tests check page controls and asset paths offline; they do not run a browser. Python tests use temporary CSVs and simulated LLM responses. No API key, network connection, or extra test dependency is required.

To check the real LLM connection configured in `.env`, run this separately:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

It asks `What is capital of India?`, prints the answer, and checks that the response is nonempty. It makes a live API request using the selected provider and may incur usage charges. Ordinary test discovery (`test*.py`) skips this live check.
