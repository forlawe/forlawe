"""Gate 2 — first patient page pass: Queue / My Visit Journey.

This is deliberately a small UX gate.  It pins the order and honesty of the
queue entry task without coupling tests to decorative HTML details.
"""
from __future__ import annotations

import re
from pathlib import Path

from conftest import csrf

ROOT = Path(__file__).resolve().parents[1]
QUEUE_TEMPLATE = ROOT / "app" / "templates" / "queue_join.html"
TICKET_TEMPLATE = ROOT / "app" / "templates" / "queue_ticket.html"


def test_queue_join_is_a_thumb_first_three_step_form(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)

    assert "Join the queue" in html
    assert "1 · Choose your service" in html
    assert "2 · Tell us who is waiting" in html
    assert "3 · Optional Fast Track" in html
    assert 'aria-labelledby="queue-form-title"' in html
    assert 'aria-live="polite"' in html
    assert 'for="q-dept"' in html
    assert 'for="q-name"' in html
    assert 'for="q-phone"' in html
    assert 'autocomplete="name"' in html
    assert 'autocomplete="tel"' in html
    assert "You will get a number and a private page showing your place." in html


def test_fast_track_is_explained_only_after_the_patient_chooses_it(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)
    checkbox = re.search(r'<input[^>]*name="is_fast_track"[^>]*>', html)
    consent = re.search(r'<input[^>]*name="fast_track_consent"[^>]*>', html)

    assert checkbox and "checked" not in checkbox.group(0)
    assert consent and "required" not in consent.group(0)
    assert '<div class="pp-gold-box" id="q-fast-panel" hidden>' in html
    assert 'id="q-fast-toggle"' in html
    assert 'data-fast="1"' in html

    source = QUEUE_TEMPLATE.read_text(encoding="utf-8")
    assert "panel.hidden = !active" in source
    assert "consent.required = active" in source
    assert "fast.checked = true" in source


def test_queue_copy_makes_the_privacy_promise_once(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)
    assert html.count("never your name") == 1
    assert html.count("quiet, private lounge") == 1
    # The paid-service wording belongs to the shared consent partial, not a
    # second hand-typed sentence on the page.
    assert html.count("I choose Fast Track. I understand it is a premium service") == 1


def test_my_visit_tracker_does_not_promise_to_say_a_patient_name_on_tv():
    source = TICKET_TEMPLATE.read_text(encoding="utf-8")
    assert "you will also hear your name" not in source
    assert "when <b>{{ t.code }}</b> shows, please go to the desk" in source


def test_invalid_queue_form_still_returns_a_live_error(client, seeded):
    response = client.post(
        "/queue/join",
        data={"_csrf": csrf(client, "/queue/join"), "department_id": "", "patient_name": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Please choose a department and enter your name." in response.data
    assert b'role="alert"' in response.data
