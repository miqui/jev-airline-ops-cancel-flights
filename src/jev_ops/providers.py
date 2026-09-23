"""Decision providers: a network-free deterministic dry-run provider and a
real OpenRouter-backed provider for TypeSafe's Jev decision model."""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Protocol

import certifi

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"

# Some Python installs (notably python.org builds on macOS) ship without a
# usable system CA bundle, so verify TLS against certifi explicitly.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

WEATHER_KEYWORDS = ["thunderstorm", "fog", "snow", "icing", "crosswind"]
MAINT_KEYWORDS = ["aog", "mel", "hydraulic", "inoperative", "leak"]

TURNAROUND_MINIMUM = 45


class DecisionProvider(Protocol):
    name: str

    def decide(self, row: dict, state: dict, questions: dict, model: str) -> dict:
        """Return a dict of answers keyed by question name."""
        ...


class ProviderError(RuntimeError):
    pass


def _keyword_noul(text: str, keywords: list[str]) -> float:
    text_l = (text or "").lower()
    return 0.9 if any(k in text_l for k in keywords) else 0.05


class DryRunProvider:
    """Deterministic, offline decision provider derived directly from the row.

    No network calls, no API key required. Used for --dry-run and tests.
    """

    name = "dry-run"

    def decide(self, row: dict, state: dict, questions: dict, model: str) -> dict:
        crew_minutes = int(row["crew_minutes_remaining"])
        maintenance_remarks = row.get("maintenance_remarks", "") or ""
        weather_remarks = row.get("weather_remarks", "") or ""

        crew_noul = 0.95 if crew_minutes < TURNAROUND_MINIMUM else 0.05
        maint_noul = _keyword_noul(maintenance_remarks, MAINT_KEYWORDS)
        weather_noul = _keyword_noul(weather_remarks, WEATHER_KEYWORDS)

        blockers = sum(1 for v in (crew_noul, maint_noul, weather_noul) if v >= 0.5)
        if blockers >= 2:
            choice = "cancel"
            risk = 3.0
        elif blockers == 1:
            choice = "delay"
            risk = 2.0
        else:
            choice = "operate"
            risk = 0.0

        def choice_probs(pick: str) -> dict:
            base = {"operate": 0.1, "delay": 0.1, "cancel": 0.1}
            base[pick] = 0.8
            return base

        return {
            "crew_shortage": {
                "noul": crew_noul,
                "confidence": 0.9,
            },
            "maintenance_blocked": {
                "noul": maint_noul,
                "confidence": 0.9,
            },
            "severe_weather": {
                "noul": weather_noul,
                "confidence": 0.9,
            },
            "recommended_action": {
                "choice": choice,
                "probabilities": choice_probs(choice),
                "confidence": 0.9,
            },
            "operational_risk": {
                "score": risk,
                "probabilities": {str(i): (1.0 if i == int(risk) else 0.0) for i in range(4)},
                "confidence": 0.9,
            },
        }


class OpenRouterProvider:
    """Calls OpenRouter's Decisions API to run Jev (typesafe/jev-1.13)."""

    name = "openrouter"

    def __init__(self, api_key: str | None = None, max_retries: int = 2, timeout: float = 30.0):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ProviderError(
                "OPENROUTER_API_KEY is not set. Export it in your environment "
                "or use --dry-run to run without the network."
            )
        self.max_retries = max_retries
        self.timeout = timeout

    def decide(self, row: dict, state: dict, questions: dict, model: str) -> dict:
        body = json.dumps({"model": model, "state": state, "questions": questions}).encode("utf-8")
        req = urllib.request.Request(
            DECISIONS_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        attempt = 0
        while True:
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=SSL_CONTEXT) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    decision = payload.get("decision", payload)
                    return decision.get("answers", {})
            except urllib.error.HTTPError as e:
                resp_body = e.read().decode("utf-8", errors="replace")
                if e.code in (429,) or e.code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(2**attempt)
                        attempt += 1
                        continue
                    raise ProviderError(
                        f"OpenRouter request failed after retries: HTTP {e.code}: {resp_body}"
                    ) from e
                raise ProviderError(f"OpenRouter request failed: HTTP {e.code}: {resp_body}") from e
            except urllib.error.URLError as e:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    attempt += 1
                    continue
                raise ProviderError(f"OpenRouter request failed: {e}") from e
