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
   - `supplier_more_info`: additional documented supplier facts not covered by the five core fields; null for HSBC or when no extra information exists. Save as one plain-text CSV column.
   - `supporting_evidence`: one to ten standardized source column names as strings, for example `["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"]`. No quotes or source values are returned. At least one name is required; ten is a maximum, not a required count. Counts can differ between incidents.
5. Validate response structure and reject empty lists or more than ten names. Normalize supplier fields to null for HSBC; replace blank core supplier facts with Unknown for SUPPLIER, while empty supplier_more_info stays null. Store returned names as text. Weak, missing, or conflicting attribution belongs in the rationale with low confidence; confidence is not measured accuracy. Absence of supplier evidence alone does not establish HSBC responsibility.
6. Call `app/llm/save_csv.py:save_result` before requesting the next row. Save source values, scalar response fields, `processing_status`, and `error` to LLM_OUTPUT.csv. There is no human review status or approval step.

## Storage and failures

- Each source value and scalar result has its own CSV column. Save supporting source names in `evidence_1_column` through `evidence_10_column`; unused slots remain empty. There are no evidence quote columns.
- Keep prompt and definitions in YAML. Store no JSON blobs, definition columns, or prompt text in CSV; arrays are reconstructed only for display/API responses.
- Process sequentially. Successful rows have `processing_status=success`; failed responses are saved as failed where possible and stop the batch, preserving earlier results.
- Every non-ID column needs a definition. Nonblank temperature is converted to a number and passed to the provider without a local range check. Connection settings use `.env` via `app/llm/llm_connection.py`.
- Existing output files do not block starting requests. The shared CSV writer still requires nonempty IDs, compatible source/result columns, and no conflicting result for an existing ID.
- Older outputs with human-review fields, UNDECIDED tags, or the previous model schema are not silently migrated. Use a separate output folder for the new schema; update the dashboard input path accordingly. Existing CSVs, including earlier FINAL.csv files, remain untouched.

Implementation: `app/llm/pipeline.py` -> `app/llm/classification.py` -> `app/llm/save_csv.py`.
