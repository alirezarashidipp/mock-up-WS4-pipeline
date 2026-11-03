# Classification in the unified incident workflow

Run `python -m app.llm.pipeline` from the project root. Data preparation remains a separate, unchanged step; see [data preparation](data_preparation.md).

```text
CLEAN.csv + field definitions + ENG_ALL.csv
    -> initialize every incident as pending in INCIDENTS.csv
    -> classify one incident -> save classification
    -> for Supplier: find engagement suggestions -> save default proposal
    -> continue with the next incident
```

The single [incident dashboard](dashboard_app.md) reads `data/run/INCIDENTS.csv`. Automatic linking does not wait for human approval. The human later reviews classification, supplier name, and engagement in that order. HSBC and UNCERTAIN do not receive automatic engagement requests.

## Classification request

1. Keep `INCIDENT_ID` locally. `app/llm/prepare_fields.py` sends every other source column as `{name, description, value}`, with descriptions from `fields/definitions.yml`. Values, including empty values, remain complete.
2. Send the instructions from `prompts/classification.yml` and the prepared fields to `classify_row`. Each request is independent and includes the prompt and definitions again.
3. Request strict JSON schema output and validate it with the Pydantic `Classification` model in `app/models.py`. Require a complete, non-refused response.
4. Convert the result to flat fields with `classification_values`, then save the incident before starting its linking request or the next incident. This function only builds values; `app/incidents.py` owns persistence.

Model input order is narrative, recorded causes, closure/resolution, investigation history, supplier/product context, then remaining metadata in source order. Every non-ID field needs a definition and appears once. Input ordering does not change source CSV columns or establish which evidence is authoritative.

## Classification response

The model returns these 17 required fields in this order. The original 12 retain their order; five nullable context fields follow them:

| Field | Meaning |
| --- | --- |
| `key_root_cause` | Documented root cause in one sentence, or null when unknown. |
| `evidence_column` | List of source-column names that informed the result. |
| `citations` | List of short source-labeled excerpts; return [] when none are available. |
| `decision_rationale` | Short evidence-based explanation of attribution and any material gaps. |
| `classification` | HSBC, SUPPLIER, or UNCERTAIN. |
| `attribution_evidence_strength` | Strict integer 0-4 describing recorded attribution evidence. |
| `supplier_name` | Documented base supplier name, such as AXA, or Unknown. |
| `supplier_product_or_service` | Documented product/service, or Unknown. |
| `supplier_action_or_failure` | Documented supplier action, defect, or omission, or Unknown. |
| `supplier_causal_explanation` | How the supplier action caused the incident, or Unknown. |
| `supplier_accountability_reason` | Why responsibility belongs to the supplier, or Unknown. |
| `supplier_more_info` | Additional nonduplicated supplier facts, or null. |
| `incident_country` | Documented country of the incident or affected service, or null. |
| `supplier_country` | For SUPPLIER, documented country of the involved supplier entity or operations; otherwise null. |
| `causing_party` | Actor explicitly recorded as causing the problem, or null when not established. |
| `affected_party` | Party explicitly recorded as affected by the problem, or null. |
| `resolving_party` | Actor explicitly recorded as restoring service or resolving the problem, or null. |

HSBC/SUPPLIER represent causal accountability. Use UNCERTAIN when the record cannot support choosing a party, and describe the missing or conflicting facts. UNCERTAIN is a successful result, not a processing failure. A missing supplier name alone does not require UNCERTAIN when supplier responsibility is otherwise supported.

For SUPPLIER, extract the base name only when supported by the record; do not invent a parent company. Preserve useful documented legal-entity or country details in `supplier_more_info`. The source text remains unchanged. The base name enables retrieval of related ENG_ALL names; it does not prove an engagement match.

The original six supplier fields and `supplier_country` become null for HSBC and UNCERTAIN. Blank core Supplier fields become Unknown; empty `supplier_more_info` stays null. CSV nulls are saved as blank cells. Rationale is a concise decision summary, not a detailed internal thought process.

The five new fields extract documented context; they do not create another classification. Return null when facts are absent, ambiguous, or conflicting. Incident geography and supplier geography must not be copied into one another or inferred from a headquarters, currency, company name, or unrelated location. Use English country names when the source is unambiguous; separate multiple explicitly relevant countries with a semicolon. Role fields may remain factual for any class: being affected or restoring service does not make an actor responsible for the cause. A mere name mention does not establish a role.

The supplier-name catalog is not supplied to classification. Its countries are human-browsing metadata, not evidence to fill the model's country fields. Original incident values remain the evidence source.

## Validation and evidence

| Check | Behavior |
| --- | --- |
| Completion | Require a choice, `finish_reason=stop`, nonempty content, and no refusal. |
| Structure | Require the 17 schema fields and their types; reject additional JSON fields. |
| Class and score | HSBC/SUPPLIER allow 1-4; UNCERTAIN allows 0-2. Reject inconsistent results without changing class or score. |
| Score type | Reject strings, booleans, floats, and integers outside 0-4. |
| Root cause and rationale | Root cause is a nonempty string or null; rationale is a nonempty string. |
| Evidence list | Require a list of strings. Empty lists are accepted; there is no maximum count. |
| Evidence names | Do not check source-name membership, spelling, uniqueness, or blank individual strings. Do not trim, correct, or deduplicate entries. |
| Citations | Require a list of strings; [] is valid. Do not check exact quote matching, source labels, duplicates, blank strings, or length. |
| Supplier fields | Require strings or null and apply the class-specific normalization above. |
| Country/actor context | Require all five keys with string or null values. Unknown facts stay null; these extracts are not independently verified. |

