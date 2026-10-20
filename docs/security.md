# Local demo boundaries

Secrets belong in the ignored .env and are never printed. llm_connection.py selects the configured provider and closes the client and any Azure credential resources.

Cleaning removes invisible special characters only. Emails, links, HTML markup, and punctuation are retained as requested. This is not anonymization. INCIDENT_ID stays local; the other configured fields are sent to the selected model service.

CSV values, evidence, prompts, and user reasons are rendered as text. Write requests require same-origin JSON and Pydantic validation. Every final decision requires an HSBC/SUPPLIER choice and a nonblank reason. No LLM outcome is finalized automatically.

Run one local worker. A lock serializes writes, record versions reject stale submissions, and finalized IDs cannot be submitted again. CSV replacement is atomic. Keep CSV outputs closed in Excel while saving.

The demo has no user login or cloud hosting. Model assessments and confidence scores in the mockup are hand-authored. No model-quality or production-readiness claim is made.
