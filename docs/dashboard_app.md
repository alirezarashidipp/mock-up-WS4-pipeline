# Dashboard flow

Run `python -m app.ui.dashboard_app` from the project root. Open `http://127.0.0.1:8766/`.

```text
data/run/LLM_OUTPUT.csv -> read successful model results -> count tags -> display details
```

## Request flow

1. `GET /` serves `frontend/dashboard/index.html`; `frontend/dashboard/app.js` requests `GET /api/dashboard` on load and Refresh.
2. `get_dashboard_data` reads `app.state.results_file`, initialized from `RESULTS_FILE`, using UTF-8 CSV input.
3. Count successful HSBC and SUPPLIER rows; count failed processing rows separately. Return successful results as dashboard records.
4. Render each incident as a card. Keep classification, decision_rationale, and llm_confidence visible. For SUPPLIER also keep all six supplier fields visible, including supplier_more_info with an empty-state message when no extra facts exist.
5. Keep source-column names, processing_status, and key_root_cause in the closed-by-default Evidence and processing details dropdown. Show only nonempty evidence slots and their actual count, without quotes. The API reconstructs supporting_evidence from evidence_N_column cells. Keep saved input values in a separate Source fields dropdown.
6. Render CSV values as text. Share `frontend/style.css` and logo artwork in `frontend/pictures/`.

## Boundaries

- LLM_OUTPUT.csv is the only data input. The app imports no LLM or review modules, makes no model calls, and writes no files.
- No human approval, correction, final-decision queue, or FINAL.csv input remains. Tags are model assessments, not human-approved outcomes.
- A missing or empty input produces an empty dashboard. Older HSBC/SUPPLIER rows can lack supplier details; display unrecorded details as Unknown without changing the CSV or inventing facts. Invalid processing statuses or other classification labels return an error. REVIEW_STATUS is not used.
- Refresh rereads the file. There is no automatic polling or notification from the LLM pipeline.
- Configure the input through `RESULTS_FILE` in `app/ui/dashboard_app.py`. The dashboard can run independently once the CSV exists.
