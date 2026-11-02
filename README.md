# HSBC Incident Classification Demo

A small Python 3.11 mock-up with CSV storage, Pydantic responses, classification review before linking, a read-only engagement dashboard, and a separate review of proposed links.

```text
RAW.csv -> Read -> Rename -> Clean -> CLEAN.csv
CLEAN.csv + Definitions + Prompt -> LLM (one row per request) -> LLM_OUTPUT.csv
LLM_OUTPUT.csv + SUPPLIER_NAME.csv -> Classification review dashboard -> CLASSIFICATION_REVIEW.csv
LLM_OUTPUT.csv + CLASSIFICATION_REVIEW.csv + ENG_ALL.csv -> Approval gate -> Candidate search -> LLM linking -> INC_LINKED.csv
INC_LINKED.csv -> Engagement dashboard -> Linked incidents -> Incident details
INC_LINKED.csv -> Human review preparation -> HUMAN_REVIEW.csv -> Human review dashboard
```

The LLM tags each incident HSBC, SUPPLIER, or UNCERTAIN. UNCERTAIN is a successful result when the record cannot support choosing the accountable party; its rationale explains the missing or conflicting facts. For SUPPLIER it also extracts the supplier name, related product/service, action or failure, causal explanation, and accountability reason. Extra recorded supplier facts go in `supplier_more_info`, left empty when none exist. Missing core Supplier facts are Unknown; all six supplier fields are null for HSBC and UNCERTAIN.

Each result includes source column names, without a minimum or fixed maximum count, saved together in exactly one `evidence_column` CSV cell, such as `INCIDENT_DESCRIPTION, ROOT_CAUSE_NOTES`. An empty list is valid and saves a blank evidence cell. New results have no numbered evidence columns. The dashboard counts all three classifications separately from processing failures and keeps decision and Supplier fields visible, with evidence names and processing status in a dropdown. `attribution_evidence_strength` rates recorded support from 0 (unsupported) to 4 (very strong), not probability of correctness. UNCERTAIN uses 0-2 to describe attribution evidence, not confidence in uncertainty. See the [five-level rubric and field order](docs/llm.md).

Model inputs are ordered as narrative, causes, closure/resolution, investigation history, supplier/product context, then remaining metadata. All non-ID values and their definitions are retained. Responses put root cause, supporting evidence, and a short rationale before classification and evidence strength, followed by supplier details.

## Setup

Run from the project root. Create the environment once; skip the first command if `.venv` exists:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Put a UTF-8 source CSV at `data/mockup/RAW.csv`.
- Put the supplier dropdown catalog at `data/mockup/SUPPLIER_NAME.csv`: one supplier name per row, optionally headed `SUPPLIER_NAME`. Keep this real-data file out of Git.
- Create `.env` using [.env.example](.env.example) if absent. Select `LLM_PROVIDER=openai` or `azure` and fill that provider's settings.
- Set `LINK_MAX_CANDIDATES=70` in `.env` to cap engagement candidates per incident. It must be a positive integer; the default is 70 when omitted.
- Configure [column names](fields/columns.yaml), [short definitions](fields/definitions.yml), and [classification instructions](prompts/classification.yml).

## Run in this order

1. Prepare data; wait for `data/run/CLEAN.csv`:

   ```powershell
   .\.venv\Scripts\python.exe -m app.data_preparation.pipeline
   ```

2. Classify rows; each response is saved immediately to `data/run/LLM_OUTPUT.csv`:

   ```powershell
   .\.venv\Scripts\python.exe -m app.llm.pipeline
   ```

