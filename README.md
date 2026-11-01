# HSBC Incident Classification Demo

A small Python 3.11 mock-up with CSV storage, Pydantic responses, and two independent read-only HSBC dashboards.

```text
RAW.csv -> Read -> Rename -> Clean -> CLEAN.csv
CLEAN.csv + Definitions + Prompt -> LLM (one row per request) -> LLM_OUTPUT.csv
LLM_OUTPUT.csv -> Classification dashboard
LLM_OUTPUT.csv + ENG_ALL.csv -> Candidate search -> LLM linking -> INC_LINKED.csv
INC_LINKED.csv -> Engagement dashboard -> Linked incidents -> Incident details
```

The LLM tags each incident HSBC, SUPPLIER, or UNCERTAIN. UNCERTAIN is a successful result when the record cannot support choosing the accountable party; its rationale explains the missing or conflicting facts. For SUPPLIER it also extracts the supplier name, related product/service, action or failure, causal explanation, and accountability reason. Extra recorded supplier facts go in `supplier_more_info`, left empty when none exist. Missing core Supplier facts are Unknown; all six supplier fields are null for HSBC and UNCERTAIN.

Each result includes one to ten source column names, saved together in exactly one `evidence_column` CSV cell, such as `INCIDENT_DESCRIPTION, ROOT_CAUSE_NOTES`. New results have no numbered evidence columns. The dashboard counts all three classifications separately from processing failures and keeps decision and Supplier fields visible, with evidence names and processing status in a dropdown. `attribution_evidence_strength` rates recorded support from 0 (unsupported) to 4 (very strong), not probability of correctness. UNCERTAIN uses 0-2 to describe attribution evidence, not confidence in uncertainty. See the [five-level rubric and field order](docs/llm.md).

Model inputs are ordered as narrative, causes, closure/resolution, investigation history, supplier/product context, then remaining metadata. All non-ID values and their definitions are retained. Responses put root cause, supporting evidence, and a short rationale before classification and evidence strength, followed by supplier details.

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

After classification, optionally link incidents to engagements. Put the UTF-8 engagement file at `data/mockup/ENG_ALL.csv`, then run this separate pipeline:

```powershell
.\.venv\Scripts\python.exe -m app.linking.pipeline
```

It writes `data/run/INC_LINKED.csv`: original incident columns, selected engagement columns prefixed with `ENG_`, and the link decision. It uses [linking instructions](prompts/linking.yml) and the existing `.env` connection. Only successful Supplier classifications enter matching. UNCERTAIN rows are SKIPPED without a model call and do not stop the batch. Ambiguous or missing Supplier matches stay undecided. The classification evidence score is preserved; `link_confidence` remains a separate self-reported 0-100 value about the engagement match.

To browse that output, start the separate engagement dashboard and open [http://127.0.0.1:8767/](http://127.0.0.1:8767/):

```powershell
.\.venv\Scripts\python.exe -m app.ui.engagement_dashboard
```

It reads only `data/run/INC_LINKED.csv`. Select an engagement to see its linked incidents, then select an incident for details. Refresh rereads the CSV. The classification dashboard on port 8766 is independent and does not need to be running.

Preparation replaces CLEAN.csv on nonempty runs. LLM results append for new incident IDs; conflicting results for an existing ID are rejected. For an older output schema, including `llm_confidence`, `supporting_evidence`, or numbered evidence columns, configure a new output folder in `app/llm/pipeline.py` and update `RESULTS_FILE` in `app/ui/dashboard_app.py`. If linking, also update the input/output paths in `app/linking/pipeline.py` and `RESULTS_FILE` in `app/ui/engagement_dashboard.py`. Old confidence values are not converted to evidence strength; dashboards show Not recorded when the score is missing and read legacy evidence without rewriting it. CSV cells contain plain values, without evidence quote columns, JSON blobs, prompt text, or definitions. CSVs and credentials stay out of Git.

## Documentation and tests

- [Data preparation](docs/data_preparation.md)
- [LLM classification and supplier extraction](docs/llm.md)
- [Incident-to-engagement linking](docs/linking.md)
- [Classification dashboard](docs/dashboard_app.md)
- [Engagement dashboard](docs/engagement_dashboard.md)
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
