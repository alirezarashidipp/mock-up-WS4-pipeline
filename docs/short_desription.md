# Classification, linking, and human review: short description

Classification returns 11 model fields. Human classification review adds six local fields before linking. Engagement linking returns five model fields. The later review of proposed links adds five separate `hitl_` fields. Neither human-review dashboard calls an LLM.

```text
CLEAN.csv -> Classification -> LLM_OUTPUT.csv
LLM_OUTPUT.csv + SUPPLIER_NAME.csv -> Human classification review -> CLASSIFICATION_REVIEW.csv
LLM_OUTPUT.csv + CLASSIFICATION_REVIEW.csv + ENG_ALL.csv -> Approved incidents -> Engagement linking -> INC_LINKED.csv
INC_LINKED.csv -> Human review preparation -> HUMAN_REVIEW.csv
HUMAN_REVIEW.csv -> Human decisions -> Save HUMAN_REVIEW.csv
```

## LLM request defaults

- Both LLM calls use provider defaults for temperature and output length. These values are not configured by the application.
- No local tokenizer, tokenizer download, or input-token precheck runs. Input is not truncated; the provider's model limits still apply.
- Structured output and incomplete-response validation remain active. `LINK_MAX_CANDIDATES=70` still caps engagement candidates. See [request defaults](llm.md#request-defaults).

The archived diagram in `.archify/dataflow-ws4-pipeline-20261102-000851/` and its frozen source snapshot are historical. The request defaults and output-validation rules in this document describe the current code.

## Three dashboards

| Dashboard | Port | CSV | Main view |
| --- | --- | --- | --- |
| Classification | 8766 | LLM_OUTPUT.csv; SUPPLIER_NAME.csv; CLASSIFICATION_REVIEW.csv | Model results, classification approval/correction, then supplier-name approval/correction. Saves separate human decisions. |
| Engagements | 8767 | INC_LINKED.csv | Engagements -> incidents -> details; read-only. |
| Human review | 8768 | HUMAN_REVIEW.csv; ENG_ALL.csv read-only catalog | Engagement first or Incident first -> shared details and Yes/No review; saves human decisions. |

Dashboards 2 and 3 start with engagement cards showing the name, company, ID, and incident count. Dashboard 3 also offers Incident first: all saved incidents, searchable and filterable by All, HSBC, SUPPLIER, UNCERTAIN, or failed/unclassified. Both review modes use the same incident details, buttons, and saved decisions. Unlinked incidents have a separate tab. Refresh keeps the selected view and reloads saved data.

Dashboard 3's Engagement first shows the full ENG_ALL catalog, including zero-incident engagements, plus saved proposal IDs absent from that catalog. Total engagements counts distinct IDs across both sources. Saved proposal values stay unchanged. If the catalog cannot be read or validated, the view shows saved proposal groups with a scope warning instead of claiming to show the full inventory.

## Classification rules

- If `classification` is `HSBC`, all six supplier fields return `null`.
- If `classification` is `SUPPLIER`, supplier fields contain documented facts. Missing core details return `Unknown`; `supplier_more_info` returns `null` when no extra facts exist.
- If `classification` is `UNCERTAIN`, all six supplier fields return `null`. `decision_rationale` explains the missing or conflicting facts that prevent assigning responsibility.
- `UNCERTAIN` is a successful classification, not a processing error. A missing supplier name alone does not require `UNCERTAIN`.

The six supplier fields are:

1. `supplier_name`: the responsible supplier's name.
2. `supplier_product_or_service`: the related product, service, or infrastructure.
3. `supplier_action_or_failure`: the recorded action, defect, or omission.
4. `supplier_causal_explanation`: how the supplier's action caused the incident or its impact.
5. `supplier_accountability_reason`: why the evidence supports assigning responsibility to the supplier.
6. `supplier_more_info`: additional documented facts, without repeating the other fields.

## Other output fields

- `key_root_cause`: the documented root cause in one sentence, or `null` if unknown.
- `evidence_column`: a list of strings that may be empty, with no fixed maximum count. An empty list saves a blank evidence cell and does not fail classification. The prompt requests relevant source column names, but Python does not check membership, spelling, duplicates, or blank individual names. Save entries in returned order without correction or deduplication.
- `decision_rationale`: a short, evidence-based explanation of the classification.
- `classification`: exactly `HSBC`, `SUPPLIER`, or `UNCERTAIN`.
- `attribution_evidence_strength`: an integer from 0 to 4: unsupported, weak, moderate, strong, or very strong. This measures attribution evidence, not probability. Valid scores are 0-2 for `UNCERTAIN` and 1-4 for `HSBC` or `SUPPLIER`. Python rejects other combinations without changing the classification or score.

## CSV rules

- Save `evidence_column` in one cell, with names separated by comma and space. Synthetic example: `COLUMN_X, COLUMN_Y`.
- Preserve source columns and `INCIDENT_ID`; the LLM does not generate them. `INCIDENT_ID` is not sent to the LLM. Evidence source names are model-reported and are not checked against the input headers.
- Pydantic output failures report only the response field and error type, such as `ValidationError: key_root_cause: string_too_short`; no incident text or raw model output is logged.
- Python adds `processing_status` and `error`. Valid classifications use `success` with an empty error; provider failures or invalid responses use `failed`. Invalid response structure or score/classification combinations follow the same failure path: save the failed row where possible and stop, preserving earlier results.

See [LLM classification and supplier extraction](llm.md) for the full rules and output order.

## Human classification review

The first dashboard keeps the model result and saves the human decision separately in CLASSIFICATION_REVIEW.csv:

1. Approve a model HSBC/SUPPLIER classification, or choose No and supply a reason plus the corrected class. A reviewer can also resolve UNCERTAIN or a processing failure with a manual HSBC/SUPPLIER decision and reason.
2. If the reviewed class is Supplier, separately approve the model supplier name, or choose No, explain why, and select the correct name from SUPPLIER_NAME.csv. Missing/Unknown names also require a catalog choice. Changing classification resets the supplier decision.
3. If the facts or correct supplier are unavailable, leave the decision Needs review. Status becomes green only after a successful save. Original model labels, supplier details, and scores are preserved.

The six added fields are `classification_review_status`, `reviewed_classification`, `classification_review_reason`, `supplier_review_status`, `reviewed_supplier_name`, and `supplier_review_reason`. Approved and corrected are completed human decisions; pending and Needs review are not. Supplier status is not applicable for HSBC. Source changes invalidate earlier approval until reviewed again.

Place the UTF-8 supplier list at `data/mockup/SUPPLIER_NAME.csv`, one name per row with an optional `SUPPLIER_NAME` header. A missing or invalid catalog shows a warning and supplies no invented names. See [classification dashboard](dashboard_app.md) for the full contract.

## Which incidents enter linking?

Saving review does not call an LLM. The next `python -m app.linking.pipeline` run applies these rules:

- Approved/corrected Supplier classification plus approved/corrected supplier name enters matching with the reviewed name.
- Approved/corrected HSBC is saved as NOT_APPLICABLE, with no candidate search or linking call.
- Pending, Needs review, incomplete supplier decisions, and stale reviews stay out of INC_LINKED.csv until resolved. Original UNCERTAIN or failed results can enter only after an explicit human decision.

The output preserves original incident/model values and the six review fields. Identical already-saved reviewed rows are skipped on rerun. Changing a saved incident's source or human decision requires a fresh output batch.

**Synthetic correction example:** the model says Supplier/Google. The reviewer approves Supplier but rejects Google, records a reason, and selects Microsoft from the catalog. Candidate search uses Microsoft; the original Google proposal stays available for comparison.

## Engagement linking example

**Synthetic example:** an incident has `processing_status=success`, `classification=SUPPLIER`, and `supplier_name=Google`. The reviewer approves both Supplier attribution and the Google name. Its recorded cause concerns a managed cloud backup service. The engagement IDs and service details below are invented for illustration.

1. Python checks each ENG_ALL row in CSV order. It checks `THIRD_PARTY_NAME` first, then `THIRD_PARTY_NORMALISED_NAME` if the first name does not match.
2. Names are normalized for matching: lowercase, ASCII folding, and single spaces between words. For example, `  GOOGLE   UK  ` becomes `google uk`. Source values stay unchanged.
3. Keep matching rows up to `LINK_MAX_CANDIDATES=70`, configured in `.env`. The first matches in CSV order are kept; there is no relevance ranking. If 10,000 rows contain only 30 Google matches, all 30 are kept.
4. Python records `link_candidate_count=30`, then sends the incident information and all 30 complete candidate rows together in one LLM request. Keep INCIDENT_ID local. If 100 rows match but the cap is 70, the saved count is 70.

Three illustrative candidates from that shortlist:

| ENGAGEMENT_ID | THIRD_PARTY_NAME | ENGAGEMENT_DESCRIPTION_TEXT |
| --- | --- | --- |
| DEMO-ENG-UK | Google UK | Managed cloud backup service |
| DEMO-ENG-US | Google US | Business email service |
| DEMO-ENG-IN | Google India | Analytics service |

The LLM compares the incident with the candidates. In this example, the documented backup-service details could support selecting `DEMO-ENG-UK`; the company name or country suffix alone is insufficient. The model returns one supplied `ENGAGEMENT_ID`, or `null` if the evidence cannot distinguish a suitable engagement.

The second LLM call returns five fields:

| Field | Meaning |
| --- | --- |
| `linked_engagement_id` | One supplied engagement ID, or null. |
| `link_reason` | A short explanation of the selection or ambiguity. |
| `link_confidence` | Link evidence strength: 0 unsupported, 1 weak, 2 moderate, 3 strong, 4 very strong. It is not a probability. |
| `link_incident_columns` | Incident column names used for the decision. |
| `link_engagement_columns` | ENG_ALL column names used for the decision. |

`link_confidence` must be an integer: selected links allow 1-4; null selections allow 0-2. Python rejects inconsistent combinations without changing the result. Strings, booleans, floats, and values outside 0-4 are invalid. This score is separate from classification evidence strength.

Python validates the selection and saves the result to **`data/run/INC_LINKED.csv`** before processing the next incident:

- A valid selection becomes `link_status=MATCHED`. Preserve the original incident columns, copy the selected engagement's actual values into `ENG_` columns, and add the link decision fields.
- No candidates or an ambiguous selection becomes `link_status=UNDECIDED`; engagement columns remain empty.
- Human-approved HSBC is `NOT_APPLICABLE`, with no candidate search or linking call. Unresolved reviews are not saved to this output; they can enter a later run after review.
- A linking request or response failure becomes `FAILED` and stops the batch after saving where possible.

Python accepts the returned source-name strings in `link_incident_columns` and `link_engagement_columns` without checking them against input headers. List types and nonempty lists for a selected engagement are still checked.

Python adds `link_status`, `link_error`, `link_candidate_count`, and `link_confidence_scale=0-4`; these are not LLM output fields. The candidate count is the shortlist size after the cap: zero for no candidates and blank when search is skipped. It remains saved after a failed request or response and does not prove delivery to the provider. When no linking call occurs, the score stays blank. Old files without the scale marker keep their legacy 0-100 values, even if a value is only 3; they are not converted to the new rubric. Preserve older files and use fresh linking and human-review outputs for the new schema, including files that lack the six classification-review fields or `link_candidate_count` even if they already have the scale marker. Update the pipeline and dashboard paths for the new batch.

The input CSVs remain unchanged. The engagement dashboard reads INC_LINKED.csv. See [Incident-to-engagement linking](linking.md) for all output columns and validation rules.

## Engagement dashboard overview

- Show the total saved incidents, successfully classified total, and separate HSBC, SUPPLIER, and UNCERTAIN counts. Show unclassified/failed rows separately; UNCERTAIN belongs in the successful total.
- For new reviewed rows, linking eligibility uses approved/corrected Supplier attribution and name. Original model class counts remain separate; a corrected original HSBC, UNCERTAIN, or failed result can be eligible. Legacy rows retain their successful-Supplier interpretation.
- Show linked incidents, undecided Supplier incidents, link failures, engagements, and companies separately. The Unlinked incidents tab keeps its HSBC, Supplier, and Other groups for inspecting saved rows.
- All counts describe the saved INC_LINKED.csv snapshot. A partial linking run may contain fewer rows than the original input. The dashboard only reads this file; it does not call an LLM or write results.

See [Engagement dashboard](engagement_dashboard.md) for exact count definitions.

## Review after linking

This later review is separate from classification approval on port 8766. Prepare `HUMAN_REVIEW.csv` from `INC_LINKED.csv`, preserving all source columns, including the six earlier review fields. Rerunning preparation keeps previous decisions and adds new incidents. Changed source values for an existing incident require a separate review output. Stop the review server before rerunning preparation.

The five additional CSV columns are:

| Column | Meaning |
| --- | --- |
| `hitl_classification` | Classification review: pending, confirmed, rejected, or not_applicable. |
| `hitl_classifivation_reasninb` | Required classification rejection reason; the spelling matches the requested column name. |
| `hitl_link` | Link review: pending, confirmed, rejected, invalidated, or not_applicable. |
| `hitl_link_reasoning` | Required link rejection reason, or the explanation for automatic invalidation. |
| `hitl_linked_engagement_id` | Accepted engagement ID; filled only when classification and link are both confirmed. |

- Classification Yes saves `confirmed` and clears its rejection reason. Classification No requires a reason, saves `rejected`, and invalidates any proposed link.
- Link review requires confirmed classification and an existing matched SUPPLIER proposal. Link Yes saves `confirmed`; Link No requires a reason and saves `rejected`. Neither action changes classification.
- Confirmations turn green only after saving successfully. If classification is confirmed again after rejection, its invalidated link becomes `pending` and needs a fresh link decision.
- For new rows, use the saved human-reviewed class and supplier eligibility for review and link availability; original model values stay visible. Legacy rows without these fields retain successful-model review rules: HSBC/UNCERTAIN have no link review, and failed/unrecognized classifications are not applicable. Missing link proposals are not applicable for link review.
- In dashboard 3, rejected or invalidated links appear in Other unlinked incidents and remain visible under their original engagement with the review status. They no longer count as active links. Original model labels, scores, `linked_engagement_id`, and `ENG_` fields remain unchanged; use `hitl_linked_engagement_id` for the human-accepted link.
- Engagement first opens an engagement, its proposed incidents, then shared review controls. Incident first opens any saved incident directly, including unmatched, HSBC, UNCERTAIN, failed, and rejected rows. A save stays in the selected mode; rejecting a proposal does not remove access to that incident from its original engagement.

**Synthetic example:** a SUPPLIER incident proposes `DEMO-ENG-UK`. Confirming classification and link saves both as `confirmed` and fills `hitl_linked_engagement_id=DEMO-ENG-UK`. Rejecting only its link clears that effective ID while classification remains confirmed. Rejecting classification invalidates the link; confirming classification later does not automatically restore it.

## Human review progress

The progress panel stays visible in both review modes, on lists and incident details. It counts **all saved HUMAN_REVIEW.csv rows**, regardless of search, classification filter, or selected engagement. Successful saves and Refresh update the counts. These totals are separate from model classification counts and add no CSV columns.

The overview shows total incidents and original successful model classifications by class, then eligible Supplier incidents with and without an original model match. For new rows this Supplier cohort follows the human-reviewed class and name; legacy rows use the model result. The two Supplier counts sum to the eligible total, which can differ from the original model-Supplier total. Human-confirmed links are separate: rejecting a link changes its review result, not the saved model match.

**Synthetic example: eight saved incidents. These are illustrative counts, not actual project results.**

| Status | Meaning | Classification | Link |
| --- | --- | --- | --- |
| Confirmed | Approved by the reviewer. | 3 | 1 |
| Pending | No human decision yet. A link may await classification confirmation. | 3 | 1 |
| Rejected | Directly rejected by the reviewer, with a reason. | 1 | 1 |
| Invalidated | Link cancelled because classification was rejected. | Not used | 1 |
| Not applicable | No successful classification or matched link is available to review. | 1 | 4 |

Each review column totals eight incidents. Do not add the two columns together: they describe two decisions for the same incidents. Reviewed HSBC and legacy UNCERTAIN links count as Not applicable, never Pending.

See [Human review](human_review.md) for the CSV fields, state transitions, and run commands.
