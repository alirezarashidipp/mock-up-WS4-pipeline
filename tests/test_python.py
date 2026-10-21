"""Small checks using temporary CSVs and simulated LLM responses."""

import json
import os
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml

from app.csv_files import read_records
from app.data_preparation import pipeline as preparation
from app.llm import classification
from app.ui.dashboard_app import get_dashboard_data
from app.ui.review_store import ReviewDecision, get_review_data, submit_review


ROOT = Path(__file__).resolve().parents[1]


class PythonTests(unittest.TestCase):
    def test_data_preparation(self):
        with TemporaryDirectory(dir=ROOT) as folder:
            raw = Path(folder) / "RAW.csv"
            clean = Path(folder) / "CLEAN.csv"
            source = "incident_id,incident_description\n001,<b>Example</b> demo@example.com!\u200b\n"
            raw.write_text(source, encoding="utf-8")

            with patch.object(preparation, "INPUT_FILE", raw), patch.object(preparation, "CLEAN_FILE", clean):
                self.assertEqual(preparation.run_pipeline(), 0)
                previous = clean.read_bytes()
                self.assertEqual(preparation.run_pipeline(), 1)
                self.assertEqual(clean.read_bytes(), previous)

            rows, error = read_records(clean)
            self.assertEqual(error, "")
            self.assertEqual(rows, [{"INCIDENT_ID": "001", "INCIDENT_DESCRIPTION": "<b>Example</b> demo@example.com!"}])
            self.assertEqual(raw.read_text(encoding="utf-8"), source)

    def test_llm_review_and_dashboard(self):
        labels = ["HSBC", "SUPPLIER", "UNDECIDED"]
        rows = []
        responses = []
        for index, label in enumerate(labels, start=1):
            value = f'Example cause {index}: service failed, then recovered.\nCheck "example".'
            rows.append({"INCIDENT_ID": f"00{index}", "INCIDENT_DESCRIPTION": value})
            result = {
                "classification": label,
                "key_root_cause": value,
                "decision_rationale": "Example explanation.",
                "supporting_evidence": [{"column": "INCIDENT_DESCRIPTION", "quote": value}],
                "llm_confidence": 80,
                "uncertainty_reason": "Example missing attribution." if label == "UNDECIDED" else None,
            }
            if label == "HSBC":
                result["supporting_evidence"] = [{"column": "INCIDENT_DESCRIPTION", "quote": word} for word in ("Example", "cause", "service", "recovered", "Check")]
            if label == "UNDECIDED":
                result["supporting_evidence"] = []
            message = SimpleNamespace(content=json.dumps(result), refusal=None)
            choice = SimpleNamespace(message=message, finish_reason="stop")
            responses.append(SimpleNamespace(choices=[choice]))

        client = Mock()
        definitions = yaml.safe_load((ROOT / "fields/definitions.yml").read_text(encoding="utf-8"))
        connection = nullcontext((client, "example-model"))

        with TemporaryDirectory(dir=ROOT) as folder:
            folder = Path(folder)
            output = folder / "LLM_OUTPUT.csv"

            def respond(**kwargs):
                index = client.chat.completions.create.call_count - 1
                if index:
                    saved_rows, _ = read_records(output)
                    self.assertEqual(len(saved_rows), index)
                return responses[index]

            client.chat.completions.create.side_effect = respond
            with patch.object(classification, "llm_connection", return_value=connection), patch.dict(os.environ, {"LLM_TEMPERATURE": ""}):
                self.assertEqual(classification.classify_rows(rows, definitions, output), 0)

            self.assertEqual(client.chat.completions.create.call_count, 3)
            for index, call in enumerate(client.chat.completions.create.call_args_list):
                messages = call.kwargs["messages"]
                fields = json.loads(messages[1]["content"])
                self.assertEqual(messages[0]["role"], "system")
                self.assertTrue(messages[0]["content"])
                self.assertEqual(len(fields), 1)
                self.assertEqual(fields[0]["value"], rows[index]["INCIDENT_DESCRIPTION"])
                self.assertEqual(fields[0]["description"], definitions["INCIDENT_DESCRIPTION"])

            saved_rows, _ = read_records(output)
            self.assertNotIn("llm_input", saved_rows[0])
            self.assertNotIn("supporting_evidence", saved_rows[0])
            self.assertEqual(saved_rows[0]["evidence_5_quote"], "Check")
            self.assertEqual(saved_rows[1]["evidence_2_quote"], "")
            self.assertEqual(saved_rows[2]["evidence_1_quote"], "")
            self.assertEqual(saved_rows[0]["INCIDENT_DESCRIPTION"], rows[0]["INCIDENT_DESCRIPTION"])
            self.assertFalse(any(name.startswith("definition_") for name in saved_rows[0]))
            original = output.read_bytes()
            queue = get_review_data(output, folder)
            self.assertEqual(queue["counts"]["pending"], 3)
            self.assertEqual(len(queue["records"][0]["result"]["supporting_evidence"]), 5)
            self.assertEqual(queue["records"][0]["model_input"][0]["value"], rows[0]["INCIDENT_DESCRIPTION"])
            self.assertEqual(queue["records"][0]["model_input"][0]["description"], definitions["INCIDENT_DESCRIPTION"])
            for record, final_class in zip(queue["records"], ["HSBC", "HSBC", "SUPPLIER"]):
                decision = ReviewDecision(incident_id=record["incident_id"], version=record["version"], final_class=final_class, user_reason="Example user reason.")
                self.assertEqual(submit_review(output, folder, decision)[1], 200)
                self.assertEqual(submit_review(output, folder, decision)[1], 409)

            self.assertEqual(get_review_data(output, folder)["counts"]["pending"], 0)
            final_rows, _ = read_records(folder / "FINAL.csv")
            self.assertFalse(any(name.startswith("definition_") for name in final_rows[0]))
            self.assertEqual([row["REVIEW_ACTION"] for row in final_rows], ["CONFIRMED", "CORRECTED", "RESOLVED_UNDECIDED"])
            self.assertTrue(all(row["STATUS"] == "FINALIZED" and row["REVIEW_DATE"].endswith("Z") for row in final_rows))
            self.assertEqual(output.read_bytes(), original)
            output.unlink()
            self.assertEqual(get_dashboard_data(folder / "FINAL.csv")["counts"], {"total": 3, "HSBC": 2, "SUPPLIER": 1})


if __name__ == "__main__":
    unittest.main()
