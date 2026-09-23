"""Deterministic synthetic flight schedule generator."""

from __future__ import annotations

import csv
import random
from pathlib import Path

FIELDNAMES = [
    "flight_no",
    "origin",
    "dest",
    "scheduled_departure",
    "aircraft_type",
    "crew_minutes_remaining",
    "maintenance_remarks",
    "weather_remarks",
    "load_factor",
]

AIRPORTS = ["JFK", "BOS", "ORD", "DEN", "SFO", "ATL", "MIA", "LAX", "SEA", "DFW"]
AIRCRAFT = ["A320", "B738", "A321", "E175", "B739", "CRJ900"]

WEATHER_REMARKS = [
    "severe thunderstorms in departure corridor",
    "dense fog, visibility below minimums",
    "heavy snow and icing conditions",
    "high crosswinds exceeding limits",
]

MAINT_REMARKS = [
    "deferred MEL item pending parts",
    "AOG - aircraft on ground",
    "hydraulic leak reported by inbound crew",
    "APU inoperative, ground power required",
]

TURNAROUND_MINIMUM = 45


def _crew_minutes(rng: random.Random, shortage: bool) -> int:
    if shortage:
        return rng.randint(0, TURNAROUND_MINIMUM - 1)
    return rng.randint(TURNAROUND_MINIMUM, 240)


def generate_flights(count: int, seed: int) -> list[dict]:
    """Generate a deterministic list of synthetic flight rows for a given seed."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for i in range(count):
        flight_no = f"JV{100 + i}"
        origin, dest = rng.sample(AIRPORTS, 2)
        hour = rng.randint(5, 22)
        minute = rng.choice([0, 15, 30, 45])
        scheduled_departure = f"2026-03-{(i % 28) + 1:02d}T{hour:02d}:{minute:02d}:00"
        aircraft_type = rng.choice(AIRCRAFT)
        load_factor = round(rng.uniform(0.45, 0.99), 2)

        roll = rng.random()
        weather_remarks = ""
        maintenance_remarks = ""
        if roll < 0.60:
            # normal routine flight
            crew_minutes_remaining = _crew_minutes(rng, shortage=False)
        elif roll < 0.72:
            # weather event
            crew_minutes_remaining = _crew_minutes(rng, shortage=False)
            weather_remarks = rng.choice(WEATHER_REMARKS)
        elif roll < 0.84:
            # crew timeout
            crew_minutes_remaining = _crew_minutes(rng, shortage=True)
        elif roll < 0.94:
            # maintenance issue
            crew_minutes_remaining = _crew_minutes(rng, shortage=False)
            maintenance_remarks = rng.choice(MAINT_REMARKS)
        else:
            # mixed / ambiguous: combination of factors
            crew_minutes_remaining = _crew_minutes(rng, shortage=rng.random() < 0.5)
            if rng.random() < 0.5:
                weather_remarks = rng.choice(WEATHER_REMARKS)
            if rng.random() < 0.5:
                maintenance_remarks = rng.choice(MAINT_REMARKS)

        rows.append(
            {
                "flight_no": flight_no,
                "origin": origin,
                "dest": dest,
                "scheduled_departure": scheduled_departure,
                "aircraft_type": aircraft_type,
                "crew_minutes_remaining": crew_minutes_remaining,
                "maintenance_remarks": maintenance_remarks,
                "weather_remarks": weather_remarks,
                "load_factor": load_factor,
            }
        )
    return rows


def write_flights_csv(path: str | Path, count: int, seed: int) -> Path:
    rows = generate_flights(count, seed)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return out_path
