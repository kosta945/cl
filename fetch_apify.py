#!/usr/bin/env python3
"""Fetch LinkedIn profile activity data via the Apify actor
`bovi/linkedin-profile-scraper` and write it out as a CSV in the schema
`main.py` expects.

Usage:
    export APIFY_API_TOKEN=apify_api_...
    python fetch_apify.py --urls urls.txt --output prospects.csv
    python main.py --input prospects.csv --output results.csv

`urls.txt` is one LinkedIn profile URL per line. You can also pass an
existing CSV that already has a `profile_url` column (e.g. one exported
from a CRM) with --input instead of --urls.

NOTE: the mapping from the actor's raw response fields to
last_post_date / posts_last_30d / comments_or_likes_last_30d is a
best-effort guess (see linkedin_activity_rank/apify_source.py docstring) —
this session couldn't reach apify.com to confirm the actor's exact output
schema. Run with --dump-raw once and check examples/apify_raw_sample.json
against what fields are actually present; adjust the candidate key lists
in apify_source.py if extraction comes up empty. Even if it does, the full
raw item is preserved in the `notes` column so nothing is lost.
"""

from __future__ import annotations

import argparse
import csv
import json

from linkedin_activity_rank.apify_source import fetch_profiles_from_apify, normalize_apify_item
from linkedin_activity_rank.schema import INPUT_COLUMNS


def _read_urls(urls_path: str | None, input_csv_path: str | None) -> list[str]:
    if urls_path:
        with open(urls_path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    with open(input_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row["profile_url"].strip() for row in reader if row.get("profile_url", "").strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--urls", help="Text file of LinkedIn profile URLs, one per line")
    parser.add_argument("--input", help="CSV with a profile_url column, instead of --urls")
    parser.add_argument("--output", required=True, help="Where to write the enriched CSV")
    parser.add_argument("--actor-id", default="bovi/linkedin-profile-scraper")
    parser.add_argument(
        "--dump-raw",
        help="Also write the unmodified Apify response items to this JSON file, for verifying field names",
    )
    args = parser.parse_args()

    if not args.urls and not args.input:
        parser.error("pass either --urls or --input")

    urls = _read_urls(args.urls, args.input)
    print(f"Fetching {len(urls)} profiles from Apify actor {args.actor_id}...")
    try:
        raw_items = fetch_profiles_from_apify(urls, actor_id=args.actor_id)
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"Got {len(raw_items)} results.")

    if args.dump_raw:
        with open(args.dump_raw, "w", encoding="utf-8") as f:
            json.dump(raw_items, f, indent=2, default=str)
        print(f"Raw Apify response written to {args.dump_raw}")

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INPUT_COLUMNS)
        writer.writeheader()
        for item in raw_items:
            writer.writerow(normalize_apify_item(item))
    print(f"Enriched CSV written to {args.output}")


if __name__ == "__main__":
    main()
