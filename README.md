# HSBC Incident Review Demo

A small Python 3.11 demo with unchanged CSV preparation, one sequential LLM pipeline, and one incident dashboard.

This is a loopback, single-process CSV demo. It has no user sign-in, recorded reviewer identity, or historical audit log. Offline checks and synthetic browser demonstrations do not establish live Azure compatibility or production readiness.

```text
RAW.csv -> read -> rename -> clean -> CLEAN.csv
For each CLEAN incident: classify -> save -> find engagements -> save -> next incident
                                            |
                                       INCIDENTS.csv
                                            |
                     Classification -> Supplier name -> Engagement
                           Three human reviews in one dashboard
```

The model returns HSBC, SUPPLIER, or UNCERTAIN. A Supplier result automatically enters engagement matching using its **base supplier name**, without waiting for human approval. Python finds matching ENG_ALL rows; the LLM suggests up to five engagements with reasons and selects its strongest proposal by default. A model default is saved, but human approval remains pending.

The dashboard lists every initialized incident, including processing failures and rows waiting to run. Review classification first, supplier name second when applicable, and engagement third. Correcting the supplier name using searchable catalog choices immediately reruns the same engagement function. Reviewers can inspect and choose from **all** Python matches, including those beyond the LLM shortlist.

On desktop, Classification and Supplier name share the top review row; Engagement occupies a full-width row below. Engagement suggestions appear as cards with green shades based on evidence strength, with the model default labeled separately from human approval. A search field and native dropdown provide access to every Python match. Selecting a card or dropdown option only changes the pending choice; saving still requires an explicit review action.

## Setup

Run from the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create your local `.env` using [.env.example](.env.example) and supply the three input CSVs listed below. Keep `.env`, all CSV files, and `data/` out of Git. `LINK_MAX_CANDIDATES` defaults to 70.

Configure [column names](fields/columns.yaml), [field definitions](fields/definitions.yml), and the two YAML [classification](prompts/classification.yml) and [linking](prompts/linking.yml) prompts. OpenAI and Azure reuse the existing connection. Requests use provider defaults for temperature and output length; the candidate cap is not a token limit.

## Data files and their contents

For the complete workflow, provide **three input CSV files**. The pipelines create **two output CSV files**.

All CSV files are local, comma-separated UTF-8 files. A UTF-8 BOM is accepted. Keep identifiers as text, including any leading zeros. Quote values containing commas, quotes, or line breaks using normal CSV quoting.

| Exact path | Who creates it? | Contents and reader |
| --- | --- | --- |
| `data/mockup/RAW.csv` | You | One incident per row. The preparation pipeline reads it. |
| `data/mockup/ENG_ALL.csv` | You | One engagement per row, including its supplier entity and service context. The LLM pipeline and dashboard read it. |
| `data/mockup/SUPPLIER_NAME.csv` | You | Supplier **base names**, optionally with a COUNTRY column. The dashboard searches and filters these choices for human corrections. |
| `data/run/CLEAN.csv` | Preparation pipeline | The incident rows after renaming and cleaning. The LLM pipeline reads it. |
| `data/run/INCIDENTS.csv` | LLM pipeline; updated by human review | Original prepared incident values, AI results, engagement proposals, and saved human decisions. The dashboard reads and updates it. |

Create `data/mockup/` and place the three input files there. The application creates output directories when saving. You do not need to create empty output CSV files.

### 1. RAW.csv — source incidents

The input columns are flexible; you do not need to supply every column listed in the mapping file.

| Example source header | Standardized header | Meaning |
| --- | --- | --- |
| `incident_id` | `INCIDENT_ID` | Incident identifier. Nonblank, unique IDs are required by the later LLM processing stage. |
| `incident_short_description` | `INCIDENT_SHORT_DESCRIPTION` | A short incident summary, useful in the dashboard. |
| `incident_description` | `INCIDENT_DESCRIPTION` | Incident narrative: what happened and which service was affected. |
| `it_incident_cause_details` | `IT_INCIDENT_CAUSE_DETAILS` | Recorded cause or investigation findings; may be blank when unknown. |

