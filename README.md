# HSBC Incident Review Demo

A small Python 3.11 demo with unchanged CSV preparation, one sequential LLM pipeline, and one incident dashboard.

```text
RAW.csv -> read -> rename -> clean -> CLEAN.csv
For each CLEAN incident: classify -> save -> find engagements -> save -> next incident
                                            |
                                       INCIDENTS.csv
                                            |
                     Classification -> Supplier name -> Engagement
                           Three human reviews in one dashboard
```

The model returns HSBC, SUPPLIER, or UNCERTAIN. A Supplier result automatically enters engagement matching using its **base supplier name**, without waiting for human approval. Python finds matching ENG_ALL rows; the LLM suggests up to five engagements with reasons and selects its strongest proposal by default. A model default is saved, but human approval remains pending.

The dashboard lists every initialized incident, including processing failures and rows waiting to run. Review classification first, supplier name second when applicable, and engagement third. Correcting the supplier name using the dropdown immediately reruns the same engagement function. Reviewers can inspect and choose from **all** Python matches, including those beyond the LLM shortlist.

## Setup

Run from the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Keep these files local and out of Git:

| File | Purpose |
| --- | --- |
| `data/mockup/RAW.csv` | Original incident data. |
| `data/mockup/ENG_ALL.csv` | Engagement catalog with unique, nonblank ENGAGEMENT_ID and THIRD_PARTY_NAME and/or THIRD_PARTY_NORMALISED_NAME. |
| `data/mockup/SUPPLIER_NAME.csv` | One base name per row, optionally headed SUPPLIER_NAME; for example AXA. |
| `.env` | Provider credentials/settings from [.env.example](.env.example); LINK_MAX_CANDIDATES defaults to 70. |

Configure [column names](fields/columns.yaml), [field definitions](fields/definitions.yml), and the two YAML [classification](prompts/classification.yml) and [linking](prompts/linking.yml) prompts. OpenAI and Azure reuse the existing connection. Requests use provider defaults for temperature and output length; the candidate cap is not a token limit.

## Run

1. Prepare incidents; this pipeline is unchanged:

   ```powershell
   .\.venv\Scripts\python.exe -m app.data_preparation.pipeline
   ```

2. Classify and automatically find engagements, one incident at a time:

   ```powershell
   .\.venv\Scripts\python.exe -m app.llm.pipeline
   ```

3. Start the only dashboard:

   ```powershell
   .\.venv\Scripts\python.exe -m app.ui.dashboard_app
   ```

Open [http://127.0.0.1:8766](http://127.0.0.1:8766). Refresh rereads saved results; stop processes with Ctrl+C.

The new output is **data/run/INCIDENTS.csv**. It contains original incident values, model classification, engagement proposals/counts, selected engagement values, and separate human decisions. Existing LLM_OUTPUT.csv, CLASSIFICATION_REVIEW.csv, INC_LINKED.csv, and HUMAN_REVIEW.csv remain untouched archives; the new workflow does not import their approvals or read them as its output. No FINAL.csv is created. The separate linking/review CLI commands and port-8767/8768 dashboards have been removed.

Initialization saves all source incidents as pending. Each classification and link result is saved before the next incident. A failed request saves its failure and stops the batch. Rerunning retries unfinished/failed model work that has no human classification decision, preserves completed results, and adds new IDs. Changed source values, output columns, or engagement columns require a fresh output; preserve earlier batches. Output/catalog paths live in `app/incidents.py`; CLEAN input and definitions live in `app/llm/pipeline.py`. Restart the dashboard after changing paths.

The CSV stores current decisions, not an audit-history log. File locking, atomic saves, and per-row versions protect concurrent pipeline/dashboard updates; stale model results or browser decisions cannot replace newer human changes.

## Code flow

The entry point reads the source, definitions, engagement catalog, and candidate limit. The per-incident loop calls `classify_and_save`, then `link_incident` when applicable. Both remain in `app/llm/pipeline.py`; request details do not obscure the batch order. The dashboard and pipeline reuse `find_engagements` for matching and suggestions.

`app/incidents.py` owns current-state saves. `app/csv_files.py` contains the shared CSV reader and atomic writer; the unused legacy append writer has been removed. Cleaning still uses the same atomic writer. File names, output columns, model prompts, review decisions, and run commands are unchanged by this cleanup.

## Checks and documentation

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
```

These existing checks use temporary CSVs and simulated responses. They do not establish provider connectivity or model accuracy. To make a real classification request using your configured provider:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

The live check uses a visibly synthetic incident and current classification schema; it does not test the separate engagement-suggestion schema.

- [Short description and AXA example](docs/short_desription.md)
- [Data preparation](docs/data_preparation.md)
- [Classification and sequential processing](docs/llm.md)
- [Engagement search and suggestions](docs/linking.md)
- [Dashboard and human decisions](docs/dashboard_app.md)
- [Project instructions](AGENTS.md)

Current source-backed diagrams:

- [Automatic incident processing](.archify/workflow-ws4-current-20261102-190621/ws4-pipeline.html)
- [Three ordered human decisions](.archify/workflow-ws4-current-20261102-190621/ws4-human-review.html)

These diagrams describe the single LLM pipeline, automatic Supplier suggestions, and the incident dashboard. Earlier diagram folders and their frozen documents are historical snapshots.
