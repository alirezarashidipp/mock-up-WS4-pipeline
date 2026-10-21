from pathlib import Path

from app.data_preparation.cleaning import clean_rows
from app.data_preparation.load_columns import load_columns
from app.data_preparation.read_csv import read_csv
from app.data_preparation.rename_columns import rename_columns
from app.data_preparation.save_csv import save_cleaned


ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = ROOT / "data/mockup/RAW.csv"
CLEAN_FILE = ROOT / "data/run/CLEAN.csv"


def run_pipeline():
    columns = load_columns(ROOT / "fields/columns.yaml")
    rows = read_csv(INPUT_FILE)
    rows = rename_columns(rows, columns)
    rows = clean_rows(rows)
    return save_cleaned(rows, CLEAN_FILE)


if __name__ == "__main__":
    try:
        raise SystemExit(run_pipeline())
    except Exception as error:
        # Error messages from providers may contain credentials.
        print(f"Stopped: {type(error).__name__}. Earlier files are preserved.")
        raise SystemExit(1) from None
