"""CLI entrypoint for jev-ops: generate synthetic flights and decide on them."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import compose, output
from .generator import write_flights_csv
from .providers import DryRunProvider, OpenRouterProvider, ProviderError
from .questions import build_questions, build_state

DEFAULT_QUESTIONS_LOG = "questions-log.json"


def _cmd_generate(args: argparse.Namespace) -> int:
    out_path = write_flights_csv(args.out, args.count, args.seed)
    print(f"Wrote {args.count} synthetic flights to {out_path}")
    return 0


def _read_flights(path: str | Path) -> list[dict]:
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def _cmd_decide(args: argparse.Namespace) -> int:
    rows = _read_flights(args.input)

    if args.dry_run:
        provider = DryRunProvider()
    else:
        try:
            provider = OpenRouterProvider()
        except ProviderError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    questions = build_questions()
    if args.log_questions:
        output.write_json(args.log_questions, questions)
    results = []
    for row in rows:
        state = build_state(row)
        try:
            answers = provider.decide(row, state, questions, args.model)
        except ProviderError as e:
            print(f"error: flight {row.get('flight_no')}: {e}", file=sys.stderr)
            return 1
        result = compose.compose_result(row["flight_no"], answers, args.threshold, provider.name)
        results.append(result)

    output.write_results(args.out, results, args.format)
    cancelled = sum(1 for r in results if r["decision"] == "cancel")
    review = sum(1 for r in results if r["review"] == "yes")
    summary = (
        f"Decided {len(results)} flights -> {cancelled} cancel, "
        f"{review} flagged for review. Wrote {args.out}"
    )
    if args.log_questions:
        summary += f", questions to {args.log_questions}"
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-ops", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Generate a synthetic flight schedule CSV")
    p_gen.add_argument("--out", default="data/flights.csv")
    p_gen.add_argument("--count", type=int, default=40)
    p_gen.add_argument("--seed", type=int, default=42)
    p_gen.set_defaults(func=_cmd_generate)

    p_dec = sub.add_parser("decide", help="Decide cancellations for a flight schedule")
    p_dec.add_argument("--in", dest="input", required=True)
    p_dec.add_argument("--out", default="results.csv")
    p_dec.add_argument("--format", choices=["csv", "json"], default="csv")
    p_dec.add_argument("--model", default="typesafe/jev-1.13")
    p_dec.add_argument("--threshold", type=float, default=0.7)
    p_dec.add_argument("--dry-run", action="store_true")
    p_dec.add_argument(
        "--log-questions",
        "--questions-log",
        nargs="?",
        const=DEFAULT_QUESTIONS_LOG,
        default=None,
        metavar="PATH",
        help=f"Log questions to PATH (default: {DEFAULT_QUESTIONS_LOG})",
    )
    p_dec.set_defaults(func=_cmd_decide)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
