import json
import tempfile
import unittest
from pathlib import Path

from jev_ops.output import write_csv, write_json

SAMPLE_RESULTS = [
    {
        "flight_no": "JV100",
        "decision": "operate",
        "cancel": "no",
        "cancel_probability": 0.05,
        "crew_shortage": 0.05,
        "maintenance_blocked": 0.05,
        "severe_weather": 0.05,
        "recommended_action": "operate",
        "operational_risk": 0.0,
        "confidence": 0.9,
        "review": "no",
        "provider": "dry-run",
        "errors": "",
    }
]


class TestOutput(unittest.TestCase):
    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.csv"
            write_csv(path, SAMPLE_RESULTS)
            content = path.read_text()
            self.assertIn("flight_no", content)
            self.assertIn("JV100", content)

    def test_json_format(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.json"
            write_json(path, SAMPLE_RESULTS)
            data = json.loads(path.read_text())
            self.assertEqual(data, SAMPLE_RESULTS)


if __name__ == "__main__":
    unittest.main()
