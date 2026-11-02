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
- Human corrections never rewrite the original model classification or its evidence score.

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
2. **Supplier name:** for a reviewed Supplier, approve the model's usable base name or select a name from SUPPLIER_NAME.csv with a reason. A corrected name immediately reruns engagement finding.
3. **Engagement:** explicitly approve the default, or choose any other Python match with a reason. None of these also requires a reason and records a completed review without an accepted link.

HSBC needs only classification review. A human correction from HSBC/UNCERTAIN/failed to Supplier enables supplier selection, then engagement finding. Later steps stay locked until their prerequisites are saved.

Changing classification resets downstream human decisions. Changing supplier removes earlier engagement approval and refreshes suggestions. Rejecting engagement leaves classification and supplier decisions unchanged. Failed refreshes preserve the human correction and allow retry. A stale response cannot overwrite a newer decision.

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

**INCIDENTS.csv** contains original incident values, 11 classification fields, processing status/error, 25 link fields, nine human-review fields, the Python row_revision, and actual selected engagement columns prefixed ENG_.

linked_engagement_id is the current model default. reviewed_engagement_id is populated only by an explicit human engagement selection. ENG_ cells describe the current selected engagement: initially the default, then the human choice; they clear when no engagement is selected. A completed None-of-these review is not a human-confirmed link.

Old output CSV files are preserved and are not migrated automatically. The archived architecture diagram represents the earlier workflow.

## Simple code flow

The entry point reads inputs, then the loop processes one incident at a time: `classify_and_save` -> `link_incident` -> next incident. The dashboard reuses `find_engagements` after supplier corrections. CSV reading/writing stays in the shared module; current incident decisions stay in the incident store. The cleanup changes code organization only, not the saved schema or business decisions.
