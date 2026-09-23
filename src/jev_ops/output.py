"""CSV and JSON writers for composed decision results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

FIELDNAMES = [
    "flight_no",
    "decision",
    "cancel",
    "cancel_probability",
    "crew_shortage",
    "maintenance_blocked",
    "severe_weather",
    "recommended_action",
    "operational_risk",
    "confidence",
    "review",
    "provider",
    "errors",
]


def write_csv(path: str | Path, results: list[dict]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    return out_path


def write_json(path: str | Path, results: list[dict]) -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)
    return out_path


def write_results(path: str | Path, results: list[dict], fmt: str = "csv") -> Path:
    if fmt == "json":
        return write_json(path, results)
    if fmt == "csv":
        return write_csv(path, results)
    raise ValueError(f"Unknown format: {fmt}")
