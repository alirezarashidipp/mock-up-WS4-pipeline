"""Small checks using temporary CSVs and simulated LLM responses."""

import json
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
from app.llm import classification, pipeline
from app.models import Classification, SUPPLIER_FIELDS
from app.ui.dashboard_app import get_dashboard_data


ROOT = Path(__file__).resolve().parents[1]


def example_response(label):
    result = {
        "classification": label,
        "key_root_cause": "Synthetic configuration error.",
        "decision_rationale": "Synthetic example explanation.",
        "evidence_column": ["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"],
        "citations": ["ROOT_CAUSE_NOTES: Synthetic recorded cause."],
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
        source_fields = {
            "ROOT_CAUSE_NOTES": "Synthetic recorded cause.",
            "PROBLEM_CLOSE_NOTES": "Synthetic closure finding.",
            "IT_PROBLEM_DESCRIPTION": "Synthetic problem narrative.",
            "INCIDENT_RESOLUTION_NOTES": "Synthetic restoration details.",
            "INCIDENT_WORK_NOTES": "Synthetic investigation notes.",
            "PROBLEM_WORK_NOTES": "Synthetic problem investigation.",
            "MAJOR_INCIDENT_FINDINGS": "Synthetic confirmed finding.",
        }
        definitions = {"INCIDENT_DESCRIPTION": "A synthetic incident narrative."}
        for name in source_fields:
            definitions[name] = "A synthetic supporting incident field."
        for row in rows:
            row.update(source_fields)
        responses = [example_response("HSBC"), example_response("SUPPLIER"), example_response("UNCERTAIN")]
        client = Mock()
        with TemporaryDirectory(dir=ROOT) as folder:
            output = Path(folder) / "INCIDENTS.csv"

            def respond(**kwargs):
                index = client.chat.completions.create.call_count - 1
                if index:
                    saved, _ = read_records(output)
                    self.assertEqual(len(saved), len(rows))
                    self.assertEqual(sum(row["processing_status"] == "success" for row in saved), index)
                return responses[index]

            client.chat.completions.create.side_effect = respond
            with patch.object(pipeline, "llm_connection", return_value=nullcontext((client, "example-model"))):
                self.assertEqual(pipeline.classify_incidents(rows, definitions, output, []), 0)
            self.assertEqual(client.chat.completions.create.call_count, 3)
            for index, call in enumerate(client.chat.completions.create.call_args_list):
                messages = call.kwargs["messages"]
                fields = json.loads(messages[1]["content"])
                self.assertTrue(messages[0]["content"])
                self.assertEqual(len(fields), len(definitions))
                self.assertEqual({field["name"] for field in fields}, set(definitions))
                for field in fields:
                    name = field["name"]
                    self.assertEqual(field["description"], definitions[name])
                    self.assertEqual(field["value"], rows[index][name])
                self.assertNotIn("temperature", call.kwargs)
                self.assertNotIn("max_completion_tokens", call.kwargs)
                self.assertNotIn("max_tokens", call.kwargs)
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
            dashboard = get_dashboard_data(output, suppliers_path=Path(folder) / "missing-suppliers.csv", engagements_path=Path(folder) / "missing-engagements.csv")
            self.assertEqual({key: dashboard["counts"][key] for key in ("total", "classified", "HSBC", "SUPPLIER", "UNCERTAIN", "failed")}, {"total": 3, "classified": 3, "HSBC": 1, "SUPPLIER": 1, "UNCERTAIN": 1, "failed": 0})
            self.assertEqual(dashboard["incidents"][1]["supplier_name"], "Unknown")
            self.assertEqual(dashboard["incidents"][1]["processing_status"], "success")
            self.assertEqual(dashboard["incidents"][0]["evidence_column"], ["INCIDENT_DESCRIPTION", "ROOT_CAUSE_NOTES"])
            self.assertEqual(dashboard["incidents"][1]["evidence_column"], expected_names)
            self.assertEqual(len(expected_names), 8)
            self.assertEqual(dashboard["incidents"][1]["supplier_more_info"], saved[1]["supplier_more_info"])
            self.assertEqual(output.read_bytes(), before)
            self.assertFalse((Path(folder) / "FINAL.csv").exists())
    def test_failed_request_is_saved_and_excluded_from_counts(self):
        rows = [{"INCIDENT_ID": "001", "INCIDENT_DESCRIPTION": "Synthetic cause."}, {"INCIDENT_ID": "002", "INCIDENT_DESCRIPTION": "Synthetic failed request."}]
        for row in rows:
            row["ROOT_CAUSE_NOTES"] = "Synthetic recorded cause."
        definitions = {
            "INCIDENT_DESCRIPTION": "Example description.",
            "ROOT_CAUSE_NOTES": "Example cause notes.",
        }
        client = Mock()
        client.chat.completions.create.side_effect = [example_response("HSBC"), OpenAIError("Synthetic request failure")]
        with TemporaryDirectory(dir=ROOT) as folder:
            output = Path(folder) / "INCIDENTS.csv"
            with patch.object(pipeline, "llm_connection", return_value=nullcontext((client, "example-model"))):
                self.assertEqual(pipeline.classify_incidents(rows, definitions, output, []), 1)
            saved, _ = read_records(output)
            self.assertEqual([row["processing_status"] for row in saved], ["success", "failed"])
            self.assertEqual(saved[1]["error"], "OpenAIError")
            self.assertEqual(saved[1]["evidence_column"], "")
            counts = get_dashboard_data(output, suppliers_path=Path(folder) / "missing-suppliers.csv", engagements_path=Path(folder) / "missing-engagements.csv")["counts"]
            self.assertEqual((counts["total"], counts["classified"], counts["HSBC"], counts["failed"]), (2, 1, 1, 1))
            self.assertFalse((Path(folder) / "FINAL.csv").exists())

    def test_supplier_fields_follow_the_tag(self):
        labels = classification.classification_schema()["properties"]["classification"]["enum"]
        self.assertEqual(set(labels), {"HSBC", "SUPPLIER", "UNCERTAIN"})
        for label in ("HSBC", "SUPPLIER", "UNCERTAIN"):
            result = json.loads(example_response(label).choices[0].message.content)
            result["evidence_column"] = ["INCIDENT_DESCRIPTION"]
            for name in SUPPLIER_FIELDS:
                result[name] = "Unneeded supplier text" if label != "SUPPLIER" else None
            if label == "SUPPLIER":
                result["supplier_name"] = "  "
            message = SimpleNamespace(content=json.dumps(result), refusal=None)
            client = Mock()
            client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
            fields = [{"name": "INCIDENT_DESCRIPTION", "description": "Example description.", "value": "Synthetic incident."}]
            classified = classification.classify_row(client, "example-model", fields, "Example prompt.")
            self.assertIsNotNone(classified)
            for name in SUPPLIER_FIELDS:
                expected = None if label != "SUPPLIER" or name == "supplier_more_info" else "Unknown"
                self.assertEqual(getattr(classified, name), expected)

    def test_evidence_allows_empty_and_long_lists(self):
        result = json.loads(example_response("SUPPLIER").choices[0].message.content)
        for count in (0, 1, 11):
            with self.subTest(count=count):
                names = [f"SYNTHETIC_COLUMN_{number}" for number in range(count)]
                result["evidence_column"] = names
                message = SimpleNamespace(content=json.dumps(result), refusal=None)
                response = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
                parsed = classification.parse_response(response)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.evidence_column, names)
        names = ["SYNTHETIC_UNKNOWN", "SYNTHETIC_UNKNOWN", " "]
        result["evidence_column"] = names
        message = SimpleNamespace(content=json.dumps(result), refusal=None)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
        parsed = classification.parse_response(response)
        self.assertEqual(parsed.evidence_column, names)
        result["evidence_column"] = [{"column": "INCIDENT_DESCRIPTION", "quote": "Old format"}]
        with self.assertRaises(ValidationError):
            Classification.model_validate(result)


if __name__ == "__main__":
    unittest.main()
