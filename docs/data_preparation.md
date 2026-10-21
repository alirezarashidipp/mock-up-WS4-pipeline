# Data preparation flow

Entry point: `python -m app.data_preparation.pipeline` from the project root.

```text
data/mockup/RAW.csv -> read -> rename -> clean -> data/run/CLEAN.csv
```

## Execution

1. `load_columns`: load `fields/columns.yaml`; its `columns` list contains `{original_name, new_name}` pairs. Definitions belong to the later LLM stage.
2. `read_csv`: read the entire source CSV using `csv.DictReader` and `utf-8-sig`. Values remain text, preserving leading zeros. Keep the source file unchanged.
3. `rename_columns`: match original headers exactly, apply mapped names, and uppercase them. Uppercase unmapped headers too. Preserve meaningful names: `incident_id` becomes `INCIDENT_ID`.
4. `clean_rows`: process each value except `INCIDENT_ID`. Remove Unicode categories `Cc` and `Cf`, retaining tabs, carriage returns, and line feeds. Convert missing non-ID values to empty strings; preserve punctuation, emails, links, HTML, and normal whitespace.
5. `save_cleaned`: write all prepared rows with headers and a UTF-8 BOM to `CLEAN.csv`, using `app.csv_files.write_records`. Row order and duplicate/empty IDs are retained.

## Boundaries

- This stage makes no LLM calls and does not load prompts or column definitions.
- No ID presence/uniqueness checks or mapping-collision checks run here. Headers that resolve to the same name overwrite earlier values in that row.
- Empty input returns exit code `1` without creating or changing output. With data rows, each run replaces `CLEAN.csv` with the newly prepared rows, including when the file already exists.
- Success returns `0` and prints `Output:` with the saved path. Runtime errors print the exception type and exit with `1`; non-UTF-8 input can cause `UnicodeDecodeError`.
- Handoff: `app.llm.pipeline` reads `CLEAN.csv`; its request flow and separate checks are documented in [llm.md](llm.md).

Implementation: `app/data_preparation/pipeline.py` calls `load_columns`, `read_csv`, `rename_columns`, `clean_rows`, then `save_cleaned`.
