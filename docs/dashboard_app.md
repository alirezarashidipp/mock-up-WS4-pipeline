# Dashboard flow

Run `python -m app.ui.dashboard_app` from the project root. Open `http://127.0.0.1:8766/`.

```text
data/run/LLM_OUTPUT.csv -> read successful model results -> count tags -> display details
```

## Request flow

1. `GET /` serves `frontend/dashboard/index.html`; `frontend/dashboard/app.js` requests `GET /api/dashboard` on load and Refresh.
2. `get_dashboard_data` reads `app.state.results_file`, initialized from `RESULTS_FILE`, using UTF-8 CSV input.
3. Count successful HSBC and SUPPLIER rows; count failed processing rows separately. Return successful results as dashboard records.
4. Show incident ID, summary, model tag, supplier name, product/service, and confidence. Collapsible details expose cause, rationale, supporting evidence/source-column names, and supplier-specific fields for SUPPLIER.
5. Render CSV values as text. Share `frontend/style.css` and logo artwork in `frontend/pictures/`.

## Boundaries

- LLM_OUTPUT.csv is the only data input. The app imports no LLM or review modules, makes no model calls, and writes no files.
- No human approval, correction, final-decision queue, or FINAL.csv input remains. Tags are model assessments, not human-approved outcomes.
- A missing or empty input produces an empty dashboard. Older HSBC/SUPPLIER rows can lack supplier details; display unrecorded details as Unknown without changing the CSV or inventing facts. Invalid processing statuses or other classification labels return an error. REVIEW_STATUS is not used.
- Refresh rereads the file. There is no automatic polling or notification from the LLM pipeline.
- Configure the input through `RESULTS_FILE` in `app/ui/dashboard_app.py`. The dashboard can run independently once the CSV exists.
