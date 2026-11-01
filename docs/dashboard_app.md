# Dashboard flow

Run `python -m app.ui.dashboard_app` from the project root. Open `http://127.0.0.1:8766/`.

```text
data/run/LLM_OUTPUT.csv -> read successful model results -> count tags -> display details
```

## Request flow

1. `GET /` serves `frontend/dashboard/index.html`; `frontend/dashboard/app.js` requests `GET /api/dashboard` on load and Refresh.
2. `get_dashboard_data` reads `app.state.results_file`, initialized from `RESULTS_FILE`, using UTF-8 CSV input.
3. Count successful HSBC, SUPPLIER, and UNCERTAIN rows in the total and in their own counters. UNCERTAIN is a valid result when the model cannot assign responsibility from the record; count failed processing rows separately. Return successful results as dashboard records.
4. Render each incident as a card. Keep classification, decision_rationale, and attribution_evidence_strength visible. Display the score as 0-4 with its label: Unsupported, Weak, Moderate, Strong, or Very strong. The expandable scale explains all five levels. This rates recorded support for assigning responsibility to HSBC or Supplier, not a probability of correctness, supplier-name extraction, or engagement matching. For UNCERTAIN, the 0-2 score describes limited support for a party attribution, not confidence in uncertainty. Only SUPPLIER cards show all six supplier fields, including supplier_more_info with an empty-state message when no extra facts exist.
5. Keep source-column names, processing_status, and key_root_cause in the closed-by-default Evidence and processing details dropdown. `read_evidence_columns` splits the single `evidence_column` CSV cell on commas, trims spaces, and returns nonempty names as the API's `evidence_column` list. For older files, it reads `supporting_evidence`, then numbered `evidence_N_column` cells if neither single-column format is present. No saved file is rewritten. Keep saved input values in a separate Source fields dropdown.
6. Render CSV values as text. Share `frontend/style.css` and logo artwork in `frontend/pictures/`.

## Boundaries

- LLM_OUTPUT.csv is the only data input. The app imports no LLM or review modules, makes no model calls, and writes no files.
- No human approval, correction, final-decision queue, or FINAL.csv input remains. Tags are model assessments, not human-approved outcomes.
- A missing or empty input produces an empty dashboard. Older HSBC/SUPPLIER rows can lack supplier details; display unrecorded details as Unknown without changing the CSV or inventing facts. Invalid processing statuses or classification labels outside HSBC, SUPPLIER, and UNCERTAIN return an error. REVIEW_STATUS is not used.
- Older results without `attribution_evidence_strength` show Not recorded. Never convert legacy `llm_confidence` percentages into evidence-strength scores. Unexpected nonblank scores display Invalid score. The [classification document](llm.md) defines the new response schema and rubric.
- Refresh rereads the file. There is no automatic polling or notification from the LLM pipeline.
- Configure the input through `RESULTS_FILE` in `app/ui/dashboard_app.py`. The dashboard can run independently once the CSV exists.
