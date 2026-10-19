import csv
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.data_preparation.cleaning import clean_rows
from app.data_preparation.prepare_fields import prepare_fields
from app.data_preparation.read_csv import read_csv
from app.data_preparation.rename_columns import rename_columns
from app.llm import classify_row
from app.save_csv import save_result
from app.csv_files import append_record
from app.review_store import sync_human_review


ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT / "data/incidents_sample_5.csv"
OUTPUT_FILE = ROOT / "data/run/LLM_OUTPUT.csv"


def main(input_file: Path = INPUT_FILE, output_file: Path = OUTPUT_FILE) -> int:
    cleaned_file = output_file.parent / "CLEANED.csv"
    if any(path.exists() for path in (output_file, cleaned_file, output_file.parent / "FINAL.csv", output_file.parent / "HUMAN_REVIEW.csv")):
        print("Batch files already exist. Choose a new output folder to preserve earlier results.")
        return 1
    columns = read_csv(ROOT / "fields/column_mapping.csv")
    definitions = yaml.safe_load((ROOT / "fields/definitions.yml").read_text(encoding="utf-8"))
    definitions = {name.upper(): description for name, description in definitions.items()}
    prompt = yaml.safe_load((ROOT / "prompts/classification.yml").read_text(encoding="utf-8"))["system"]

    rows = read_csv(input_file)
    if not rows:
        return 1
    rows = rename_columns(rows, columns)
    if not rows:
        return 1
    rows = clean_rows(rows)
    for row in rows:
        saved, error = append_record(cleaned_file, row)
        if not saved:
            print(error)
            return 1

    load_dotenv(ROOT / ".env")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    with OpenAI(timeout=60, max_retries=1) as client:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        for index, row in enumerate(rows, start=1):
            fields = prepare_fields(row, definitions)
            try:
                result = classify_row(client, model, fields, prompt)
            except (OpenAIError, ValidationError) as error:
                save_result(output_file, row, None, type(error).__name__)
                print(f"Stopped at row {index}: {type(error).__name__}. Earlier results are saved.")
                return 1
            saved = save_result(output_file, row, result, "Invalid model output" if result is None else "")
            if not saved:
                return 1
            if saved["classification"] == "UNDECIDED":
                routed = sync_human_review(output_file, output_file.parent)
                if "error" in routed:
                    print(routed["error"])
                    return 1
            if result is None:
                print(f"Stopped at row {index}: incomplete output or unsupported evidence.")
                return 1
            print(f"Saved {index}/{len(rows)}")
    print(f"Output: {output_file}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, TypeError, csv.Error, yaml.YAMLError, OpenAIError, ValidationError) as error:
        # API error text can contain credentials, so display only its type.
        print(f"Stopped: {type(error).__name__}. Check input files, YAML settings, and API configuration.")
        sys.exit(1)
