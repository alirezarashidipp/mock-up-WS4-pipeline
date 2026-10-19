# HSBC Incident Classification Demo

A small Python 3.11 demo: plain functions, CSV files, Pydantic, and a local FastAPI review screen.

## Flow

[View the workflow diagram](docs/architecture.md).

```text
RAW CSV
  -> rename columns + clean text
  -> CLEANED.csv
  -> one row + field definitions + prompt -> LLM
  -> LLM_OUTPUT.csv
       -> SUPPLIER / HSBC -> user approves -> FINAL.csv
                          -> user rejects  -> HUMAN_REVIEW.csv
       -> UNDECIDED                        -> HUMAN_REVIEW.csv
```

The source CSV and its identifiers are preserved. CLEANED.csv is never updated by review and human-review rows are never automatically sent back to the LLM.

## Open the mockup

```powershell
.\.venv\Scripts\python.exe -m app.review --demo
```

Open http://127.0.0.1:8765/ and refresh. The five synthetic rows and hand-authored model responses live in `data/mockup/`: RAW.csv, CLEANED.csv, and LLM_OUTPUT.csv. The demo makes no model calls. Three rows have definite classifications; two are undecided and are automatically routed to HUMAN_REVIEW.csv. FINAL.csv is created on the first approval.

Approval/rejection writes real local demo CSVs. Old demo files and decisions are preserved in their earlier locations.

## Run the model manually

1. Set INPUT_FILE and OUTPUT_FILE in `app/main.py`. The default input is the five-row synthetic sample; outputs go in `data/run/`.
2. Keep the OpenAI key in the ignored `.env`.
3. Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
.\.venv\Scripts\python.exe -m app.review
```

The pipeline standardizes names to UPPERCASE, removes ordinary email addresses, saves CLEANED.csv, then processes each cleaned row. One row makes one independent model request. Output contains cleaned input values and six model fields:

- classification: SUPPLIER, HSBC, or UNDECIDED.
- key_root_cause.
- decision_rationale.
- supporting_evidence: exact field/quote pairs, stored as JSON in a CSV cell.
- llm_confidence: self-reported confidence in the selected label, not measured accuracy.
- uncertainty_reason: required for UNDECIDED.

An API or validation failure is saved as a failure and stops the run; it is not treated as UNDECIDED. Use a new output folder for another run. Existing batch files are not overwritten.

## Review files

FINAL.csv contains cleaned inputs, LLM output, and approval metadata.

HUMAN_REVIEW.csv contains exactly the CLEANED.csv columns plus:

| Column | User rejection | Model uncertainty |
| --- | --- | --- |
| STATUS | USER_REJECTED | LLM_UNDECIDED |
| REVIEW_DATE | UTC rejection time | UTC routing time |
| REJECTION_REASON | Required user reason | Empty |
| LLM_UNCERTAINTY_REASON | Empty | Model's explanation |

FINAL.csv uses STATUS=USER_APPROVED and a UTC REVIEW_DATE; both reason fields are empty. ROW_ID links every file. Model reasoning and evidence remain in LLM_OUTPUT.csv.

Review dates are recorded once; reloading does not duplicate decisions or replace their dates. Source fields and evidence are collapsible in the UI.

## Configuration

- `fields/column_mapping.csv`: original and standardized names.
- `fields/definitions.yml`: short English column definitions.
- `prompts/classification.yml`: draft classification rules.
- `app/main.py`: file paths.

Run one local worker and finish classification before review. Keep output CSVs closed in Excel while saving. Stop the app with Ctrl+C. The non-LLM follow-up classification is outside this demo.

No test suite or live model evaluation was run for this update. Python 3.11 is the target; the existing virtual environment uses Python 3.14.