The prompt asks for relevant evidence-column names. Python preserves the returned order and joins them with comma and space in one CSV cell. An empty list saves a blank cell. Source values remain in their own columns. Source excerpts go only in the shared `citations` cell. No numbered evidence columns, definitions, prompt text, or JSON blobs are written to the CSV.

Both LLM responses return `citations`. Python labels each line `Classification:` or `Engagement:` and saves them together in one plain-text CSV cell. These are model-provided excerpts, not independently verified evidence. Linking refreshes replace only the Engagement part, preserving classification excerpts; proposal resets and failed/no-call lookups clear stale engagement citations. Earlier citations are excluded from subsequent linking inputs.

| Score | Label | Attribution evidence |
| --- | --- | --- |
| 0 | Unsupported | No recorded causal evidence distinguishes a party. |
| 1 | Weak | Indirect references or unconfirmed suspicion; important causal facts are absent. |
| 2 | Moderate | Relevant evidence with material gaps or unresolved contradiction. |
| 3 | Strong | Concrete facts support the responsible party and mechanism. |
| 4 | Very strong | Documented causal finding, corroborating details, and no unresolved material counterevidence. |

These scores are model assessments of the recorded evidence, not probabilities or measured accuracy. UNCERTAIN scores describe support for attributing a party, not confidence in uncertainty. Scores 1-2 do not automatically force HSBC/SUPPLIER to become UNCERTAIN. Supplier-name review and engagement evidence are separate decisions.

## Provider defaults

Classification and [linking](linking.md) reuse `app/llm/llm_connection.py` for OpenAI or Azure. Both use `store=False`, strict JSON schema, and local Pydantic validation. Both schemas use the shared `remove_schema_limits` helper in `app/models.py` to omit unsupported provider keywords while Pydantic retains local validation.

Requests omit `temperature`, `max_tokens`, and `max_completion_tokens`. There is no local token counting, tokenizer download, or input truncation. Provider context limits still apply. The shared connection uses a 60-second SDK timeout and one SDK retry. `LINK_MAX_CANDIDATES` independently limits engagement rows prepared for the linking call.

## Saving, stopping, and resuming

`app/llm/pipeline.py` starts with `run_llm_pipeline`: read source rows, read definitions, read engagements, load the candidate limit, then process incidents. Its per-row coordinator calls `classify_and_save` for the classification request and immediate save, then `link_incident` for reusable `find_engagements` and proposal saving. These functions stay together in the existing pipeline module. Before requests begin, all current CLEAN rows are saved as pending incidents so the dashboard can show the complete batch. Each incident then progresses through classification and, for SUPPLIER, engagement suggestions before the next row starts.

`INCIDENTS.csv` contains all source columns, the 17 classification fields (including the shared `citations` column), `processing_status` and `error`, 25 flat linking fields, nine human-review fields, and a Python-managed row_revision. It also contains an `ENG_`-prefixed column for each ENG_ALL field. These cells copy the actual selected engagement row: initially the model default, then the accepted human choice when changed. No selection leaves them blank. Model proposal IDs, reasons, and scores remain separate from human decisions. The dashboard also reads the current catalog when browsing alternatives.

Classification processing is `pending`, `success`, or `failed`. Classification and linking failures are saved where possible and stop the batch; earlier results remain saved. Rerunning retries unfinished or failed work without repeating a successful classification unnecessarily. Rows with a recorded human classification decision are skipped, preventing a model rerun from replacing human work.

Pydantic classification failures record only recognized response field names and error types, such as `ValidationError: key_root_cause: string_too_short`. Unknown field names become `response`. Other failures record exception types. Raw responses, source values, and credentials are not logged.

The incident store checks schema, nonblank unique IDs, and unchanged source values. Changed source rows or columns require a fresh batch output. This processing-stage validation does not change the cleaning pipeline. Writes use an operating-system lock, atomic replacement, and a current row-version check that includes the incrementing revision so dashboard and CLI saves cannot silently overwrite each other.

An existing unified `INCIDENTS.csv` missing `citations` or any of `incident_country`, `supplier_country`, `causing_party`, `affected_party`, and `resolving_party` reads with those missing columns blank in memory. Reading does not write the file, infer old facts, or rerun models. The next normal save adds the missing supported columns while preserving source values, other rows, and decisions. Malformed rows and other incompatible schema changes are still rejected.

Older `LLM_OUTPUT.csv`, `INC_LINKED.csv`, `CLASSIFICATION_REVIEW.csv`, `HUMAN_REVIEW.csv`, and other historical CSVs remain untouched and are not automatically imported. Use the new `INCIDENTS.csv` workflow; old confidence values are not converted to the new evidence scales.

## Explicit live connection check

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_llm_connection.py -v
```

This existing check prepares one visibly synthetic incident and reuses the classification prompt, field definitions, shared connection, and `classify_row`. It reads and writes no incident CSV. A pass establishes connectivity and a valid classification response for that request, not classification accuracy or support for the separate linking response schema. Ordinary `test_*.py` discovery skips this explicitly named live check. Mocked/offline checks do not verify live provider behavior.
