# Classification dashboard and human review

Run `python -m app.ui.dashboard_app` from the project root. Open `http://127.0.0.1:8766/`.

```text
LLM_OUTPUT.csv + SUPPLIER_NAME.csv -> inspect model result -> review classification -> review supplier name
    -> save CLASSIFICATION_REVIEW.csv -> eligible for the next linking pipeline run
```

## Request flow

1. `GET /` serves `frontend/dashboard/index.html`; `frontend/dashboard/app.js` requests `GET /api/dashboard` on load and Refresh.
2. Read `app.state.results_file` (LLM_OUTPUT.csv), merge saved decisions from `app.state.review_file` (CLASSIFICATION_REVIEW.csv), and load dropdown names from `app.state.suppliers_file` (SUPPLIER_NAME.csv). Source and model values remain unchanged. GET and Refresh do not save decisions.
3. Count successful HSBC, SUPPLIER, and UNCERTAIN rows in the total and in their own counters. UNCERTAIN is a valid result when the model cannot assign responsibility from the record; count failed processing rows separately. Return both successful and failed rows as dashboard records. Failed records include their saved error and original source fields; they do not contribute to the classified total.
4. Render each incident as a card. Failed cards show processing status, the saved error, and the Source fields dropdown instead of presenting a successful classification. Keep classification, decision_rationale, and attribution_evidence_strength visible. Display the score as 0-4 with its label: Unsupported, Weak, Moderate, Strong, or Very strong. The expandable scale explains all five levels. This rates recorded support for assigning responsibility to HSBC or Supplier, not a probability of correctness, supplier-name extraction, or engagement matching. For UNCERTAIN, the 0-2 score describes limited support for a party attribution, not confidence in uncertainty. Only SUPPLIER cards show all six supplier fields, including supplier_more_info with an empty-state message when no extra facts exist.
5. Keep source-column names, processing_status, and key_root_cause in the closed-by-default Evidence and processing details dropdown. `read_evidence_columns` splits the single `evidence_column` CSV cell on commas, trims spaces, and returns nonempty names as the API's `evidence_column` list. For older files, it reads `supporting_evidence`, then numbered `evidence_N_column` cells if neither single-column format is present. No saved file is rewritten. Keep saved input values in a separate Source fields dropdown.
6. Show separate classification and supplier-name review panels. `POST /api/classification-review` saves a decision, then returns refreshed records and counts. Keep the selected model filter after a successful save. Render CSV values, names, and reasons as text. Share `frontend/style.css` and logo artwork in `frontend/pictures/`.

## Summary filters

The five summary counts are buttons. Select one to filter the incident cards:

| Button | Visible records |
| --- | --- |
| Classified incidents | All successful HSBC, SUPPLIER, and UNCERTAIN rows; this is the default view. |
| HSBC | Successful HSBC rows. |
| SUPPLIER | Successful SUPPLIER rows. |
| UNCERTAIN | Successful UNCERTAIN rows. |
| Processing failures | Failed rows, including the saved error and original source fields. |

Only one filter is active at a time. The active button is visibly selected and exposes its state with `aria-pressed`. All five counts always describe the complete saved file; filtering does not recalculate them. An empty selection shows a message for that group. Refresh rereads the file and keeps the selected filter. Selecting Classified incidents returns to the full successful-results view. Buttons support both mouse and keyboard use.

## Two human decisions

1. **Classification:** Approved accepts a successful model HSBC or SUPPLIER result. No requires a reason and a corrected HSBC/SUPPLIER choice. For UNCERTAIN or failed processing, the reviewer can make a manual choice with a reason. If the facts remain insufficient, choose Needs review rather than forcing a class.
2. **Supplier name:** available only after the reviewed class is Supplier. Approved accepts a usable model supplier name. No requires a reason and a name selected from the catalog. Missing/Unknown names or a new Supplier attribution require a catalog selection. Needs review leaves the name unresolved. A classification change resets its dependent supplier review.

A corrected choice is an explicit human decision and is accepted for handoff, while remaining labelled Corrected by reviewer. Green status appears only after the server successfully saves. Approving Supplier classification alone does not approve its name. Reviewed HSBC needs no supplier decision. Model labels, scores, reasons, and names remain visible as the original proposal.

