def rename_columns(rows: list[dict[str, str]], column_names: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    mapping = {}
    for field in column_names:
        mapping[field["original_name"]] = field["new_name"].upper()

    if len(mapping) != len(column_names) or len(set(mapping.values())) != len(mapping):
        print("Each original name and each new name must appear once in columns.yaml.")
        return []
    if set(rows[0]) != set(mapping) or "INCIDENT_ID" not in mapping.values():
        print("Map every CSV column in columns.yaml, including one column named INCIDENT_ID.")
        return []

    renamed_rows = []
    for row in rows:
        renamed = {}
        for original_name, new_name in mapping.items():
            renamed[new_name] = row[original_name]
        renamed_rows.append(renamed)

    ids = [row["INCIDENT_ID"] for row in renamed_rows]
    if any(not incident_id.strip() for incident_id in ids) or len(ids) != len(set(ids)):
        print("Every INCIDENT_ID must be nonempty and unique.")
        return []
    return renamed_rows
