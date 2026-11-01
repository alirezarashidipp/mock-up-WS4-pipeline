# Engagement dashboard

Run `python -m app.ui.engagement_dashboard` from the project root after linking. Open `http://127.0.0.1:8767/`.

```text
data/run/INC_LINKED.csv -> Engagements -> Linked incidents -> Incident details
                       -> Unlinked incidents -> Filter by group -> Incident details
```

## Flow

1. `GET /` serves `frontend/engagements/index.html`; its script requests `GET /api/engagements` on load and Refresh.
2. Read INC_LINKED.csv and group `link_status=MATCHED` rows by `linked_engagement_id`. Engagement names, companies, and engagement fields come from the saved `ENG_` columns. Keep separate engagements even when they share a company.
3. Show engagement/company cards with linked incident counts in the Engagements tab. The Unlinked incidents tab includes every row without a matched engagement and supports group filtering and incident search.
4. Split the unlinked total into three nonoverlapping groups:
   - HSBC: `classification=HSBC` and `link_status=NOT_APPLICABLE`. No supplier engagement link is required.
   - Supplier: `classification=SUPPLIER` and `link_status=UNDECIDED`. No confirmed match was found; the saved reason may describe missing candidates, missing supplier information, or ambiguity.
   - Other: failed or skipped rows, plus remaining unlinked rows whose classification/status pair does not fit either group above. Keep these separate from successful HSBC and undecided Supplier rows.
5. Selecting an engagement opens its linked incident list. Selecting a linked or unlinked incident opens its saved incident, supplier, and linking details, including the saved reason and processing status. Show classification `attribution_evidence_strength` as 0-4 with its label (Unsupported, Weak, Moderate, Strong, Very strong), plus an expandable explanation of the five levels. Keep `link_confidence` separate on its existing 0-100 scale. Linked incidents also show the selected engagement. Hash URLs retain navigation through refresh and browser Back.
6. Render every CSV value as text. Reuse `frontend/style.css` and the existing logo artwork.

## API counts and records

`GET /api/engagements` keeps the existing `engagements` list and `counts.unlinked_incidents` total. It also returns `unlinked_groups`, with `hsbc`, `supplier`, and `other` lists containing the complete saved rows. The three new counts are `hsbc_incidents`, `supplier_unlinked_incidents`, and `other_unlinked_incidents`; their sum equals `unlinked_incidents`. Matched rows remain grouped by engagement ID and are not included in any unlinked group.

## Boundaries

- INC_LINKED.csv is the only data input. Keep the full saved incident row available for details; do not query ENG_ALL.csv, LLM_OUTPUT.csv, or an LLM.
- The app writes no files and provides no review or editing actions. Linking confidence is model-reported, not measured accuracy.
- Attribution evidence strength rates recorded support for the selected HSBC/SUPPLIER classification, not probability of correctness or supplier-name extraction. It is separate from engagement matching. A score of 4 is not 100% accuracy; repeated copies of one statement are not independent evidence.
- Old rows without `attribution_evidence_strength` show Not recorded; legacy `llm_confidence` is never converted. Unexpected nonblank scores display Invalid score. All saved row values remain available in the incident details dropdown without rewriting the CSV.
- A missing or empty file produces an empty view. Refresh rereads the CSV; there is no polling or pipeline dependency at runtime.
- The classification dashboard on port 8766 remains separate. This dashboard does not require it to be running.
