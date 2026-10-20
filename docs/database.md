# CSV storage

| File | Contents |
| --- | --- |
| RAW.csv | Original input and identifiers; unchanged. |
| CLEAN.csv | Standardized names in YAML order; only invisible special characters removed. |
| LLM_OUTPUT.csv | Cleaned source values, six model fields, exact llm_input and llm_prompt snapshots, and processing metadata. |
| FINAL.csv | The full original result plus FINAL_CLASS, USER_REASON, REVIEW_ACTION, REVIEW_DATE, and STATUS. |

The six model fields are classification, key_root_cause, decision_rationale, supporting_evidence, llm_confidence, and uncertainty_reason. Evidence and input fields are JSON arrays inside CSV cells.

Final metadata:

- FINAL_CLASS: HSBC or SUPPLIER chosen by the user.
- USER_REASON: required, nonblank, at most 2000 characters.
- REVIEW_ACTION: CONFIRMED, CORRECTED, or RESOLVED_UNDECIDED.
- REVIEW_DATE: UTC ISO 8601 timestamp.
- STATUS: FINALIZED.

The model classification is preserved separately from FINAL_CLASS. INCIDENT_ID links every file. Pending means a successful LLM_OUTPUT row has no matching INCIDENT_ID in FINAL.csv. Failed model requests are pipeline failures, not UNDECIDED decisions.

Outputs default to data/run/. The hand-authored five-row mockup uses data/mockup/. FINAL.csv is created on the first user decision. Older CLEANED.csv or HUMAN_REVIEW.csv files are preserved and ignored by the new workflow. Older final-result schemas are rejected explicitly; use a separate batch folder rather than overwriting decisions.
