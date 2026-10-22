# HSBC Incident Classification Demo

A small Python 3.11 mock-up with CSV storage, Pydantic responses, and a read-only HSBC dashboard.

```text
RAW.csv -> Read -> Rename -> Clean -> CLEAN.csv
CLEAN.csv + Definitions + Prompt -> LLM (one row per request) -> LLM_OUTPUT.csv
LLM_OUTPUT.csv -> Dashboard
```

The LLM tags each incident HSBC or SUPPLIER. For SUPPLIER it also extracts the supplier name, related product/service, action or failure, causal explanation, accountability reason, and evidence with source column names. Missing supplier facts are Unknown. The tag is a model assessment; weak evidence is stated in the rationale with low self-reported confidence.

## Setup

Run from the project root. Create the environment once; skip the first command if `.venv` exists:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Put a UTF-8 source CSV at `data/mockup/RAW.csv`.
- Create `.env` using [.env.example](.env.example) if absent. Select `LLM_PROVIDER=openai` or `azure` and fill that provider's settings. `LLM_TEMPERATURE` is optional.
- Configure [column names](fields/columns.yaml), [short definitions](fields/definitions.yml), and [classification instructions](prompts/classification.yml).

## Run in this order

1. Prepare data; wait for `data/run/CLEAN.csv`:

   ```powershell
   .\.venv\Scripts\python.exe -m app.data_preparation.pipeline
   ```

2. Classify rows; each response is saved immediately to `data/run/LLM_OUTPUT.csv`:

   ```powershell
   .\.venv\Scripts\python.exe -m app.llm.pipeline
   ```

3. Start the dashboard and open [http://127.0.0.1:8766/](http://127.0.0.1:8766/):

   ```powershell
   .\.venv\Scripts\python.exe -m app.ui.dashboard_app
   ```

The dashboard reads LLM_OUTPUT.csv only. Click Refresh to reread results; stop with Ctrl+C. There is no human approval step or new FINAL.csv. Existing CSVs from earlier versions remain untouched.

Preparation replaces CLEAN.csv on nonempty runs. LLM results append for new incident IDs; conflicting results for an existing ID are rejected. For an older output schema, configure a new output folder in `app/llm/pipeline.py` and update `RESULTS_FILE` in `app/ui/dashboard_app.py`. CSV cells contain plain values and numbered evidence pairs, without JSON blobs, prompt text, or definitions. CSVs and credentials stay out of Git.

## Documentation and tests

- [Data preparation](docs/data_preparation.md)
- [LLM classification and supplier extraction](docs/llm.md)
- [Dashboard](docs/dashboard_app.md)
- AI agents: follow [AGENTS.md](AGENTS.md) before changing code.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_frontend.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_python.py -v
```

These tests run offline with temporary CSVs and simulated LLM replies. Frontend checks cover assets and controls, not browser interaction. To make a real request using `.env`, run the separate connection check:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

It asks `What is capital of India?` and checks for a nonempty reply. Ordinary test discovery skips this live API call.
