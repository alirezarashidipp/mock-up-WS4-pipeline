from pathlib import Path

import yaml

from app.csv_files import read_records
from app.llm.classification import classify_rows


ROOT = Path(__file__).resolve().parents[2]
INPUT_FILE = ROOT / "data/run/CLEAN.csv"
OUTPUT_FILE = ROOT / "data/run/LLM_OUTPUT.csv"
DEFINITIONS_FILE = ROOT / "fields/definitions.yml"


def run_llm_pipeline():
    rows, error = read_records(INPUT_FILE)
    if error:
        print(error)
        return 1
    definitions_text = DEFINITIONS_FILE.read_text(encoding="utf-8")
    definitions = yaml.safe_load(definitions_text)
    return classify_rows(rows, definitions, OUTPUT_FILE)


if __name__ == "__main__":
    try:
        raise SystemExit(run_llm_pipeline())
    except Exception as error:
        # Error messages from providers may contain credentials.
        print(f"Stopped: {type(error).__name__}. Earlier files are preserved.")
        raise SystemExit(1) from None
