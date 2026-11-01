"""Small checks using temporary CSVs and simulated LLM responses."""

import json
import os
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai import OpenAIError
from pydantic import ValidationError

from app.csv_files import read_records, write_records
from app.data_preparation import pipeline as preparation
from app.llm import classification
from app.models import Classification, SUPPLIER_FIELDS
from app.ui.dashboard_app import get_dashboard_data


ROOT = Path(__file__).resolve().parents[1]


def example_response(label):
    result = {
        "classification": label,
        "key_root_cause": "Synthetic configuration error.",
        "decision_rationale": "Synthetic example explanation.",
        "evidence_column": ["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"],
        "attribution_evidence_strength": 3,
    }
    for name in SUPPLIER_FIELDS:
        result[name] = None
    if label == "UNCERTAIN":
        result["key_root_cause"] = None
        result["decision_rationale"] = "Synthetic record lacks evidence to attribute responsibility."
        result["attribution_evidence_strength"] = 0
    if label == "SUPPLIER":
        result.update(
            supplier_name="Unknown",
            supplier_product_or_service="Example managed gateway",
            supplier_action_or_failure="Supplier deployed a defective routing change.",
            supplier_causal_explanation="The change interrupted synthetic payment routing.",
            supplier_accountability_reason="The recorded supplier change caused the failure.",
            supplier_more_info="The synthetic supplier recorded a regional maintenance window.",
        )
        result["evidence_column"].extend([
            "PROBLEM_CLOSE_NOTES", "IT_PROBLEM_DESCRIPTION", "INCIDENT_RESOLUTION_NOTES",
            "INCIDENT_WORK_NOTES", "PROBLEM_WORK_NOTES", "MAJOR_INCIDENT_FINDINGS",
        ])
    message = SimpleNamespace(content=json.dumps(result), refusal=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


class PythonTests(unittest.TestCase):
    def test_data_preparation(self):
        with TemporaryDirectory(dir=ROOT) as folder:
            raw = Path(folder) / "RAW.csv"
            clean = Path(folder) / "CLEAN.csv"
            source = "incident_id,incident_description\n001,<b>Example</b> demo@example.com!\u200b\n"
            raw.write_text(source, encoding="utf-8")
            clean.write_text("Old generated output", encoding="utf-8")
            with patch.object(preparation, "INPUT_FILE", raw), patch.object(preparation, "CLEAN_FILE", clean):
                self.assertEqual(preparation.run_pipeline(), 0)
                self.assertEqual(preparation.run_pipeline(), 0)
            rows, error = read_records(clean)
            self.assertEqual(error, "")
            self.assertEqual(rows, [{"INCIDENT_ID": "001", "INCIDENT_DESCRIPTION": "<b>Example</b> demo@example.com!"}])
            self.assertEqual(raw.read_text(encoding="utf-8"), source)

    def test_llm_saves_each_response_and_dashboard_reads_it(self):
        rows = [
            {"INCIDENT_ID": "001", "INCIDENT_DESCRIPTION": "Synthetic HSBC cause."},
            {"INCIDENT_ID": "002", "INCIDENT_DESCRIPTION": "Synthetic supplier cause."},
            {"INCIDENT_ID": "003", "INCIDENT_DESCRIPTION": "Synthetic uncertain attribution."},
        ]
        definitions = {"INCIDENT_DESCRIPTION": "A synthetic incident narrative."}
        responses = [example_response("HSBC"), example_response("SUPPLIER"), example_response("UNCERTAIN")]
        client = Mock()
        with TemporaryDirectory(dir=ROOT) as folder:
            output = Path(folder) / "LLM_OUTPUT.csv"

            def respond(**kwargs):
                index = client.chat.completions.create.call_count - 1
                if index:
                    saved, _ = read_records(output)
                    self.assertEqual(len(saved), index)
                return responses[index]

            client.chat.completions.create.side_effect = respond
            with patch.object(classification, "llm_connection", return_value=nullcontext((client, "example-model"))), patch.dict(os.environ, {"LLM_TEMPERATURE": "3"}):
                self.assertEqual(classification.classify_rows(rows, definitions, output), 0)
            self.assertEqual(client.chat.completions.create.call_count, 3)
            for index, call in enumerate(client.chat.completions.create.call_args_list):
                messages = call.kwargs["messages"]
                fields = json.loads(messages[1]["content"])
                self.assertTrue(messages[0]["content"])
                self.assertEqual(fields, [{"name": "INCIDENT_DESCRIPTION", "description": definitions["INCIDENT_DESCRIPTION"], "value": rows[index]["INCIDENT_DESCRIPTION"]}])
                self.assertEqual(call.kwargs["temperature"], 3.0)
            saved, error = read_records(output)
            self.assertEqual(error, "")
            self.assertEqual([row["classification"] for row in saved], ["HSBC", "SUPPLIER", "UNCERTAIN"])
            self.assertEqual(saved[2]["processing_status"], "success")
            self.assertEqual(saved[2]["attribution_evidence_strength"], "0")
            for name in SUPPLIER_FIELDS:
                self.assertEqual(saved[0][name], "")
                self.assertTrue(saved[1][name])
                self.assertEqual(saved[2][name], "")
            self.assertEqual(saved[1]["supplier_name"], "Unknown")
            self.assertEqual(saved[0]["evidence_column"], "INCIDENT_DESCRIPTION, ROOT_CAUSE_NOTES")
            expected_names = json.loads(responses[1].choices[0].message.content)["evidence_column"]
            self.assertEqual(saved[1]["evidence_column"], ", ".join(expected_names))
            self.assertEqual([name for name in saved[1] if name.startswith("evidence_")], ["evidence_column"])
            self.assertFalse(any(name.endswith("_quote") for name in saved[1]))
            self.assertEqual(saved[1]["supplier_more_info"], "The synthetic supplier recorded a regional maintenance window.")
            for row in saved:
                self.assertTrue(all(name not in row for name in ("llm_input", "llm_prompt", "review_status")))
                self.assertFalse(any(name.startswith("definition_") for name in row))
            before = output.read_bytes()
            dashboard = get_dashboard_data(output)
            self.assertEqual(dashboard["counts"], {"total": 3, "HSBC": 1, "SUPPLIER": 1, "UNCERTAIN": 1, "failed": 0})
            self.assertEqual(dashboard["records"][1]["supplier_name"], "Unknown")
            self.assertEqual(dashboard["records"][1]["processing_status"], "success")
            self.assertEqual(dashboard["records"][0]["evidence_column"], ["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"])
            self.assertEqual(dashboard["records"][1]["evidence_column"], expected_names)
            self.assertEqual(len(expected_names), 8)
            self.assertEqual(dashboard["records"][1]["supplier_more_info"], saved[1]["supplier_more_info"])
            self.assertEqual(output.read_bytes(), before)
            self.assertFalse((Path(folder) / "FINAL.csv").exists())
            for row in saved:
                for name in SUPPLIER_FIELDS:
                    row.pop(name)
                names = row.pop("evidence_column").split(", ")
                for number in range(1, 11):
                    row[f"evidence_{number}_column"] = names[number - 1] if number <= len(names) else ""
            write_records(output, saved)
            older_dashboard = get_dashboard_data(output)
            self.assertEqual(older_dashboard["counts"], dashboard["counts"])
            self.assertEqual(older_dashboard["records"][1]["supplier_name"], "")
            self.assertEqual(older_dashboard["records"][1]["evidence_column"], expected_names)

    def test_failed_request_is_saved_and_excluded_from_counts(self):
        rows = [{"INCIDENT_ID": "001", "INCIDENT_DESCRIPTION": "Synthetic cause."}, {"INCIDENT_ID": "002", "INCIDENT_DESCRIPTION": "Synthetic failed request."}]
        client = Mock()
        client.chat.completions.create.side_effect = [example_response("HSBC"), OpenAIError("Synthetic request failure")]
        with TemporaryDirectory(dir=ROOT) as folder:
            output = Path(folder) / "LLM_OUTPUT.csv"
            with patch.object(classification, "llm_connection", return_value=nullcontext((client, "example-model"))), patch.dict(os.environ, {"LLM_TEMPERATURE": ""}):
                self.assertEqual(classification.classify_rows(rows, {"INCIDENT_DESCRIPTION": "Example description."}, output), 1)
            saved, _ = read_records(output)
            self.assertEqual([row["processing_status"] for row in saved], ["success", "failed"])
            self.assertEqual(saved[1]["error"], "OpenAIError")
            self.assertEqual(saved[1]["evidence_column"], "")
            self.assertEqual(get_dashboard_data(output)["counts"], {"total": 1, "HSBC": 1, "SUPPLIER": 0, "UNCERTAIN": 0, "failed": 1})
            self.assertFalse((Path(folder) / "FINAL.csv").exists())

    def test_supplier_fields_follow_the_tag(self):
        labels = classification.classification_schema()["properties"]["classification"]["enum"]
        self.assertEqual(set(labels), {"HSBC", "SUPPLIER", "UNCERTAIN"})
        for label in ("HSBC", "SUPPLIER", "UNCERTAIN"):
            result = json.loads(example_response(label).choices[0].message.content)
            for name in SUPPLIER_FIELDS:
                result[name] = "Unneeded supplier text" if label != "SUPPLIER" else None
            if label == "SUPPLIER":
                result["supplier_name"] = "  "
            message = SimpleNamespace(content=json.dumps(result), refusal=None)
            client = Mock()
            client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
            fields = [{"name": "INCIDENT_DESCRIPTION", "description": "Example description.", "value": "Synthetic incident."}]
            with patch.dict(os.environ, {"LLM_TEMPERATURE": ""}):
                classified = classification.classify_row(client, "example-model", fields, "Example prompt.")
            self.assertIsNotNone(classified)
            for name in SUPPLIER_FIELDS:
                expected = None if label != "SUPPLIER" or name == "supplier_more_info" else "Unknown"
                self.assertEqual(getattr(classified, name), expected)

    def test_evidence_count_is_one_to_ten(self):
        result = json.loads(example_response("SUPPLIER").choices[0].message.content)
        evidence = result["evidence_column"][0]
        for count in (1, 2, 8, 10):
            with self.subTest(count=count):
                result["evidence_column"] = [evidence] * count
                parsed = Classification.model_validate(result)
                self.assertEqual(len(parsed.evidence_column), count)
        for count in (0, 11):
            with self.subTest(count=count):
                result["evidence_column"] = [evidence] * count
                with self.assertRaises(ValidationError):
                    Classification.model_validate(result)
        result["evidence_column"] = [{"column": "INCIDENT_DESCRIPTION", "quote": "Old format"}]
        with self.assertRaises(ValidationError):
            Classification.model_validate(result)


if __name__ == "__main__":
    unittest.main()
