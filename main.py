#!/usr/bin/env python3
"""CLI entry point: rate LinkedIn prospect activity as GREEN / ORANGE / RED.

Usage:
    python main.py --input examples/sample_input.csv --output results.csv
    python main.py --input prospects.csv --output results.csv --no-claude
"""

from __future__ import annotations

import argparse
from collections import Counter

from linkedin_activity_rank.pipeline import run
from linkedin_activity_rank.schema import Rating

RATING_LABEL = {
    Rating.GREEN: "GREEN  (active)",
    Rating.ORANGE: "ORANGE (sort of active)",
    Rating.RED: "RED    (not active)",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input CSV of prospects")
    parser.add_argument("--output", required=True, help="Output CSV with ratings")
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Disable Claude fallback; ambiguous/underspecified rows default to RED",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the Claude model used for fallback rating (default: claude-sonnet-5, or $CLAUDE_MODEL)",
    )
    args = parser.parse_args()

    results = run(
        args.input,
        args.output,
        use_claude=not args.no_claude,
        model=args.model,
    )

    counts = Counter(result.rating for _, result in results)
    print(f"Rated {len(results)} profiles -> {args.output}\n")
    for rating in (Rating.GREEN, Rating.ORANGE, Rating.RED):
        print(f"  {RATING_LABEL[rating]}: {counts.get(rating, 0)}")


if __name__ == "__main__":
    main()
