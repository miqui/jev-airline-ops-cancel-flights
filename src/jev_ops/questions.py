"""Builds the per-flight `state` payload and the fixed Jev questions dict.

Weights for the composite score used at composition time (see compose.py).
"""

from __future__ import annotations

CREW_WEIGHT = 0.25
MAINT_WEIGHT = 0.35
WEATHER_WEIGHT = 0.40

TURNAROUND_MINIMUM = 45


def build_state(row: dict) -> dict:
    """Subset of CSV fields, nested, containing only what the questions need."""
    return {
        "flight": {
            "flight_no": row["flight_no"],
            "origin": row["origin"],
            "dest": row["dest"],
            "scheduled_departure": row["scheduled_departure"],
            "aircraft_type": row["aircraft_type"],
            "crew_minutes_remaining": int(row["crew_minutes_remaining"]),
            "load_factor": float(row["load_factor"]),
            "turnaround_minimum": TURNAROUND_MINIMUM,
        },
        "maintenance": {
            "remarks": row.get("maintenance_remarks", "") or "",
        },
        "weather": {
            "remarks": row.get("weather_remarks", "") or "",
        },
    }


def build_questions() -> dict:
    """Fixed question set: 3 noul, 1 choice, 1 score - evaluated in parallel."""
    return {
        "crew_shortage": {
            "type": "noul",
            "instructions": (
                "Is the flight crew at risk of exceeding duty limits before "
                "departure, given `flight.crew_minutes_remaining` compared "
                "against `flight.turnaround_minimum`?"
            ),
            "criteria": {
                "true": {
                    "what": (
                        "Remaining crew duty minutes are at or below the "
                        "turnaround minimum, meaning the crew cannot legally "
                        "operate the flight without a timeout or reassignment."
                    ),
                    "not_for": (
                        "Crew has a healthy buffer of duty minutes well above "
                        "the turnaround minimum."
                    ),
                    "examples": [
                        "crew_minutes_remaining=10, turnaround_minimum=45",
                        "crew_minutes_remaining=0, turnaround_minimum=45",
                    ],
                },
                "false": {
                    "what": (
                        "Remaining crew duty minutes comfortably exceed the turnaround minimum."
                    ),
                    "not_for": "Crew minutes remaining are at or near the minimum.",
                    "examples": [
                        "crew_minutes_remaining=180, turnaround_minimum=45",
                    ],
                },
            },
        },
        "maintenance_blocked": {
            "type": "noul",
            "instructions": (
                "Does `maintenance.remarks` describe an unresolved mechanical "
                "issue that would block safe departure?"
            ),
            "criteria": {
                "true": {
                    "what": (
                        "Remarks describe a grounding condition: AOG, deferred "
                        "MEL item pending parts, hydraulic leak, inoperative "
                        "system required for dispatch."
                    ),
                    "not_for": (
                        "Remarks are empty or describe a fully resolved, "
                        "routine maintenance action with no dispatch impact."
                    ),
                    "examples": [
                        "AOG - aircraft on ground",
                        "hydraulic leak reported by inbound crew",
                        "deferred MEL item pending parts",
                    ],
                },
                "false": {
                    "what": "Remarks are empty or describe no dispatch-blocking issue.",
                    "not_for": (
                        "Remarks mention AOG, MEL holds, leaks, or inoperative required systems."
                    ),
                    "examples": ["", "routine inspection completed, no findings"],
                },
            },
        },
        "severe_weather": {
            "type": "noul",
            "instructions": (
                "Does `weather.remarks` describe weather conditions severe "
                "enough to threaten a safe departure?"
            ),
            "criteria": {
                "true": {
                    "what": (
                        "Remarks describe severe thunderstorms, dense fog "
                        "below minimums, heavy snow/icing, or crosswinds "
                        "exceeding limits."
                    ),
                    "not_for": (
                        "Remarks are empty or describe mild/normal weather "
                        "with no operational impact."
                    ),
                    "examples": [
                        "severe thunderstorms in departure corridor",
                        "dense fog, visibility below minimums",
                        "heavy snow and icing conditions",
                    ],
                },
                "false": {
                    "what": "Remarks are empty or describe benign weather.",
                    "not_for": (
                        "Remarks mention storms, fog below minimums, "
                        "snow/icing, or crosswind limits."
                    ),
                    "examples": ["", "clear skies, light winds"],
                },
            },
        },
        "recommended_action": {
            "type": "choice",
            "instructions": (
                "Given the flight, maintenance, and weather state, what "
                "action should operations take for this flight?"
            ),
            "criteria": {
                "operate": {
                    "what": "Flight can depart as scheduled with no material safety or legal risk.",
                    "not_for": "Any unresolved crew, maintenance, or weather blocker exists.",
                    "examples": ["healthy crew minutes, no remarks, clear weather"],
                },
                "delay": {
                    "what": (
                        "A temporary blocker (e.g. a maintenance fix in "
                        "progress, a passing weather cell, or a crew swap) "
                        "can plausibly resolve before a reasonable delay window."
                    ),
                    "not_for": (
                        "The blocker is open-ended (AOG, no crew available, "
                        "widespread severe weather) with no clear resolution time."
                    ),
                    "examples": [
                        "fog expected to clear within the hour",
                        "MEL item awaiting a part already en route",
                    ],
                },
                "cancel": {
                    "what": (
                        "Blockers are severe, compounding, or open-ended "
                        "enough that departure is not viable this cycle."
                    ),
                    "not_for": "A single minor or resolvable issue exists.",
                    "examples": [
                        "AOG plus crew timeout",
                        "severe thunderstorms with no crew minutes remaining",
                    ],
                },
            },
        },
        "operational_risk": {
            "type": "score",
            "instructions": (
                "On a 0-3 rubric, how severe is the overall operational risk "
                "for this flight considering crew, maintenance, and weather "
                "together?"
            ),
            "criteria": [
                {
                    "level": 0,
                    "what": "Minor, routine operations with no notable risk factors.",
                    "signals": ["no remarks", "healthy crew minutes", "clear weather"],
                },
                {
                    "level": 1,
                    "what": "A single, minor, likely-resolvable risk factor.",
                    "signals": ["mild weather remark", "minor deferred item"],
                },
                {
                    "level": 2,
                    "what": "A single significant risk factor or two moderate ones.",
                    "signals": [
                        "crew near minimum",
                        "one severe weather remark",
                        "one open maintenance issue",
                    ],
                },
                {
                    "level": 3,
                    "what": "Severe, multi-factor disruption with compounding risk.",
                    "signals": [
                        "crew timeout combined with AOG or severe weather",
                        "multiple simultaneous blockers",
                    ],
                },
            ],
        },
    }
