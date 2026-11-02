"""Live connection check. Run explicitly; ordinary test discovery skips this file."""

import unittest

import yaml

from app.llm.classification import PROMPT_FILE, classify_row
from app.llm.llm_connection import llm_connection
from app.llm.pipeline import DEFINITIONS_FILE
from app.llm.prepare_fields import prepare_fields


class LLMConnectionTest(unittest.TestCase):
    def test_llm_responds(self):
        row = {
            "INCIDENT_ID": "SYNTHETIC-CONNECTION-CHECK",
            "INCIDENT_DESCRIPTION": "Synthetic connection check: an internal payment service was temporarily unavailable.",
            "ROOT_CAUSE_NOTES": "Synthetic confirmed finding: an HSBC engineer applied an incorrect internal routing configuration. Reverting that change restored the service. No supplier action caused this example incident.",
        }
        try:
            definitions_text = DEFINITIONS_FILE.read_text(encoding="utf-8")
            definitions = yaml.safe_load(definitions_text)
            fields = prepare_fields(row, definitions)
            prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
            prompt = yaml.safe_load(prompt_text)["system"]
            with llm_connection() as (client, model):
                result = classify_row(client, model, fields, prompt)
        except Exception as error:
            # Provider and validation errors may contain credentials or input values.
            raise AssertionError(
                f"LLM connection check failed: {type(error).__name__}. "
                "Check .env, connectivity, prompt files, and structured-output support."
            ) from None

        self.assertIsNotNone(
            result,
            "The model response was empty, refused, incomplete, or failed classification validation.",
        )
        print("Connection check passed: the synthetic request returned a valid structured classification. No CSV files were read or written.")


if __name__ == "__main__":
    unittest.main()
