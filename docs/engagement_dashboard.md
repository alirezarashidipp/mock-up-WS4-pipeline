# Engagement dashboard

Run `python -m app.ui.engagement_dashboard` from the project root after linking. Open `http://127.0.0.1:8767/`.

```text
data/run/INC_LINKED.csv -> Engagements -> Linked incidents -> Incident details
                       -> Unlinked incidents -> Filter by group -> Incident details
```

## Flow

1. `GET /` serves `frontend/engagements/index.html`; its script requests `GET /api/engagements` on load and Refresh.
2. Read INC_LINKED.csv and group `link_status=MATCHED` rows by `linked_engagement_id`. Engagement names, companies, and engagement fields come from the saved `ENG_` columns. Keep separate engagements even when they share a company.
3. Show two overview sections above the incident/engagement lists. Incident classification shows total saved incidents, successfully classified incidents, HSBC, SUPPLIER, UNCERTAIN, and unclassified/failed rows. Engagement linking shows eligible Supplier incidents, linked incidents, undecided Supplier incidents, link failures, engagements, and companies. The Engagements tab shows engagement/company cards with linked incident counts. The Unlinked incidents tab includes every row without a matched engagement and supports group filtering and incident search.
4. Split the unlinked total into three nonoverlapping groups:
   - HSBC: `classification=HSBC` and `link_status=NOT_APPLICABLE`. No supplier engagement link is required.
   - Supplier: `classification=SUPPLIER` and `link_status=UNDECIDED`. No confirmed match was found; the saved reason may describe missing candidates, missing supplier information, or ambiguity.
   - Other: successful UNCERTAIN classifications with `link_status=SKIPPED`, failed or other skipped rows, plus remaining unlinked rows whose classification/status pair does not fit either group above. UNCERTAIN is a valid classification; its linking is skipped because supplier accountability is not established. Keep these separate from successful HSBC and undecided Supplier rows.
5. Selecting an engagement opens its linked incident list. Selecting a linked or unlinked incident opens its saved incident, supplier, and linking details, including the saved reason and processing status. Show classification `attribution_evidence_strength` as 0-4 with its label (Unsupported, Weak, Moderate, Strong, Very strong), plus an expandable explanation of the five levels. Show new `link_confidence` values with `link_confidence_scale=0-4` as Link evidence strength, using the same labels and a separate expandable link rubric. The two scores assess different decisions. Linked incidents also show the selected engagement. Hash URLs retain navigation through refresh and browser Back.
6. Render every CSV value as text. Reuse `frontend/style.css` and the existing logo artwork.

## API counts and records

`GET /api/engagements` returns these overview counts from the saved INC_LINKED.csv rows:

| Count | Meaning |
| --- | --- |
| `total_incidents` | Every saved incident row. |
| `classified_incidents` | Rows with `processing_status=success` and a recognized HSBC, SUPPLIER, or UNCERTAIN classification. |
| `classified_hsbc` | Successfully classified HSBC rows. |
| `classified_supplier` | Successfully classified SUPPLIER rows. |
| `classified_uncertain` | Successfully classified UNCERTAIN rows. UNCERTAIN is a valid result. |
| `unclassified_incidents` | Total minus classified: failed, missing, or unrecognized classification status/label. |
| `eligible_incidents` | Successfully classified SUPPLIER rows, including those with an Unknown supplier, no candidates, or a linking failure. Eligibility does not guarantee a link or an LLM call. |
| `link_failed_incidents` | Rows with `link_status=FAILED`. |

The three class counts sum to `classified_incidents`; classified plus unclassified equals `total_incidents`. `eligible_incidents` equals `classified_supplier`.

The API preserves the existing `engagements` list, linking counts, and `unlinked_groups` containing complete saved rows in `hsbc`, `supplier`, and `other` lists. The group counts `hsbc_incidents`, `supplier_unlinked_incidents`, and `other_unlinked_incidents` sum to `unlinked_incidents`. `hsbc_incidents` counts the HSBC/NOT_APPLICABLE group, while `classified_hsbc` counts successful HSBC classifications independently of linking status. Matched rows remain grouped by engagement ID and are outside the unlinked groups.

## Boundaries

- INC_LINKED.csv is the only data input. Keep the full saved incident row available for details; do not query ENG_ALL.csv, LLM_OUTPUT.csv, or an LLM.
- Overview totals describe the saved INC_LINKED.csv snapshot. If linking stopped partway through a batch, they do not represent every original input incident. Refresh reads the latest saved snapshot.
- The app writes no files and provides no review or editing actions. New `link_confidence` values assess recorded support for a unique engagement link, not probability or measured accuracy. The [linking document](linking.md) defines the rubric: unsupported, weak, moderate, strong, and very strong. Selected links allow 1-4; null selections allow 0-2. A blank score shows Not recorded.
- Attribution evidence strength rates recorded support for assigning responsibility to HSBC or Supplier, not probability of correctness or supplier-name extraction. For UNCERTAIN, scores 0-2 describe the limited attribution evidence, not confidence in uncertainty. It is separate from engagement matching. A score of 4 is not 100% accuracy; repeated copies of one statement are not independent evidence.
- The single classification `evidence_column` cell is preserved and visible in All incident fields. It contains comma-separated source column names; the dashboard does not generate extra evidence columns.
- Old rows without `attribution_evidence_strength` show Not recorded; legacy `llm_confidence` is never converted. Unexpected nonblank scores display Invalid score. All saved row values remain available in the incident details dropdown without rewriting the CSV.
- Read `link_confidence_scale` to identify the new link rubric. Markerless link scores display explicitly as legacy confidence on their original 0-100 scale, without conversion, even when their value is 0-4. Unknown scales and invalid scores are flagged rather than guessed. The Python CSV writer adds the scale marker; the dashboard only reads it.
- A missing or empty file produces an empty view. Refresh rereads the CSV; there is no polling or pipeline dependency at runtime.
- The classification dashboard on port 8766 remains separate. This dashboard does not require it to be running.
- [Human review](human_review.md) runs separately on port 8768 and reuses this frontend with review controls. It reads and updates HUMAN_REVIEW.csv; this port-8767 dashboard remains read-only and shows the original model results from INC_LINKED.csv.