The separate review summary counts completed classification decisions, pending classifications, pending supplier-name decisions, and Supplier incidents ready for linking. These totals cover all loaded incidents, regardless of the selected model filter. Model totals and filters continue to reflect the original LLM result; a manually resolved processing failure remains in the Processing failures filter.

## Supplier catalog

Place a UTF-8, single-column file at `data/mockup/SUPPLIER_NAME.csv`, with one supplier name per row. The `SUPPLIER_NAME` header is optional and case-insensitive; a headerless list is accepted. Blank rows and duplicate names do not create extra dropdown options. Preserve name spelling. Multiple columns are invalid. The app reads the catalog without changing it or adding supplier names.

A missing, empty, unreadable, or invalid catalog produces a visible warning. The reviewer can still inspect incidents and approve a usable existing model name, but cannot save a catalog correction until a valid option is available. If the actual supplier is absent, leave the name Needs review and update the source catalog separately; do not select an unrelated company.

## Saved review fields

`data/run/CLASSIFICATION_REVIEW.csv` preserves the source row and adds six local fields. It is separate from LLM_OUTPUT.csv and from the later HUMAN_REVIEW.csv.

| Field | Meaning |
| --- | --- |
| `classification_review_status` | `pending`, `approved`, `corrected`, or `needs_review`. |
| `reviewed_classification` | Human-selected `HSBC` or `SUPPLIER`; blank while unresolved. |
| `classification_review_reason` | Required explanation for correction or Needs review. |
| `supplier_review_status` | `pending`, `approved`, `corrected`, `needs_review`, or `not_applicable`. |
| `reviewed_supplier_name` | Approved model name or selected catalog name; blank while unresolved or not applicable. |
| `supplier_review_reason` | Required explanation for correction or Needs review. |

New incidents start without approval. Saved decisions are valid only for the same source row. If an incident's source values change, its old approval is not reused; refresh and review it again. A write validates the incident ID, current source and review version, allowed transition, required reason, and any selected catalog name before atomically replacing the review CSV. Changed source columns require a fresh classification-review output, preserving the older file. Reasons must be nonblank when required and at most 2,000 characters. `review_version` and `review_stale` are API metadata, not CSV columns. Repeated or blank source IDs cannot safely identify a review and are rejected here; data-preparation behavior is unchanged.

The local API checks Host and Origin on writes and serializes updates in one server process. Run one classification-review server for a given output file. It stores current decisions, not a reviewer-identity or audit-history system.

## Handoff to linking

Saving a decision never starts an LLM request. Run `python -m app.linking.pipeline` after reviewing incidents. Only a current, approved/corrected Supplier classification with an approved/corrected supplier name can enter candidate search. Approved/corrected HSBC rows need no linking call. Pending, Needs review, or stale rows are held out of INC_LINKED.csv, so later approval can enter a subsequent run. The [linking document](linking.md) defines output preservation and rerun behavior.

## Boundaries

- The app reads LLM_OUTPUT.csv, CLASSIFICATION_REVIEW.csv, and SUPPLIER_NAME.csv. It writes only CLASSIFICATION_REVIEW.csv, imports no LLM modules, and makes no model calls.
- The later [review of proposed links](human_review.md) remains separate on port 8768 and uses HUMAN_REVIEW.csv. No FINAL.csv is created.
- A missing or empty input produces an empty dashboard. Older HSBC/SUPPLIER rows can lack supplier details; display unrecorded details as Unknown without changing the CSV or inventing facts. Invalid processing statuses or successful classification labels outside HSBC, SUPPLIER, and UNCERTAIN return an error. Failed rows may have a blank classification. REVIEW_STATUS is not used.
- Older results without `attribution_evidence_strength` show Not recorded. Never convert legacy `llm_confidence` percentages into evidence-strength scores. Unexpected nonblank scores display Invalid score. The [classification document](llm.md) defines the new response schema and rubric.
- Refresh rereads the file. There is no automatic polling or notification from the LLM pipeline.
- Configure source, review, and catalog paths through `RESULTS_FILE`, `REVIEW_FILE`, and `SUPPLIERS_FILE`. The dashboard can run independently once source rows exist. Preserve earlier output files when changing batch paths.
