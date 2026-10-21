import unicodedata


def clean_text(value: str) -> str:
    if value is None:
        return ""
    # Remove invisible control/format characters while retaining normal text and whitespace.
    return "".join(char for char in value if char in "\t\n\r" or unicodedata.category(char) not in ("Cc", "Cf"))


def clean_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned_rows = []
    for row in rows:
        cleaned = row.copy()
        for name, value in row.items():
            if name != "INCIDENT_ID":
                cleaned[name] = clean_text(value)
        cleaned_rows.append(cleaned)
    return cleaned_rows
