# Project instructions

- This is a small Python 3.11 proof of concept. Keep the main flow linear and readable.
- Use plain functions and direct library calls. Keep Python code in `app/` and preparation steps in `app/data_preparation/`.
- Preserve source CSV files and identifiers. Credentials belong in the ignored `.env` file; never print them.
- Keep sample data and example classification rules clearly labelled as examples.
- Keep the original-to-standardized mapping in `fields/column_mapping.csv`, definitions in `fields/definitions.yml`, and model instructions in `prompts/classification.yml`.
- Read `app/AGENTS.md` for Python changes and `frontend/AGENTS.md` for review UI changes.
- Verify changes with `python -m unittest discover -s tests -v`. Distinguish offline checks from live API results.
