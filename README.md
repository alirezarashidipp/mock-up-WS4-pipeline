# HSBC Incident Classification Demo

A small Python demo with plain functions, CSV storage, Pydantic, and an HSBC-themed FastAPI review screen.

## Flow

[View the workflow diagram](docs/architecture.md).

```text
RAW.csv -> Standardize names -> Clean special characters -> CLEAN.csv
CLEAN row + Prompt + Short column definitions -> LLM -> LLM_OUTPUT.csv
LLM_OUTPUT.csv -> User chooses HSBC / SUPPLIER and gives a reason -> FINAL.csv
FINAL.csv -> Simple dashboard
```

All three LLM outcomes remain pending until the user acts. The original LLM class is preserved, even when the user changes it. No separate HUMAN_REVIEW.csv is written.

## Four run commands

From the project root in PowerShell, use the existing .venv. Install requirements once if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

1. Prepare the data:

```powershell
.\.venv\Scripts\python.exe -m app.data_preparation.pipeline
```

This runs app/data_preparation/pipeline.py: read RAW.csv, standardize column names, clean, and save CLEAN.csv. It makes no model calls and needs no model credentials.

2. Send the saved CLEAN.csv to the model:

```powershell
.\.venv\Scripts\python.exe -m app.llm.pipeline
```

This runs app/llm/pipeline.py: read CLEAN.csv, load the separate field definitions and prompt, classify each row, and save LLM_OUTPUT.csv. Configure .env before this step. It does not rename, clean, or rewrite CLEAN.csv. Wait for it to finish before reviewing.

3. Start the review application:

```powershell
.\run_review_app.ps1
```

