"""Clock format: never dump a pile of minutes like 256m."""
from datetime import timedelta

from app.models import now_naive
from app.timefmt import fmt_hm, last_active_phrase, say_hm


def test_clock_uses_hours_and_minutes():
    assert fmt_hm(154) == "2:34m"
    assert fmt_hm(256) == "4:16m"
    assert fmt_hm(1465) == "24:25m"
    assert fmt_hm(45) == "0:45m"
    assert fmt_hm(0) == "0:00m"
    assert fmt_hm(None) == "—"


def test_voice_says_hours_and_minutes():
    assert say_hm(154) == "2 hours 34 minutes"
    assert say_hm(90) == "1 hour 30 minutes"
    assert say_hm(1) == "1 minute"
    assert say_hm(60) == "1 hour"
    assert say_hm(None) == "—"


def test_last_active_phrase_says_last_active_never_available():
    now = now_naive()
    assert last_active_phrase(None, now) is None
    assert last_active_phrase(now - timedelta(seconds=45), now) == "last active just now"
    assert last_active_phrase(now - timedelta(hours=1, minutes=5), now) == \
        "last active 1 hour 5 minutes ago"
    assert last_active_phrase(now - timedelta(days=1), now) == \
        "last active 24 hours ago"
    # A login is presence, not duty — the wording must never claim availability.
    for p in ("last active just now", "last active 1 hour 5 minutes ago"):
        assert "available" not in p and "on duty" not in p