**Synthetic example — fictional incident records, not real HSBC or supplier events:**

```csv
incident_id,incident_short_description,incident_description,it_incident_cause_details
SYNTHETIC-001,Synthetic internal gateway issue,An HSBC operator applied an incorrect gateway setting.,Internal configuration was recorded as the cause.
SYNTHETIC-002,Synthetic supplier gateway issue,Atlas Cloud deployed a gateway change that interrupted service.,The supplier confirmed its deployment caused the interruption.
SYNTHETIC-003,Synthetic unresolved interruption,A service interruption was reported but the responsible party was not established.,
```

Preparation matches source headers exactly against `fields/columns.yaml`, applies the mapped name, and uppercases unmapped headers. For every non-ID column present after renaming, `fields/definitions.yml` must contain a nonblank definition under that standardized name. Extra incident columns are preserved and sent to classification with their definitions.

Source columns must not use reserved result/review names or the `ENG_` prefix; unified processing rejects those collisions.

Cleaning itself retains empty/repeated IDs; the later unified processing stage rejects them. Keep source headers unique and avoid mapping two headers to the same standardized name, because preparation does not check those collisions.

### 2. ENG_ALL.csv — engagement catalog

Use these uppercase header names exactly; this file does not pass through the renaming pipeline.

| Column | Required? | Meaning |
| --- | --- | --- |
| `ENGAGEMENT_ID` | Yes | Nonblank, unique engagement identifier. |
| `THIRD_PARTY_NAME` | At least one supplier-name column | Original supplier/entity name, such as Atlas Cloud UK. Checked first during matching. |
| `THIRD_PARTY_NORMALISED_NAME` | At least one supplier-name column | Alternative catalog name. Checked if THIRD_PARTY_NAME did not match. |
| `ENGAGEMENT_NAME` | Recommended | Human-readable engagement title. |
| `ENGAGEMENT_DESCRIPTION_TEXT` | Recommended | What service or work the engagement covers. |
| `SERVICE_CATEGORY_L1_NAME` | Optional context | Service category. |
| `PRIMARY_BENEFICIARY_COUNTRY_TERRITORY_ISO_NAME` | Optional context | Beneficiary country; this is not necessarily the incident location. |

Use a header row with nonblank, unique column names and the same number of cells in every record.

Provide `THIRD_PARTY_NAME`, `THIRD_PARTY_NORMALISED_NAME`, or both. The minimum structure enables name retrieval; service and other factual context help distinguish engagements. Additional catalog columns are retained, included in candidate data, and available for comparison.

**Synthetic example — fictional supplier entities and engagements:**

```csv
ENGAGEMENT_ID,THIRD_PARTY_NAME,THIRD_PARTY_NORMALISED_NAME,ENGAGEMENT_NAME,ENGAGEMENT_DESCRIPTION_TEXT,SERVICE_CATEGORY_L1_NAME,PRIMARY_BENEFICIARY_COUNTRY_TERRITORY_ISO_NAME
DEMO-ENG-001,Atlas Cloud UK,atlas cloud uk,UK gateway support,Managed cloud gateway for UK services,Technology,United Kingdom
DEMO-ENG-002,Atlas Cloud US,atlas cloud us,US payroll support,Hosted payroll application support,Technology,United States
DEMO-ENG-003,Nimbus Networks UK,nimbus networks uk,UK network support,Managed office network connectivity,Technology,United Kingdom
```

Python normalizes names only for matching, preserving catalog values. It searches `THIRD_PARTY_NAME` before `THIRD_PARTY_NORMALISED_NAME` within each row, keeps all matches for human browsing, and prepares the first `LINK_MAX_CANDIDATES` matches for the model (70 by default). File order is not a relevance ranking. The batch loads this catalog before classification begins.

