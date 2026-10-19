import re


# shortcut: covers ordinary email addresses; extend if unusual formats appear.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


def clean_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned_rows = []
    for row in rows:
        cleaned = row.copy()
        for name, value in row.items():
            if name != "ROW_ID":
                cleaned[name] = EMAIL_PATTERN.sub("[EMAIL]", value).strip()
        cleaned_rows.append(cleaned)
    return cleaned_rows
