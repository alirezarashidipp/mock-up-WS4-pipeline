# API integration

The manual pipeline sends one incident per OpenAI request using the existing Responses API and Pydantic structured output. The review app uses FastAPI and makes no model calls.

Input column mapping is in `fields/column_mapping.csv`; definitions are in `fields/definitions.yml`. Each supplied field has its standardized UPPERCASE name, definition, and cleaned value. `ROW_ID` stays local.

## Classification response

The current stage has exactly six model fields:

| Field | Meaning |
| --- | --- |
| `classification` | `SUPPLIER`, `HSBC`, or `UNDECIDED`. |
| `key_root_cause` | One sentence stating the documented cause, or null if unknown. |
| `decision_rationale` | A short explanation of the accountability decision and relevant limitations. |
| `supporting_evidence` | Up to five objects with `column` and an exact `quote` from a cleaned input value. |
| `llm_confidence` | An integer from 0 to 100: model self-assessment of the selected label, including UNDECIDED; not measured accuracy. |
| `uncertainty_reason` | Missing or conflicting facts preventing attribution; required for UNDECIDED and null otherwise. |

A definite class requires evidence. Exact-quote checks verify that a snippet exists in the supplied field; they do not establish semantic correctness. Confidence never approves a row automatically.

The draft prompt distinguishes technical cause from accountability. A vendor defect can still support HSBC accountability when documented, feasible HSBC controls or upgrades would have prevented the impact. Unsupported assumptions about controls are forbidden. A recovery action alone does not establish responsibility. Business incidents use the same three classes based on the evidenced responsible party.

ServiceNow and architect labels are context, not sufficient proof. Architect fields remain visible as supplied context, so this is not a blind evaluation. No labelled few-shot examples were supplied or added.

## FastAPI review API

- GET `/api/review` returns successful records and counts for pending, human review, approved, and failed rows.
- POST `/api/reload` synchronizes undecided records into HUMAN_REVIEW and returns fresh records.
- POST `/api/review` accepts `row_id`, `version`, `decision` (Approved or Rejected), and `reason_of_rejection`.

Rejection requires a reason. Stale or already-routed records return 409. Approval writes `FINAL.csv`; rejection writes `HUMAN_REVIEW.csv`. Automatic routing uses `LLM_UNDECIDED`; user rejection uses `USER_REJECTED`.

All write requests require same-origin JSON. Run one local worker. CSVs using the earlier ten-field response need a new classification run in a separate batch folder; they are not silently relabelled.

HUMAN_REVIEW.csv stores only cleaned input columns plus STATUS, REVIEW_DATE, REJECTION_REASON, and LLM_UNCERTAINTY_REASON. FINAL.csv retains the model results too. Review responses expose review_date for display; timestamps are UTC and recorded when a row is first routed or reviewed. The mockup uses data/mockup/ and the manual pipeline defaults to data/run/.
