def rename_columns(rows: list[dict[str, str]], column_names: list[dict[str, str]]) -> list[dict[str, str]]:
    mapping = {}
    for field in column_names:
        mapping[field["original_name"]] = field["new_name"].upper()

    if len(mapping) != len(column_names) or len(set(mapping.values())) != len(mapping):
        print("Each original name and each new name must appear once in column_mapping.csv.")
        return []
    if set(rows[0]) != set(mapping) or "ROW_ID" not in mapping.values():
        print("Map every CSV column in column_mapping.csv, including one column named ROW_ID.")
        return []

    renamed_rows = []
    for row in rows:
        renamed = {}
        for original_name, value in row.items():
            renamed[mapping[original_name]] = value
        renamed_rows.append(renamed)

    ids = [row["ROW_ID"] for row in renamed_rows]
    if any(not row_id.strip() for row_id in ids) or len(ids) != len(set(ids)):
        print("Every ROW_ID must be nonempty and unique.")
        return []
    return renamed_rows
