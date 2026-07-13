from datetime import date, timedelta

from linkedin_activity_rank.apify_source import normalize_apify_item


def test_normalize_uses_flat_candidate_keys_when_present():
    item = {
        "fullName": "Alice Kim",
        "profileUrl": "https://www.linkedin.com/in/alicekim",
        "lastActivityDate": "2026-07-05",
        "postsLast30Days": 6,
        "commentsLast30Days": 22,
    }
    row = normalize_apify_item(item)
    assert row["name"] == "Alice Kim"
    assert row["profile_url"] == "https://www.linkedin.com/in/alicekim"
    assert row["last_post_date"] == "2026-07-05"
    assert row["posts_last_30d"] == 6
    assert row["comments_or_likes_last_30d"] == 22


def test_normalize_derives_from_activity_list_when_flat_keys_missing():
    recent = (date.today() - timedelta(days=5)).isoformat()
    old = (date.today() - timedelta(days=90)).isoformat()
    item = {
        "fullName": "Ben Ortiz",
        "url": "https://www.linkedin.com/in/benortiz",
        "activity": [{"date": recent}, {"date": old}],
    }
    row = normalize_apify_item(item)
    assert row["last_post_date"] == recent
    assert row["posts_last_30d"] == 1  # only the recent one falls in the 30d window


def test_normalize_preserves_raw_item_in_notes_even_when_unmapped():
    item = {"fullName": "Mystery Person", "someWeirdField": "unmapped data"}
    row = normalize_apify_item(item)
    assert row["last_post_date"] == ""
    assert row["posts_last_30d"] == ""
    assert "unmapped data" in row["notes"]
