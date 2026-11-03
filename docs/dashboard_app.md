# Single incident dashboard

Run `python -m app.ui.dashboard_app` and open [http://127.0.0.1:8766](http://127.0.0.1:8766).

The app reads and updates **data/run/INCIDENTS.csv**. It reads SUPPLIER_NAME.csv for base-name corrections and ENG_ALL.csv for complete engagement details and matching. Catalog files are never written. There is one incident-first view; the former engagement-first and separate human-review dashboards have been removed.

## Browse and counts

Every initialized incident appears, including pending and failed processing. Model class counts distinguish HSBC, SUPPLIER, and UNCERTAIN; processing failures remain separate. Search, clickable count cards, and review filters narrow the visible list. Global counts describe the whole saved batch and stay independent of these filters.

Each incident opens a summary and three ordered review panels. On desktop, Classification and Supplier name sit side by side in the top row, with a full-width Engagement panel underneath. Narrow screens stack the panels. Source fields and supporting details use closed dropdowns. Model results and human decisions are labeled separately. CSV values render as text. Opening a detail or refreshing results does not call an LLM or save a decision. Country and actor context is labeled as original model extraction: incident country, supplier country, causing party, affected party, and resolving party. Missing values remain explicit. These facts remain separate from human supplier-name choices and are not silently reassigned when a name is corrected.

Two separate dropdowns identify the model stages:

- **Classification evidence and supplier details** shows the original classification, processing status, root cause, source-column evidence links, Supplier facts, and `Classification:` citations.
- **Linking evidence and engagement details** shows linking status, the lookup supplier, model default, decision reason, link evidence strength, retrieval/suggestion counts, each saved suggestion's ID/reason/score, and `Engagement:` citations. The saved current engagement's catalog details are labeled separately because a human choice can differ from the model default. NOT_APPLICABLE and SKIPPED remain visible when linking did not run.

Citations remain unverified text in one shared CSV cell; the frontend separates them by their saved stage prefixes. Missing stage citations are explicitly shown as not recorded. Unprefixed legacy text stays visible under **Unassigned legacy citations (stage unknown)** in the classification dropdown and is not attributed to classification. This display change adds no columns or model requests. **Original incident fields** retains its existing content, layout, and source-link navigation.

## Review aids

- **At a glance** summarizes the whole saved batch with deterministic counts: successful classifications, pending/failed processing, remaining reviews, and human-confirmed links. It makes no extra model request.
- **Where review is waiting** assigns every incident to exactly one bucket: processing, classification, supplier name, engagement, or complete. Counts stay global while search and filters change; a bucket opens its review queue. Pending processing waits for the pipeline; failed classification can proceed to manual review. Reviewed HSBC and completed no-link decisions belong to complete.
- **Next action** identifies the first unfinished step for the open incident and explains what to do. It uses the existing review rules.
- **AI proposal vs human decision** compares classification, supplier name, and engagement with saved reasons. Classification and supplier values are the original model results; the engagement proposal is the current model default, which may have been replaced after a supplier correction. Pending, not-applicable, and completed no-link decisions remain distinct. This is a current-state comparison, not an audit history.
- **Evidence links** open and focus the corresponding saved source field. Unknown evidence names are visibly unavailable; empty source values remain inspectable. This navigation does not add model-output validation or verify citation excerpts.
- **Engagement comparison** places up to three current Python matches side by side, including catalog fields, available suggestion reasons and evidence scores, and default/human-choice labels. Different catalog values are highlighted; a difference is not proof that either option is correct. Missing data remain explicit. Browsing and comparing candidates do not select or approve them.
- **How Python matched this name** shows the lookup base name, normalized names, matching source column, and containment or fuzzy-match method. The explanation reuses the matching logic, checks THIRD_PARTY_NAME before THIRD_PARTY_NORMALISED_NAME, and retains source order. Fuzzy similarity at 0.8 is a retrieval rule, not a probability or relevance score.

## Guided synthetic scenarios

The collapsed walkthrough presents three illustrative cases: approve a Supplier result; correct a supplier name and explain the refreshed suggestions; resolve an Uncertain classification through a reasoned human decision. Previous/next controls explain the ordered steps.

The walkthrough is visibly synthetic and runs only in the browser. Its example outcomes are illustrative, not live model results. It makes no provider calls, saves no decisions, and does not enter the incident counts. Real incident review continues through the existing forms and POST endpoints.

These review aids reuse the single dashboard and existing saved data. They add no CSV columns, processing pipeline, or extra dashboard.

## Decisions

| Step | Approved | Disagree |
| --- | --- | --- |
| Classification | Accept a successful model HSBC/SUPPLIER result. | Require a reason and corrected class. HSBC/SUPPLIER resolve the stage; UNCERTAIN remains unresolved. |
| Supplier name | Accept the original model's usable base supplier name. | Require a reason and exact choice from SUPPLIER_NAME.csv. |
| Engagement | Explicitly accept the model default. | Require a reason and choose another current Python match, or None of these. |

Pending processing cannot be reviewed. A failed model classification can be resolved manually with a reason. Approved UNCERTAIN cannot advance: the reviewer must resolve the class first. Reviewed HSBC completes review without supplier/engagement decisions. Reviewed Supplier requires both later steps.

Supplier corrections from the dropdown immediately call the reusable engagement finder. The server saves the correction and resets the old engagement decision before requesting fresh suggestions. Busy/error messages describe the current operation. A failure preserves the correction; retry uses the same function.

The model returns up to five suggestions with reasons and evidence scores, and selects its strongest by default. The reviewer can also browse and select **all** Python matches, including candidates beyond the LLM cap. A stored model default is never silently human-approved. None of these completes review with a blank human engagement ID, so completed-review and confirmed-link counts differ.

## Engagement selection

- Show up to five model suggestions directly as cards. Each card includes its engagement ID, service details, reason, and numeric evidence strength. Stronger evidence uses a deeper green; equal scores use the same shade. The legend makes clear that color describes model evidence, not human approval.
- Keep the model-default badge separate from the locally selected radio option and the saved human decision. Clicking a suggestion or choosing a dropdown option updates the pending selection only.
- The labeled search field and native dropdown cover all Python matches, including rows beyond the LLM cap. Search by engagement ID, supplier name, or service. A selected engagement remains available when it does not match the current search; clearing the search restores the full list. Card and dropdown selections stay synchronized.
- Explicitly approve the model default with the approval action naming its ID. Selecting another engagement or None of these requires a nonblank reason and an explicit save. Model-default selection alone does not confirm a link.
- Engagement decisions remain locked until classification and supplier-name review are complete. Stale incident/catalog results and running suggestions cannot be approved. Viewing cards, changing the pending selection, searching, and comparing make no model request or saved decision.

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

Use UTF-8 CSV in either supported format:

- One supplier base-name column, with an optional SUPPLIER_NAME header, preserving existing files.
- Two headered columns, SUPPLIER_NAME and COUNTRY, in either order; header matching is case-insensitive. Country cells may be blank.

Record one country per row and repeat a base name for multiple countries. Exact repeated names become one choice with their country metadata. Outer whitespace is trimmed in memory and source order is retained. Use consistent country names; the app does not guess or populate missing country values. Legal entities and individual engagements remain in ENG_ALL.csv. Catalogs are read-only.

The correction form searches partial names without case or accent sensitivity and optionally filters by country. All countries is the default; incident or model supplier country never silently prefilters choices. Results arrive in pages of 50, with navigation and a total count, instead of mounting thousands of options. The selected name is preserved across search/filter/page changes. Clearing the country filter restores access to names without country metadata. Searching and browsing do not call a model or save a decision.

A correction still requires a nonblank reason and an exact name from the current catalog at save time. Country is browsing metadata, not supplier identity, a saved human country decision, or a hard engagement-search constraint. The catalog is not sent to the classification model. Missing/invalid catalogs produce visible messages rather than an empty successful result.

## API and persistence

`app/ui/dashboard_app.py` owns HTTP routes, request validation, and dashboard response data. It passes file paths to `app/review.py`, which owns human decisions, completion rules, supplier-name choices, and engagement refreshes. `app/incidents.py` owns reads, version checks, and atomic incident updates. These modules keep framework state out of the review rules.

- GET /api/dashboard: all incidents with next actions, global model/review and bottleneck counts, the overview text, distinct supplier count, country choices, and catalog notes. It does not include the full supplier-name list.
- GET /api/suppliers?q=...&country=...&offset=0: up to 50 matching distinct supplier names with their countries, filtered total, offset, has_more, and an error field.
- GET /api/incidents/{id}/engagements: all matches, matching explanations, up to five suggestions, defaults/human choice, saved engagement details, and catalog freshness.
- POST /api/review: save an ordered classification, supplier, or engagement decision.
- POST /api/incidents/{id}/refresh-links: rerun suggestions after supplier review is complete.

Engagement approval reads the catalog once, checks its saved fingerprint, finds the supplier matches, validates the selected ID, and copies values from that same catalog snapshot. It does not build a display response to validate a decision.

The page and favicon reuse `frontend/pictures/hsbc-logo.svg`. HTML and JavaScript remain in `frontend/dashboard/`, with shared styling in `frontend/style.css`.

The frontend uses the current API arrays for source fields, evidence names, matches, and suggestions directly. Saved engagement details and candidate details share one renderer; all three disagreement forms share the nonblank-reason check.

Dashboard data follows read inputs -> describe each incident -> count -> return. The frontend comparison separates initial candidate choices, user selection controls, and table rendering into plainly named functions in the existing files.

Writes require the current version, valid choices, and nonblank disagreement reasons. The loopback server checks request host/origin and JSON content type. Atomic CSV replacement and a short file lock serialize pipeline/dashboard writes; the lock is released during provider calls. Run one local dashboard process. The input source values and identifiers are immutable after initialization; changed sources require a fresh batch.

Older unified `INCIDENTS.csv` files missing `citations` or any of the five country/actor context columns display those fields blank. GET requests do not rewrite files or rerun models. The next normal save adds the missing supported columns and preserves source values, other rows, and decisions.

Paths are defined in app/incidents.py and imported by the pipeline/dashboard. The old separate review files are preserved as archives; their decisions are not imported into INCIDENTS.csv.
