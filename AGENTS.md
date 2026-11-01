# Project instructions

- This is a small Python 3.11 demo. Use plain functions, short steps, and direct library calls. Keep Python code in `app/`.
- Keep project code, configuration, documentation, and UI text in English. Keep instructions in this root AGENTS.md only.
- Preserve source CSV files and identifiers. Keep CSV files, `data/`, credentials, and `.env` out of Git; never print credentials.
- Mark synthetic examples visibly. Verify changes with a lightweight affected-code check; distinguish offline checks from live API results. Create test files only when the user asks.

## Read the relevant docs first

Before explaining or changing a stage, read its document and inspect the current implementation:

- Data preparation, renaming, or cleaning: [docs/data_preparation.md](docs/data_preparation.md).
- LLM requests, supplier extraction, response schema, or CSV saving: [docs/llm.md](docs/llm.md).
- Engagement candidate search, linking requests, or INC_LINKED.csv: [docs/linking.md](docs/linking.md).
- Classification dashboard input, counts, or display: [docs/dashboard_app.md](docs/dashboard_app.md).
- Engagement dashboard grouping, navigation, or details: [docs/engagement_dashboard.md](docs/engagement_dashboard.md).

Read only relevant documents and keep them aligned with behavior changes. Use [README.md](README.md) for setup and run commands.

## Python pipeline

- Keep `app/data_preparation/pipeline.py` linear: read, rename, clean, save CLEAN.csv. Keep `app/llm/pipeline.py` separate: read CLEAN.csv, load definitions, classify, save LLM_OUTPUT.csv.
- Names belong in `fields/columns.yaml`; definitions keyed by standardized names belong in `fields/definitions.yml`; instructions belong in `prompts/classification.yml`.
- Use Pydantic for model inputs and responses. Exclude INCIDENT_ID from model input.
- Cleaning removes invisible control/format characters only; preserve punctuation, emails, HTML, and normal whitespace. Preparation retains empty/repeated IDs and uppercases unmapped headers; add no ID, CSV-shape, or mapping-collision checks to that stage.
- Model classification is HSBC, SUPPLIER, or UNCERTAIN. Use UNCERTAIN when the evidence cannot support choosing the accountable party; this is a successful result, not a processing failure. Explain missing or conflicting facts in decision_rationale. Supplier details are null for HSBC and UNCERTAIN; for SUPPLIER extract only documented facts and use Unknown for missing core details. Keep additional nonduplicated supplier facts in supplier_more_info, or null when none exist.
- Score attribution_evidence_strength from 0 to 4 using the prompt rubric. For UNCERTAIN use 0-2 to describe support for attributing a party, not confidence in uncertainty. Reject an UNCERTAIN response with a score above 2. The score is evidence strength, not a probability.
- Order model inputs as narrative, causes, closure/resolution, investigation history, supplier/product context, then remaining metadata. Preserve every non-ID field and value. Order response fields as root cause, supporting evidence, rationale, classification, evidence strength, then the six supplier fields.
- Save each result in `app/llm/save_csv.py` before requesting the next row. The model's evidence_column list contains one to ten standardized source column names. Join them with comma and space in exactly one evidence_column CSV cell, such as COLUMN_X, COLUMN_Y. New outputs have no supporting_evidence or numbered evidence columns. Keep source values and scalar model fields in their own columns, without evidence quotes, JSON blobs, definitions, or prompt text.
- Pass configured numeric temperature to the provider without a local range check. Existing output does not block starting the LLM pipeline; preserve records and retain conflicting-ID checks when saving.
- Preserve response-structure checks and safe CSV writing. Store returned supporting source names as text. Avoid custom exception layers.
- Keep engagement linking independent in `app/linking/`: preserve LLM_OUTPUT rows, select only a supplied ENG_ALL candidate or leave the link undecided, and save INC_LINKED.csv. Only successful SUPPLIER classifications enter matching. UNCERTAIN is SKIPPED without candidate search or an LLM call and does not stop the batch. Reuse the existing LLM connection; keep the classification dashboard on LLM_OUTPUT.csv.

## Dashboards

- Human review is removed. There is no approval queue, review API, or new FINAL.csv output. Preserve existing CSV files from earlier versions.
- Keep the minimal English HSBC frontend in `frontend/dashboard/`, with styling in `frontend/style.css` and logo artwork in `frontend/pictures/`.
- Run `app/ui/dashboard_app.py` independently on port 8766. Its only data input is LLM_OUTPUT.csv; it imports no LLM modules and makes no model calls or file writes.
- Count successful HSBC, SUPPLIER, and UNCERTAIN classifications separately, include all three in the total, and report failed rows separately. Keep classification, rationale, evidence strength, and all six supplier fields visible on SUPPLIER cards. Keep evidence names, processing_status, and root cause in a closed dropdown; saved input fields have a separate dropdown. Render CSV values as text. Read evidence_column with read-only fallback to legacy supporting_evidence or evidence_N_column cells. Do not convert legacy llm_confidence values into evidence scores.
- Keep `app/ui/engagement_dashboard.py` independent on port 8767, reading only INC_LINKED.csv. Use `frontend/engagements/` to show engagements and companies, then their linked incidents, then incident details. Group MATCHED rows by engagement ID, not company name; count other rows separately. Make no LLM calls or file writes and render CSV values as text.
