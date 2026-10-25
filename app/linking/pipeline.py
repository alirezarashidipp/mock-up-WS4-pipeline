from pathlib import Path

import yaml

from app.csv_files import read_records
from app.linking.linking import link_incidents


ROOT = Path(__file__).resolve().parents[2]
INCIDENT_FILE = ROOT / "data/run/LLM_OUTPUT.csv"
ENGAGEMENT_FILE = ROOT / "data/mockup/ENG_ALL.csv"
OUTPUT_FILE = ROOT / "data/run/INC_LINKED.csv"
PROMPT_FILE = ROOT / "prompts/linking.yml"


def run_linking_pipeline():
    incidents, error = read_records(INCIDENT_FILE)
    if error:
        print(error)
        return 1
    engagements, error = read_records(ENGAGEMENT_FILE)
    if error:
        print(f"Place ENG_ALL.csv at {ENGAGEMENT_FILE}.")
        return 1
    prompt = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))["system"]
    return link_incidents(incidents, engagements, prompt, OUTPUT_FILE)


if __name__ == "__main__":
    try:
        raise SystemExit(run_linking_pipeline())
    except Exception as error:
        # Provider error messages can contain credentials.
        print(f"Stopped: {type(error).__name__}. Earlier files are preserved.")
        raise SystemExit(1) from None
