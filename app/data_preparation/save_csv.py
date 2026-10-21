from app.csv_files import append_record


def save_cleaned(rows, path):
    if not rows:
        return 1
    if path.exists():
        print("CLEAN.csv already exists. Choose a new file to preserve earlier data.")
        return 1
    for row in rows:
        saved, error = append_record(path, row)
        if not saved:
            print(error)
            return 1
    print(f"Output: {path}")
    return 0
