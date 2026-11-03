# Project instructions

- This is a small Python 3.11 demo. Use plain functions, short explicit steps, and direct library calls. Keep Python code in app/.
- Keep code, configuration, docs, and UI text in English. Keep project instructions in this root AGENTS.md only.
- Preserve source CSV files and identifiers. CSV files, data/, credentials, and .env stay out of Git; never print credentials or raw provider errors.
- Mark synthetic examples visibly. Verify changes with a lightweight affected-code check; distinguish offline checks from live API results. Create test files only when the user asks.

## Code style

- Keep entry points and coordinators readable as a short recipe: read inputs, prepare, classify and save, then link and save. Put request/error-handling details in plainly named functions.
- Prefer ordinary functions, clear variables, direct library calls, and separate readable statements. Preserve domain names such as INCIDENT_ID.
- Reuse existing modules and dependencies. Remove code with no callers and repeated implementations; do not add generic workflow wrappers, new configuration systems, or many tiny files.
- Implement the current CSV/API contract directly. Keep validation for invalid input, credentials, source preservation, and safe saves; remove only checks proven redundant.
- Preserve behavior while refactoring. Add no speculative features or production infrastructure, and create no test files unless asked. Use a small affected-code check and report exactly what ran.

## Read relevant docs and implementation first

- Preparation/cleaning: docs/data_preparation.md.
- Classification/LLM requests: docs/llm.md.
- Engagement matching/suggestions: docs/linking.md.
- Dashboard/human decisions: docs/dashboard_app.md.
- Setup and commands: README.md. Compact business flow: docs/short_description.md.
- Update the relevant docs when behavior changes. README.md and docs/short_description.md link the current source-backed .archify workflow diagrams; older diagram folders and frozen source documents remain historical.

## Keep the workflow simple

- Do not change Cleaning unless explicitly requested. app/data_preparation/pipeline.py remains read -> rename -> clean -> save CLEAN.csv. Preparation retains empty/repeated IDs and uppercases unmapped headers; add no ID, CSV-shape, or mapping-collision checks to that stage.
- Cleaning removes invisible control/format characters only; preserve punctuation, emails, HTML, and normal whitespace.
- One LLM entry point: app/llm/pipeline.py reads CLEAN.csv, initializes all pending incidents, then classifies and automatically finds engagements for each incident before advancing to the next.
- One dashboard: app/ui/dashboard_app.py on loopback port 8766, frontend/dashboard/, frontend/style.css, and existing logo in frontend/pictures/.
- One current output: data/run/INCIDENTS.csv, containing immutable source values, model results, link proposals, selected ENG_ values, and separate human decisions. Preserve old CSVs without automatic migration; no FINAL.csv or duplicate dashboards/pipelines.
- Keep the reusable find_engagements function in app/linking/linking.py independent of saving and human approval. Both the pipeline and real-time supplier corrections call it.
- Keep shared classification/linking contracts, output defaults, citation formatting, and schema-limit conversion in app/models.py, without file or provider calls.
- Keep incident storage, schema/version checks, and selected engagement snapshots in app/incidents.py. Keep human decision rules and refresh orchestration in app/review.py with explicit file-path arguments; it must not depend on FastAPI state.
- Keep HTTP routing, request validation, and dashboard presentation in app/ui/dashboard_app.py. Reuse frontend/pictures/hsbc-logo.svg for the page and favicon instead of duplicating artwork.

## Classification

