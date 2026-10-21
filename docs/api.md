# API integration

The manual pipeline sends one incident per Chat Completions request with a strict JSON schema and validates the response locally with Pydantic. `app/llm/llm_connection.py` selects OpenAI API-key authentication or Azure service-principal authentication using `LLM_PROVIDER`. The review app uses FastAPI and makes no model calls.

Azure's supported JSON Schema subset omits some length and range constraints. The request schema omits those keywords for both providers, while the original Pydantic model still enforces them on the response. See [Microsoft's structured-output documentation](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs).

The preparation pipeline uses `fields/columns.yaml` for renaming and writes CLEAN.csv. The separate LLM pipeline reads CLEAN.csv and `fields/definitions.yml`. Each supplied field has its standardized UPPERCASE name, definition, and cleaned value. `INCIDENT_ID` stays local.

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

## Independent FastAPI apps

- Review app, port 8765: GET /api/review returns all successful records and counts for pending, finalized, undecided-pending, and failed rows. GET requests do not write files.
- Review app, port 8765: POST /api/review accepts incident_id, version, final_class (HSBC or SUPPLIER), and user_reason. All successful model classes can be finalized; a nonblank reason is required in every case.
- Dashboard app, port 8766: GET /api/dashboard reads FINAL.csv only and returns final-class counts, percentages, review-action counts, and finalized incident summaries. This app has no review or save API and works without the review process or LLM_OUTPUT.csv.

Review exposes the exact saved model_input list and prompt so changes to the YAML do not rewrite what the original model saw. UNDECIDED records stay pending and can be resolved by the user. No automatic HUMAN_REVIEW routing remains.

Finalization preserves the full original result and adds FINAL_CLASS, USER_REASON, REVIEW_ACTION, REVIEW_DATE, and STATUS=FINALIZED. Conflicting, stale, or duplicate decisions return 409. Invalid JSON fields return 422; a whitespace-only reason returns 400.

Writes require same-origin JSON. CSV values are rendered as text. Run one local worker. The review and dashboard make no model calls.
