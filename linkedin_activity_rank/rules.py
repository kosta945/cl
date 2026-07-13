"""Deterministic rating rules based on structured activity fields.

Two independent signals are considered when present:
  - recency:   days since their last post/share/comment
  - frequency: how many posts and how much engagement they logged in the
               last 30 days

Each signal casts an independent GREEN/ORANGE/RED "vote". If the signals
agree (or only one is available), the rule engine is confident and no LLM
call is needed. If they disagree by more than one tier, the row is flagged
LOW confidence so the pipeline can hand it to Claude for a judgment call.
"""

from __future__ import annotations

from datetime import date

from .schema import Confidence, Profile, Rating, RatingResult

# Recency thresholds (days since last activity).
RECENCY_GREEN_MAX_DAYS = 14
RECENCY_ORANGE_MAX_DAYS = 45

# Frequency thresholds (posts in the last 30 days).
FREQUENCY_GREEN_MIN_POSTS = 4
FREQUENCY_ORANGE_MIN_POSTS = 1

# Engagement thresholds (comments/likes in the last 30 days), used only to
# nudge a borderline frequency vote, not as a standalone signal.
ENGAGEMENT_GREEN_MIN = 10
ENGAGEMENT_ORANGE_MIN = 2

_TIER_ORDER = [Rating.RED, Rating.ORANGE, Rating.GREEN]


def _recency_vote(profile: Profile) -> tuple[Rating, str] | None:
    if profile.last_post_date is None:
        return None
    days = (date.today() - profile.last_post_date).days
    if days <= RECENCY_GREEN_MAX_DAYS:
        return Rating.GREEN, f"last active {days}d ago"
    if days <= RECENCY_ORANGE_MAX_DAYS:
        return Rating.ORANGE, f"last active {days}d ago"
    return Rating.RED, f"last active {days}d ago"


def _frequency_vote(profile: Profile) -> tuple[Rating, str] | None:
    if profile.posts_last_30d is None:
        return None
    posts = profile.posts_last_30d
    engagement = profile.comments_or_likes_last_30d or 0

    if posts >= FREQUENCY_GREEN_MIN_POSTS or engagement >= ENGAGEMENT_GREEN_MIN:
        rating = Rating.GREEN
    elif posts >= FREQUENCY_ORANGE_MIN_POSTS or engagement >= ENGAGEMENT_ORANGE_MIN:
        rating = Rating.ORANGE
    else:
        rating = Rating.RED
    return rating, f"{posts} posts / {engagement} comments+likes in last 30d"


def rule_based_rating(profile: Profile) -> RatingResult | None:
    """Return a RatingResult from structured fields, or None if there's
    nothing structured to work with (caller should try the Claude fallback
    or fall back to notes)."""
    recency = _recency_vote(profile)
    frequency = _frequency_vote(profile)

    if recency is None and frequency is None:
        return None

    if recency is not None and frequency is not None:
        r_rating, r_reason = recency
        f_rating, f_reason = frequency
        gap = abs(_TIER_ORDER.index(r_rating) - _TIER_ORDER.index(f_rating))
        reasoning = f"{r_reason}; {f_reason}"
        if gap == 0:
            return RatingResult(r_rating, Confidence.HIGH, "rule", reasoning)
        if gap == 1:
            # Agree within one tier: take the more optimistic-but-cautious
            # middle ground by preferring the lower (less active) tier,
            # since one stale signal shouldn't overstate activity.
            worse = min([r_rating, f_rating], key=lambda r: _TIER_ORDER.index(r))
            return RatingResult(worse, Confidence.MEDIUM, "rule", reasoning)
        # gap == 2: signals flatly contradict each other (e.g. posted
        # yesterday but 0 posts in 30d) -> let Claude adjudicate.
        return RatingResult(r_rating, Confidence.LOW, "rule", reasoning)

    # Only one structured signal available.
    rating, reason = recency or frequency
    return RatingResult(rating, Confidence.MEDIUM, "rule", reason)
