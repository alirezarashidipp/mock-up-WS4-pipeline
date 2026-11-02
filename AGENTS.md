# Project instructions

- This is a small Python 3.11 demo. Use plain functions, short explicit steps, and direct library calls. Keep Python code in app/.
- Keep code, configuration, docs, and UI text in English. Keep project instructions in this root AGENTS.md only.
- Preserve source CSV files and identifiers. CSV files, data/, credentials, and .env stay out of Git; never print credentials or raw provider errors.
- Mark synthetic examples visibly. Verify changes with a lightweight affected-code check; distinguish offline checks from live API results. Create test files only when the user asks.

## Read relevant docs and implementation first

- Preparation/cleaning: docs/data_preparation.md.
- Classification/LLM requests: docs/llm.md.
- Engagement matching/suggestions: docs/linking.md.
- Dashboard/human decisions: docs/dashboard_app.md.
- Setup and commands: README.md. Compact business flow: docs/short_desription.md.
- Update the relevant docs when behavior changes. .archify diagrams and frozen source documents are historical.

## Keep the workflow simple

- Do not change Cleaning unless explicitly requested. app/data_preparation/pipeline.py remains read -> rename -> clean -> save CLEAN.csv. Preparation retains empty/repeated IDs and uppercases unmapped headers; add no ID, CSV-shape, or mapping-collision checks to that stage.
- Cleaning removes invisible control/format characters only; preserve punctuation, emails, HTML, and normal whitespace.
- One LLM entry point: app/llm/pipeline.py reads CLEAN.csv, initializes all pending incidents, then classifies and automatically finds engagements for each incident before advancing to the next.
- One dashboard: app/ui/dashboard_app.py on loopback port 8766, frontend/dashboard/, frontend/style.css, and existing logo in frontend/pictures/.
- One current output: data/run/INCIDENTS.csv, containing immutable source values, model results, link proposals, selected ENG_ values, and separate human decisions. Preserve old CSVs without automatic migration; no FINAL.csv or duplicate dashboards/pipelines.
- Keep the reusable find_engagements function in app/linking/linking.py independent of saving and human approval. Both the pipeline and real-time supplier corrections call it.

## Classification

- Names belong in fields/columns.yaml, standardized definitions in fields/definitions.yml, and instructions in prompts/classification.yml.
- Use Pydantic inputs/responses and strict Structured Outputs. Keep INCIDENT_ID local. Order inputs: narrative, causes, closure/resolution, investigation history, supplier/product context, remaining metadata. Preserve every non-ID source value.
- Classify HSBC, SUPPLIER, or UNCERTAIN. UNCERTAIN is a successful result when attribution is unsupported or conflicting; explain limitations in decision_rationale.
- Output order: root cause, evidence_column, rationale, classification, evidence strength, six supplier fields.
- Supplier fields are null for HSBC/UNCERTAIN. For SUPPLIER, extract recorded facts; missing core details become Unknown, absent extra facts become null. supplier_name is the documented base name; retain useful full-entity/country details in supplier_more_info without inventing a parent company.
- attribution_evidence_strength is a strict integer 0-4, not probability. Reject UNCERTAIN above 2 and HSBC/SUPPLIER at 0; preserve valid 1-4 definite classifications. Do not repair inconsistent labels/scores.
- evidence_column is a list of strings, including an empty list, with no fixed maximum. Python does not validate individual names, duplicates, or blanks. Preserve order and join with comma and space in one cell; no evidence quotes or numbered evidence columns.
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
- Catalogs are read-only. Check candidate membership and catalog freshness before engagement approval. Changed catalog columns require a fresh output batch.
- Render CSV values as text, show missing/invalid catalog messages, keep original model counts separate from human review progress, and preserve list filters/open incident after save.
- No LLM calls or file writes on GET. Human supplier correction/retry may call the LLM on POST. Green confirmation appears only after a successful save.
