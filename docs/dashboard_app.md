# Dashboard flow

Run `python -m app.ui.dashboard_app` from the project root. Open `http://127.0.0.1:8766/`.

```text
data/run/LLM_OUTPUT.csv -> read saved results -> count classes and failures -> filter incidents -> display details
```

## Request flow

1. `GET /` serves `frontend/dashboard/index.html`; `frontend/dashboard/app.js` requests `GET /api/dashboard` on load and Refresh.
2. `get_dashboard_data` reads `app.state.results_file`, initialized from `RESULTS_FILE`, using UTF-8 CSV input.
3. Count successful HSBC, SUPPLIER, and UNCERTAIN rows in the total and in their own counters. UNCERTAIN is a valid result when the model cannot assign responsibility from the record; count failed processing rows separately. Return both successful and failed rows as dashboard records. Failed records include their saved error and original source fields; they do not contribute to the classified total.
4. Render each incident as a card. Failed cards show processing status, the saved error, and the Source fields dropdown instead of presenting a successful classification. Keep classification, decision_rationale, and attribution_evidence_strength visible. Display the score as 0-4 with its label: Unsupported, Weak, Moderate, Strong, or Very strong. The expandable scale explains all five levels. This rates recorded support for assigning responsibility to HSBC or Supplier, not a probability of correctness, supplier-name extraction, or engagement matching. For UNCERTAIN, the 0-2 score describes limited support for a party attribution, not confidence in uncertainty. Only SUPPLIER cards show all six supplier fields, including supplier_more_info with an empty-state message when no extra facts exist.
5. Keep source-column names, processing_status, and key_root_cause in the closed-by-default Evidence and processing details dropdown. `read_evidence_columns` splits the single `evidence_column` CSV cell on commas, trims spaces, and returns nonempty names as the API's `evidence_column` list. For older files, it reads `supporting_evidence`, then numbered `evidence_N_column` cells if neither single-column format is present. No saved file is rewritten. Keep saved input values in a separate Source fields dropdown.
6. Render CSV values as text. Share `frontend/style.css` and logo artwork in `frontend/pictures/`.

## Summary filters

The five summary counts are buttons. Select one to filter the incident cards:

| Button | Visible records |
| --- | --- |
| Classified incidents | All successful HSBC, SUPPLIER, and UNCERTAIN rows; this is the default view. |
| HSBC | Successful HSBC rows. |
| SUPPLIER | Successful SUPPLIER rows. |
| UNCERTAIN | Successful UNCERTAIN rows. |
| Processing failures | Failed rows, including the saved error and original source fields. |

Only one filter is active at a time. The active button is visibly selected and exposes its state with `aria-pressed`. All five counts always describe the complete saved file; filtering does not recalculate them. An empty selection shows a message for that group. Refresh rereads the file and keeps the selected filter. Selecting Classified incidents returns to the full successful-results view. Buttons support both mouse and keyboard use.

## Boundaries

- LLM_OUTPUT.csv is the only data input. The app imports no LLM or review modules, makes no model calls, and writes no files.
- This dashboard has no human approval, correction, final-decision queue, or FINAL.csv input. Tags are model assessments, not human-approved outcomes. [Human review](human_review.md) runs separately on port 8768.
- A missing or empty input produces an empty dashboard. Older HSBC/SUPPLIER rows can lack supplier details; display unrecorded details as Unknown without changing the CSV or inventing facts. Invalid processing statuses or successful classification labels outside HSBC, SUPPLIER, and UNCERTAIN return an error. Failed rows may have a blank classification. REVIEW_STATUS is not used.
- Older results without `attribution_evidence_strength` show Not recorded. Never convert legacy `llm_confidence` percentages into evidence-strength scores. Unexpected nonblank scores display Invalid score. The [classification document](llm.md) defines the new response schema and rubric.
- Refresh rereads the file. There is no automatic polling or notification from the LLM pipeline.
- Configure the input through `RESULTS_FILE` in `app/ui/dashboard_app.py`. The dashboard can run independently once the CSV exists.
