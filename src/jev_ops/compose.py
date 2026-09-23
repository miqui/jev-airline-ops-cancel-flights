"""Composition of Jev answers into a final cancellation decision.

Deterministic logic lives here in code; the model only answers atomic
questions. Parse defensively so a missing field records an error for that
flight instead of crashing the whole run.

Confidence contract (per the Jev/OpenRouter API): noul answers never carry a
confidence field - that is expected, not an error. Only choice and score
answers carry `confidence`. Flight-level confidence is taken from the
`recommended_action` choice answer, falling back to the `operational_risk`
score answer if the choice confidence is missing; it is left blank only if
neither is present.
"""

from __future__ import annotations

from .questions import CREW_WEIGHT, MAINT_WEIGHT, WEATHER_WEIGHT

REVIEW_BAND = 0.4
CONFIDENCE_GATE = 0.7


def _get(d: dict, key: str, default=None):
    try:
        return d.get(key, default)
    except AttributeError:
        return default


def error_result(flight_no: str, message: str, provider_name: str) -> dict:
    """Placeholder result for a flight that failed before answers were composed
    (e.g. a malformed CSV row or an unrecoverable provider error), so one bad
    flight doesn't abort the whole batch."""
    return {
        "flight_no": flight_no,
        "decision": "error",
        "cancel": "no",
        "cancel_probability": "",
        "crew_shortage": "",
        "maintenance_blocked": "",
        "severe_weather": "",
        "recommended_action": "",
        "operational_risk": "",
        "confidence": "",
        "review": "yes",
        "provider": provider_name,
        "errors": message,
    }


def compose_result(flight_no: str, answers: dict, threshold: float, provider_name: str) -> dict:
    errors = []

    def noul(name: str) -> float:
        # Noul answers have no confidence field by API contract - only
        # {"type": "noul", "noul": <float>}. Do not treat that as an error.
        a = _get(answers, name, {}) or {}
        val = _get(a, "noul")
        if val is None:
            errors.append(f"missing noul for {name}")
            val = 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            errors.append(f"non-numeric noul for {name}")
            return 0.0

    crew_shortage = noul("crew_shortage")
    maintenance_blocked = noul("maintenance_blocked")
    severe_weather = noul("severe_weather")

    action_answer = _get(answers, "recommended_action", {}) or {}
    recommended_action = _get(action_answer, "choice")
    action_conf = _get(action_answer, "confidence")
    if recommended_action is None:
        errors.append("missing choice for recommended_action")
        recommended_action = "unknown"
    if action_conf is not None:
        try:
            action_conf = float(action_conf)
        except (TypeError, ValueError):
            errors.append("non-numeric confidence for recommended_action")
            action_conf = None

    risk_answer = _get(answers, "operational_risk", {}) or {}
    operational_risk = _get(risk_answer, "score")
    risk_conf = _get(risk_answer, "confidence")
    if operational_risk is None:
        errors.append("missing score for operational_risk")
        operational_risk = 0.0
    if risk_conf is not None:
        try:
            risk_conf = float(risk_conf)
        except (TypeError, ValueError):
            errors.append("non-numeric confidence for operational_risk")
            risk_conf = None

    try:
        operational_risk = float(operational_risk)
    except (TypeError, ValueError):
        errors.append("non-numeric score for operational_risk")
        operational_risk = 0.0

    # Flight-level confidence: choice confidence first, then score confidence,
    # blank if neither answer carried one.
    flight_confidence = action_conf if action_conf is not None else risk_conf

    composite = (
        CREW_WEIGHT * crew_shortage
        + MAINT_WEIGHT * maintenance_blocked
        + WEATHER_WEIGHT * severe_weather
    )

    if composite >= threshold or recommended_action == "cancel":
        decision = "cancel"
    elif composite >= REVIEW_BAND:
        decision = "review"
    else:
        decision = "operate"

    review = decision == "review" or (
        flight_confidence is not None and flight_confidence < CONFIDENCE_GATE
    )

    return {
        "flight_no": flight_no,
        "decision": decision,
        "cancel": "yes" if decision == "cancel" else "no",
        "cancel_probability": round(composite, 4),
        "crew_shortage": round(crew_shortage, 4),
        "maintenance_blocked": round(maintenance_blocked, 4),
        "severe_weather": round(severe_weather, 4),
        "recommended_action": recommended_action,
        "operational_risk": round(operational_risk, 4),
        "confidence": round(flight_confidence, 4) if flight_confidence is not None else "",
        "review": "yes" if review else "no",
        "provider": provider_name,
        "errors": "; ".join(errors) if errors else "",
    }
