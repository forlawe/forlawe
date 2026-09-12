"""Clock format: never dump a pile of minutes like 256m."""
from app.timefmt import fmt_hm, say_hm


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
