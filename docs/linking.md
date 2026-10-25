# Incident-to-engagement linking

Run `python -m app.linking.pipeline` from the project root, after classification.

```text
data/run/LLM_OUTPUT.csv + data/mockup/ENG_ALL.csv
    -> find supplier candidates -> ask LLM -> save data/run/INC_LINKED.csv
```

## Per incident

1. Keep the complete LLM_OUTPUT row. Only successful SUPPLIER classifications enter matching.
2. Compare `supplier_name` with `THIRD_PARTY_NAME` and `THIRD_PARTY_NORMALISED_NAME`. Python normalizes case/punctuation and uses whole-word or fuzzy matching at 0.8. Keep every matching engagement row; name similarity retrieves candidates, not a confirmed link. Blank/Unknown names produce no candidates. Lexical matching can miss aliases such as EY versus Ernst & Young.
3. Send the incident fields, prior model results, all candidate rows, and `prompts/linking.yml` to the LLM. Keep INCIDENT_ID local. Prior model results are context, not proof. Reuse `app/llm/llm_connection.py` and its OpenAI/Azure settings.
4. The model chooses one candidate ENGAGEMENT_ID or null when evidence is insufficient or ambiguous. Return a short reason, self-reported confidence from 0 to 100, and separate incident/engagement source-column name lists, without quotes.
5. Validate the response structure, selected ID against exactly one candidate, and source names against supplied headers. Copy the selected engagement's actual CSV values; do not generate its details with the model.
6. Save that row before processing the next incident. Never modify either input CSV.

## Output

- Preserve every original LLM_OUTPUT column. Add every ENG_ALL column with an `ENG_` prefix; for example, `ENG_ENGAGEMENT_ID` and `ENG_THIRD_PARTY_NAME`. Leave these cells empty when no engagement is selected.
- Add `linked_engagement_id`, `link_status`, `link_reason`, `link_confidence`, `link_incident_columns`, `link_engagement_columns`, and `link_error`.
- Join source-column lists with comma and space in their respective cells. Store no JSON, prompt, or evidence quotes.

| link_status | Meaning |
| --- | --- |
| MATCHED | The model selected one supplied engagement. |
| UNDECIDED | No name candidates, unknown supplier, or insufficient evidence to select one. |
| NOT_APPLICABLE | The incident was classified HSBC; no linking request. |
| SKIPPED | Classification did not succeed; no linking request. |
| FAILED | The linking request or response failed validation. |

Provider/invalid-response failures are saved where possible, then stop the batch; earlier rows remain saved. The shared writer retains schema and conflicting-ID checks. Use a separate output file for changed decisions rather than overwriting saved results.

The dashboard still reads only LLM_OUTPUT.csv. Linking is an independent command; INC_LINKED.csv is not displayed there. Candidate retrieval is a simple lexical demo and does not guarantee all relevant engagements are found. Offline simulated checks do not establish live matching accuracy.
