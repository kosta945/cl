"""Data model for a single prospect row and the possible ratings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

# Expected input CSV columns. Only `name` and `profile_url` are required;
# everything else is optional but the more signals you provide, the fewer
# rows need to fall back to Claude.
INPUT_COLUMNS = [
    "name",
    "profile_url",
    "last_post_date",           # YYYY-MM-DD, date of their most recent post/share/comment
    "posts_last_30d",           # integer count of posts/shares in the last 30 days
    "comments_or_likes_last_30d",  # integer count of comments/likes they made in the last 30 days
    "notes",                    # freeform text, e.g. pasted snippets from their "Activity" tab
]

OUTPUT_COLUMNS = INPUT_COLUMNS + [
    "rating",
    "confidence",
    "method",
    "reasoning",
]


class Rating(str, Enum):
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    RED = "RED"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Profile:
    name: str
    profile_url: str
    last_post_date: Optional[date] = None
    posts_last_30d: Optional[int] = None
    comments_or_likes_last_30d: Optional[int] = None
    notes: str = ""

    def has_structured_signal(self) -> bool:
        return self.last_post_date is not None or self.posts_last_30d is not None

    def has_any_signal(self) -> bool:
        return self.has_structured_signal() or bool(self.notes.strip())


@dataclass
class RatingResult:
    rating: Rating
    confidence: Confidence
    method: str  # "rule" or "claude"
    reasoning: str
