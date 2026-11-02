import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from app.classification_review import REVIEW_FILE, load_reviewed_rows
from app.csv_files import read_records
from app.linking.linking import link_incidents


ROOT = Path(__file__).resolve().parents[2]
INCIDENT_FILE = ROOT / "data/run/LLM_OUTPUT.csv"
ENGAGEMENT_FILE = ROOT / "data/mockup/ENG_ALL.csv"
OUTPUT_FILE = ROOT / "data/run/INC_LINKED.csv"
PROMPT_FILE = ROOT / "prompts/linking.yml"


def run_linking_pipeline():
    load_dotenv(ROOT / ".env")
    try:
        max_candidates = int(os.getenv("LINK_MAX_CANDIDATES", "70"))
        if max_candidates < 1:
            raise ValueError
    except ValueError:
        print("LINK_MAX_CANDIDATES must be a positive integer.")
        return 1

    try:
        incidents = load_reviewed_rows(INCIDENT_FILE, REVIEW_FILE)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Classification review could not be loaded: {type(error).__name__}. Check the input and review CSV files.")
        return 1
    for incident in incidents:
        incident.pop("review_version", None)
        incident.pop("review_stale", None)
    engagements, error = read_records(ENGAGEMENT_FILE)
    if error:
        print(f"Place ENG_ALL.csv at {ENGAGEMENT_FILE}.")
        return 1
    prompt = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))["system"]
    return link_incidents(incidents, engagements, prompt, OUTPUT_FILE, max_candidates)


if __name__ == "__main__":
    try:
        raise SystemExit(run_linking_pipeline())
    except Exception as error:
        # Provider error messages can contain credentials.
        print(f"Stopped: {type(error).__name__}. Earlier files are preserved.")
        raise SystemExit(1) from None