This runs app/review_app.py at [the review queue](http://127.0.0.1:8765/). It reads LLM_OUTPUT.csv, lets the user select HSBC or SUPPLIER and provide a reason, and saves to FINAL.csv. Keep this terminal open.

4. In another terminal, start the independent dashboard:

```powershell
.\run_dashboard_app.ps1
```

This runs app/dashboard_app.py at [the final decisions dashboard](http://127.0.0.1:8766/). It reads FINAL.csv only and shows three counts and a small table. Click Refresh after saving decisions. It works while the review application is stopped and starts empty when FINAL.csv is absent.

Both apps run independently and make no model calls. Stop either app with Ctrl+C in its own terminal.

The app reads the locally generated data/run/LLM_OUTPUT.csv. FINAL.csv is created when a user saves the first final decision.

## Column configuration and preparation

`fields/columns.yaml` contains only the original and standardized column names:

```yaml
columns:
  - original_name: incident_description
    new_name: INCIDENT_DESCRIPTION
```

`fields/definitions.yml` contains the short definitions, linked by standardized name:

```yaml
INCIDENT_DESCRIPTION: A detailed account of the incident and its impact.
```

Both files cover all 72 input columns transcribed from the supplied screenshots. Each definition is a draft interpretation of the field name and visible sample content. The preparation pipeline renames columns in YAML order and creates CLEAN.csv. Preserve meaningful source names and qualifiers such as ID, NAME, FLAG, and DATETIME; standardize their case to UPPERCASE without shortening them. incident_id becomes INCIDENT_ID and stays out of the model input.

The source headers must match the 72 original_name entries in this file. CSV files and the data/ directory are excluded from Git; supply your own local input and set INPUT_FILE to its path. No real incident values were copied from the screenshots into sample CSVs. Duration units, severity/impact code scales, and timestamp timezones remain unspecified. problem_close_notes and it_problem_close_notes remain separate fields.

Cleaning removes invisible control/format characters such as null and zero-width characters. It keeps tabs and line breaks, meaningful punctuation and symbols, emails, HTML, and normal whitespace. It does not anonymize data. INCIDENT_ID and the raw source file are preserved.

## Run a real model manually

1. Set INPUT_FILE and CLEAN_FILE in `app/data_preparation/pipeline.py`; set INPUT_FILE and OUTPUT_FILE in `app/llm/pipeline.py`. The default input is data/mockup/RAW.csv; outputs default to data/run/.
2. Configure the ignored .env, using .env.example as a reference.
3. Run the two pipelines:

```powershell
.\.venv\Scripts\python.exe -m app.data_preparation.pipeline
.\.venv\Scripts\python.exe -m app.llm.pipeline
```

Then start the review and dashboard applications in separate terminals using the commands above. If you change the output folder, also update the dashboard's FINAL_FILE path in app/dashboard_app.py.

Each row makes one independent request with its standardized names, definitions, values, and prompt. INCIDENT_ID stays local. Results are saved after each row.

LLM_OUTPUT.csv contains the cleaned source values and six model fields: classification, key_root_cause, decision_rationale, supporting_evidence, llm_confidence, and uncertainty_reason. The llm_input and llm_prompt cells preserve the exact input snapshot. Confidence is self-reported, not measured accuracy.

A failed request or invalid response records a pipeline failure and stops; it is not classified as UNDECIDED. Existing batch files are preserved. Use a new output folder for another run.

## Human decisions

- LLM says HSBC: confirm HSBC or correct to SUPPLIER.
- LLM says SUPPLIER: confirm SUPPLIER or correct to HSBC.
- LLM says UNDECIDED: read why, inspect all saved input fields, and choose HSBC or SUPPLIER.
- Every route requires the user's reason and an explicit Save final decision action.

Source fields and their definitions, supporting quotes, full rationale, and the original prompt are available in collapsible sections. All model input fields open automatically for UNDECIDED. The record stays pending until the API confirms that it was saved.

FINAL.csv keeps all source and model-result fields plus:

| Field | Value |
| --- | --- |
| FINAL_CLASS | HSBC or SUPPLIER, selected by the user |
| USER_REASON | Required user explanation |
| REVIEW_ACTION | CONFIRMED, CORRECTED, or RESOLVED_UNDECIDED |
| REVIEW_DATE | UTC timestamp |
| STATUS | FINALIZED |

The independent dashboard reads FINAL.csv only. It shows total finalized incidents, HSBC and SUPPLIER counts, and a table with incident ID, summary, final class, and user reason. Pending incidents are excluded. It never calls the model.

Legacy review files are left in place and ignored. Results without input snapshots or FINAL.csv files using the old schema require a separate batch folder; existing decisions are not silently migrated or overwritten.

## Code map

- `app/data_preparation/pipeline.py`: read -> rename -> clean -> save CLEAN.csv.
- `app/llm/pipeline.py`: read CLEAN.csv -> load definitions -> classify -> save LLM_OUTPUT.csv.
- `run_review_app.ps1`: run the review app on port 8765.
- `run_dashboard_app.ps1`: run the independent dashboard on port 8766.
- `app/data_preparation/`: CSV preparation functions.
- `app/llm/llm_connection.py`: provider selection and authentication.
- `app/llm/classification.py`: prepare each row, request and validate the model response, and save LLM_OUTPUT.csv.
- `app/review_store.py`: pending queue, final decisions, and dashboard totals.
- `app/review_app.py`: show LLM results and save user decisions.
- `app/dashboard_app.py`: display final CSV decisions in a separate app.
- `frontend/`: minimal review page and dashboard.
- `fields/columns.yaml`: original-to-standardized name mappings only.
- `fields/definitions.yml`: short definitions keyed by standardized column names.
- `prompts/classification.yml`: classification instructions.

Finish classification before reviewing. Run one local worker and keep output CSVs closed in Excel. Stop with Ctrl+C.

## LLM connection

The pipeline uses the same call for both providers:

```python
with llm_connection() as (client, model):
    result = classify_row(client, model, fields, prompt)
```

For local OpenAI, set `LLM_PROVIDER=openai`, keep `OPENAI_API_KEY` in `.env`, and optionally set `OPENAI_MODEL` (default: `gpt-4.1-mini`).

Set `LLM_TEMPERATURE` in `.env` to a number from 0 to 2, for example `LLM_TEMPERATURE=0.2`. Leave it blank to omit the parameter and keep the model's default. Use a value only when the selected model supports it. The setting applies to both connection providers; restart the pipeline after changing it.

For Azure, set `LLM_PROVIDER=azure` and fill these values:

```dotenv
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_OPENAI_TOKEN_SCOPE=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=
AZURE_OPENAI_DEPLOYMENT=gpt-5.1
```

Use the endpoint, token scope, and API version for your Azure resource. `AZURE_OPENAI_DEPLOYMENT` is your deployment name; it can differ from the underlying model name. The selected deployment and API version must support Chat Completions with structured JSON output. Token acquisition and refresh use `EnvironmentCredential` and a bearer token provider; no access token is copied into `.env`.

Optional `HTTPS_PROXY` and `NO_PROXY` settings are read by the client libraries. Keep them empty or unset when unnecessary; a typical local bypass is `localhost,127.0.0.1`. TLS verification stays enabled. Existing process environment variables take precedence over `.env`; restart the pipeline after changing settings.

Only the selected provider's credentials are required. Switching providers does not change the CSV pipeline, prompt, or review UI. This supports the two configured providers; other API protocols need an adapter.

Python 3.11 is the target; the existing virtual environment uses Python 3.14.
