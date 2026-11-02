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
2. **Supplier name:** available only after the reviewed class is Supplier. Approved accepts a usable model supplier name. No requires a reason and a name selected from the catalog. Missing/Unknown names or a new Supplier attribution require a catalog selection. Needs review leaves the name unresolved. Saving any classification decision resets its dependent supplier review, even when approving the same model class again.

A corrected choice is an explicit human decision and is accepted for handoff, while remaining labelled Corrected by reviewer. Green status appears only after the server successfully saves. Approving Supplier classification alone does not approve its name. Reviewed HSBC needs no supplier decision. Model labels, scores, reasons, and names remain visible as the original proposal.

The separate review summary covers all loaded incidents, regardless of the selected model filter:

| Counter | Included rows |
| --- | --- |
| Classification approved / corrected | Current classification status is approved or corrected, for either HSBC or Supplier. |
| Classification awaiting decision | Every other current row: pending, Needs more information, or a stale prior decision. |
| Supplier name awaiting decision | Approved/corrected Supplier class whose name is not yet approved/corrected. |
| Ready for linking | Approved/corrected Supplier class and a usable approved/corrected supplier name. |

The first two counters sum to all current LLM_OUTPUT rows, including model processing failures. The last two describe the reviewed Supplier subset; HSBC does not need a supplier-name decision. Model totals and filters continue to reflect the original LLM result; a manually resolved processing failure remains in the Processing failures filter.

## Decision scenarios

| Model result / current step | Reviewer action | Saved outcome | Next step |
| --- | --- | --- | --- |
| HSBC is correct | Approved | Class `approved`, reviewed class HSBC | Review complete; no supplier-name decision or linking call. |
| HSBC should be Supplier | No, select SUPPLIER, explain why | Class `corrected` | Select the supplier from the catalog and explain the choice. |
| Supplier is correct | Approved | Class `approved`, supplier name `pending` | Review the supplier name separately. |
| Supplier should be HSBC | No, select HSBC, explain why | Class `corrected`, supplier name `not_applicable` | No supplier linking call. |
| UNCERTAIN or processing failure | Record human decision, select HSBC or SUPPLIER, explain why | Class `corrected`; original model result remains unchanged | Supplier requires a name decision; HSBC does not. |
| Human cannot determine the class | Select Cannot determine yet and give a reason | Class `needs_review`, reviewed class blank | Wait for more information; no linking. |
| Supplier name is correct | Approved in the supplier-name panel | Name `approved` | Ready for the next linking run. |
| Supplier name is wrong or missing | Select a catalog name and give a reason | Name `corrected` | Ready for the next linking run. |
| Correct supplier is unknown or absent from the catalog | Select Cannot determine / supplier not listed and give a reason | Name `needs_review`, reviewed name blank | Wait for more information; no linking. |

The UI labels a `needs_review` decision **Needs more information**. Selecting No only opens the correction form; it changes no saved decision until Save human decision succeeds. There is no separate `rejected` state in this stage: a saved No is either a reasoned correction or an unresolved review. Rejecting the supplier name leaves its approved classification unchanged. The later post-link review has its own `rejected` state.

## Supplier catalog

Place a UTF-8, single-column file at `data/mockup/SUPPLIER_NAME.csv`, with one supplier name per row. The `SUPPLIER_NAME` header is optional and case-insensitive; a headerless list is accepted. Trim leading and trailing whitespace for dropdown options, preserve case and internal text, and remove exact duplicate trimmed names in first-seen order. Blank rows are ignored; differently cased names remain separate. Dropdown loading does not use fuzzy matching or the engagement-search normalizer. Multiple columns are invalid. The app reads the catalog without changing it or adding supplier names.

**Synthetic catalog example (illustrative names only):**

```csv
SUPPLIER_NAME
Example Cloud Ltd
"Example Services, Inc."
```

Quote a name containing a comma so it remains one CSV cell. Removing the first line gives the supported headerless format. Approving a usable model name preserves that model value; a correction must match a current dropdown option exactly.

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

New incidents appear as pending when LLM_OUTPUT.csv is read. CLASSIFICATION_REVIEW.csv is created on the first successful decision save and contains only incident IDs with saved decisions; opening the page or refreshing does not add untouched rows. Review totals use all current LLM_OUTPUT rows, including those absent from the review CSV. Saved decisions are valid only for the same source row. If an incident's source values change, its old approval is not reused; refresh and review it again. The old saved row remains on disk until a new decision for that incident is saved. The page displays the current source as pending with a stale-review warning in the meantime. A write validates the incident ID, current source and review version, allowed transition, required reason, and any selected catalog name before atomically replacing the review CSV. Changed source columns require a fresh classification-review output, preserving the older file. Reasons must be nonblank when required and at most 2,000 characters. `review_version` and `review_stale` are API metadata, not CSV columns. Repeated or blank source IDs cannot safely identify a review and are rejected here; data-preparation behavior is unchanged.

If another save or source change invalidates the page version, the save is rejected; Refresh loads the current state. Failed saves retain the entered form text and do not turn the decision green.

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
