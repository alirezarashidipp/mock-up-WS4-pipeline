# Short description

There are two processing entry points: unchanged Cleaning, then one LLM pipeline. There is one incident dashboard.

```text
RAW -> Cleaning -> CLEAN
For each incident: Classification -> Automatic engagement suggestions -> Save INCIDENTS.csv
Dashboard: 1. Classification -> 2. Supplier name -> 3. Engagement
```

## Classification

- HSBC: all six supplier fields return null; automatic linking is not applicable.
- SUPPLIER: return the documented base supplier name and supplier facts. Unknown core facts return Unknown; absent extra facts return null.
- UNCERTAIN: all supplier fields return null. Explain missing or conflicting facts. Automatic linking is skipped.
- UNCERTAIN is a successful model result, not a processing failure.
- Evidence strength is an integer from 0 to 4, not a probability. UNCERTAIN uses 0-2; HSBC/SUPPLIER use 1-4.
- evidence_column contains source names joined with comma and space in one CSV cell. Empty lists are accepted.
- Both LLM responses include citations: short source-labeled excerpts, or []. Python does not check exact matches against source text.
- Human corrections never rewrite the original model classification or its evidence score.
- Five nullable context fields follow the original 12 fields: incident_country, supplier_country, causing_party, affected_party, and resolving_party. They contain documented source facts only; absent, conflicting, or ambiguous facts stay null.
- Incident country means the incident/affected-service location; supplier country means the involved supplier entity/operations country. Do not infer either from headquarters or copy one into the other. Supplier country is null for HSBC/UNCERTAIN.
- An actor can cause, suffer, or resolve a problem; those roles are distinct. Being affected or helping restore service does not establish responsibility.

## Automatic linking

- Model Supplier results enter matching immediately, before human review.
- Match the base name against THIRD_PARTY_NAME first, then THIRD_PARTY_NORMALISED_NAME within each ENG_ALL row.
- Normalize only for matching: lowercase, ASCII folding, and words separated by one space. Preserve original names in saved/displayed data.
- Keep every Python match available for human browsing. Send the first LINK_MAX_CANDIDATES matches to the LLM; the default cap is 70.
- Return at most five distinct engagement suggestions, each with a short reason and evidence strength 1-4. Select one of the strongest as the model default.
- If no candidate is supportable, return no suggestions and no default. Do not force five.
- Save the default automatically. It is still awaiting human approval.
- Counts are separate: all Python matches, capped LLM candidates, and returned suggestions. A candidate count does not prove the provider received a request.

## Human review

1. **Classification:** approve the model's HSBC/SUPPLIER class, or select Disagree with a reason and corrected class. An unresolved UNCERTAIN stays here. Failed classifications can receive a reasoned manual decision.
2. **Supplier name:** for a reviewed Supplier, approve the model's usable base name or search SUPPLIER_NAME.csv, optionally filter by country, and select a name with a reason. Results are paged in groups of 50 and keep the selected name during filtering. A corrected name immediately reruns engagement finding.
3. **Engagement:** explicitly approve the default, or choose any other Python match with a reason. None of these also requires a reason and records a completed review without an accepted link.

HSBC needs only classification review. A human correction from HSBC/UNCERTAIN/failed to Supplier enables supplier selection, then engagement finding. Later steps stay locked until their prerequisites are saved.

Changing classification resets downstream human decisions. Changing supplier removes earlier engagement approval and refreshes suggestions. Rejecting engagement leaves classification and supplier decisions unchanged. Failed refreshes preserve the human correction and allow retry. A stale response cannot overwrite a newer decision.

## Supplier catalog and country context

Existing one-column SUPPLIER_NAME.csv files remain valid. Optionally add a COUNTRY column with headers SUPPLIER_NAME,COUNTRY; repeat the base name for each country and leave unknown countries blank. Countries help the human browse a large catalog. The default filter is all countries, and the selected base name remains the saved choice. Country does not hard-filter Engagements or add another review step. The app never fills or rewrites source catalogs, and the supplier-name catalog is not sent to classification.

The dashboard shows country and actor fields as original model extracts, separately from the corrected supplier name. Correcting a name does not turn the previous model's country or actor assertions into facts about the replacement.