### 3. SUPPLIER_NAME.csv — human dropdown choices

Keep supplier **base names** here; legal entities and individual engagements remain in ENG_ALL.csv. Both formats are supported:

- Existing one-column files, with or without a `SUPPLIER_NAME` header.
- A two-column file with `SUPPLIER_NAME,COUNTRY` headers. The two headers may be reversed and are case-insensitive. COUNTRY may be blank.

**Synthetic example — fictional suppliers and illustrative country metadata:**

```csv
SUPPLIER_NAME,COUNTRY
Atlas Cloud,United Kingdom
Atlas Cloud,United States
Nimbus Networks,United Kingdom
Example Supplier,
```

Use one country per row and repeat the base name when several countries are relevant. The dashboard combines repeated exact names into one choice with its recorded countries. Use consistent country labels, preferably English country names. Countries describe the supplier entity or operations represented by your catalog; they do not automatically identify an incident's country or a supplier's headquarters.

The correction form supports partial-name search, an optional country filter, and 50 results per page. It starts with all countries and preserves the selected name across searches and pages. Clearing the country filter also makes names without country metadata reachable. The server validates the exact current catalog name again when saving; a correction still requires a reason.

The base name Atlas Cloud can match both Atlas Cloud UK and Atlas Cloud US in ENG_ALL. Names in the two files do not have to be identical. Country helps browse supplier names; it is not a hard engagement filter or a separate saved human decision. This catalog is not sent to classification, and the full supplier list is not sent to the LLM. Outer whitespace is trimmed in memory. The app never writes the catalog or invents missing countries.

### 4. CLEAN.csv — generated preparation output

The preparation pipeline creates this file with standardized headers and cleaned values. It preserves incident IDs, row order, punctuation, normal whitespace, and source information. For the synthetic RAW example above, its first data row is:

```csv
INCIDENT_ID,INCIDENT_SHORT_DESCRIPTION,INCIDENT_DESCRIPTION,IT_INCIDENT_CAUSE_DETAILS
SYNTHETIC-001,Synthetic internal gateway issue,An HSBC operator applied an incorrect gateway setting.,Internal configuration was recorded as the cause.
```

This is a one-row illustration; the generated file contains every input row. Running preparation again replaces CLEAN.csv. It does not classify incidents.

### 5. INCIDENTS.csv — generated results and human decisions

The application creates this file and updates it after each processing or review step. It stores one current record per incident.

| Column group | Contents |
| --- | --- |
| Prepared source fields | Every CLEAN.csv column, including `INCIDENT_ID`, with its prepared value preserved. |
| Classification | `classification`, `key_root_cause`, `decision_rationale`, `attribution_evidence_strength`, `evidence_column`, and the original six supplier-detail fields. |
| Extracted context | `incident_country`, `supplier_country`, `causing_party`, `affected_party`, and `resolving_party`; documented facts only, blank when unknown. |
| Citations | One shared `citations` cell with Classification: and Engagement: lines; excerpts are model-provided and unverified. |
| Processing | `processing_status` and `error`. |
| Engagement proposal | `link_supplier_name`, `link_status`, `linked_engagement_id`, `link_reason`, `link_confidence`, the three candidate/suggestion counts, and catalog/error information. |
| Up to five suggestions | Flat `link_1_engagement_id`, `link_1_reason`, `link_1_evidence_strength` columns through slot 5. Unused slots are blank. |
| Human decisions | Status, chosen value, and reason for each of classification, supplier name, and engagement: nine separate fields. |
| Selected engagement | Actual catalog columns prefixed `ENG_`, such as `ENG_ENGAGEMENT_ID` and `ENG_THIRD_PARTY_NAME`. |
| Save version | `row_revision`, maintained by Python to reject stale saves. |

**Synthetic excerpt — selected columns only, illustrating a saved model proposal before human review. This is not a complete file template or a live model result:**

