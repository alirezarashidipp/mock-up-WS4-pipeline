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
   - `classification`: HSBC or SUPPLIER, representing causal accountability rather than infrastructure ownership.
   - `key_root_cause`, `decision_rationale`: documented cause and concise attribution explanation.
   - `attribution_evidence_strength`: integer 0-4 describing recorded evidence for the selected HSBC/SUPPLIER attribution, using the rubric below. This replaces `llm_confidence` in new results.
   - `supplier_name`, `supplier_product_or_service`, `supplier_action_or_failure`, `supplier_causal_explanation`, `supplier_accountability_reason`: null for HSBC; documented details or Unknown for SUPPLIER.
   - `supplier_more_info`: additional documented supplier facts not covered by the five core fields; null for HSBC or when no extra information exists. Save as one plain-text CSV column.
   - `supporting_evidence`: one to ten standardized source column names as strings, for example `["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"]`. No quotes or source values are returned. At least one name is required; ten is a maximum, not a required count. Counts can differ between incidents.
5. Validate response structure and reject empty lists, more than ten names, or evidence scores that are not integers from 0 to 4. Normalize supplier fields to null for HSBC; replace blank core supplier facts with Unknown for SUPPLIER, while empty supplier_more_info stays null. Store returned names as text. Weak, missing, or conflicting attribution belongs in the rationale and the evidence score. Absence of supplier evidence alone does not establish HSBC responsibility.
6. Call `app/llm/save_csv.py:save_result` before requesting the next row. Save source values, scalar response fields, `processing_status`, and `error` to LLM_OUTPUT.csv. There is no human review status or approval step.

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
supporting_evidence
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
| 0 | UNSUPPORTED | No recorded causal evidence distinguishes HSBC from Supplier; the required binary tag is tentative. |
| 1 | WEAK | Only indirect references or unconfirmed suspicion support the tag; key causal facts are absent. |
| 2 | MODERATE | Some relevant causal evidence exists, but a material contradiction or missing causal link remains. |
| 3 | STRONG | Concrete facts support the responsible party and mechanism; remaining gaps do not substantially challenge the tag. |
| 4 | VERY_STRONG | A clear documented causal finding has supporting details, with no unresolved material counterevidence in the supplied record. |

This is a model assessment of the supplied evidence, not a probability or measured accuracy. Zero does not mean the tag is false, and four does not guarantee it is true. Repeated statements are not independent evidence. A missing supplier name does not automatically weaken an otherwise supported Supplier attribution. Supplier-name certainty and engagement-link confidence are separate questions.

The model returns only the integer; dashboards derive its label. The provider schema restricts the score to the five integers, and Pydantic also rejects invalid values locally. No logprobs or extra model calls are added.

## Storage and failures

- Each source value and scalar result has its own CSV column. Join supporting source names with comma and space in one `supporting_evidence` cell, for example `INCIDENT_DESCRIPTION, ROOT_CAUSE_NOTES`. The CSV writer quotes that cell automatically. There are no numbered evidence or evidence quote columns in new outputs.
- Keep prompt and definitions in YAML. Store no JSON blobs, definition columns, or prompt text in CSV; arrays are reconstructed only for display/API responses.
- Process sequentially. Successful rows have `processing_status=success`; failed responses are saved as failed where possible and stop the batch, preserving earlier results.
- Every non-ID column needs a definition. Nonblank temperature is converted to a number and passed to the provider without a local range check. Connection settings use `.env` via `app/llm/llm_connection.py`.
- Existing output files do not block starting requests. The shared CSV writer still requires nonempty IDs, compatible source/result columns, and no conflicting result for an existing ID.
- Older outputs with `llm_confidence`, numbered evidence columns, human-review fields, UNDECIDED tags, or the previous model schema are not silently migrated. A 0-100 confidence value cannot be converted into this evidence rubric. Use a separate output folder for the new schema; update dashboard and linking input/output paths accordingly. The writer rejects appending the new schema to an older output. Dashboards show Not recorded when the evidence score is absent. Existing CSVs, including earlier FINAL.csv files, remain untouched.

Implementation: `app/llm/pipeline.py` -> `app/llm/classification.py` -> `app/llm/save_csv.py`.
