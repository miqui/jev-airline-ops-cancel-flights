import csv
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from jev_ops.cli import main


class TestCli(unittest.TestCase):
    def test_generate_then_decide_dry_run_csv(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.csv"

            rc = main(["generate", "--out", str(flights_path), "--count", "15", "--seed", "42"])
            self.assertEqual(rc, 0)
            self.assertTrue(flights_path.exists())

            rc = main(
                [
                    "decide",
                    "--in",
                    str(flights_path),
                    "--out",
                    str(results_path),
                    "--dry-run",
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue(results_path.exists())

            with results_path.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 15)
            for row in rows:
                self.assertIn(row["decision"], {"operate", "review", "cancel"})
                self.assertEqual(row["provider"], "dry-run")

    def test_decide_dry_run_json_format(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.json"

            main(["generate", "--out", str(flights_path), "--count", "5", "--seed", "1"])
            rc = main(
                [
                    "decide",
                    "--in",
                    str(flights_path),
                    "--out",
                    str(results_path),
                    "--format",
                    "json",
                    "--dry-run",
                ]
            )
            self.assertEqual(rc, 0)
            data = json.loads(results_path.read_text())
            self.assertEqual(len(data), 5)

    def test_decide_log_questions(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.csv"

            main(["generate", "--out", str(flights_path), "--count", "5", "--seed", "1"])
            orig_cwd = os.getcwd()
            try:
                os.chdir(d)
                rc = main(
                    [
                        "decide",
                        "--in",
                        str(flights_path),
                        "--out",
                        str(results_path),
                        "--dry-run",
                        "--log-questions",
                    ]
                )
                self.assertEqual(rc, 0)
                log_file = Path("questions-log.json")
                self.assertTrue(log_file.exists())
                data = json.loads(log_file.read_text())
                self.assertIn("crew_shortage", data)
                self.assertIn("maintenance_blocked", data)
                self.assertIn("severe_weather", data)
                self.assertIn("recommended_action", data)
                self.assertIn("operational_risk", data)
            finally:
                os.chdir(orig_cwd)

    def test_decide_questions_log_alias(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.csv"

            main(["generate", "--out", str(flights_path), "--count", "5", "--seed", "1"])
            orig_cwd = os.getcwd()
            try:
                os.chdir(d)
                rc = main(
                    [
                        "decide",
                        "--in",
                        str(flights_path),
                        "--out",
                        str(results_path),
                        "--dry-run",
                        "--questions-log",
                    ]
                )
                self.assertEqual(rc, 0)
                log_file = Path("questions-log.json")
                self.assertTrue(log_file.exists())
            finally:
                os.chdir(orig_cwd)

    def test_decide_log_questions_custom_path(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.csv"
            log_path = Path(d) / "my-questions.json"

            main(["generate", "--out", str(flights_path), "--count", "5", "--seed", "1"])
            orig_cwd = os.getcwd()
            try:
                os.chdir(d)
                rc = main(
                    [
                        "decide",
                        "--in",
                        str(flights_path),
                        "--out",
                        str(results_path),
                        "--dry-run",
                        "--log-questions",
                        str(log_path),
                    ]
                )
                self.assertEqual(rc, 0)
                self.assertTrue(log_path.exists())
                self.assertIn("crew_shortage", json.loads(log_path.read_text()))
                self.assertFalse(Path("questions-log.json").exists())
            finally:
                os.chdir(orig_cwd)

    def test_decide_without_log_questions(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.csv"

            main(["generate", "--out", str(flights_path), "--count", "5", "--seed", "1"])
            orig_cwd = os.getcwd()
            try:
                os.chdir(d)
                rc = main(
                    [
                        "decide",
                        "--in",
                        str(flights_path),
                        "--out",
                        str(results_path),
                        "--dry-run",
                    ]
                )
                self.assertEqual(rc, 0)
                self.assertFalse(Path("questions-log.json").exists())
            finally:
                os.chdir(orig_cwd)

    def test_decide_missing_input_file(self):
        with tempfile.TemporaryDirectory() as d:
            missing_path = Path(d) / "does-not-exist.csv"
            results_path = Path(d) / "results.csv"

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(
                    [
                        "decide",
                        "--in",
                        str(missing_path),
                        "--out",
                        str(results_path),
                        "--dry-run",
                    ]
                )
            self.assertEqual(rc, 1)
            self.assertIn("input file not found", stderr.getvalue())
            self.assertFalse(results_path.exists())

    def test_decide_malformed_row_does_not_abort_batch(self):
        with tempfile.TemporaryDirectory() as d:
            flights_path = Path(d) / "flights.csv"
            results_path = Path(d) / "results.csv"

            main(["generate", "--out", str(flights_path), "--count", "5", "--seed", "1"])
            with flights_path.open() as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)
            rows[2]["crew_minutes_remaining"] = "not-a-number"
            with flights_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(
                    [
                        "decide",
                        "--in",
                        str(flights_path),
                        "--out",
                        str(results_path),
                        "--dry-run",
                    ]
                )
            self.assertEqual(rc, 1)
            self.assertIn(f"error: flight {rows[2]['flight_no']}", stderr.getvalue())

            with results_path.open() as f:
                results = list(csv.DictReader(f))
            self.assertEqual(len(results), 5)
            bad_row = results[2]
            self.assertEqual(bad_row["decision"], "error")
            self.assertEqual(bad_row["review"], "yes")
            self.assertNotEqual(bad_row["errors"], "")
            good_rows = [r for i, r in enumerate(results) if i != 2]
            for row in good_rows:
                self.assertNotEqual(row["decision"], "error")
                self.assertEqual(row["errors"], "")


if __name__ == "__main__":
    unittest.main()
