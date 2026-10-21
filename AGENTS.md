# Project instructions

- This is a small Python 3.11 demo. Keep the main flow linear and readable.
- Use plain functions and direct library calls. Keep Python code in `app/` and preparation steps in `app/data_preparation/`.
- Preserve source CSV files and identifiers. Credentials belong in the ignored `.env` file; never print them.
- Keep sample data and example classification rules clearly labelled as examples.
- Keep original-to-standardized names in `fields/columns.yaml`, definitions keyed by standardized names in `fields/definitions.yml`, and model instructions in `prompts/classification.yml`.
- Keep all project instructions in this root `AGENTS.md`; do not create additional `AGENTS.md` files in subfolders.
- Verify changes with a lightweight check of the affected code. Distinguish offline checks from live API results.
- Keep project code, configuration, documentation, and UI text in English. Keep CSV files, `data/`, and credentials out of Git.
- Use lightweight inline checks; create test files only when the user asks.

## Read the relevant docs first

Before explaining or changing a stage, read its document and inspect the current implementation:

- Data preparation, renaming, or cleaning: [docs/data_preparation.md](docs/data_preparation.md).
- LLM requests, response schema, or result storage: [docs/llm.md](docs/llm.md).
- Review UI, `review_store.py`, or user decisions: [docs/review_app.md](docs/review_app.md).
- Dashboard input, counts, or display: [docs/dashboard_app.md](docs/dashboard_app.md).

Read only the documents relevant to the task. Keep the affected document aligned with behavior changes. Use [README.md](README.md) for setup and run commands.

## Python code

- Keep `app/data_preparation/pipeline.py` linear: read, rename, clean, save CLEAN.csv. Keep `app/llm/pipeline.py` separate: read CLEAN.csv, load definitions, classify, save LLM_OUTPUT.csv.
- Use Pydantic for the fields sent to the model and the structured response.
- Exclude row IDs from model input. Cleaning removes invisible control/format characters only; preserve punctuation, emails, HTML, and normal whitespace.
- Data preparation retains empty/repeated IDs and uppercases unmapped headers; do not add ID, CSV-shape, or mapping-collision validation to this stage. Preserve existing downstream checks for model responses, evidence quotes, and safe review saves.
- Use short functions and clear early returns; avoid custom exception layers.

## Frontend

- Keep the HSBC review UI minimal, English, and dependency-free.
- Run review and dashboard as independent apps: `app/review_app.py` on port 8765 and `app/dashboard_app.py` on port 8766.
- Display source fields, evidence, and analysis in collapsible sections; render CSV values as text.
- Keep every successful model result, including UNDECIDED, pending until a user selects HSBC or SUPPLIER and provides a reason.
- Save the original model result and the user's final class, reason, action, UTC date, and FINALIZED status in FINAL.csv.
- Show evidence and saved input definitions/values to reviewers; expand all model input fields for UNDECIDED.
- The dashboard reads FINAL.csv directly, counts the user's FINAL_CLASS, and imports no review or LLM modules. It runs without the other processes. Review never writes HUMAN_REVIEW.csv.
- Do not remove or mark records complete until the API confirms a save.
- Keep synthetic demo data visibly disclosed. Review makes no LLM calls.
