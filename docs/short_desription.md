# Classification, linking, and human review: short description

Classification returns 11 model fields. Engagement linking returns five model fields. Human review adds five local review fields without calling an LLM.

```text
CLEAN.csv -> Classification -> LLM_OUTPUT.csv
LLM_OUTPUT.csv + ENG_ALL.csv -> Engagement linking -> INC_LINKED.csv
INC_LINKED.csv -> Human review preparation -> HUMAN_REVIEW.csv
HUMAN_REVIEW.csv -> Human decisions -> Save HUMAN_REVIEW.csv
```

## LLM request defaults

- Both LLM calls use provider defaults for temperature and output length. These values are not configured by the application.
- No local tokenizer, tokenizer download, or input-token precheck runs. Input is not truncated; the provider's model limits still apply.
- Structured output and incomplete-response validation remain active. `LINK_MAX_CANDIDATES=70` still caps engagement candidates. See [request defaults](llm.md#request-defaults).

The archived diagram in `.archify/dataflow-ws4-pipeline-20261102-000851/` predates removal of the request settings. Its shared-budget description and frozen source snapshot are historical; the request defaults above describe the current code.

## Three dashboards

| Dashboard | Port | CSV | Main view |
| --- | --- | --- | --- |
| Classification | 8766 | LLM_OUTPUT.csv | HSBC, SUPPLIER, and UNCERTAIN results; read-only. |
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
- `evidence_column`: a list of 1-10 distinct, nonblank standardized column names from this row's model input. Return names only, without source values or quotations. Python rejects unknown or repeated names and does not trim or correct them. A referenced source value may be empty to identify missing information.
- `decision_rationale`: a short, evidence-based explanation of the classification.
- `classification`: exactly `HSBC`, `SUPPLIER`, or `UNCERTAIN`.
- `attribution_evidence_strength`: an integer from 0 to 4: unsupported, weak, moderate, strong, or very strong. This measures attribution evidence, not probability. Valid scores are 0-2 for `UNCERTAIN` and 1-4 for `HSBC` or `SUPPLIER`. Python rejects other combinations without changing the classification or score.

## CSV rules

- Save `evidence_column` in one cell, with names separated by comma and space. Synthetic example: `COLUMN_X, COLUMN_Y`.
- Preserve source columns and `INCIDENT_ID`; the LLM does not generate them. `INCIDENT_ID` is not sent to the LLM and cannot appear in `evidence_column`.
- Python adds `processing_status` and `error`. Valid classifications use `success` with an empty error; provider failures or invalid responses use `failed`. Invalid evidence names or score/classification combinations follow the same failure path: save the failed row where possible and stop, preserving earlier results.

See [LLM classification and supplier extraction](llm.md) for the full rules and output order.

## Which incidents enter linking?

Only incidents with `processing_status=success` and `classification=SUPPLIER` enter engagement matching.

- If a successful classification is `HSBC`, skip candidate search and the second LLM call. Set `link_status=NOT_APPLICABLE`.
- If a successful classification is `UNCERTAIN`, skip candidate search and the second LLM call. Set `link_status=SKIPPED`.

These incidents are still saved in INC_LINKED.csv with their original incident data and classification results. Engagement columns and `link_confidence` remain empty. Processing continues with the next incident.

## Engagement linking example

**Synthetic example:** an incident has `processing_status=success`, `classification=SUPPLIER`, and `supplier_name=Google`. Its recorded cause concerns a managed cloud backup service. The engagement IDs and service details below are invented for illustration.

1. Python checks each ENG_ALL row in CSV order. It checks `THIRD_PARTY_NAME` first, then `THIRD_PARTY_NORMALISED_NAME` if the first name does not match.
2. Names are normalized for matching: lowercase, ASCII folding, and single spaces between words. For example, `  GOOGLE   UK  ` becomes `google uk`. Source values stay unchanged.
3. Keep matching rows up to `LINK_MAX_CANDIDATES=70`, configured in `.env`. The first matches in CSV order are kept; there is no relevance ranking. If 10,000 rows contain only 30 Google matches, all 30 are kept.
4. Send the incident information and all 30 complete candidate rows together in one LLM request. Keep INCIDENT_ID local.

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
- HSBC is `NOT_APPLICABLE`; UNCERTAIN or failed classification is `SKIPPED`. These rows are saved without candidate search or a linking LLM call.
- A linking request or response failure becomes `FAILED` and stops the batch after saving where possible.

Python adds `link_status`, `link_error`, and `link_confidence_scale=0-4`; these are not LLM output fields. When no linking call occurs, the score stays blank. Old files without the scale marker keep their legacy 0-100 values, even if a value is only 3; they are not converted to the new rubric. Use a fresh output file for new results because the CSV schema has changed.

The input CSVs remain unchanged. The engagement dashboard reads INC_LINKED.csv. See [Incident-to-engagement linking](linking.md) for all output columns and validation rules.

## Engagement dashboard overview

- Show the total saved incidents, successfully classified total, and separate HSBC, SUPPLIER, and UNCERTAIN counts. Show unclassified/failed rows separately; UNCERTAIN belongs in the successful total.
- Only successful SUPPLIER classifications are eligible for linking. Count them as eligible even if the supplier is Unknown, no candidates are found, or linking fails.
- Show linked incidents, undecided Supplier incidents, link failures, engagements, and companies separately. The Unlinked incidents tab keeps its HSBC, Supplier, and Other groups for inspecting saved rows.
- All counts describe the saved INC_LINKED.csv snapshot. A partial linking run may contain fewer rows than the original input. The dashboard only reads this file; it does not call an LLM or write results.

See [Engagement dashboard](engagement_dashboard.md) for exact count definitions.

## Human review

Prepare `HUMAN_REVIEW.csv` from `INC_LINKED.csv`, preserving all source columns. Rerunning preparation keeps previous decisions and adds new incidents. Changed source values for an existing incident require a separate review output. Stop the review server before rerunning preparation.

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
- Successful HSBC and UNCERTAIN classifications can be reviewed, but their link review is `not_applicable`. Failed or unrecognized classifications count as `not_applicable` for classification review. Missing link proposals count as `not_applicable` for link review.
- In dashboard 3, rejected or invalidated links appear in Other unlinked incidents and remain visible under their original engagement with the review status. They no longer count as active links. Original model labels, scores, `linked_engagement_id`, and `ENG_` fields remain unchanged; use `hitl_linked_engagement_id` for the human-accepted link.
- Engagement first opens an engagement, its proposed incidents, then shared review controls. Incident first opens any saved incident directly, including unmatched, HSBC, UNCERTAIN, failed, and rejected rows. A save stays in the selected mode; rejecting a proposal does not remove access to that incident from its original engagement.

**Synthetic example:** a SUPPLIER incident proposes `DEMO-ENG-UK`. Confirming classification and link saves both as `confirmed` and fills `hitl_linked_engagement_id=DEMO-ENG-UK`. Rejecting only its link clears that effective ID while classification remains confirmed. Rejecting classification invalidates the link; confirming classification later does not automatically restore it.

## Human review progress

The progress panel stays visible in both review modes, on lists and incident details. It counts **all saved HUMAN_REVIEW.csv rows**, regardless of search, classification filter, or selected engagement. Successful saves and Refresh update the counts. These totals are separate from model classification counts and add no CSV columns.

The model overview shows total incidents, successful classifications and each class, then successful Supplier incidents with and without an original model match. These two Supplier counts sum to the successful Supplier total. Human-confirmed links are separate: rejecting a link changes its review result, not the saved model match.

**Synthetic example: eight saved incidents. These are illustrative counts, not actual project results.**

| Status | Meaning | Classification | Link |
| --- | --- | --- | --- |
| Confirmed | Approved by the reviewer. | 3 | 1 |
| Pending | No human decision yet. A link may await classification confirmation. | 3 | 1 |
| Rejected | Directly rejected by the reviewer, with a reason. | 1 | 1 |
| Invalidated | Link cancelled because classification was rejected. | Not used | 1 |
| Not applicable | No successful classification or matched link is available to review. | 1 | 4 |

Each review column totals eight incidents. Do not add the two columns together: they describe two decisions for the same incidents. HSBC and UNCERTAIN links count as Not applicable, never Pending.

See [Human review](human_review.md) for the CSV fields, state transitions, and run commands.
