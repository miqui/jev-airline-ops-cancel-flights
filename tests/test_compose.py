import unittest

from jev_ops.compose import compose_result
from jev_ops.questions import CREW_WEIGHT, MAINT_WEIGHT, WEATHER_WEIGHT


def make_answers(
    crew=0.0,
    maint=0.0,
    weather=0.0,
    choice="operate",
    risk=0.0,
    action_confidence: float | None = 0.9,
    risk_confidence: float | None = 0.9,
):
    """Noul answers never carry confidence per the API contract; only choice
    and score answers do."""
    answers = {
        "crew_shortage": {"noul": crew},
        "maintenance_blocked": {"noul": maint},
        "severe_weather": {"noul": weather},
        "recommended_action": {
            "choice": choice,
            "probabilities": {"operate": 0.8, "delay": 0.1, "cancel": 0.1},
        },
        "operational_risk": {
            "score": risk,
            "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0, "3": 0.0},
        },
    }
    if action_confidence is not None:
        answers["recommended_action"]["confidence"] = action_confidence
    if risk_confidence is not None:
        answers["operational_risk"]["confidence"] = risk_confidence
    return answers


class TestCompose(unittest.TestCase):
    def test_weights_math(self):
        answers = make_answers(crew=0.8, maint=0.6, weather=0.2)
        expected = CREW_WEIGHT * 0.8 + MAINT_WEIGHT * 0.6 + WEATHER_WEIGHT * 0.2
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertAlmostEqual(result["cancel_probability"], round(expected, 4))

    def test_operate_band(self):
        answers = make_answers(crew=0.0, maint=0.0, weather=0.0)
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["decision"], "operate")
        self.assertEqual(result["cancel"], "no")

    def test_review_band(self):
        # composite between 0.4 and threshold(0.7)
        answers = make_answers(crew=0.0, maint=1.0, weather=0.3)
        composite = MAINT_WEIGHT * 1.0 + WEATHER_WEIGHT * 0.3
        self.assertGreaterEqual(composite, 0.4)
        self.assertLess(composite, 0.7)
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["cancel"], "no")

    def test_cancel_band_by_composite(self):
        answers = make_answers(crew=1.0, maint=1.0, weather=1.0)
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["decision"], "cancel")
        self.assertEqual(result["cancel"], "yes")

    def test_cancel_forced_by_recommended_action(self):
        # low composite but model explicitly recommends cancel
        answers = make_answers(crew=0.0, maint=0.0, weather=0.0, choice="cancel")
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["decision"], "cancel")

    def test_high_choice_confidence_in_review_band_not_flagged_twice(self):
        # composite 0.4065 (review band), choice confidence 0.72 (>= gate) ->
        # review is driven by the band alone, not the confidence gate, and
        # stays "yes" because decision == review; confidence reports 0.72.
        answers = make_answers(
            crew=0.0, maint=1.0, weather=0.14125, choice="operate", action_confidence=0.72
        )
        composite = MAINT_WEIGHT * 1.0 + WEATHER_WEIGHT * 0.14125
        self.assertAlmostEqual(round(composite, 4), 0.4065)
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["cancel_probability"], 0.4065)
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["review"], "yes")
        self.assertEqual(result["confidence"], 0.72)

    def test_operate_band_with_high_choice_confidence_not_flagged(self):
        # composite below the review band and choice confidence 0.72 (>= gate)
        # -> no review flag at all.
        answers = make_answers(
            crew=0.0, maint=0.0, weather=0.0, choice="operate", action_confidence=0.72
        )
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["decision"], "operate")
        self.assertEqual(result["review"], "no")
        self.assertEqual(result["confidence"], 0.72)

    def test_low_choice_confidence_flags_review(self):
        # composite below the review band but choice confidence 0.5 (< gate)
        # -> flagged for review purely on confidence.
        answers = make_answers(
            crew=0.0, maint=0.0, weather=0.0, choice="operate", action_confidence=0.5
        )
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["decision"], "operate")
        self.assertEqual(result["review"], "yes")
        self.assertEqual(result["confidence"], 0.5)

    def test_missing_choice_confidence_falls_back_to_score_confidence(self):
        answers = make_answers(
            crew=0.0, maint=0.0, weather=0.0, action_confidence=None, risk_confidence=0.55
        )
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["confidence"], 0.55)
        self.assertEqual(result["review"], "yes")

    def test_no_choice_or_score_confidence_leaves_confidence_blank(self):
        # Neither choice nor score confidence present -> confidence blank,
        # and review is decided solely by the composite band (here: operate).
        answers = make_answers(
            crew=0.0, maint=0.0, weather=0.0, action_confidence=None, risk_confidence=None
        )
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["confidence"], "")
        self.assertEqual(result["decision"], "operate")
        self.assertEqual(result["review"], "no")

    def test_missing_noul_confidence_not_an_error_and_not_flagged(self):
        # Noul answers never carry confidence by API contract - missing
        # confidence there must not appear in errors nor force review.
        answers = make_answers(crew=0.0, maint=0.0, weather=0.0)
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertEqual(result["errors"], "")
        self.assertEqual(result["review"], "no")

    def test_missing_fields_recorded_as_error_not_crash(self):
        answers = {
            "crew_shortage": {},
            "maintenance_blocked": {"noul": 0.1},
            "severe_weather": {"noul": 0.1},
            "recommended_action": {},
            "operational_risk": {},
        }
        result = compose_result("JV100", answers, threshold=0.7, provider_name="dry-run")
        self.assertIn("errors", result)
        self.assertNotEqual(result["errors"], "")
        self.assertEqual(result["decision"], "operate")


if __name__ == "__main__":
    unittest.main()
