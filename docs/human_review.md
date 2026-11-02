# Human review

Human review is a separate local stage after engagement linking. It reuses the engagement dashboard layout and adds Yes/No decisions for classification and the proposed engagement link.

```text
INC_LINKED.csv -> read -> preserve previous reviews -> add new incidents -> HUMAN_REVIEW.csv
HUMAN_REVIEW.csv -> review dashboard -> validate decision -> save HUMAN_REVIEW.csv
```

The dashboard has two ways to reach the same incident details and review controls. Engagement first is the default:

```text
Engagement first -> Engagement list -> Selected engagement's incidents -> Incident details and Yes/No review
Incident first -> All saved incidents -> Incident details and Yes/No review
```

Engagement cards show the engagement name, company, ID, and proposed incident count. Their incident lists retain original model proposals, including links later rejected or invalidated by human review. Status badges distinguish those decisions. Rejection does not move the reviewer away from the selected engagement.

Engagement first reads the full `data/mockup/ENG_ALL.csv` catalog, including engagements with zero saved incidents, and includes saved proposal IDs absent from that catalog. `total_engagements` counts the distinct union of those IDs. Saved proposal fields take precedence; catalog data adds otherwise missing engagement groups without rewriting incident or review values. If the catalog is missing, unreadable, or invalid, the view falls back to saved proposal groups and displays an explicit scope warning. Review remains available, but that fallback is not a full engagement inventory.

Incident first lists every saved HUMAN_REVIEW.csv row: matched or unmatched Supplier incidents, HSBC, UNCERTAIN, failed classifications, and rejected reviews. Search the list and filter by All, HSBC, SUPPLIER, UNCERTAIN, or failed/unclassified results. Both modes use the same saved decisions and the same Yes/No panels. An incident-first save stays in that mode. Breadcrumbs return to the selected list, and saved detail URLs or Refresh preserve the view.

The separate Unlinked incidents tab remains available. Rejected and invalidated links appear there as well as under their original engagement proposal; this is two views of the same saved incident, not duplicate CSV rows.

## Run

From the project root, prepare the review file before starting the review server:

```powershell
.\.venv\Scripts\python.exe -m app.human_review.pipeline
.\.venv\Scripts\python.exe -m app.ui.human_review_app
```

Open `http://127.0.0.1:8768/`. Use Engagement first, Incident first, or Unlinked incidents to reach an incident. Review controls appear in its details. Saved confirmations are green; rejection requires a reason. Refresh reloads the saved data.

Preparation reads `data/run/INC_LINKED.csv` and writes `data/run/HUMAN_REVIEW.csv`. It preserves every source field and identifier. On rerun, it keeps prior decisions and adds new incident IDs. It does not remove previously saved incidents. A changed source row or schema is rejected instead of attaching an old approval to changed evidence; use a separate review output for a changed batch. Empty input leaves existing files unchanged. Run preparation while the review server is stopped.

## CSV fields

All original model and engagement columns remain unchanged. Five additional columns store the current human decisions:

| Column | Values or purpose |
| --- | --- |
| `hitl_classification` | `pending`, `confirmed`, `rejected`, or `not_applicable` when no successful recognized classification exists. |
| `hitl_classifivation_reasninb` | Required reason when classification is rejected; blank after confirmation. This exact spelling preserves the requested column name. |
| `hitl_link` | `pending`, `confirmed`, `rejected`, `invalidated`, or `not_applicable`. |
| `hitl_link_reasoning` | Required reason for a rejected link, or an explanation when classification rejection invalidates the link. Blank after link confirmation or reset to pending. |
| `hitl_linked_engagement_id` | The effective human-confirmed engagement ID. Filled only when classification and link are both confirmed; otherwise blank. |

The original `linked_engagement_id`, `link_status=MATCHED`, and `ENG_` columns describe the model's proposal. They do not imply human approval. Consumers of reviewed results must use the `hitl_` fields, especially `hitl_linked_engagement_id`, for the accepted link.

## Decisions

Classification can be reviewed only when `processing_status=success` and the result is HSBC, SUPPLIER, or UNCERTAIN. Confirming UNCERTAIN accepts the model's inability to attribute responsibility; it does not create a Supplier result. Failed classifications have no successful decision to approve.

Link review is available only for a successful SUPPLIER classification that has been confirmed and has an existing valid matched engagement proposal. No controls create a new classification or choose a different engagement. HSBC, UNCERTAIN, and rows without a matched proposal have no link to approve.

| Action | Classification result | Link result |
| --- | --- | --- |
| Classification Yes | `confirmed`; clear classification rejection reason. | Keep an existing link decision. If the link was invalidated by prior classification rejection, reset it to `pending` and require a fresh decision. |
| Classification No, with reason | `rejected`; save the reason. | Invalidate an existing matched proposal and clear the effective engagement ID. Rows without a proposal remain `not_applicable`. |
| Link Yes | Keep `confirmed` classification. | `confirmed`; clear the link rejection reason and fill the effective engagement ID. |
| Link No, with reason | Keep `confirmed` classification. | `rejected`; save the reason and clear the effective engagement ID. |