- Names belong in fields/columns.yaml, standardized definitions in fields/definitions.yml, and instructions in prompts/classification.yml.
- Use Pydantic inputs/responses and strict Structured Outputs. Keep INCIDENT_ID local. Order inputs: narrative, causes, closure/resolution, investigation history, supplier/product context, remaining metadata. Preserve every non-ID source value.
- Classify HSBC, SUPPLIER, or UNCERTAIN. UNCERTAIN is a successful result when attribution is unsupported or conflicting; explain limitations in decision_rationale.
- Output order: preserve the original 12 fields (root cause, evidence_column, citations, rationale, classification, evidence strength, six supplier fields), then append incident_country, supplier_country, causing_party, affected_party, and resolving_party. All 17 keys are required in model responses; the five new fields allow null.
- Supplier fields are null for HSBC/UNCERTAIN. For SUPPLIER, extract recorded facts; missing core details become Unknown, absent extra facts become null. supplier_name is the documented base name; retain useful full-entity/country details in supplier_more_info without inventing a parent company.
- Country/actor context must come from recorded facts only; use null for missing, ambiguous, or conflicting information. Distinguish incident/affected-service country from the involved supplier entity/operations country. Use English country names when unambiguous and semicolons for multiple explicit countries; never guess from headquarters, currency, names, or unrelated locations. Keep supplier_country null for HSBC/UNCERTAIN. Affected and resolving actors are not automatically causal actors; roles may be documented for any class.
- attribution_evidence_strength is a strict integer 0-4, not probability. Reject UNCERTAIN above 2 and HSBC/SUPPLIER at 0; preserve valid 1-4 definite classifications. Do not repair inconsistent labels/scores.
- evidence_column is a list of strings, including an empty list, with no fixed maximum. Python does not validate individual names, duplicates, or blanks. Preserve order and join with comma and space in one cell; no source excerpts in evidence_column or numbered evidence columns.
- Both responses include citations as a list of strings; [] is valid. Check structure only, not exact quotes, source labels, duplicates, blanks, or length. Save one shared citations cell with Classification: and Engagement: line prefixes. Replacing or clearing a model link result replaces only its citation lines. Exclude saved citations from subsequent linking inputs.
- Preserve completion/refusal/schema validation, including Azure-compatible schema restrictions. Reuse the current OpenAI/Azure connection and provider defaults; do not reintroduce temperature or token-limit controls removed at the user's request.
- Save classification before linking, and save linking before processing the next incident. Save a failed row and stop. Reruns retry unfinished/failed work without overwriting human decisions or completed results.

## Engagements

- Automatic model Supplier results enter matching immediately; human approval is not a batch prerequisite. HSBC is NOT_APPLICABLE; UNCERTAIN is SKIPPED. Missing supplier names produce no matches.
- Normalize only for matching. Within each ENG_ALL row check THIRD_PARTY_NAME before THIRD_PARTY_NORMALISED_NAME; add each matching row once. Preserve original values and source order.
- Retain ALL matches for human browsing. LINK_MAX_CANDIDATES is a positive .env integer defaulting to 70 and caps only the first rows prepared for the LLM. This is not a relevance ranking or token budget.
- Keep all-match, capped-candidate, and suggestion counts separate; a count does not prove delivery to the provider.
- Return at most five distinct suggestions, each with reason and strict evidence score 1-4. Every ID must belong to the supplied shortlist. The selected default must be one of the strongest suggestions. Empty suggestions require a null default; do not force a link.
- Evidence strength is not measured confidence/probability. No linking call leaves the score blank. Keep original classification evidence distinct from link evidence.
- Save fixed flat suggestion slots, not JSON CSV cells. Persist selected catalog values in ENG_ columns, not LLM-generated catalog text. Keep old-schema output files untouched.

## Human review and persistence

