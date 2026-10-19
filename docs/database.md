# CSV files

No database.

| File | Contents |
| --- | --- |
| Raw input CSV | Original data and identifiers, unchanged. |
| CLEANED.csv | Standardized UPPERCASE input columns and cleaned values. |
| LLM_OUTPUT.csv | Cleaned inputs, six model fields, processing_status, review_status, error. |
| FINAL.csv | Approved LLM output with STATUS=USER_APPROVED and review metadata. |
| HUMAN_REVIEW.csv | Cleaned input columns plus STATUS, REVIEW_DATE, REJECTION_REASON, LLM_UNCERTAINTY_REASON. |

Review metadata dates use UTC ISO 8601. Human-review STATUS is USER_REJECTED or LLM_UNDECIDED. Only the corresponding reason field is populated. Approval has empty reasons.

ROW_ID is preserved across files. A row cannot enter both FINAL.csv and HUMAN_REVIEW.csv. Existing decisions persist across restarts.

Real pipeline outputs default to data/run/. The hand-authored mockup uses data/mockup/. FINAL.csv is created when the first approval is saved; HUMAN_REVIEW.csv is created when a row needs human review. Earlier demo files are preserved.