Classification rejection replaces the link's current review result with `invalidated` and the explanation: `Classification rejected; review the link again after confirming classification.` The classification reason remains in its own column. The CSV stores current decisions, not a review-history log.

**Synthetic example:** incident `DEMO-INC-1` is classified SUPPLIER and proposes `DEMO-ENG-UK`. After Yes for classification and link, both review fields are `confirmed` and the effective ID is `DEMO-ENG-UK`. If the reviewer later rejects classification, the link becomes `invalidated` and its effective ID becomes blank. A later classification Yes changes the link to `pending`, so a new link Yes is required. Rejecting only the link never changes the classification decision.

## Dashboard and saving

- Human review progress stays visible in both modes, on lists and incident details. It counts every saved row in HUMAN_REVIEW.csv, regardless of search, classification/group filter, or selected incident. Refresh and a successfully saved decision update these totals.
- Classification review has separate Confirmed, Pending, Rejected, and Not applicable counts. Link review has Confirmed, Pending, Rejected, Invalidated, and Not applicable counts. Each group's counts sum to the total number of saved incidents. These are two decisions per incident, so do not add the two groups together.
- Successful HSBC and UNCERTAIN classifications can be pending, confirmed, or rejected; their link review is always not applicable. Failed classification is not applicable. A row without a matched engagement proposal is not applicable for link review. A pending link can be waiting for classification confirmation before its controls become available.
- Invalidated links were cancelled because classification was rejected. Keep them separate from directly rejected links, which leave classification confirmed.
- The overview shows total saved incidents, successful model classifications split by HSBC/SUPPLIER/UNCERTAIN, and failed/unclassified rows. Successful Supplier incidents are split into those with an original model match and those without one. These two Supplier counts sum to successful Supplier classifications. Human-confirmed links are counted separately.
- Rejecting a classification does not rewrite the model's label, evidence score, or original match. Original model matches, current active proposals, and human-confirmed links are different counts. A rejected or invalidated link remains a model match but no longer counts as an active or human-confirmed link.
- Engagement first keeps all original matched proposals available for inspection, with their pending, confirmed, rejected, or invalidated status. Rejected and invalidated links also appear in Other unlinked incidents. No view treats a pending proposal as human confirmation.
- The review app reads and updates HUMAN_REVIEW.csv and reads ENG_ALL.csv for the engagement catalog. It never writes the catalog. `app.state.catalog_file` defaults to `data/mockup/ENG_ALL.csv`. GET requests do not create files or save decisions. A missing review file prompts running the preparation command.
- `POST /api/review` accepts the incident ID, decision target, confirmation or rejection, reason, and current `review_version`. Reasons for rejection must be nonblank and at most 2,000 characters. Unknown fields, invalid targets, unavailable decisions, and stale versions are rejected without saving. Refresh before retrying a stale decision.
- `review_version` is computed from the saved row and returned by the API; it is not an extra CSV column. The server serializes updates within its single local process and uses the existing atomic CSV writer. Run one review server process for a given output file.
- CSV text is rendered as text, including rejection reasons. The loopback server checks local request hosts and origins for writes. This is a local demo with current-state decisions, not a multi-user approval or audit service.
- There are no LLM calls, reclassification requests, or automatic relinking. Source CSVs remain unchanged. The read-only classification dashboard on port 8766 and engagement dashboard on port 8767 remain independent. No FINAL.csv is created.

### Review count fields

`GET /api/engagements` and successful review saves return these additional `counts` keys in human-review mode only:

| Classification review | Link review |
| --- | --- |
| `review_classification_confirmed` | `review_link_confirmed` |
| `review_classification_pending` | `review_link_pending` |
| `review_classification_rejected` | `review_link_rejected` |
| `review_classification_not_applicable` | `review_link_not_applicable` |
| — | `review_link_invalidated` |

These counts are calculated from the existing `hitl_classification` and `hitl_link` columns. No CSV columns, decisions, or scores are added or changed by counting.

### Navigation data and model counts

The review API includes `all_incidents` for the complete saved incident list, `all_engagements` for Engagement first, and `engagement_scope_note` explaining the available catalog scope. The existing active `engagements` and `unlinked_groups` remain separate from that browsing list. Review decisions are shared across all views.

Additional overview counts are `total_engagements`, `supplier_model_linked_incidents`, and `supplier_without_model_link_incidents`. Total engagements follows the catalog scope above; incident counts cover the saved HUMAN_REVIEW.csv snapshot. The two Supplier counts use successful model classifications and the original `link_status=MATCHED`, independently of human decisions. `review_link_confirmed` counts accepted human links. Search and filters do not change these global totals.
