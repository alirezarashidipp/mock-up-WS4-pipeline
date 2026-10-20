# Project instructions

- This is a small Python 3.11 demo. Keep the main flow linear and readable.
- Use plain functions and direct library calls. Keep Python code in `app/` and preparation steps in `app/data_preparation/`.
- Preserve source CSV files and identifiers. Credentials belong in the ignored `.env` file; never print them.
- Keep sample data and example classification rules clearly labelled as examples.
- Keep each column's original name, new name, and definition together in `fields/columns.yaml`; model instructions belong in `prompts/classification.yml`.
- Keep all project instructions in this root `AGENTS.md`; do not create additional `AGENTS.md` files in subfolders.
- Verify changes with `python -m unittest discover -s tests -v`. Distinguish offline checks from live API results.

## Python code

- Keep `main.py` readable from top to bottom: read, rename, clean, prepare, classify, save.
- Use Pydantic for the fields sent to the model and the structured response.
- Exclude row IDs from model input. Cleaning removes invisible control/format characters only; preserve punctuation, emails, HTML, and normal whitespace.
- Keep essential checks for CSV shape, unique IDs, mapping collisions, and evidence quotes.
- Use short functions and clear early returns; avoid custom exception layers.

## Frontend

- Keep the HSBC review UI minimal, English, and dependency-free.
- Display source fields, evidence, and analysis in collapsible sections; render CSV values as text.
- Keep every successful model result, including UNDECIDED, pending until a user selects HSBC or SUPPLIER and provides a reason.
- Save the original model result and the user's final class, reason, action, UTC date, and FINALIZED status in FINAL.csv.
- Show evidence and saved input definitions/values to reviewers; expand all model input fields for UNDECIDED.
- The dashboard reads FINAL.csv only and counts the user's FINAL_CLASS. Review never writes HUMAN_REVIEW.csv.
- Do not remove or mark records complete until the API confirms a save.
- Keep synthetic demo data visibly disclosed. Review makes no LLM calls.