3. Start the dashboard and open [http://127.0.0.1:8766/](http://127.0.0.1:8766/):

   ```powershell
   .\.venv\Scripts\python.exe -m app.ui.dashboard_app
   ```

The classification dashboard preserves LLM_OUTPUT.csv and saves human decisions separately in `data/run/CLASSIFICATION_REVIEW.csv`. First approve the model's HSBC/SUPPLIER classification, or choose No and record a reason plus the corrected class. UNCERTAIN and processing failures can receive a manual decision with a reason. If the reviewed class is Supplier, separately approve its model name or select the correct name from SUPPLIER_NAME.csv with a reason. Insufficient information stays Needs review. Only persisted approvals or corrections count as complete. Click Refresh to reread results; stop with Ctrl+C. See [classification review scenarios](docs/dashboard_app.md#decision-scenarios) and the [supplier CSV format](docs/dashboard_app.md#supplier-catalog).

After classification review, link approved incidents to engagements. Put the UTF-8 engagement file at `data/mockup/ENG_ALL.csv`, then run this separate pipeline. Saving a dashboard decision does not call an LLM; it makes the incident eligible for this next run:

```powershell
.\.venv\Scripts\python.exe -m app.linking.pipeline
```

It writes `data/run/INC_LINKED.csv`: original incident/model columns, the six classification-review fields, selected engagement columns prefixed with `ENG_`, and the link decision. It uses [linking instructions](prompts/linking.yml) and the existing `.env` connection. Only reviewed Supplier incidents with an approved or corrected supplier name enter matching, using that reviewed name. Approved HSBC rows are saved as NOT_APPLICABLE without a call. Pending, unresolved, and stale reviews are excluded from the output until complete. Ambiguous or missing engagement matches stay undecided. Reruns skip identical saved reviewed incidents; changed decisions or source values for an already-linked ID require a fresh output batch. The classification evidence score is preserved; `link_confidence` separately rates engagement-link evidence from 0 to 4, not probability. Selected links allow 1-4; null selections allow 0-2. Python rejects inconsistent results and adds `link_confidence_scale=0-4` to identify the new rubric. No linking call means no score.

Candidate search keeps the first matches in ENG_ALL.csv order, up to `LINK_MAX_CANDIDATES`, and sends the complete shortlisted rows together in one request. It checks `THIRD_PARTY_NAME` before `THIRD_PARTY_NORMALISED_NAME` within each row. Names are normalized for matching only; the cap does not rank relevance and can exclude later matches. Python saves the shortlist size after the cap as `link_candidate_count`: zero for no candidates, blank when search is skipped. The count remains saved on request failure and is not proof of delivery to the provider. See [linking](docs/linking.md) for normalization and selection rules.

To browse that output, start the separate engagement dashboard and open [http://127.0.0.1:8767/](http://127.0.0.1:8767/):

```powershell
.\.venv\Scripts\python.exe -m app.ui.engagement_dashboard
```

It reads only `data/run/INC_LINKED.csv`. Select an engagement to see its linked incidents, then select an incident for details. Refresh rereads the CSV. The classification dashboard on port 8766 is independent and does not need to be running.

## Review after linking

Prepare a separate review file after linking, then start its dashboard:

```powershell
.\.venv\Scripts\python.exe -m app.human_review.pipeline
.\.venv\Scripts\python.exe -m app.ui.human_review_app
```

Open [http://127.0.0.1:8768/](http://127.0.0.1:8768/). Engagement first starts with engagements and their proposed incidents. Incident first lists all saved incidents, with search and classification filters, including unmatched and failed rows. Both modes open the same classification and link Yes/No controls and save to the same review file. Original proposals remain inspectable under their engagement after rejection; rejected or invalidated links also appear in Unlinked incidents. Global model-result and human-review counts stay separate.

Engagement first reads `data/mockup/ENG_ALL.csv` to include catalog engagements with no incidents, plus any saved proposal IDs absent from the catalog. It preserves saved proposal fields and never writes ENG_ALL.csv. A missing, unreadable, or invalid catalog falls back to saved proposal groups with a visible scope warning; incident review still works.

A saved confirmation is green; rejection requires a reason. Confirm classification before reviewing its proposed link. Rejecting classification invalidates that link. Rejecting only the link leaves classification confirmed. Confirming classification again makes an invalidated link pending, requiring a fresh link decision.

All original columns and model proposals remain in `data/run/HUMAN_REVIEW.csv`, alongside the human decisions. Only `hitl_linked_engagement_id` represents a human-confirmed link; it stays blank until both decisions are confirmed. The preparation command preserves existing reviews and adds new incidents on rerun. If an existing incident's source values changed, it stops instead of carrying approval onto changed evidence; use a separate review output for that changed batch. Run preparation while the review server is stopped. No LLM call occurs. This review file and its five `hitl_` fields are separate from the earlier classification review on port 8766; the port-8767 engagement dashboard remains read-only. See [Human review](docs/human_review.md) for fields, transitions, and run boundaries.

Preparation replaces CLEAN.csv on nonempty runs. LLM results append for new incident IDs; conflicting results for an existing ID are rejected. For an older output schema, including `llm_confidence`, `supporting_evidence`, or numbered evidence columns, configure a new output folder in `app/llm/pipeline.py` and update `RESULTS_FILE` in `app/ui/dashboard_app.py`. If linking, also update the input/output paths in `app/linking/pipeline.py` and `RESULTS_FILE` in `app/ui/engagement_dashboard.py`. Old confidence values are not converted to evidence strength; dashboards show Not recorded when the score is missing and read legacy evidence without rewriting it. CSV cells contain plain values, without evidence quote columns, JSON blobs, prompt text, or definitions. CSVs and credentials stay out of Git.

Older INC_LINKED.csv files without `link_confidence_scale` keep their legacy 0-100 link confidence, including values between 0 and 4. The engagement dashboard labels them as legacy values without conversion. The writer rejects appending the new schema to files missing the classification-review fields, `link_confidence_scale`, or `link_candidate_count`; use a fresh linking output file or batch folder and point the engagement dashboard at it. For human review, update its input and use a fresh review output and matching dashboard path. Existing files and prior review decisions remain preserved; historical candidate counts are not backfilled.

## Saved files and batch paths

| File | What it stores | Writer |
| --- | --- | --- |
| `data/run/LLM_OUTPUT.csv` | Original incident fields and model classification results. | Classification pipeline. Human review leaves it unchanged. |
| `data/run/CLASSIFICATION_REVIEW.csv` | Original row plus six pre-link review fields for IDs with saved decisions. | Classification dashboard. Untouched rows appear pending without being written. |
| `data/run/INC_LINKED.csv` | Approved incidents, their review fields, and linking results. | Linking pipeline. |
| `data/run/HUMAN_REVIEW.csv` | Linking snapshot plus five later `hitl_` decisions. | Post-link preparation and review dashboard. |

When switching batches, keep the paired paths aligned:

- The classification dashboard's `RESULTS_FILE` and linking pipeline's `INCIDENT_FILE` must refer to the same LLM_OUTPUT.csv.
- Set `REVIEW_FILE` in `app/classification_review.py` for the shared classification-review output; the dashboard and linking pipeline import it. `SUPPLIERS_FILE` in the same module points to the read-only name catalog.
- Set the linking pipeline's `OUTPUT_FILE` and engagement dashboard's `RESULTS_FILE` to the same new INC_LINKED.csv.
- Set the post-link preparation's `INPUT_FILE` to that linking output and its `OUTPUT_FILE` to a matching HUMAN_REVIEW.csv. The post-link dashboard imports that output path.

Restart affected dashboard processes after editing these path constants. A changed linking schema needs fresh linking and post-link review outputs; existing classification approvals can still be used when they match the current LLM_OUTPUT rows. A changed classification source schema also requires a fresh CLASSIFICATION_REVIEW.csv. Keep the earlier files.

## Documentation and tests

- [Short description and review example](docs/short_desription.md)
- [Data preparation](docs/data_preparation.md)
- [LLM classification and supplier extraction](docs/llm.md)
- [Incident-to-engagement linking](docs/linking.md)
- [Classification dashboard](docs/dashboard_app.md)
- [Engagement dashboard](docs/engagement_dashboard.md)
- [Human review](docs/human_review.md)
- AI agents: follow [AGENTS.md](AGENTS.md) before changing code.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_frontend.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_python.py -v
```

These tests run offline with temporary CSVs and simulated LLM replies. Frontend checks cover assets and controls, not browser interaction. To make a real request using `.env`, run the separate connection check:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

It classifies one visibly synthetic incident using the current YAML prompt, field definitions, Pydantic schema, and `classify_row`. It uses the selected OpenAI/Azure connection, provider defaults for temperature and output length, and `store=False`. No local tokenizer or input-token precheck runs. Empty, refused, incomplete, or invalid structured responses fail. It prints only a fixed success message or a sanitized error; no CSV files are read or written. This checks connectivity and the classification response contract, not model accuracy or the linking schema. Ordinary test discovery skips this live API call.
