# Engagement dashboard

Run `python -m app.ui.engagement_dashboard` from the project root after linking. Open `http://127.0.0.1:8767/`.

```text
data/run/INC_LINKED.csv -> Engagements and companies -> Linked incidents -> Incident details
```

## Flow

1. `GET /` serves `frontend/engagements/index.html`; its script requests `GET /api/engagements` on load and Refresh.
2. Read INC_LINKED.csv and group `link_status=MATCHED` rows by `linked_engagement_id`. Engagement names, companies, and engagement fields come from the saved `ENG_` columns. Keep separate engagements even when they share a company.
3. Show engagement/company cards with linked incident counts. Count other link statuses separately; they do not belong to an engagement.
4. Selecting an engagement opens its incident list. Selecting an incident opens its saved incident, supplier, engagement, and linking details. Hash URLs retain navigation through refresh and browser Back.
5. Render every CSV value as text. Reuse `frontend/style.css` and the existing logo artwork.

## Boundaries

- INC_LINKED.csv is the only data input. Keep the full saved incident row available for details; do not query ENG_ALL.csv, LLM_OUTPUT.csv, or an LLM.
- The app writes no files and provides no review or editing actions. Linking confidence is model-reported, not measured accuracy.
- A missing or empty file produces an empty view. Refresh rereads the CSV; there is no polling or pipeline dependency at runtime.
- The classification dashboard on port 8766 remains separate. This dashboard does not require it to be running.
