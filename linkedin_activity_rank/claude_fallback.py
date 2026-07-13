"""Claude-powered fallback rating for rows the rule engine can't confidently
score: missing structured data but freeform notes exist, or structured
signals flatly contradict each other.
"""

from __future__ import annotations

import json
import os
import re

from .schema import Confidence, Profile, Rating, RatingResult

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

RUBRIC = """You are rating how actively a LinkedIn prospect uses LinkedIn, given \
whatever signals are available about them. Assign exactly one rating:

- GREEN ("active"): posts, comments, or otherwise engages roughly weekly or \
more; clear recent activity (within ~2 weeks) or a consistently high posting \
cadence.
- ORANGE ("sort of active"): engages occasionally, roughly monthly, or their \
most recent activity is a few weeks to ~6 weeks old; mixed or sparse signals.
- RED ("not active"): little to no evidence of activity in the last couple \
of months, or the profile looks dormant; also use RED when there is no \
usable evidence of activity at all.

Respond with ONLY a JSON object, no other text:
{"rating": "GREEN|ORANGE|RED", "confidence": "HIGH|MEDIUM|LOW", "reasoning": "<one sentence>"}
"""


def _profile_to_prompt(profile: Profile) -> str:
    fields = {
        "name": profile.name,
        "profile_url": profile.profile_url,
        "last_post_date": profile.last_post_date.isoformat() if profile.last_post_date else None,
        "posts_last_30d": profile.posts_last_30d,
        "comments_or_likes_last_30d": profile.comments_or_likes_last_30d,
        "notes": profile.notes or None,
    }
    return "Prospect data:\n" + json.dumps(fields, indent=2)


def _parse_response(text: str) -> RatingResult:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return RatingResult(
            Rating.RED, Confidence.LOW, "claude",
            "Could not parse a rating from the model response; defaulted to RED.",
        )
    data = json.loads(match.group(0))
    rating = Rating(data["rating"].upper())
    confidence = Confidence(data.get("confidence", "MEDIUM").upper())
    reasoning = data.get("reasoning", "")
    return RatingResult(rating, confidence, "claude", reasoning)


def claude_rating(profile: Profile, model: str = DEFAULT_MODEL) -> RatingResult:
    """Call the Claude API to rate a single ambiguous/underspecified profile.

    Requires ANTHROPIC_API_KEY to be set. Raises RuntimeError if the
    `anthropic` package isn't installed or the key is missing.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "The 'anthropic' package is required for Claude fallback rating. "
            "Install it with: pip install anthropic"
        ) from exc

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=RUBRIC,
        messages=[{"role": "user", "content": _profile_to_prompt(profile)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_response(text)
