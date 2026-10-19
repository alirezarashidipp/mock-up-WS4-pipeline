# Demo architecture

```mermaid
flowchart TD
    RAW["RAW.csv<br/>Original incident records"]
    MAP["column_mapping.csv<br/>Original name → UPPERCASE name"]
    PREP["Data preparation<br/>Rename columns · Clean text"]
    CLEAN["CLEANED.csv<br/>Cleaned records with preserved ROW_ID"]

    PROMPT["classification.yml<br/>Classification instructions"]
    DEFINITIONS["definitions.yml<br/>Short column definitions"]
    LLM["LLM classification<br/>One request per row"]
    OUTPUT["LLM_OUTPUT.csv<br/>Cleaned inputs + classification<br/>Root cause · Rationale · Evidence<br/>Confidence · Uncertainty reason"]

    UI["FastAPI + Frontend<br/>User reviews the decision"]
    FINAL["FINAL.csv<br/>Cleaned inputs + LLM output<br/>STATUS: USER_APPROVED<br/>REVIEW_DATE"]
    HUMAN["HUMAN_REVIEW.csv<br/>Cleaned input columns<br/>+ STATUS<br/>+ REVIEW_DATE<br/>+ REJECTION_REASON<br/>+ LLM_UNCERTAINTY_REASON"]

    RAW --> PREP
    MAP -.-> PREP
    PREP --> CLEAN

    CLEAN --> LLM
    PROMPT -.-> LLM
    DEFINITIONS -.-> LLM
    LLM --> OUTPUT

    OUTPUT -->|"SUPPLIER or HSBC"| UI
    OUTPUT -->|"UNDECIDED<br/>STATUS: LLM_UNDECIDED"| HUMAN

    UI -->|"User approves"| FINAL
    UI -->|"User rejects with a reason<br/>STATUS: USER_REJECTED"| HUMAN

    classDef file fill:#f5f5f5,stroke:#666,color:#222
    classDef process fill:#fff,stroke:#db0011,stroke-width:2px,color:#222
    classDef config fill:#fafafa,stroke:#999,stroke-dasharray:5 5,color:#444
    classDef approved fill:#edf7ef,stroke:#39804b,color:#224b2c
    classDef human fill:#fff8e7,stroke:#b58829,color:#654e1c

    class RAW,CLEAN,OUTPUT file
    class PREP,LLM,UI process
    class MAP,PROMPT,DEFINITIONS config
    class FINAL approved
    class HUMAN human
```

The manual pipeline saves cleaned data before calling the model. LLM_OUTPUT.csv contains the same cleaned values and structured results. FastAPI reads this self-contained output without making model calls.

Human review receives cleaned columns plus STATUS, REVIEW_DATE, REJECTION_REASON, and LLM_UNCERTAINTY_REASON. Final approval keeps the model results too. ROW_ID links all files.

Uncertain rows are routed during classification, at app startup, and on explicit reload. Existing rows are skipped so dates remain unchanged. Review never edits raw data, CLEANED.csv, or LLM_OUTPUT.csv.

One local worker and a lock serialize writes. CSV replacement is atomic and duplicate/stale decisions are rejected. This is a small demo; complete a batch before reviewing it.
