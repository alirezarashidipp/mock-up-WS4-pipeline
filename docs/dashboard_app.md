# Single incident dashboard

Run `python -m app.ui.dashboard_app` and open [http://127.0.0.1:8766](http://127.0.0.1:8766).

The app reads and updates **data/run/INCIDENTS.csv**. It reads SUPPLIER_NAME.csv for base-name corrections and ENG_ALL.csv for complete engagement details and matching. Catalog files are never written. There is one incident-first view; the former engagement-first and separate human-review dashboards have been removed.

## Browse and counts

Every initialized incident appears, including pending and failed processing. Model class counts distinguish HSBC, SUPPLIER, and UNCERTAIN; processing failures remain separate. Search, clickable count cards, and review filters narrow the visible list. Global counts describe the whole saved batch and stay independent of these filters.

Each incident opens a summary and three review panels in order, left to right on desktop. Source fields and supporting details use closed dropdowns. Model results and human decisions are labeled separately. CSV values render as text. Opening a detail or refreshing results does not call an LLM or save a decision. The model-evidence dropdown shows the shared `citations` cell as **Model citations (not verified)**, with Classification and Engagement lines rendered as text.

## Decisions

| Step | Approved | Disagree |
| --- | --- | --- |
| Classification | Accept a successful model HSBC/SUPPLIER result. | Require a reason and corrected class. HSBC/SUPPLIER resolve the stage; UNCERTAIN remains unresolved. |
| Supplier name | Accept the original model's usable base supplier name. | Require a reason and exact choice from SUPPLIER_NAME.csv. |
| Engagement | Explicitly accept the model default. | Require a reason and choose another current Python match, or None of these. |

Pending processing cannot be reviewed. A failed model classification can be resolved manually with a reason. Approved UNCERTAIN cannot advance: the reviewer must resolve the class first. Reviewed HSBC completes review without supplier/engagement decisions. Reviewed Supplier requires both later steps.

Supplier corrections from the dropdown immediately call the reusable engagement finder. The server saves the correction and resets the old engagement decision before requesting fresh suggestions. Busy/error messages describe the current operation. A failure preserves the correction; retry uses the same function.

The model returns up to five suggestions with reasons and evidence scores, and selects its strongest by default. The reviewer can also browse and select **all** Python matches, including candidates beyond the LLM cap. A stored model default is never silently human-approved. None of these completes review with a blank human engagement ID, so completed-review and confirmed-link counts differ.

## Upstream changes and stale results

- Saving classification resets supplier and engagement reviews. Non-Supplier classes clear engagement proposals.
- Saving supplier review resets engagement approval. A changed base name clears/recomputes the proposals.
- Changing only engagement does not alter classification or supplier review.
- Refreshing engagement suggestions resets human engagement approval and saves a new default.
- Catalog changes make existing suggestions stale; refresh before approving an engagement. Changed catalog column structure requires a fresh output batch.
- Each displayed incident carries a computed review_version, including the persisted row_revision that increases on every save. A save or completed model request with an old version is rejected rather than overwriting a newer decision.
- Confirmations turn green only after the server saves successfully. Filters and the open incident are retained after a save.

## Saved fields

Original model fields remain separate from these nine human fields:

| Field | Meaning |
| --- | --- |
| classification_review_status | pending, approved, or disagree. |
| reviewed_classification | Human-selected class; blank until a decision. |
| classification_review_reason | Reason for classification disagreement. |
| supplier_review_status | pending, approved, disagree, or not_applicable. |
| reviewed_supplier_name | Accepted/corrected base supplier name. |
| supplier_review_reason | Reason for supplier-name disagreement. |
| engagement_review_status | pending, approved, disagree, or not_applicable. |
| reviewed_engagement_id | Human-selected engagement; blank until explicitly chosen, or after None of these. |
| engagement_review_reason | Reason for changing/rejecting the model default. |

linked_engagement_id remains the current model default. The actual selected catalog values are stored in ENG_ columns: initially the model default, later the human choice. Upstream resets/rejections clear or restore this snapshot consistently. These are current-state decisions, not an audit trail of every earlier click.

## Supplier catalog

Use a UTF-8 one-column CSV with optional SUPPLIER_NAME header. Names are base names, such as AXA; legal entities and country variants belong in ENG_ALL.csv. Outer whitespace is trimmed; exact duplicate names are removed while retaining source order. Corrections must select a current catalog name. Missing/invalid catalogs produce visible messages rather than an empty successful result.

## API and persistence

`app/ui/dashboard_app.py` owns HTTP routes, request validation, and dashboard response data. It passes file paths to `app/review.py`, which owns human decisions, completion rules, supplier-name choices, and engagement refreshes. `app/incidents.py` owns reads, version checks, and atomic incident updates. These modules keep framework state out of the review rules.

- GET /api/dashboard: all incidents, model/review counts, supplier options, and catalog notes.
- GET /api/incidents/{id}/engagements: all matches, up to five suggestions, defaults/human choice, saved engagement details, and catalog freshness.
- POST /api/review: save an ordered classification, supplier, or engagement decision.
- POST /api/incidents/{id}/refresh-links: rerun suggestions after supplier review is complete.

Engagement approval reads the catalog once, checks its saved fingerprint, finds the supplier matches, validates the selected ID, and copies values from that same catalog snapshot. It does not build a display response to validate a decision.

The page and favicon reuse `frontend/pictures/hsbc-logo.svg`. HTML and JavaScript remain in `frontend/dashboard/`, with shared styling in `frontend/style.css`.

The frontend uses the current API arrays for source fields, evidence names, matches, and suggestions directly. Saved engagement details and candidate details share one renderer; all three disagreement forms share the nonblank-reason check.

Writes require the current version, valid choices, and nonblank disagreement reasons. The loopback server checks request host/origin and JSON content type. Atomic CSV replacement and a short file lock serialize pipeline/dashboard writes; the lock is released during provider calls. Run one local dashboard process. The input source values and identifiers are immutable after initialization; changed sources require a fresh batch.

Older unified `INCIDENTS.csv` files without `citations` display a blank value. GET requests do not rewrite them; the next normal save adds this column and preserves other values and decisions.

Paths are defined in app/incidents.py and imported by the pipeline/dashboard. The old separate review files are preserved as archives; their decisions are not imported into INCIDENTS.csv.
