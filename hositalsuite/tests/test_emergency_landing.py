"""Emergency landing page — separated from Join-a-queue (owner, 2026-09-13).

WHAT THE OWNER ASKED FOR
------------------------
1. "Join a queue page should be separated from emergency landing page."
   The emergency page used to BE the join-a-queue form with a red hero
   (?emergency=1), so an emergency patient saw queue, booking and Fast-Track
   content. Now /emergency is its own page and /queue/join is the ordinary
   queue form only.
2. "Emergency landing page carries the same info with Join a queue, booking
   and Fast-Track" — that was the complaint: it must NOT. One instruction,
   one action (register the A&E arrival), help-desk numbers. Nothing else.
3. "'Which Service Do you Need' should be removed from the Emergency landing
   page" — there is no dropdown of any kind on /emergency; the A&E department
   rides along as a hidden field.
4. The same dropdown on the patient pages shows ONLY Reception/Front Desk,
   HIMS/Records and Fast-Track/Premium Service (see also
   tests/test_patient_places.py and the booking assertions below).
"""
from __future__ import annotations

import re

from app.models import Department, QueueTicket, db

from conftest import csrf

HIDDEN_INPUT = re.compile(r'<input[^>]*type="hidden"[^>]*>')


def _hidden_fields(html: str) -> dict:
    out = {}
    for tag in HIDDEN_INPUT.findall(html):
        name = re.search(r'name="([^"]+)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = value.group(1) if value else ""
    return out


def _select(html: str) -> str:
    return html.split('<select name="department_id"', 1)[1].split("</select>", 1)[0]


# --------------------------------------------------------------- the new page
def test_emergency_page_is_its_own_page(client, seeded):
    html = client.get("/emergency").get_data(as_text=True)
    assert "Go to Accident & Emergency Now" in html
    # NO service dropdown of any kind — nothing to choose in an emergency
    assert "<select" not in html
    # and none of the join-a-queue / booking / Fast-Track content either
    low = html.lower()
    assert "fast track" not in low
    assert "fast-track" not in low
    assert "appointment_date" not in html
    assert "which service" not in low
    assert "get my queue number" not in low
    # the A&E destination rides along as a fixed hidden field
    assert 'name="department_id"' in html
    # help-desk numbers still one tap away
    assert 'class="help-desk"' in html


def test_join_a_queue_page_carries_no_emergency_content(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)
    assert "Go to Accident & Emergency Now" not in html
    assert "🚨 Emergency" not in html
    # the ordinary form is intact: three services, name, phone, submit
    select = _select(html)
    assert "Reception / Front Desk" in select
    assert "HIMS / Records" in select
    assert "Fast-Track / Premium Service" in select


def test_old_emergency_address_still_works(client, seeded):
    """Printed posters, the welcome card and the old banner pointed at
    /queue/join?emergency=1 — those people must still reach A&E."""
    r = client.get("/queue/join?emergency=1")
    assert r.status_code == 302
    assert "/emergency" in r.headers["Location"]


def test_emergency_form_registers_an_ae_number(client, seeded):
    html = client.get("/emergency").get_data(as_text=True)
    data = _hidden_fields(html)
    data["_csrf"] = csrf(client, "/emergency")
    data["patient_name"] = "Musa Bello"
    data["phone"] = "08011112222"
    r = client.post("/queue/join", data=data, follow_redirects=True)
    assert r.status_code == 200
    t = db.session.query(QueueTicket).first()
    assert t is not None and t.patient_name == "Musa Bello"
    dept = db.session.get(Department, t.department_id)
    assert "emergency" in dept.name.lower() or "accident" in dept.name.lower()


def test_welcome_page_emergency_button_points_at_the_new_page(client, seeded):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/emergency"' in html
    assert "/queue/join?emergency=1" not in html


# ------------------------------------------------- the three-service dropdown
def test_booking_dropdown_shows_only_the_three_services(client, seeded):
    plain = client.get("/book").get_data(as_text=True)
    select = _select(plain)
    assert "Reception / Front Desk" in select
    assert "HIMS / Records" in select
    assert "Fast-Track / Premium Service" in select
    # nothing else sneaks in — exactly three real/door options + placeholder
    options = re.findall(r"<option[^>]*>", select)
    assert len(options) == 4, options
    # the free door must never POST the premium department: its Fast-Track
    # line is a door (data-goto), not a value (pinned rule, see
    # tests/test_fasttrack_doors.py)
    ft = db.session.query(Department).filter_by(name="Fast Track").first()
    assert ft is not None
    assert f'value="{ft.id}"' not in select
    assert "data-goto=" in select


def test_fast_track_door_dropdown_lists_the_premium_service(client, seeded):
    gold = client.get("/book/fast-track").get_data(as_text=True)
    select = _select(gold)
    ft = db.session.query(Department).filter_by(name="Fast Track").first()
    assert re.search(rf'<option value="{ft.id}"[^>]*selected', select), (
        "the Fast-Track door must pre-select the premium service")
