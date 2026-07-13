"""CSV in -> rule engine -> Claude fallback for ambiguous rows -> CSV out."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .claude_fallback import claude_rating
from .rules import rule_based_rating
from .schema import Confidence, OUTPUT_COLUMNS, Profile, Rating, RatingResult


def _parse_optional_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def _parse_optional_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def read_profiles(input_path: str | Path) -> list[Profile]:
    profiles = []
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            profiles.append(
                Profile(
                    name=row.get("name", "").strip(),
                    profile_url=row.get("profile_url", "").strip(),
                    last_post_date=_parse_optional_date(row.get("last_post_date", "")),
                    posts_last_30d=_parse_optional_int(row.get("posts_last_30d", "")),
                    comments_or_likes_last_30d=_parse_optional_int(
                        row.get("comments_or_likes_last_30d", "")
                    ),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return profiles


def rate_profile(profile: Profile, use_claude: bool = True, model: str | None = None) -> RatingResult:
    result = rule_based_rating(profile)

    needs_fallback = result is None or result.confidence == Confidence.LOW
    if needs_fallback and use_claude and profile.has_any_signal():
        kwargs = {"model": model} if model else {}
        try:
            return claude_rating(profile, **kwargs)
        except RuntimeError as exc:
            if result is not None:
                result.reasoning += f" (Claude fallback unavailable: {exc})"
                return result
            return RatingResult(
                Rating.RED,
                Confidence.LOW,
                "rule",
                f"No structured activity data, and Claude fallback unavailable: {exc}",
            )

    if result is not None:
        return result

    return RatingResult(
        Rating.RED,
        Confidence.LOW,
        "rule",
        "No activity data provided; defaulted to RED.",
    )


def run(
    input_path: str | Path,
    output_path: str | Path,
    use_claude: bool = True,
    model: str | None = None,
) -> list[tuple[Profile, RatingResult]]:
    profiles = read_profiles(input_path)
    results = [(p, rate_profile(p, use_claude=use_claude, model=model)) for p in profiles]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for profile, result in results:
            writer.writerow(
                {
                    "name": profile.name,
                    "profile_url": profile.profile_url,
                    "last_post_date": profile.last_post_date.isoformat()
                    if profile.last_post_date
                    else "",
                    "posts_last_30d": profile.posts_last_30d
                    if profile.posts_last_30d is not None
                    else "",
                    "comments_or_likes_last_30d": profile.comments_or_likes_last_30d
                    if profile.comments_or_likes_last_30d is not None
                    else "",
                    "notes": profile.notes,
                    "rating": result.rating.value,
                    "confidence": result.confidence.value,
                    "method": result.method,
                    "reasoning": result.reasoning,
                }
            )

    return results
