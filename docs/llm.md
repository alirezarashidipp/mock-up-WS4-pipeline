# LLM classification and supplier extraction

Entry point: `python -m app.llm.pipeline` from the project root.

```text
CLEAN.csv -> one row per request -> validate response -> save LLM_OUTPUT.csv -> dashboard
```

## Per request

1. Read the next row from `data/run/CLEAN.csv`; retain INCIDENT_ID locally.
2. `app/llm/prepare_fields.py` builds `{name, description, value}` objects for non-ID columns, using `fields/definitions.yml`, in the input order below. It preserves all original values, including empty values.
3. Send the `system` value from `prompts/classification.yml` plus that row's fields. Repeat the prompt and definitions on every independent request.
4. Parse the response with the Pydantic `Classification` model:
   - `classification`: HSBC, SUPPLIER, or UNCERTAIN. HSBC/SUPPLIER represent causal accountability rather than infrastructure ownership. Use UNCERTAIN when missing facts, conflicting evidence, or shared responsibility prevent choosing a party; explain why in `decision_rationale`.
   - `key_root_cause`, `decision_rationale`: documented cause and concise attribution explanation.
   - `attribution_evidence_strength`: integer 0-4 describing recorded support for attributing responsibility, using the rubric below. For UNCERTAIN, use 0-2 for the available attribution evidence, not certainty about being uncertain. This replaces `llm_confidence` in new results.
   - `supplier_name`, `supplier_product_or_service`, `supplier_action_or_failure`, `supplier_causal_explanation`, `supplier_accountability_reason`: null for HSBC and UNCERTAIN; documented details or Unknown for SUPPLIER.
   - `supplier_more_info`: additional documented supplier facts not covered by the five core fields; null for HSBC/UNCERTAIN or when no extra information exists. Save as one plain-text CSV column.
   - `evidence_column`: one to ten distinct, nonblank standardized source column names from this row's model input, for example `["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"]`. No evidence quotations or source values are returned. For UNCERTAIN, names can identify fields showing ambiguity or missing causal information. At least one name is required; ten is a maximum, not a target.
5. `parse_response(response, fields)` checks completion/refusal and validates the Pydantic response. It rejects HSBC/SUPPLIER with score 0 and UNCERTAIN with score 3 or 4. It also checks that each evidence name is nonblank, appears exactly in the supplied input field names, and is not repeated. Names are not trimmed, corrected, or deduplicated; valid names keep their returned order. A source value may be empty when it identifies missing information. INCIDENT_ID cannot be evidence because it is not sent to the model. Empty evidence lists, more than ten names, or scores that are not integers from 0 to 4 remain invalid. `normalize_supplier_fields` sets supplier fields to null for HSBC/UNCERTAIN; blank core Supplier facts become Unknown, while empty supplier_more_info stays null. Absence of supplier evidence alone does not establish HSBC responsibility.
6. Call `app/llm/save_csv.py:save_result` before requesting the next row. Save source values, scalar response fields, `processing_status`, and `error` to LLM_OUTPUT.csv. There is no human review status or approval step.

UNCERTAIN is a valid classification with `processing_status=success`; it does not stop the batch. A provider failure or invalid response has `processing_status=failed`. Failed evidence-name or score/classification checks use this same failure path: save the failed row where possible, stop the batch, and preserve earlier results. Python does not repair the names or change the classification. A missing supplier name alone does not require UNCERTAIN when Supplier accountability is otherwise supported. A documented technical cause may remain available even when the accountable party is uncertain.

## Request defaults

Classification and linking use the selected provider's defaults for temperature and output length. Requests omit `temperature`, `max_tokens`, and `max_completion_tokens`. There is no local token-counting step, tokenizer download, or input-token precheck. The provider's model limits still apply; input is not truncated.

Strict JSON schema, Pydantic validation, refusal checks, and incomplete-response checks remain active. The shared connection keeps its 60-second SDK timeout and one SDK retry. `LINK_MAX_CANDIDATES` independently limits shortlisted rows.

## Input and output order

`FIELD_ORDER` in `app/llm/prepare_fields.py` lists the priority columns in these groups:

1. Incident/problem narrative: short descriptions, descriptions, and summaries.
2. Recorded causes: `ROOT_CAUSE_NOTES`, `IT_INCIDENT_CAUSE_DETAILS`, `PROBLEM_TASK_CAUSE_NOTES`, root-cause code, and causing-change ID.
3. Closure/resolution: close notes, resolution descriptions/details, fix notes, workaround, and read-across details.
4. Investigation history: incident/problem work notes, major-incident findings, and additional comments.
5. Context: supplier names, configuration items, business services, assignment groups, and ownership.
6. Remaining metadata and additional columns, in their original source order.

