# LLM classification and supplier extraction

Entry point: `python -m app.llm.pipeline` from the project root.

```text
CLEAN.csv -> one row per request -> validate response -> save LLM_OUTPUT.csv -> dashboard
```

## Per request

1. Read the next row from `data/run/CLEAN.csv`; retain INCIDENT_ID locally.
2. `app/llm/prepare_fields.py` builds `{name, description, value}` objects for non-ID columns, using `fields/definitions.yml`.
3. Send the `system` value from `prompts/classification.yml` plus that row's fields. Repeat the prompt and definitions on every independent request.
4. Parse the response with the Pydantic `Classification` model:
   - `classification`: HSBC or SUPPLIER, representing causal accountability rather than infrastructure ownership.
   - `key_root_cause`, `decision_rationale`, `llm_confidence`: documented cause, concise attribution explanation, and self-reported confidence from 0 to 100.
   - `supplier_name`, `supplier_product_or_service`, `supplier_action_or_failure`, `supplier_causal_explanation`, `supplier_accountability_reason`: null for HSBC; documented details or Unknown for SUPPLIER.
   - `supporting_evidence`: unlimited `{column, quote}` objects. These carry supporting text and source column names, including supplier signals.
5. Validate response structure. Normalize supplier fields to null for HSBC and replace blank/missing supplier facts with Unknown for SUPPLIER. Store evidence as returned; do not compare quotes against source values. An empty evidence list is allowed when nothing useful is recorded. Weak, missing, or conflicting attribution belongs in the rationale with low confidence; confidence is not measured accuracy. Absence of supplier evidence alone does not establish HSBC responsibility.
6. Call `app/llm/save_csv.py:save_result` before requesting the next row. Save source values, scalar response fields, `processing_status`, and `error` to LLM_OUTPUT.csv. There is no human review status or approval step.

## Storage and failures

- Each source value and scalar result has its own CSV column. Evidence uses numbered `evidence_N_column`/`evidence_N_quote` pairs; headers expand without dropping earlier evidence.
- Keep prompt and definitions in YAML. Store no JSON blobs, definition columns, or prompt text in CSV; arrays are reconstructed only for display/API responses.
- Process sequentially. Successful rows have `processing_status=success`; failed responses are saved as failed where possible and stop the batch, preserving earlier results.
- Every non-ID column needs a definition. Nonblank temperature is converted to a number and passed to the provider without a local range check. Connection settings use `.env` via `app/llm/llm_connection.py`.
- Existing output files do not block starting requests. The shared CSV writer still requires nonempty IDs, compatible source/result columns, and no conflicting result for an existing ID.
- Older outputs with human-review fields, UNDECIDED tags, or the previous model schema are not silently migrated. Use a separate output folder for the new schema; update the dashboard input path accordingly. Existing CSVs, including earlier FINAL.csv files, remain untouched.

Implementation: `app/llm/pipeline.py` -> `app/llm/classification.py` -> `app/llm/save_csv.py`.
