# LLM request flow

Entry point: `python -m app.llm.pipeline` from the project root.

```text
CLEAN.csv -> one row per request -> validate response -> save LLM_OUTPUT.csv
```

## Per request

1. Take the next row from `data/run/CLEAN.csv`, in file order.
2. Keep `INCIDENT_ID` locally to associate the result with its source row.
3. Build a JSON array for the other columns: `{name, description, value}`. Resolve each description by standardized column name from `fields/definitions.yml`.
4. Send two messages: `system` = the `system` value from `prompts/classification.yml`; `user` = the JSON array for this row. Repeat the prompt and definitions in every request. Requests contain no earlier rows or conversation history.
5. Request a structured JSON response using the `Classification` schema in `app/models.py`:
   - `classification`: `HSBC`, `SUPPLIER`, or `UNDECIDED`.
   - `key_root_cause`: one sentence, or `null` if unknown.
   - `decision_rationale`: concise evidence-based explanation.
   - `supporting_evidence`: up to five `{column, quote}` objects with exact input quotes.
   - `llm_confidence`: integer 0-100; model-reported confidence, not measured accuracy.
   - `uncertainty_reason`: required nonblank text for `UNDECIDED`; `null` otherwise.
6. Validate with Pydantic and verify evidence quotes against this row. `HSBC` and `SUPPLIER` require supporting evidence.
7. Save the source row, response fields, `llm_input` snapshot, `llm_prompt`, and processing/review metadata to `data/run/LLM_OUTPUT.csv` before processing the next row.

## Batch behavior

- Processing is sequential: three rows produce three separate requests when all succeed.
- Definitions and prompt are loaded once per batch; connection settings come from `.env` through `app/llm/llm_connection.py`.
- Every non-ID input column needs a definition. Existing `LLM_OUTPUT.csv` or `FINAL.csv` in the output folder blocks a new batch.
- Successful results, including `UNDECIDED`, receive `PENDING_REVIEW`. Human decisions are handled by the separate review app.
- API/validation errors or invalid responses stop the batch after attempting to save the failed row; earlier saved results remain. A save failure also stops processing.
- The shared CSV writer still requires nonempty IDs and rejects conflicting records with the same ID. Relaxed ID handling in data preparation does not extend to this stage.

Implementation: `app/llm/pipeline.py` -> `app/llm/classification.py` -> `app/llm/save_csv.py`.
