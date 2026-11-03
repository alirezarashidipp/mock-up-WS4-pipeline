# Engagement suggestions and review

Engagement finding is part of the single `python -m app.llm.pipeline` workflow. There is no separate linking CLI or engagement dashboard.

```text
classify one incident -> save classification
    SUPPLIER -> Python name search -> LLM suggestions -> save default proposal
    HSBC     -> NOT_APPLICABLE, no search or call
    UNCERTAIN -> SKIPPED, wait for a definite human classification
```

`app/linking/linking.py:find_engagements` serves both automatic processing and the [incident dashboard](dashboard_app.md). It accepts the incident, ENG_ALL rows, current base supplier name, and candidate cap; it returns flat result fields without saving files. The batch pipeline or `app/review.py` saves them through `app/incidents.py` in `data/run/INCIDENTS.csv`.

## Three different counts

| Saved field | What it counts |
| --- | --- |
| `link_match_count` | All ENG_ALL rows matching the normalized supplier name. The user can browse all of them. |
| `link_candidate_count` | The first matching rows prepared for the model, after the configured cap. |
| `link_suggestion_count` | Zero to five candidates recommended by the model. |

Set `LINK_MAX_CANDIDATES=70` in `.env`. The shared `load_max_candidates` function requires a positive integer and defaults to 70. This is a row cap, not a relevance ranking or token budget.

Synthetic example: AXA matches 100 ENG_ALL rows. The dashboard can browse all 100; the LLM receives the first 70; it may suggest three. The saved counts are 100, 70, and 3. A relevant engagement later in source order can be excluded from the model shortlist but remains available for human selection.

Counts are blank when search has not run. No lexical matches produce zeros and no model call. Counts already prepared remain recorded if a request or response fails; they do not prove successful delivery to the provider.

## Python retrieval

1. Read ENG_ALL as UTF-8 CSV. Require nonblank unique `ENGAGEMENT_ID` values, consistent rows, and at least one of `THIRD_PARTY_NAME` or `THIRD_PARTY_NORMALISED_NAME`. Reject malformed input before making a model call.
2. Normalize the current supplier base name and candidate names for matching only: Unicode NFKD, ASCII folding, lowercase, then letter/number tokens joined with single spaces. Original values and IDs remain unchanged.
3. For each row, check `THIRD_PARTY_NAME` first, then `THIRD_PARTY_NORMALISED_NAME`. Add the row once if either name matches by whole-word containment or fuzzy similarity at 0.8.
4. Keep all matches in ENG_ALL order. `find_candidates(..., max_candidates=None)` returns them all; the service slices the list to the LLM cap separately.

The dashboard explains each match using the same Python helper as retrieval: original and normalized names, the first matching column, and the containment or fuzzy rule. Explanations are read-only and add no saved columns.

Blank and placeholder names such as Unknown produce no candidates. Lexical retrieval can miss aliases such as EY versus Ernst & Young. Name similarity supplies options, not proof of an incident relationship.

Synthetic example: base name AXA can retrieve both AXA Insurance and AXA Com. The incident's insurance or communications facts determine which engagement is plausible. Supplier catalog names and engagement entity names do not need to be identical.

## Linking request and response

`prompts/linking.yml` supplies the instructions. A Pydantic `LinkInput` contains the current `supplier_name`, incident context, and complete capped engagement rows. It is serialized inside `<link_request>` tags; the prompt treats all contents as data. `INCIDENT_ID`, previous linking fields, the shared `citations` value, and human-review bookkeeping stay out of the model payload.

The explicit current supplier name overrides a conflicting earlier model supplier name. Original incident facts remain the basis for matching; descriptions of a rejected supplier are not assumed applicable. Classification country and actor fields are fallible model extracts, not additional verified sources. Check original incident facts; do not transfer the previous supplier's country or role to a corrected supplier. The prompt defines engagement fields, warns against supplier-name-only matches, distinguishes beneficiary geography from incident and supplier geography, and asks for concise supported reasons. The optional country filter in supplier-name correction only helps browse that catalog. It does not exclude engagement candidates or change the existing matching rules.

The `LinkInput`, `EngagementSuggestion`, and `EngagementSuggestions` contracts live in `app/models.py`. The strict structured response has four top-level fields:

| Field | Contract |
| --- | --- |
| `suggestions` | Zero to five items, each containing `engagement_id`, `reason`, and `evidence_strength`. |
| `selected_engagement_id` | The strongest suggestion's exact ID, or null when suggestions is empty. |
| `reason` | Concise explanation of the default, alternatives, or why no candidate is supported. |
| `citations` | List of short excerpts labeled `INCIDENT.<column>` or `<ENGAGEMENT_ID>.<column>`; [] when none are available. |

Each suggestion must identify a distinct supplied candidate and contain a nonblank reason. Suggestions use strict integer scores 1-4: weak, moderate, strong, very strong. Unsupported candidates have conceptual score 0 and are omitted. An empty list is valid when none fits.