```csv
INCIDENT_ID,classification,supplier_name,link_status,linked_engagement_id,classification_review_status,supplier_review_status,engagement_review_status,reviewed_engagement_id
SYNTHETIC-002,SUPPLIER,Atlas Cloud,READY,DEMO-ENG-001,pending,pending,pending,
```

Attribution and link evidence scores use 0-4, not probabilities. Link evidence stays blank when no linking call occurs. Evidence column names share one `evidence_column` cell; suggestions use flat columns rather than JSON cells.

Classification now returns 17 fields, including the shared citations field and five country/actor context fields. Incident country and supplier country have different meanings. Resolving or suffering a problem does not establish responsibility for causing it. These are model extracts, not human-confirmed facts.

The saved model default is not human approval. The dashboard records human choices separately. See [classification fields](docs/llm.md#classification-response), [linking fields](docs/linking.md#saved-linking-fields), and [human-review fields](docs/dashboard_app.md#saved-fields) for the full field definitions.

A local `INCIDENTS.csv.lock` may also appear during saving; it is an application-managed locking file, not a data input. Historical LLM_OUTPUT.csv, INC_LINKED.csv and review CSVs are archives, not required inputs for this workflow.

## Run

1. Prepare incidents; this pipeline is unchanged:

   ```powershell
   .\.venv\Scripts\python.exe -m app.data_preparation.pipeline
   ```

2. Classify and automatically find engagements, one incident at a time:

   ```powershell
   .\.venv\Scripts\python.exe -m app.llm.pipeline
   ```

3. Start the only dashboard:

   ```powershell
   .\.venv\Scripts\python.exe -m app.ui.dashboard_app
   ```

Open [http://127.0.0.1:8766](http://127.0.0.1:8766). Refresh rereads saved results; stop processes with Ctrl+C.

The new output is **data/run/INCIDENTS.csv**. It contains original incident values, model classification, engagement proposals/counts, selected engagement values, separate human decisions, and one shared citations column. Citations are source-labeled model excerpts and are not checked for exact matches. Existing LLM_OUTPUT.csv, CLASSIFICATION_REVIEW.csv, INC_LINKED.csv, and HUMAN_REVIEW.csv remain untouched archives; the new workflow does not import their approvals or read them as its output. No FINAL.csv is created. The separate linking/review CLI commands and port-8767/8768 dashboards have been removed.

Initialization saves all source incidents as pending. Each classification and link result is saved before the next incident. A failed request saves its failure and stops the batch. Rerunning retries unfinished/failed model work that has no human classification decision, preserves completed results, and adds new IDs. Changed source values, output columns, or engagement columns require a fresh output; preserve earlier batches. Output/catalog paths live in `app/incidents.py`; CLEAN input and definitions live in `app/llm/pipeline.py`. Restart the dashboard after changing paths.

Existing unified INCIDENTS.csv files missing citations or any of the five country/actor fields remain readable with those fields blank in memory. Reading does not rewrite the file or rerun completed model work. The next normal save adds the missing supported columns while preserving source values and human decisions. Historical output formats are not imported.

The CSV stores current decisions, not an audit-history log. File locking, atomic saves, and per-row versions protect concurrent pipeline/dashboard updates; stale model results or browser decisions cannot replace newer human changes.

## Project layout

```text
app/                              Python application
  data_preparation/
    pipeline.py                   Read -> rename -> clean -> save CLEAN.csv
    load_columns.py               Read the header mapping
    read_csv.py                   Read source rows
    rename_columns.py             Apply standardized column names
    cleaning.py                   Remove invisible control/format characters
    save_csv.py                   Save the prepared rows
  llm/
    pipeline.py                   Classify -> save -> link -> save, one incident at a time
    prepare_fields.py             Order source fields and attach definitions
    classification.py             Classification request and response handling
    llm_connection.py             Shared OpenAI/Azure connection
  linking/
    candidates.py                 Python name matching and match explanations
    linking.py                    Catalog loading and reusable engagement suggestions
  ui/dashboard_app.py             HTTP routes and dashboard response data
  models.py                       Shared Pydantic contracts and output defaults
  incidents.py                    Incident CSV storage, versions and engagement values
  review.py                       Human decisions and immediate supplier-based relinking
  csv_files.py                    Shared CSV reading and atomic writing
frontend/
  dashboard/index.html            The single dashboard page
  dashboard/app.js                Review controls, counts and comparisons
  style.css                       Dashboard styling
  pictures/hsbc-logo.svg           Shared logo
fields/
  columns.yaml                    Source header -> standardized name mapping
  definitions.yml                 Standardized field name -> English definition
prompts/
  classification.yml              Classification instructions
  linking.yml                     Engagement suggestion instructions
data/                             Local files; excluded from Git
  mockup/RAW.csv                   Input incidents
  mockup/ENG_ALL.csv               Input engagement catalog
  mockup/SUPPLIER_NAME.csv         Input supplier base-name catalog
  run/CLEAN.csv                   Generated prepared incidents
  run/INCIDENTS.csv               Generated results and human decisions
docs/                             Stage documentation and short_description.md
tests/
  test_pipeline.py                Existing offline pipeline checks
  test_frontend.py                Existing offline frontend checks
  check_llm_connection.py          Explicit live classification connection check
requirements.txt                  Python dependencies
.env.example                      Provider configuration template
.env                              Local credentials and settings; excluded from Git
AGENTS.md                         Project instructions
README.md                         Setup, data contents and run commands
```

The separation follows responsibility: preparation, model requests, matching, storage, human decisions, and presentation. The application has two processing entry points and one dashboard; linking is reused by both the LLM pipeline and supplier-name corrections.

The bundled Python package `__init__.py` files remain in place. Architecture diagrams under `.archify/`, images under `docs/images/`, and browser-check screenshots under `output/playwright/` are supporting artifacts; the application does not need them to run.

## Code flow

The entry point reads the source, definitions, engagement catalog, and candidate limit. The per-incident loop calls `classify_and_save`, then `link_incident` when applicable. Both remain in `app/llm/pipeline.py`; request details do not obscure the batch order. The dashboard and pipeline reuse `find_engagements` for matching and suggestions.

`app/review.py` applies human decisions and runs engagement refreshes using explicit file paths. It does not depend on FastAPI state. The dashboard supplies those paths and formats HTTP responses; `app/incidents.py` owns current-state persistence and stale-version checks. Shared model contracts and output defaults stay in `app/models.py`, and both LLM requests reuse its schema-limit conversion. The structure keeps the existing run commands, CSV/API contracts, prompts, and review behavior.

## Checks and documentation

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py" -v
```

The existing `test_pipeline.py` and `test_frontend.py` checks use temporary CSVs and simulated responses. They do not establish provider connectivity or model accuracy. To make a real classification request using your configured provider:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

The live check uses a visibly synthetic incident and current classification schema; it does not test the separate engagement-suggestion schema.

- [Short description and AXA example](docs/short_description.md)
- [Data preparation](docs/data_preparation.md)
- [Classification and sequential processing](docs/llm.md)
- [Engagement search and suggestions](docs/linking.md)
- [Dashboard and human decisions](docs/dashboard_app.md)
- [Project instructions](AGENTS.md)

Current source-backed diagrams:

- [Automatic incident processing](.archify/workflow-ws4-current-20261102-190621/ws4-pipeline.html)
- [Three ordered human decisions](.archify/workflow-ws4-current-20261102-190621/ws4-human-review.html)

These diagrams describe the single LLM pipeline, automatic Supplier suggestions, and the incident dashboard at their pinned source revision. They do not yet illustrate the country/actor fields or paged supplier search; the documents above describe those additions. Earlier diagram folders and their frozen documents remain historical snapshots.
