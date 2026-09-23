import json
import ssl
import unittest
import unittest.mock as mock

from jev_ops.providers import DryRunProvider, OpenRouterProvider, ProviderError
from jev_ops.questions import build_questions, build_state

ROW_NORMAL = {
    "flight_no": "JV100",
    "origin": "JFK",
    "dest": "BOS",
    "scheduled_departure": "2026-03-01T08:00:00",
    "aircraft_type": "A320",
    "crew_minutes_remaining": "180",
    "maintenance_remarks": "",
    "weather_remarks": "",
    "load_factor": "0.7",
}

ROW_CREW_TIMEOUT = dict(ROW_NORMAL, crew_minutes_remaining="10")
ROW_MAINT = dict(ROW_NORMAL, maintenance_remarks="AOG - aircraft on ground")
ROW_WEATHER = dict(ROW_NORMAL, weather_remarks="severe thunderstorms in departure corridor")


class TestDryRunProvider(unittest.TestCase):
    def setUp(self):
        self.provider = DryRunProvider()
        self.questions = build_questions()

    def test_deterministic(self):
        state = build_state(ROW_NORMAL)
        a1 = self.provider.decide(ROW_NORMAL, state, self.questions, "typesafe/jev-1.13")
        a2 = self.provider.decide(ROW_NORMAL, state, self.questions, "typesafe/jev-1.13")
        self.assertEqual(a1, a2)

    def test_normal_flight_operates(self):
        state = build_state(ROW_NORMAL)
        answers = self.provider.decide(ROW_NORMAL, state, self.questions, "m")
        self.assertLess(answers["crew_shortage"]["noul"], 0.5)
        self.assertLess(answers["maintenance_blocked"]["noul"], 0.5)
        self.assertLess(answers["severe_weather"]["noul"], 0.5)
        self.assertEqual(answers["recommended_action"]["choice"], "operate")

    def test_crew_timeout_detected(self):
        state = build_state(ROW_CREW_TIMEOUT)
        answers = self.provider.decide(ROW_CREW_TIMEOUT, state, self.questions, "m")
        self.assertGreaterEqual(answers["crew_shortage"]["noul"], 0.5)

    def test_maintenance_keyword_detected(self):
        state = build_state(ROW_MAINT)
        answers = self.provider.decide(ROW_MAINT, state, self.questions, "m")
        self.assertGreaterEqual(answers["maintenance_blocked"]["noul"], 0.5)

    def test_weather_keyword_detected(self):
        state = build_state(ROW_WEATHER)
        answers = self.provider.decide(ROW_WEATHER, state, self.questions, "m")
        self.assertGreaterEqual(answers["severe_weather"]["noul"], 0.5)


class TestOpenRouterProvider(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ProviderError):
                OpenRouterProvider()

    def test_request_shape_mocked(self):
        questions = build_questions()
        state = build_state(ROW_NORMAL)

        fake_response_body = json.dumps(
            {
                "decision": {
                    "answers": {
                        "crew_shortage": {"noul": 0.1, "confidence": 0.9},
                        "maintenance_blocked": {"noul": 0.1, "confidence": 0.9},
                        "severe_weather": {"noul": 0.1, "confidence": 0.9},
                        "recommended_action": {
                            "choice": "operate",
                            "probabilities": {"operate": 0.8, "delay": 0.1, "cancel": 0.1},
                            "confidence": 0.9,
                        },
                        "operational_risk": {
                            "score": 0.0,
                            "probabilities": {"0": 1.0},
                            "confidence": 0.9,
                        },
                    }
                }
            }
        ).encode("utf-8")

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return fake_response_body

        captured = {}

        def fake_urlopen(req, timeout=None, context=None):
            captured["url"] = req.full_url
            captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["context"] = context
            return FakeResp()

        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=True):
            provider = OpenRouterProvider()
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                answers = provider.decide(ROW_NORMAL, state, questions, "typesafe/jev-1.13")

        self.assertEqual(captured["url"], "https://openrouter.ai/api/alpha/decisions")
        self.assertEqual(captured["headers"].get("authorization"), "Bearer test-key")
        self.assertIsInstance(captured["context"], ssl.SSLContext)
        self.assertEqual(captured["body"]["model"], "typesafe/jev-1.13")
        self.assertEqual(set(captured["body"]["questions"].keys()), set(questions.keys()))
        self.assertIn("crew_shortage", answers)
        self.assertEqual(answers["recommended_action"]["choice"], "operate")


if __name__ == "__main__":
    unittest.main()