The default must belong to the suggestions and have the highest evidence score. When scores tie, the model selects its best factual fit and explains ambiguity. The default is a proposal awaiting human approval. The prompt asks for strongest-first order; Python validates the default's score and candidate membership without silently repairing an invalid response.

Pydantic rejects additional fields, incorrect types, more than five suggestions, and out-of-range scores. Python also rejects duplicate or out-of-shortlist IDs, whitespace-only reasons, missing/default mismatches, and a weaker default. Responses need a completed non-refused choice. The shared `app.models.remove_schema_limits` helper removes Azure-unsupported min/max schema keywords recursively from the provider schema; Python still enforces these limits.

Citation strings refer to original incident or candidate values, not earlier model summaries. Python checks only the list/string structure; it does not verify exact quotation, source labels, duplicates, blank entries, or length.

Provider settings, `store=False`, timeout, retry, and omitted temperature/token parameters are shared with [classification](llm.md#provider-defaults). No input token counter or tokenizer download is added.

## Saved linking fields

The service returns 25 linking fields plus `citations`, shared with classification in the final CSV:

| Fields | Meaning |
| --- | --- |
| `link_supplier_name` | Base name used for this lookup. |
| `link_status` | Processing/proposal status below. |
| `linked_engagement_id` | Model-selected default proposal, not a human-confirmed link. |
| `link_reason`, `link_confidence` | Overall decision summary and default evidence strength. |
| `link_match_count`, `link_candidate_count`, `link_suggestion_count` | Distinct counts described above. |
| `link_error` | Exception type only on failure. |
| `link_catalog_hash` | SHA-256 of the complete catalog rows, including order, for stale-proposal detection. |
| `link_1_engagement_id`, `link_1_reason`, `link_1_evidence_strength` through slot 5 | Five fixed suggestion slots; unused slots are blank. |

The caller combines model excerpts into exactly one `citations` cell, with `Classification:` and `Engagement:` line prefixes. A new lookup replaces the Engagement part; proposal resets and failed/no-call lookups clear it while keeping classification excerpts. The dashboard marks these excerpts as unverified.

`link_confidence` is the selected suggestion's 1-4 evidence score. A model response with no suggestions saves 0; no linking call leaves it blank. It is not a probability. Classification evidence and engagement evidence measure different claims.

| `link_status` | Meaning |
| --- | --- |
| PENDING | Engagement work has not started. |
| RUNNING | A lookup has started; no new completed proposal is saved yet. |
| READY | One to five suggestions and a model default are available. |
| NO_MATCH | No lexical matches, or the model found no supported suggestions. |
| FAILED | Catalog preparation, request, or response validation failed. |
| NOT_APPLICABLE | The effective classification is HSBC. |
| SKIPPED | Classification remains unresolved; supplier linking is unavailable. |

Suggestion IDs, scores, and reasons are flat CSV cells, without JSON blobs. The caller additionally saves an `ENG_`-prefixed snapshot of every actual catalog field for the current selected engagement. Initially this is the model default; a different accepted human choice replaces the snapshot, while the original model default ID and reasons remain separate. No selection or a no-link decision clears the snapshot. The API joins proposal IDs with the current catalog when displaying alternatives and also exposes the saved snapshot. Source engagement files are never written. Historical linking outputs remain untouched and are not migrated into the new schema.

## Human decisions and immediate supplier changes

The single dashboard shows all incidents. `app/review.py` owns the human decision rules and immediate refresh flow, using explicit file paths supplied by the HTTP app. Review proceeds left to right:

1. **Classification:** approve a model HSBC/SUPPLIER decision, or disagree with a reason and select a corrected class. UNCERTAIN remains blocked until the human chooses a definite HSBC or SUPPLIER result. Processing failures can be resolved manually with a reason.
2. **Supplier name:** for a reviewed Supplier incident, approve the usable model base name or choose a replacement from `SUPPLIER_NAME.csv` and give a reason. The file contains base names with optional COUNTRY metadata and is read-only. The correction form searches names and optionally filters countries, showing 50 choices per page while retaining the selected name. Country is not a separate saved review decision. A changed name immediately runs the same `find_engagements` function and replaces the current suggestions/default; engagement approval resets.
3. **Engagement:** explicitly approve the default or select a different matching engagement with a reason. The reviewer can inspect every Python match, including candidates beyond the model cap. The accepted choice is stored separately as `reviewed_engagement_id`; the model default remains in `linked_engagement_id`. A reviewer can also disagree with all matches and save no link with a reason.

Changing classification resets downstream reviews. HSBC has no supplier/engagement review; an unresolved class cannot advance. Rejecting or changing an engagement does not reject the classification. A model default or merely opening the page never counts as human approval.

The nine review fields are the status, selected value, and reason for classification, supplier, and engagement. The incident store uses atomic replacement, a cross-process lock, and row-version checks. Catalog fingerprints prevent accepting proposals against a changed catalog until lookup is refreshed. Pipeline failures save and stop; unfinished/failed work can be retried without overwriting a recorded human classification decision. See [classification saving](llm.md#saving-stopping-and-resuming) and the [dashboard](dashboard_app.md) for the remaining workflow rules.
