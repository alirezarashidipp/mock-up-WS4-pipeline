# Dashboard flow

Run `python -m app.dashboard_app` from the project root. Open `http://127.0.0.1:8766/`.

```text
data/run/FINAL.csv -> read -> count FINAL_CLASS -> display counts and table
```

## Request flow

1. `GET /` serves `frontend/dashboard.html`; `frontend/dashboard.js` requests `GET /api/dashboard` on load and when Refresh is clicked.
2. `dashboard_app.get_dashboard_data` reads `app.state.final_file`, initialized from `FINAL_FILE`, using `csv.DictReader` and `utf-8-sig`.
3. For each row, read `INCIDENT_ID`, `FINAL_CLASS`, and `USER_REASON`; use `INCIDENT_SHORT_DESCRIPTION` as the optional summary.
4. Count `total`, `HSBC`, and `SUPPLIER` using `FINAL_CLASS`, the user's final decision.
5. Return `{records, counts, demo}`. Each record contains `{incident_id, summary, final_class, user_reason}`. The UI renders the three counts and four-column table using text values.

## Boundaries

- `FINAL.csv` is the only data input. The app imports no review or LLM modules and needs neither process running.
- It reads no RAW, CLEAN, or LLM_OUTPUT files; it makes no model calls and writes no files.
- It uses the rows already present in FINAL.csv; it does not revalidate model results, evidence, or review history.
- Missing or empty FINAL.csv produces an empty dashboard. Invalid classes, missing required row fields, or read/encoding failures return an error with HTTP 400.
- Refresh rereads the file. There is no automatic polling or notification from review.
- Configure the input path through `FINAL_FILE` in `app/dashboard_app.py`.
