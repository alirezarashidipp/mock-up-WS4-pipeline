# Demo architecture

```mermaid
flowchart TD
    RAW["RAW.csv<br/>Original incident records"] --> RENAME["Standardize column names"]
    CONFIG["fields/columns.yaml<br/>Original name · New name"] -.-> RENAME
    RENAME --> CLEANING["Remove invisible special characters only"]
    CLEANING --> CLEAN["CLEAN.csv"]
    CLEAN --> LLM["LLM · One request per row"]
    DEFINITIONS["fields/definitions.yml<br/>Standardized name · Definition"] -.-> LLM
    PROMPT["prompts/classification.yml"] -.-> LLM
    ENV[".env<br/>Provider · Model · Temperature"] -.-> CONNECTION["llm_connection.py<br/>OpenAI or Azure"]
    CONNECTION -.-> LLM
    LLM --> OUTPUT["LLM_OUTPUT.csv<br/>Cleaned values · Exact input and prompt<br/>Original model result"]
    OUTPUT -->|"HSBC / SUPPLIER / UNDECIDED"| REVIEW["review_app.py · Port 8765<br/>Choose HSBC or SUPPLIER + Mandatory reason"]
    REVIEW -->|"No user action"| PENDING["Remain PENDING_REVIEW"]
    PENDING --> REVIEW
    REVIEW -->|"Save final decision"| FINAL["FINAL.csv<br/>Original LLM result + FINAL_CLASS<br/>USER_REASON · REVIEW_ACTION<br/>REVIEW_DATE · STATUS = FINALIZED"]
    FINAL --> DASHBOARD["dashboard_app.py · Port 8766<br/>Independent read-only dashboard"]
    classDef process fill:#fff,stroke:#db0011,stroke-width:2px,color:#222
    classDef file fill:#f5f5f5,stroke:#666,color:#222
    classDef final fill:#edf7ef,stroke:#39804b,color:#224b2c
    class RENAME,CLEANING,LLM,CONNECTION,REVIEW process
    class RAW,CONFIG,DEFINITIONS,CLEAN,PROMPT,ENV,OUTPUT,PENDING file
    class FINAL,DASHBOARD final
```

Two pipelines run independently. app/data_preparation/pipeline.py reads RAW.csv, renames using fields/columns.yaml, cleans, and saves CLEAN.csv without calling a model. app/llm/pipeline.py reads the saved CLEAN.csv and fields/definitions.yml, classifies each row, and saves LLM_OUTPUT.csv. Definitions are keyed by standardized column name. CLEAN.csv is generated, not manually maintained.

Cleaning removes invisible Unicode control/format characters except tabs and line breaks. It preserves punctuation, symbols, emails, HTML, and ordinary whitespace. INCIDENT_ID is unchanged and excluded from model input.

Each successful model response remains pending until the user submits HSBC or SUPPLIER with a reason. Confirmation, correction, and resolution of UNDECIDED all write FINAL.csv. Human-review routing files are no longer used.

The saved llm_input and llm_prompt cells preserve the request's exact fields, definitions, values, and instructions. Review and dashboard are separate apps on ports 8765 and 8766, with separate run commands. Neither calls the model. The dashboard reads FINAL.csv independently and has no save endpoint.

Run one local worker and finish a batch before review. A process lock serializes writes, atomic replacement preserves existing files on save errors, unique IDs prevent duplicates, and versions reject stale decisions.
