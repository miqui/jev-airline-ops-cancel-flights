# jev-ops

Decide flight cancellations using TypeSafe's Jev decision model, reached via
OpenRouter's Decisions API. Stdlib-only, `uv`-managed CLI.

## What it is

Jev (`typesafe/jev-1.13`) is a "System One" decision model: it does not
generate text. You send it a `state` (nested JSON facts about a flight) plus
typed `questions`, and it returns typed answers. This tool sends one request
per flight, mixing all three Jev primitives in parallel:

- **Noul** (yes/no probability + confidence): `crew_shortage`,
  `maintenance_blocked`, `severe_weather` — three atomic, independent checks.
- **Choice** (categorical + probabilities + confidence): `recommended_action`
  — operate / delay / cancel.
- **Score** (0-3 rubric + confidence): `operational_risk`.

## Design

```
CSV row --> build_state() --> Jev (3 noul + 1 choice + 1 score, parallel)
                                      |
                                      v
                              answers dict
                                      |
                                      v
                  compose.py: composite = 0.25*crew_shortage
                                        + 0.35*maintenance_blocked
                                        + 0.40*severe_weather
                                      |
                     composite >= threshold OR choice == cancel -> cancel
                     composite >= 0.4                            -> review
                     else                                        -> operate
                     any confidence < 0.7                         -> review flag
                                      |
                                      v
                           results.csv / results.json
```

Deterministic composition logic (weights, thresholds, confidence gating)
lives in code (`compose.py`, `questions.py`), never in the model. Jev only
answers atomic, independent sub-questions; this keeps the reasoning
auditable and the model calls parallelizable.

Weights: `CREW_WEIGHT=0.25`, `MAINT_WEIGHT=0.35`, `WEATHER_WEIGHT=0.40`
(defined in `src/jev_ops/questions.py`).

Decision bands: `cancel` if composite >= `--threshold` (default 0.7) or the
model's own `recommended_action` is `cancel`; `review` if composite is in
`[0.4, threshold)`; otherwise `operate`.

Confidence contract: **noul answers never carry a `confidence` field** — per
the Jev/OpenRouter API, a noul answer is only `{"type": "noul", "noul":
<float>}`. That is expected, not an error, and missing noul confidence never
appears in the `errors` column and never forces review on its own. Only
`choice` and `score` answers carry `confidence`. The flight-level
`confidence` column is the `recommended_action` choice answer's confidence,
falling back to the `operational_risk` score answer's confidence if the
choice confidence is missing, and left blank only if neither is present.

A flight is flagged for human `review` when the composite lands in the
`[0.4, threshold)` band, **or** when a flight-level confidence is present
and below 0.7 — low-confidence answers get a human, not a guess. A blank
confidence never forces review by itself.

## Run manually

```bash
uv sync

# Generate a synthetic flight schedule (deterministic given the seed)
uv run jev-ops generate --out data/flights.csv --count 40 --seed 42

# Decide offline, no API key or network needed
uv run jev-ops decide --in data/flights.csv --out results.csv --dry-run

# Decide for real against OpenRouter (requires OPENROUTER_API_KEY)
export OPENROUTER_API_KEY=sk-or-...
uv run jev-ops decide --in data/flights.csv --out results.csv \
    --model typesafe/jev-1.13 --threshold 0.7

# JSON output instead of CSV
uv run jev-ops decide --in data/flights.csv --out results.json --format json --dry-run
```

Expected `results.csv` columns:

```
flight_no,decision,cancel,cancel_probability,crew_shortage,maintenance_blocked,
severe_weather,recommended_action,operational_risk,confidence,review,provider,errors
```

`decision` is one of `operate` / `review` / `cancel`; `cancel` is `yes`/`no`;
`cancel_probability` is the composite score in [0, 1].

## Testing

```bash
uv run ruff check .
uv run ruff format --check .
uv run python -m unittest discover -s tests -v
```

All tests run offline: `DryRunProvider` derives deterministic answers
directly from each CSV row (no network, no API key). `OpenRouterProvider`
is exercised only against a mocked `urllib.request.urlopen` that asserts
request shape (URL, `Authorization` header, model, question keys) — the
real network path is never hit in CI.

## CI

`.github/workflows/ci.yml` runs two jobs: `lint` (ruff check + format
check) and `test` (needs: lint; runs the unittest suite). Both are keyless —
no `OPENROUTER_API_KEY` is ever required in CI.
