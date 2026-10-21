# LLM request flow

Entry point: `python -m app.llm.pipeline` from the project root.

```text
CLEAN.csv -> one row per request -> validate response -> save LLM_OUTPUT.csv
```

## Per request

1. Take the next row from `data/run/CLEAN.csv`, in file order.
2. Keep `INCIDENT_ID` locally to associate the result with its source row.
3. `app/llm/prepare_fields.py` builds a JSON array for the other columns: `{name, description, value}`. Resolve each description by standardized column name from `fields/definitions.yml`.
4. Send two messages: `system` = the `system` value from `prompts/classification.yml`; `user` = the JSON array for this row. Repeat the prompt and definitions in every request. Requests contain no earlier rows or conversation history.
5. Request a structured JSON response using the `Classification` schema in `app/models.py`:
   - `classification`: `HSBC`, `SUPPLIER`, or `UNDECIDED`.
   - `key_root_cause`: one sentence, or `null` if unknown.
   - `decision_rationale`: concise evidence-based explanation.
   - `supporting_evidence`: a list of `{column, quote}` objects, without a count limit.
   - `llm_confidence`: integer 0-100; model-reported confidence, not measured accuracy.
   - `uncertainty_reason`: required nonblank text for `UNDECIDED`; `null` otherwise.
6. Validate the response structure with Pydantic and check classification/uncertainty consistency. `HSBC` and `SUPPLIER` require supporting evidence. Store evidence as returned; do not compare quotes with source text.
7. Call `app/llm/save_csv.py:save_result` immediately after validation, before requesting the next row. Save the source values, response fields, and processing/review metadata to `data/run/LLM_OUTPUT.csv`.

## CSV columns

- Each source value and scalar response field has its own column.
- Evidence uses numbered pairs: `evidence_1_column`, `evidence_1_quote`, and so on. Start with five empty pairs for a stable base header and add further pairs when returned. The writer expands existing headers and fills unused cells without dropping earlier evidence.
- Keep definitions in `fields/definitions.yml` and the prompt in `prompts/classification.yml`. Send both to the model on every request; store neither in the output CSV.
- Store no JSON blobs, arrays, or dictionaries in CSV cells. JSON is used only for API requests/responses in memory. Review reconstructs input fields from saved values plus the current definitions YAML, and evidence from the separate columns.
- Older outputs containing `llm_input` or JSON evidence are left unchanged; generate a new batch for review with this schema.

## Batch behavior

- Processing is sequential: three rows produce three separate requests when all succeed.
- Definitions and prompt are loaded once per batch; connection settings come from `.env` through `app/llm/llm_connection.py`.
- Every non-ID input column needs a definition. Existing `LLM_OUTPUT.csv` or `FINAL.csv` does not block starting the LLM pipeline. New incident IDs append to the existing output; a conflicting result for an existing ID still fails at CSV saving. Earlier results and final decisions are preserved.
- A nonblank `LLM_TEMPERATURE` is converted to a number and passed to the provider without a local range check. The provider decides whether it supports the value.
- Successful results, including `UNDECIDED`, receive `PENDING_REVIEW`. Human decisions are handled by the separate review app.
- API/validation errors or invalid responses stop the batch after attempting to save the failed row; earlier saved results remain. A save failure also stops processing.
- The shared CSV writer still requires nonempty IDs and rejects conflicting records with the same ID. Relaxed ID handling in data preparation does not extend to this stage.

Implementation: `app/llm/pipeline.py` -> `app/llm/classification.py` -> `app/llm/save_csv.py`.
