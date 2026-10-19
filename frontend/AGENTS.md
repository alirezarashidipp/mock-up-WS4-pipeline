# Frontend instructions

- Keep the HSBC review UI minimal, English, and dependency-free.
- Display source fields, evidence, and analysis in collapsible sections; render CSV values as text.
- Only pending SUPPLIER/HSBC decisions can be approved or rejected.
- Approval saves to FINAL.csv; rejection requires a reason and routes to HUMAN_REVIEW.csv.
- UNDECIDED results are routed automatically and show why the LLM could not decide.
- Do not remove or mark records complete until the API confirms a save.
- Keep synthetic demo data visibly disclosed. Review makes no LLM calls.
