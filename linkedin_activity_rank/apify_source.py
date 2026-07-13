"""Fetch LinkedIn profile data via the Apify actor `bovi/linkedin-profile-scraper`
(https://apify.com/bovi/linkedin-profile-scraper) and normalize it into the
CSV schema the rating pipeline expects.

IMPORTANT — unverified field mapping: this session's network egress policy
blocks apify.com, so the actor's exact input/output field names could not be
confirmed against the live API docs. The call to the actor itself (via the
official `apify-client` SDK, whose interface is stable and well documented
independent of any one actor) is correct. The RAW_ACTIVITY_KEY_CANDIDATES
lists below are a best-effort guess at where recent-activity data might live
in the response. Run `fetch_apify.py` once with `--dump-raw` and check the
output against your own account/actor version; adjust the candidate key
names (or add exact ones) in this file to match what you actually get back.
To hedge against a wrong guess, the full raw item is always preserved in the
`notes` column as JSON, so the Claude fallback can still reason over it even
if structured extraction here finds nothing.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Iterable

DEFAULT_ACTOR_ID = "bovi/linkedin-profile-scraper"

# Best-effort guesses for where each signal might appear in the actor's
# output item. Checked in order; first match wins. VERIFY against a real
# response (see module docstring) and adjust as needed.
LAST_POST_DATE_KEY_CANDIDATES = [
    "lastActivityDate",
    "lastPostDate",
    "lastActivityAt",
    "latestPostDate",
]
POSTS_COUNT_KEY_CANDIDATES = [
    "postsLast30Days",
    "recentPostsCount",
    "postsCount",
    "activityCount",
]
ENGAGEMENT_COUNT_KEY_CANDIDATES = [
    "commentsLast30Days",
    "recentEngagementCount",
    "engagementCount",
]
# Container keys that might hold a list of recent posts/activity items,
# each with its own date, used to derive last_post_date/posts_last_30d if
# the flat keys above aren't present.
ACTIVITY_LIST_KEY_CANDIDATES = ["activity", "recentActivity", "posts", "updates"]
ACTIVITY_ITEM_DATE_KEY_CANDIDATES = ["date", "postedAt", "publishedAt", "time"]


def _get_first(item: dict, keys: Iterable[str]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # epoch millis or seconds
        ts = value / 1000 if value > 10**12 else value
        return datetime.fromtimestamp(ts).date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def normalize_apify_item(item: dict) -> dict:
    """Map one raw Apify dataset item to our input CSV columns."""
    name = item.get("fullName") or item.get("name") or ""
    profile_url = item.get("profileUrl") or item.get("url") or item.get("linkedinUrl") or ""

    last_post_date = _parse_date(_get_first(item, LAST_POST_DATE_KEY_CANDIDATES))
    posts_last_30d = _get_first(item, POSTS_COUNT_KEY_CANDIDATES)
    engagement = _get_first(item, ENGAGEMENT_COUNT_KEY_CANDIDATES)

    if last_post_date is None or posts_last_30d is None:
        activity_list = _get_first(item, ACTIVITY_LIST_KEY_CANDIDATES)
        if isinstance(activity_list, list) and activity_list:
            dates = [
                d
                for entry in activity_list
                if isinstance(entry, dict)
                for d in [_parse_date(_get_first(entry, ACTIVITY_ITEM_DATE_KEY_CANDIDATES))]
                if d is not None
            ]
            if dates:
                if last_post_date is None:
                    last_post_date = max(dates)
                if posts_last_30d is None:
                    posts_last_30d = sum(1 for d in dates if (date.today() - d).days <= 30)

    return {
        "name": name,
        "profile_url": profile_url,
        "last_post_date": last_post_date.isoformat() if last_post_date else "",
        "posts_last_30d": posts_last_30d if posts_last_30d is not None else "",
        "comments_or_likes_last_30d": engagement if engagement is not None else "",
        # Always keep the raw item so the Claude fallback (or a human) can
        # recover anything the structured extraction above missed.
        "notes": json.dumps(item, default=str)[:4000],
    }


def fetch_profiles_from_apify(
    profile_urls: list[str],
    api_token: str | None = None,
    actor_id: str = DEFAULT_ACTOR_ID,
) -> list[dict]:
    """Run the Apify actor against a list of LinkedIn profile URLs and
    return the raw dataset items (one per profile, order not guaranteed to
    match input order)."""
    try:
        from apify_client import ApifyClient
    except ImportError as exc:
        raise RuntimeError(
            "The 'apify-client' package is required. Install it with: pip install apify-client"
        ) from exc

    token = api_token or os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("APIFY_API_TOKEN is not set.")

    client = ApifyClient(token)
    # Input key is a best-effort guess (`profileUrls`) — verify against the
    # actor's real input schema in the Apify Console "Input" tab if this
    # doesn't work, and adjust here.
    run = client.actor(actor_id).call(run_input={"profileUrls": profile_urls})
    dataset_id = run["defaultDatasetId"]
    return list(client.dataset(dataset_id).iterate_items())
