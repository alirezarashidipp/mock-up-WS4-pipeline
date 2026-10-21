# Review flow

Run `python -m app.review_app` from the project root after LLM results are saved. Open `http://127.0.0.1:8765/`.

```text
LLM_OUTPUT.csv + existing FINAL.csv -> review UI -> user decision -> append FINAL.csv
```

## Read and display

1. `GET /` serves `frontend/index.html`; `frontend/app.js` requests `GET /api/review`.
2. `review_app.py` calls `review_store.get_review_data`. Read `data/run/LLM_OUTPUT.csv` and optional `data/run/FINAL.csv` from the same batch.
3. Validate model results, input snapshots, evidence quotes, and existing final decisions. Failed model rows are counted but excluded from review records.
4. Return source fields, saved model input definitions/values, prompt, result, row version, and review state. Successful results remain `PENDING_REVIEW` until a matching final decision exists, including `UNDECIDED`.
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
- One local worker serializes review access with a lock. Invalid input/batches return errors; missing, finalized, stale, or conflicting decisions return HTTP 409.
- The dashboard runs independently. Its only data input is the saved `FINAL.csv`; see [dashboard_app.md](dashboard_app.md).
