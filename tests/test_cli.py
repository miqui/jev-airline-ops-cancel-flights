import csv
import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
