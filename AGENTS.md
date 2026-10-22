# Project instructions

- This is a small Python 3.11 demo. Use plain functions, short steps, and direct library calls. Keep Python code in `app/`.
- Keep project code, configuration, documentation, and UI text in English. Keep instructions in this root AGENTS.md only.
- Preserve source CSV files and identifiers. Keep CSV files, `data/`, credentials, and `.env` out of Git; never print credentials.
- Mark synthetic examples visibly. Verify changes with a lightweight affected-code check; distinguish offline checks from live API results. Create test files only when the user asks.

## Read the relevant docs first

Before explaining or changing a stage, read its document and inspect the current implementation:

- Data preparation, renaming, or cleaning: [docs/data_preparation.md](docs/data_preparation.md).
- LLM requests, supplier extraction, response schema, or CSV saving: [docs/llm.md](docs/llm.md).
- Dashboard input, counts, or display: [docs/dashboard_app.md](docs/dashboard_app.md).

Read only relevant documents and keep them aligned with behavior changes. Use [README.md](README.md) for setup and run commands.

## Python pipeline

- Keep `app/data_preparation/pipeline.py` linear: read, rename, clean, save CLEAN.csv. Keep `app/llm/pipeline.py` separate: read CLEAN.csv, load definitions, classify, save LLM_OUTPUT.csv.
- Names belong in `fields/columns.yaml`; definitions keyed by standardized names belong in `fields/definitions.yml`; instructions belong in `prompts/classification.yml`.
- Use Pydantic for model inputs and responses. Exclude INCIDENT_ID from model input.
- Cleaning removes invisible control/format characters only; preserve punctuation, emails, HTML, and normal whitespace. Preparation retains empty/repeated IDs and uppercases unmapped headers; add no ID, CSV-shape, or mapping-collision checks to that stage.
- Model classification is HSBC or SUPPLIER. Supplier details are null for HSBC; for SUPPLIER extract only documented facts and use Unknown for missing core details. Keep additional nonduplicated supplier facts in supplier_more_info, or null when none exist. State weak or conflicting attribution in the rationale with low self-reported confidence.
- Save each result in `app/llm/save_csv.py` before requesting the next row. supporting_evidence contains zero to ten standardized source column names as strings. Save names in evidence_1_column through evidence_10_column; unused slots are empty. Keep source values and scalar model fields in their own columns, without evidence quotes, JSON blobs, definitions, or prompt text.
- Pass configured numeric temperature to the provider without a local range check. Existing output does not block starting the LLM pipeline; preserve records and retain conflicting-ID checks when saving.
- Preserve response-structure checks and safe CSV writing. Store returned supporting source names as text. Avoid custom exception layers.

## Dashboard

- Human review is removed. There is no approval queue, review API, or new FINAL.csv output. Preserve existing CSV files from earlier versions.
- Keep the minimal English HSBC frontend in `frontend/dashboard/`, with styling in `frontend/style.css` and logo artwork in `frontend/pictures/`.
- Run `app/ui/dashboard_app.py` independently on port 8766. Its only data input is LLM_OUTPUT.csv; it imports no LLM modules and makes no model calls or file writes.
- Count successful model classifications, and report failed rows separately. Display supplier details only for SUPPLIER, along with analysis and evidence/source-column names. Render CSV values as text.