## Dashboard review aids

Classification and Supplier name share the top row on desktop; Engagement spans the row underneath. Suggestions are visible cards, shaded from deep to pale green by evidence strength. The model-default badge and saved approval status remain separate. A search field and dropdown cover all matching engagements, preserve the current selection during filtering, and stay synchronized with the cards. An explicit approval or reasoned correction saves the decision.

- **At a glance** summarizes the saved batch. The bottleneck map counts each incident once in processing, classification, supplier name, engagement, or complete; clicking a bucket opens its queue.
- Each incident has a **next action**, an **AI proposal vs human decision** comparison with reasons, and evidence links that open the saved source field. Unavailable source names are labeled without rejecting the model output.
- Compare up to three engagement candidates side by side. Highlight actual catalog differences and inspect how Python normalized and matched each name. Neither differences nor name similarity establish the correct engagement.
- A clearly labeled **synthetic walkthrough** explains Supplier approval, supplier correction, and resolving Uncertain. It makes no model calls or saved decisions and is excluded from real counts.

These are presentation aids in the existing dashboard. The CSV schema and ordered review rules are unchanged; the proposal comparison shows current state, not a full decision history.

## Synthetic AXA example

SUPPLIER_NAME.csv contains the base name **AXA**. ENG_ALL.csv contains records named **AXA Insurance**, **AXA Com**, and other AXA entities.

1. The model classifies a synthetic incident as SUPPLIER and returns AXA.
2. Python finds 30 engagement rows through normalized name matching.
3. With a cap of 70, all 30 are prepared for one linking request.
4. The model returns up to five suggestions with reasons and selects its strongest as the saved default.
5. The dashboard shows **30 matches / 30 LLM candidates / up to 5 suggestions**. All 30 can be inspected.
6. The reviewer approves Supplier classification, approves AXA, and explicitly approves an engagement.
7. If the reviewer changes AXA to another catalog base name with a reason, search and suggestion generation run again immediately. The new default remains pending human approval.

## Saved output

**INCIDENTS.csv** contains original incident values, 17 classification fields (including citations), processing status/error, 25 link fields, nine human-review fields, the Python row_revision, and actual selected engagement columns prefixed ENG_.

The single citations cell contains lines labeled Classification: and Engagement:. A new linking lookup replaces only Engagement citations; proposal resets or failed/no-call lookups clear stale Engagement excerpts. The dashboard labels them as unverified. Existing unified outputs missing citations or any of the five country/actor fields read those columns as blank in memory and gain them on the next normal save, without rerunning completed model work or replacing source values and human decisions.

linked_engagement_id is the current model default. reviewed_engagement_id is populated only by an explicit human engagement selection. ENG_ cells describe the current selected engagement: initially the default, then the human choice; they clear when no engagement is selected. A completed None-of-these review is not a human-confirmed link.

Old output CSV files are preserved and are not migrated automatically. Earlier architecture diagrams remain historical snapshots.

## Current workflow diagrams

- [Six-stage workflow infographic](images/ws4-incident-workflow.png): a shareable overview of automatic proposals and ordered human review.

- [Automatic incident processing](../.archify/workflow-ws4-current-20261102-190621/ws4-pipeline.html): unchanged Cleaning, sequential classification and automatic Supplier suggestions, per-incident saves, and retry behavior.
- [Three ordered human decisions](../.archify/workflow-ws4-current-20261102-190621/ws4-human-review.html): classification, supplier name, engagement approval or correction, immediate name-based recomputation, and completion without a link.

The diagrams cite the implementation at a pinned source revision. They describe the overall workflow, not a live provider run, and do not yet illustrate the added country/actor fields or paged supplier search. The current contracts are documented above.

## Simple code flow

The entry point reads inputs, then processes one incident at a time: `classify_and_save` -> `link_incident` -> next incident. Shared LLM contracts and output defaults live in `app/models.py`. `app/incidents.py` stores the current snapshot; `app/review.py` applies human decisions and reuses `find_engagements` after supplier corrections. The dashboard handles HTTP and display. The business flow and run commands stay the same; the classification result adds the five nullable context columns described above.
