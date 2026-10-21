from app.csv_files import write_records


def save_cleaned(rows, path):
    if not rows:
        return 1
    write_records(path, rows)
    print(f"Output: {path}")
    return 0
