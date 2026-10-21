# Review flow

Run `python -m app.ui.review_app` from the project root after LLM results are saved. Open `http://127.0.0.1:8765/`.

```text
LLM_OUTPUT.csv + existing FINAL.csv -> review UI -> user decision -> append FINAL.csv
```

## Read and display

1. `GET /` serves `frontend/review/index.html`; `frontend/review/app.js` requests `GET /api/review`. Shared styling and logo artwork remain in `frontend/style.css` and `frontend/pictures/`.
2. `app/ui/review_app.py` calls `app/ui/review_store.py` (`get_review_data`). Read `data/run/LLM_OUTPUT.csv` and optional `data/run/FINAL.csv` from the same batch.
3. Reconstruct model inputs from saved source values and the current `fields/definitions.yml`, and evidence from all `evidence_N_column`/`evidence_N_quote` pairs. Validate result structure and existing final decisions; extra empty evidence pairs from header expansion do not invalidate earlier decisions. Display evidence as returned without comparing it with source text. Failed model rows are counted but excluded from review records.
4. Return source fields, current definitions, saved input values, result, row version, and review state. Definitions are not stored in CSV; changing the YAML changes their review display. Successful results remain `PENDING_REVIEW` until a matching final decision exists, including `UNDECIDED`. The prompt is neither stored nor displayed.
5. Display source data, evidence, and analysis in collapsible sections. Expand model inputs for `UNDECIDED`; render CSV values as text.

## Save a decision

1. User selects `HSBC` or `SUPPLIER` and provides a reason for every decision.
2. `POST /api/review` accepts `{incident_id, version, final_class, user_reason}` as same-origin JSON. Pydantic validates the payload; the trimmed reason must be nonblank and at most 2000 characters.
3. `review_store.submit_review` reloads the batch, verifies the incident is successful and pending, and compares the SHA-256 row version to reject stale decisions.
4. Copy the original row unchanged and add `FINAL_CLASS`, `USER_REASON`, `REVIEW_ACTION`, UTC `REVIEW_DATE`, and `STATUS=FINALIZED`.
5. Set action to `CONFIRMED` when labels match, `CORRECTED` when they differ, or `RESOLVED_UNDECIDED` for an undecided model result. Append to `data/run/FINAL.csv` using the shared CSV writer.
6. Return success only after saving. The UI reloads the queue after confirmation; unsuccessful saves leave the incident pending.

## Boundaries

- Review makes no LLM calls and preserves `LLM_OUTPUT.csv`. It never writes `HUMAN_REVIEW.csv`.
- CSV storage uses separate columns, without JSON blobs. The review API returns ordinary JSON objects/arrays for the frontend; evidence arrives as an array, not a JSON-encoded string.
- One local worker serializes review access with a lock. Invalid input/batches return errors; missing, finalized, stale, or conflicting decisions return HTTP 409.
- The dashboard runs independently. Its only data input is the saved `FINAL.csv`; see [dashboard_app.md](dashboard_app.md).
