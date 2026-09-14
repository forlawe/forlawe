"""Patient-interface copy pass — 2026-09-14 (owner).

"Remove repetition of instruction/direction, make each page's instruction
presentation short but still meaningful, clear tone, premium presentation."

Pinned outcomes:
* every promise/instruction appears ONCE per page (no repeated paragraphs,
  no repeated footer lines);
* the long "What happens next / How it works / What to do now" prose boxes
  are replaced by the shared premium step chips (.pp-steps);
* the pages still say everything a patient needs (meaningful, not terse):
  privacy promise, routing hint, premium consent, help desk.
"""
from __future__ import annotations

STEP_PAGES = ("/queue/join", "/book", "/book/fast-track", "/emergency")


def _get(client, url):
    return client.get(url).get_data(as_text=True)


# ------------------------------------------------- repetition is gone
def test_queue_page_says_each_thing_once(client, seeded):
    html = _get(client, "/queue/join")
    assert html.count("never your name") == 1, "privacy promise stated once"
    assert html.count("quiet, private lounge") == 1, "consent carries it alone"
    assert "What happens next?" not in html
    assert "You'll get a number and a private tracker showing your live position" not in html
    assert "Your number only shows on TV, not your name</div>" not in html  # old footer repeat
    # still meaningful: routing + premium + privacy all present, shortly
    assert "New here? Reception / Front Desk." in html
    assert "Our premium lane" in html
    assert "Your number shows on TV — never your name." in html


def test_booking_page_says_each_thing_once(client, seeded):
    for url in ("/book", "/book/fast-track"):
        html = _get(client, url)
        assert "How it works:" not in html, url
        assert html.count("WhatsApp first, then SMS") == 1, url
        assert "We will do our best to see you at your chosen time." not in html, url
    gold = _get(client, "/book/fast-track")
    assert gold.count("quiet, private lounge") == 1, "consent carries it alone"


def test_emergency_page_says_each_thing_once(client, seeded):
    html = _get(client, "/emergency")
    assert "What to do now" not in html
    assert html.count("seen immediately") <= 2   # hero + nothing else verbose
    assert "never your name" in html
    assert "Go to A&amp;E" in html or "Go to A&E" in html


def test_hub_pitches_are_short(client, seeded):
    html = _get(client, "/")
    assert "No long queue. Calm, fast, private." not in html
    assert "PAY MORE, GET FAST" not in html
    assert "Book ahead — walk straight to our quiet executive lounge." in html
    assert "⭐ PREMIUM • EXECUTIVE LOUNGE • SEEN FAST" in html
    # one emergency instruction, not three sentences
    assert "tell reception it's an emergency and you will be seen immediately." in html


# ------------------------------------------------- premium presentation
def test_step_chips_replace_the_prose_boxes(client, seeded):
    for url in STEP_PAGES:
        html = _get(client, url)
        assert 'class="pp-steps' in html, url
        assert "<li><b>1</b>" in html, url


def test_short_pages_still_carry_their_meaning(client, seeded):
    """Short must not mean silent: the load-bearing lines survive."""
    queue = _get(client, "/queue/join")
    assert "You don't need to pick Fast Track if your health condition need special attention." in queue
    assert 'class="help-desk"' in queue
    book = _get(client, "/book")
    assert 'class="help-desk"' in book
    assert "Already booked?" in book
    emerg = _get(client, "/emergency")
    assert 'class="help-desk"' in emerg
    assert "ask for directions" in emerg
    complaint = _get(client, "/complaint")
    assert "Every complaint is read and acted on." in complaint
    feedback = _get(client, "/feedback")
    assert "How was your visit?" in feedback
