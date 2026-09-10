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


def test_join_page_emergency_banner_same_rule(client, seeded):
    html = client.get("/queue/join?emergency=1").get_data(as_text=True)
    assert "Go to Accident & Emergency Now" in html
    assert "🔗 Linked to A&E" not in html          # repetition removed
    assert "ask for directions" in html            # demoted secondary line
    # the ONE action on this page is the emergency-number form itself
    assert "emergency number below shows at the desk" in html
