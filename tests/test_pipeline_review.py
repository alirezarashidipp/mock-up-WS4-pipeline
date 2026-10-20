import csv
import io
import json
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.data_preparation.cleaning import clean_rows
from app.data_preparation.load_columns import load_columns
from app.data_preparation.prepare_fields import prepare_fields
from app.data_preparation.read_csv import read_csv
from app.data_preparation.rename_columns import rename_columns
from app.main import ROOT, main
from app.models import Classification
from app.review import app
from app.review_store import ReviewDecision, get_dashboard_data, get_review_data, submit_review
from app.save_csv import save_result


def synthetic_batch():
    # Offline fixtures use the current schema, never the photographed incident.
    columns = load_columns(ROOT / "fields/columns.yaml")
    rows, assessments = [], []
    for index, label in enumerate(("SUPPLIER", "HSBC", "UNDECIDED", "SUPPLIER", "UNDECIDED"), start=1):
        row = {column["original_name"]: "" for column in columns}
        cause = "Cause not established." if label == "UNDECIDED" else f"Synthetic {label} change caused the outage."
        row.update(incident_id=f"{index:04d}", incident_short_description="Synthetic test incident", root_cause_notes=cause)
        rows.append(row)
        assessments.append(Classification(
            classification=label,
            key_root_cause=None if label == "UNDECIDED" else cause,
            decision_rationale="Synthetic assessment for an offline workflow check.",
            supporting_evidence=[{"column": "ROOT_CAUSE_NOTES", "quote": cause}],
            llm_confidence=70,
            uncertainty_reason="Cause not established." if label == "UNDECIDED" else None,
        ))
    return columns, rows, assessments


class PreparationTests(unittest.TestCase):
    def test_special_character_cleanup_preserves_meaningful_text(self):
        text = "  <b>Error</b> & user@example.com /a-b_v1.2?x=1\n\t± café  "
        rows = [{"INCIDENT_ID": "0001", "DESCRIPTION": "\x00" + text + "\u200b\x7f"}]
        result = clean_rows(rows)
        self.assertEqual(result[0]["DESCRIPTION"], text)
        self.assertEqual(result[0]["INCIDENT_ID"], "0001")
        self.assertEqual(rows[0]["DESCRIPTION"], "\x00" + text + "\u200b\x7f")

    def test_one_yaml_drives_names_order_and_definitions(self):
        columns, raw, _ = synthetic_batch()
        reordered = [dict(reversed(list(row.items()))) for row in raw]
        rows = rename_columns(reordered, columns)
        expected = [column["new_name"].upper() for column in columns]
        self.assertEqual(list(rows[0]), expected)
        self.assertTrue(all(name == name.upper() for name in expected))
        self.assertEqual(len(expected), 72)
        self.assertEqual(len(set(expected)), 72)
        self.assertTrue(all(column["new_name"] == column["original_name"].upper() for column in columns))
        self.assertEqual(rows[0]["INCIDENT_ID"], "0001")
        definitions = {column["new_name"].upper(): column["description"] for column in columns}
        payload = prepare_fields(rows[0], definitions)
        self.assertNotIn("INCIDENT_ID", [field["name"] for field in payload])
        self.assertEqual(len(payload), 71)
        self.assertTrue(all(field["description"] == definitions[field["name"]] for field in payload))

    def test_mapping_collisions_and_duplicate_ids_are_rejected(self):
        columns = [
            {"original_name": "ID", "new_name": "INCIDENT_ID"},
            {"original_name": "Text", "new_name": "TEXT"},
        ]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rename_columns([{"ID": "1", "Text": "a"}, {"ID": "1", "Text": "b"}], columns), [])
            columns[1]["new_name"] = "INCIDENT_ID"
            self.assertEqual(rename_columns([{"ID": "1", "Text": "a"}], columns), [])

    def test_manual_pipeline_saves_clean_and_exact_request_snapshots(self):
        _, raw, assessments = synthetic_batch()
        with tempfile.TemporaryDirectory() as directory:
            raw_file = Path(directory) / "RAW.csv"
            with raw_file.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(raw[0]))
                writer.writeheader()
                writer.writerows(raw)
            original = raw_file.read_bytes()
            output = Path(directory) / "LLM_OUTPUT.csv"
            with patch("app.main.llm_connection", return_value=nullcontext((Mock(), "test-model"))):
                with patch("app.main.classify_row", side_effect=assessments) as classify:
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(main(raw_file, output), 0)
            clean = read_csv(output.parent / "CLEAN.csv")
            saved = read_csv(output)
            self.assertEqual(len(saved), 5)
            for row, cleaned, request in zip(saved, clean, classify.call_args_list):
                self.assertEqual(row["INCIDENT_ID"], cleaned["INCIDENT_ID"])
                self.assertNotIn("ROW_ID", row)
                self.assertEqual({name: row[name] for name in cleaned}, cleaned)
                self.assertEqual(json.loads(row["llm_input"]), request.args[2])
                self.assertEqual(row["llm_prompt"], request.args[3])
            self.assertEqual(get_review_data(output, output.parent)["counts"]["pending"], 5)
            self.assertFalse((output.parent / "HUMAN_REVIEW.csv").exists())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(raw_file, output), 1)
            self.assertEqual(raw_file.read_bytes(), original)


class ReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.results = self.folder / "LLM_OUTPUT.csv"
        columns, raw, assessments = synthetic_batch()
        definitions = {column["new_name"]: column["description"] for column in columns}
        for row, result in zip(rename_columns(raw, columns), assessments):
            self.assertTrue(save_result(self.results, row, result, prepare_fields(row, definitions), "Synthetic test prompt."))

    def decision(self, incident_id, final_class, reason="The recorded incident evidence supports this responsibility."):
        data = get_review_data(self.results, self.folder)
        self.assertNotIn("error", data)
        row = next(row for row in data["records"] if row["incident_id"] == incident_id)
        return ReviewDecision(incident_id=incident_id, version=row["version"], final_class=final_class, user_reason=reason)

    def test_all_three_llm_classes_stay_pending_without_user_action(self):
        before = self.results.read_bytes()
        for _ in range(2):
            data = get_review_data(self.results, self.folder)
            self.assertEqual(data["counts"], {"pending": 5, "finalized": 0, "undecided": 2, "failed": 0})
            self.assertTrue(all(row["review_status"] == "PENDING_REVIEW" for row in data["records"]))
        self.assertFalse((self.folder / "FINAL.csv").exists())
        self.assertFalse((self.folder / "HUMAN_REVIEW.csv").exists())
        self.assertEqual(self.results.read_bytes(), before)
        self.assertEqual(get_dashboard_data(self.folder)["counts"]["total"], 0)

    def test_confirmation_corrections_and_undecided_resolution_feed_final_dashboard(self):
        routes = [
            ("0001", "SUPPLIER", "CONFIRMED"),
            ("0002", "SUPPLIER", "CORRECTED"),
            ("0003", "HSBC", "RESOLVED_UNDECIDED"),
            ("0004", "HSBC", "CORRECTED"),
            ("0005", "SUPPLIER", "RESOLVED_UNDECIDED"),
        ]
        original = self.results.read_bytes()
        for incident_id, final_class, action in routes:
            with self.subTest(incident_id=incident_id):
                decision = self.decision(incident_id, final_class)
                _, status = submit_review(self.results, self.folder, decision)
                self.assertEqual(status, 200)
                saved = next(row for row in read_csv(self.folder / "FINAL.csv") if row["INCIDENT_ID"] == incident_id)
                self.assertEqual(saved["FINAL_CLASS"], final_class)
                self.assertEqual(saved["REVIEW_ACTION"], action)
                self.assertEqual(saved["USER_REASON"], decision.user_reason)
                self.assertEqual(saved["STATUS"], "FINALIZED")
                self.assertTrue(saved["REVIEW_DATE"].endswith("Z"))
        self.assertEqual(self.results.read_bytes(), original)
        self.assertEqual(get_review_data(self.results, self.folder)["counts"]["pending"], 0)
        dashboard = get_dashboard_data(self.folder)
        self.assertEqual(dashboard["counts"], {
            "total": 5, "HSBC": 2, "SUPPLIER": 3,
            "CONFIRMED": 1, "CORRECTED": 2, "RESOLVED_UNDECIDED": 2,
        })
        self.assertEqual(dashboard["percentages"], {"HSBC": 40.0, "SUPPLIER": 60.0})

    def test_every_route_requires_reason_and_a_definite_final_class(self):
        for incident_id in ("0001", "0002", "0003"):
            with self.subTest(incident_id=incident_id):
                _, status = submit_review(self.results, self.folder, self.decision(incident_id, "HSBC", reason="  "))
                self.assertEqual(status, 400)
        with self.assertRaises(ValidationError):
            ReviewDecision(incident_id="0001", version="test", final_class="UNDECIDED", user_reason="Reason")
        self.assertFalse((self.folder / "FINAL.csv").exists())

    def test_duplicate_or_stale_submission_cannot_finalize_twice(self):
        decision = self.decision("0001", "SUPPLIER")
        _, status = submit_review(self.results, self.folder, decision.model_copy(update={"version": "stale"}))
        self.assertEqual(status, 409)
        self.assertEqual(submit_review(self.results, self.folder, decision)[1], 200)
        saved = (self.folder / "FINAL.csv").read_bytes()
        self.assertEqual(submit_review(self.results, self.folder, decision)[1], 409)
        self.assertEqual((self.folder / "FINAL.csv").read_bytes(), saved)
        self.assertEqual(get_review_data(self.results, self.folder)["counts"]["finalized"], 1)

    def test_dashboard_is_independent_of_llm_output(self):
        decision = self.decision("0003", "HSBC")
        self.assertEqual(submit_review(self.results, self.folder, decision)[1], 200)
        self.results.unlink()
        data = get_dashboard_data(self.folder)
        self.assertNotIn("error", data)
        self.assertEqual(data["counts"]["HSBC"], 1)
        self.assertEqual(data["counts"]["RESOLVED_UNDECIDED"], 1)

    def test_failed_save_preserves_final_and_keeps_incident_pending(self):
        self.assertEqual(submit_review(self.results, self.folder, self.decision("0001", "SUPPLIER"))[1], 200)
        saved = (self.folder / "FINAL.csv").read_bytes()
        decision = self.decision("0002", "HSBC")
        with patch("app.csv_files.os.replace", side_effect=OSError("CSV locked")):
            with self.assertRaises(OSError):
                submit_review(self.results, self.folder, decision)
        self.assertEqual((self.folder / "FINAL.csv").read_bytes(), saved)
        self.assertEqual(get_review_data(self.results, self.folder)["counts"]["pending"], 4)

    def test_edited_or_mismatched_batch_is_not_silently_merged(self):
        self.assertEqual(submit_review(self.results, self.folder, self.decision("0001", "SUPPLIER"))[1], 200)
        rows = read_csv(self.results)
        rows[0]["decision_rationale"] += " Changed externally."
        with self.results.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        self.assertIn("error", get_review_data(self.results, self.folder))

    def test_local_http_review_to_dashboard_flow_and_origin_guard(self):
        with patch.object(app.state, "results_file", self.results), patch.object(app.state, "output_dir", self.folder):
            with TestClient(app, base_url="http://127.0.0.1:8765") as client:
                for path in ("/", "/dashboard", "/app.js", "/dashboard.js", "/style.css"):
                    self.assertEqual(client.get(path).status_code, 200)
                self.assertEqual(client.get("/api/dashboard").json()["counts"]["total"], 0)
                decision = self.decision("0003", "SUPPLIER").model_dump()
                self.assertEqual(client.post("/api/review", json=decision).status_code, 403)
                self.assertEqual(client.post("/api/review", json=decision, headers={"Origin": "https://other.example"}).status_code, 403)
                response = client.post("/api/review", json=decision, headers={"Origin": "http://127.0.0.1:8765"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.get("/api/review").json()["counts"]["pending"], 4)
                self.assertEqual(client.get("/api/dashboard").json()["counts"]["SUPPLIER"], 1)
                self.assertEqual(client.post("/api/review", json=decision, headers={"Origin": "http://127.0.0.1:8765"}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
