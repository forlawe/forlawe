"""F-040: the emergency banner gives ONE instruction, not three.

The product's own AI rule is "ONE INSTRUCTION, NOT THREE". The public
emergency banner violated it — two equal buttons, a phone button, a voice
button AND a repeating "Linked:" line all pointing at the same two places.
Fix: one primary action (register the A&E arrival), everything else demoted
to a single small secondary line; the repetition is gone.
"""
from __future__ import annotations


def test_hub_banner_has_one_primary_action(client, seeded):
    html = client.get("/").get_data(as_text=True)
    # the ONE primary action
    assert "I'm coming to A&E — register me now" in html
    # exactly one big red button in the emergency card (no competing equals)
    assert html.count("background:#c62828;color:#fff;font-weight:900") == 1
    # the repeating link line is gone
    assert "🔗 Linked:" not in html
    # the other paths survive, demoted to small text
    assert "ask for directions" in html


def test_emergency_landing_page_same_rule(client, seeded):
    """2026-09-13: the emergency content moved to its OWN page (/emergency) —
    the join-a-queue form no longer wears the red hat. Same F-040 rule there:
    one instruction, one primary action, everything else demoted."""
    html = client.get("/emergency").get_data(as_text=True)
    assert "Go to Accident & Emergency Now" in html
    assert "🔗 Linked to A&E" not in html          # repetition removed
    assert "ask for directions" in html            # demoted secondary line
    # the ONE action on this page is the emergency-number form itself
    assert "shows at the desk" in html
    # and the old address still lands people on the emergency page
    r = client.get("/queue/join?emergency=1")
    assert r.status_code == 302 and "/emergency" in r.headers["Location"]