Only columns present in the row are sent. Every non-ID column still needs a definition and is included exactly once. Reordering affects only the model payload; it does not reorder source CSVs or saved source fields. Field position and names do not establish authority: recorded confirmation, timing, and counterevidence matter across all fields.

The Pydantic model defines this response schema order, also used for new CSV result columns after the source columns:

```text
key_root_cause
evidence_column
decision_rationale
classification
attribution_evidence_strength
supplier_name
supplier_product_or_service
supplier_action_or_failure
supplier_causal_explanation
supplier_accountability_reason
supplier_more_info
```

The rationale remains a short evidence-based explanation, not a detailed internal thought process. Schema order controls the serialized response, not the model's internal reasoning. This ordering is a design choice; offline checks do not establish improved classification accuracy.

## Attribution evidence strength

| Score | Display label | Recorded support for the selected attribution |
| --- | --- | --- |
| 0 | UNSUPPORTED | No recorded causal evidence distinguishes HSBC from Supplier; choose UNCERTAIN. |
| 1 | WEAK | Only indirect references or unconfirmed suspicion support the tag; key causal facts are absent. |
| 2 | MODERATE | Some relevant causal evidence exists, but a material contradiction or missing causal link remains. |
| 3 | STRONG | Concrete facts support the responsible party and mechanism; remaining gaps do not substantially challenge the tag. |
| 4 | VERY_STRONG | A clear documented causal finding has supporting details, with no unresolved material counterevidence in the supplied record. |

This is a model assessment of the supplied evidence, not a probability or measured accuracy. Zero does not mean the tag is false, and four does not guarantee it is true. Repeated statements are not independent evidence. A missing supplier name does not automatically weaken an otherwise supported Supplier attribution. Supplier-name certainty and engagement-link confidence are separate questions.

For UNCERTAIN, a score of 0-2 describes how much causal support is available for assigning responsibility to one party. It does not measure confidence in abstaining. Valid scores are 0-2 for UNCERTAIN and 1-4 for HSBC/SUPPLIER. Python rejects UNCERTAIN with scores of 3 or 4 and HSBC/SUPPLIER with score 0; it does not automatically change the classification or score. Scores of 1 or 2 do not force a party classification to UNCERTAIN.

The model returns only the integer; dashboards derive its label. The provider schema restricts the score to the five integers, and Pydantic also rejects invalid values locally. No logprobs or extra model calls are added.

## Storage and failures

- Each source value and scalar result has its own CSV column. Join source names with comma and space in exactly one `evidence_column` cell, for example `INCIDENT_DESCRIPTION, ROOT_CAUSE_NOTES`. The CSV writer quotes that cell automatically so its commas do not create additional columns. New outputs contain neither `supporting_evidence`, numbered evidence columns, nor evidence quotation columns. The model uses a JSON list for validation; the saved CSV cell is plain text, not a JSON blob.
- Keep prompt and definitions in YAML. Store no JSON blobs, definition columns, or prompt text in CSV; arrays are reconstructed only for display/API responses.
- Process sequentially. Successful HSBC, SUPPLIER, and UNCERTAIN rows have `processing_status=success`; failed responses are saved as failed where possible and stop the batch, preserving earlier results.
- Every non-ID column needs a definition. Connection settings use `.env` via `app/llm/llm_connection.py`.
- Existing output files do not block starting requests. The shared CSV writer still requires nonempty IDs, compatible source/result columns, and no conflicting result for an existing ID.
- Older outputs with `llm_confidence`, `supporting_evidence`, numbered evidence columns, human-review fields, UNDECIDED tags, or the previous model schema are not silently migrated. A 0-100 confidence value cannot be converted into this evidence rubric. Use a separate output folder for the new schema; update dashboard and linking input/output paths accordingly. The writer rejects appending the new schema to an older output. Dashboards show Not recorded when the evidence score is absent and read legacy evidence columns without rewriting them. Existing CSVs, including earlier FINAL.csv files, remain untouched.

Implementation: `app/llm/pipeline.py` -> `app/llm/classification.py` -> `app/llm/save_csv.py`.

## Explicit live connection check

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

`tests/check_llm_connection.py` prepares one visibly synthetic incident with the existing field definitions and classification YAML prompt. It reuses `llm_connection` and `classify_row`, so the selected OpenAI/Azure provider, provider defaults for temperature and output length, `store=False`, strict JSON schema, and existing response validation all apply. No local tokenizer runs before the request. Success requires a valid structured classification, not a particular label or exact evidence score. Empty, refused, incomplete, malformed, or semantically inconsistent responses fail.

The check makes one logical completion request when its connection settings are valid; the shared SDK retry setting still applies. It reads no incident CSV and writes no CSV output. Console output contains a fixed success message or a sanitized exception type, not raw provider messages or generated text. Ordinary `test_*.py` discovery skips this live check. Passing it verifies that request's connectivity and classification contract; it does not establish classification accuracy or validate the linking schema.
