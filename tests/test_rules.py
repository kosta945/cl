from datetime import date, timedelta

from linkedin_activity_rank.rules import rule_based_rating
from linkedin_activity_rank.schema import Confidence, Profile, Rating


def _profile(**kwargs) -> Profile:
    defaults = dict(name="Test", profile_url="https://linkedin.com/in/test")
    defaults.update(kwargs)
    return Profile(**defaults)


def test_recent_and_frequent_is_green_high_confidence():
    p = _profile(
        last_post_date=date.today() - timedelta(days=2),
        posts_last_30d=8,
        comments_or_likes_last_30d=20,
    )
    result = rule_based_rating(p)
    assert result.rating == Rating.GREEN
    assert result.confidence == Confidence.HIGH


def test_stale_and_quiet_is_red_high_confidence():
    p = _profile(
        last_post_date=date.today() - timedelta(days=120),
        posts_last_30d=0,
        comments_or_likes_last_30d=0,
    )
    result = rule_based_rating(p)
    assert result.rating == Rating.RED
    assert result.confidence == Confidence.HIGH


def test_moderate_activity_is_orange():
    p = _profile(
        last_post_date=date.today() - timedelta(days=20),
        posts_last_30d=2,
        comments_or_likes_last_30d=4,
    )
    result = rule_based_rating(p)
    assert result.rating == Rating.ORANGE
    assert result.confidence == Confidence.HIGH


def test_conflicting_signals_are_low_confidence():
    # Posted yesterday, but frequency counter says nothing in 30 days.
    p = _profile(
        last_post_date=date.today() - timedelta(days=1),
        posts_last_30d=0,
        comments_or_likes_last_30d=0,
    )
    result = rule_based_rating(p)
    assert result.confidence == Confidence.LOW


def test_single_signal_is_medium_confidence():
    p = _profile(last_post_date=date.today() - timedelta(days=5))
    result = rule_based_rating(p)
    assert result.rating == Rating.GREEN
    assert result.confidence == Confidence.MEDIUM


def test_no_structured_signal_returns_none():
    p = _profile(notes="Looked pretty active when I checked manually.")
    assert rule_based_rating(p) is None
