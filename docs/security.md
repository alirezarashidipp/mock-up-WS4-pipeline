# Local demo boundaries

Credentials remain in the ignored .env and are never printed.

The pipeline keeps ROW_ID local, removes ordinary emails, and standardizes column names before saving CLEANED.csv and sending values to the model. This limited cleanup is not complete anonymization; raw and cleaned records can still contain sensitive information.

The UI renders CSV values as text. Writes require same-origin JSON and are validated with Pydantic. Only pending definite classifications can be approved or rejected; rejection requires a reason.

Use one local worker and keep batch outputs closed in Excel while saving. Atomic replacement protects existing files from interrupted writes. This demo has no authentication or multi-user deployment.

Demo assessments and confidence scores are hand-authored. Prompt rules remain draft interpretations, not approved HSBC policy.