- The dashboard lists all incidents and exposes three ordered steps: Classification -> Supplier name -> Engagement. Keep original model values distinct from human decisions.
- Classification: Approved accepts a successful definite model class; Disagree requires a reason and corrected class. UNCERTAIN remains unresolved until a definite class is selected. Failed results can be manually resolved; pending processing cannot.
- Reviewed HSBC completes review without downstream stages. Reviewed Supplier requires name review, then engagement review.
- Supplier: approve a usable model base name, or select a current SUPPLIER_NAME.csv base name with a reason. Changing the name immediately reruns find_engagements; failures preserve the correction and allow retry.
- Engagement: explicit approval is required even for the saved default. A different selection may come from ALL Python matches and requires a reason. None of these requires a reason and completes review without an accepted link.
- Changes to upstream decisions reset downstream approvals. Rejection of engagement leaves earlier decisions intact. Never treat a model default or pending proposal as human-confirmed.
- Keep nine fields: classification_review_status/reviewed_classification/classification_review_reason; supplier_review_status/reviewed_supplier_name/supplier_review_reason; engagement_review_status/reviewed_engagement_id/engagement_review_reason.
- linked_engagement_id is the current model default; reviewed_engagement_id is the explicit human choice. ENG_ values follow the current selection. These are current-state records, not an audit history.
- Keep source values immutable, validate IDs/schema in the unified processing stage, and reject changed-source batches. Do not add such checks to Cleaning.
- Serialize writes with the existing atomic CSV writer and a short interprocess file lock. Increment the persisted row_revision on every save and include it in per-row versions; stale browser saves and old model responses must not overwrite newer decisions. Release locks during provider calls.
- Existing unified INCIDENTS.csv files missing citations or any of the five country/actor fields read those missing columns as blank in memory. Do not write on GET, invent old facts, or rerun completed models for missing context. The next normal save adds the supported missing columns while retaining sources, other rows, and decisions; malformed rows and historical output formats remain rejected/untouched.
- Catalogs are read-only. Check candidate membership and catalog freshness before engagement approval. Changed catalog columns require a fresh output batch.
- Render CSV values as text, show missing/invalid catalog messages, keep original model counts separate from human review progress, and preserve list filters/open incident after save.
- No LLM calls or file writes on GET. Human supplier correction/retry may call the LLM on POST. Green confirmation appears only after a successful save.

## Dashboard review aids

- Preserve the existing Original incident fields content, layout, and behavior unless explicitly requested otherwise.
- Keep separate Classification evidence and supplier details and Linking evidence and engagement details dropdowns. Display citations only under their saved Classification:/Engagement: stage; keep unprefixed legacy text explicitly unassigned, never guessed. Preserve the shared CSV cell, unverified labels, evidence-source navigation, and no-call/empty states.
- Keep Classification and Supplier name side by side on desktop, with Engagement spanning the next row; stack panels on narrow screens.
- Show original model country/actor context separately from human decisions. Do not imply a corrected supplier inherits the previous model supplier's country or role.
- Accept supplier catalogs as legacy one-column base names (optional header) or headered SUPPLIER_NAME,COUNTRY in either order with case-insensitive headers. COUNTRY is optional per row; aggregate repeated exact base names and their countries without writing the catalog or guessing metadata.
- Supplier correction uses partial-name search, an explicit optional country filter defaulting to all, and pages of 50 choices. Retain selections across filtering and paging; keep all names reachable. GET /api/suppliers returns bounded results; dashboard data returns supplier count/country choices rather than thousands of names.
- Validate the exact current catalog name and a nonblank disagreement reason on save. Country is browsing metadata only: no new human-review country column, automatic geographic exclusion from engagement matching, or supplier catalog in the classification prompt.
- Show suggestion cards with numeric evidence scores and consistent green shades by score. Distinguish evidence color, model default, pending selection, and saved human approval explicitly.
- Keep the all-match search and native dropdown synchronized with suggestion selection. Retain the selected engagement during filtering. Search and local selection must not call a model or save a decision; preserve ordered review, reason, freshness, and save guards.

- Keep At a glance, next actions, and disjoint processing/classification/supplier/engagement/complete bottleneck counts derived from existing saved state. Global counts stay independent of filters; completed no-link decisions are not human-confirmed links.
- Keep the three-case walkthrough visibly synthetic, browser-only, outside real counts, and free of provider calls or saved decisions. Real review uses the existing ordered forms.
- Compare original classification/supplier results and the current engagement default against human decisions with reasons. Label pending, not-applicable, and no-link outcomes accurately; do not imply a historical audit trail.
- Evidence navigation may open an existing source field or mark its name unavailable; it must not introduce evidence-name validation or citation verification. Render source values as text.
- Compare up to three current matching engagements using actual catalog fields; highlight differences without treating them as proof of correctness. Explain normalization and the matching column/method through the same Python logic used for retrieval, preserving column precedence and source order. These aids add no CSV columns, pipelines, or dashboards.
