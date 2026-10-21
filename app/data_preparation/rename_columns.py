def rename_columns(rows: list[dict[str, str]], column_names: list[dict[str, str]]) -> list[dict[str, str]]:
    mapping = {}
    for field in column_names:
        mapping[field["original_name"]] = field["new_name"].upper()

    renamed_rows = []
    for row in rows:
        renamed = {}
        for original_name, value in row.items():
            new_name = mapping.get(original_name, original_name.upper())
            renamed[new_name] = value
        renamed_rows.append(renamed)

    return renamed_rows
