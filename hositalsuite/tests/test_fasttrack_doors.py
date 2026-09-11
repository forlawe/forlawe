"""Fast Track: two honest doors, and entry routing by patient history.

WHY THIS FILE EXISTS
--------------------
`test_booking.py` posts `is_fast_track="1"` by hand. That is a perfectly good
unit test of the *server*, and it is exactly why a broken *form* went unnoticed:
the fields a patient's browser really submits are the thing that decides whether
a premium booking is stored as premium.

So every booking assertion here parses the hidden inputs out of the rendered
page and posts those — nothing hand-added. If the template and the server ever
disagree again, this file fails instead of a patient silently getting the wrong
service (in either direction: charged for Fast Track they did not choose, or
given a normal booking after tapping the gold card).
"""
import re
from datetime import timedelta

from app.models import Appointment, Patient, db, now_naive
from app.models_v2 import PersonalTvSession

from conftest import csrf

HIDDEN_INPUT = re.compile(r'<input[^>]*type="hidden"[^>]*>')


def _hidden_fields(html: str) -> dict:
    """Every hidden input the page renders — what the browser sends untouched."""
    out = {}
    for tag in HIDDEN_INPUT.findall(html):
        name = re.search(r'name="([^"]+)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = value.group(1) if value else ""
    return out


def _submit_as_browser(client, seeded, page: str, idem: str, **extra):
    """Fill in the visible fields a patient would, post the rest as rendered."""
    html = client.get(page).get_data(as_text=True)
    data = _hidden_fields(html)
    data["_csrf"] = csrf(client, page)
    data["idem"] = idem
    data.update({
        "consent": "1",
        "department_id": seeded["dept"],
        "appointment_date": (now_naive().date() + timedelta(days=1)).isoformat(),
        "appointment_time": "09:00",
        "patient_name": "Chinwe Obi",
        "phone": "08033334444",
    })
    data.update(extra)
    return client.post("/book/submit", data=data, follow_redirects=True)


def _join_queue(client, seeded, name: str, phone: str = ""):
    return client.post("/queue/join", data={
        "_csrf": csrf(client, "/queue/join"),
        "department_id": seeded["dept"],
        "patient_name": name, "phone": phone,
    }, follow_redirects=True)


# ---------------------------------------------------------------- two doors
def test_normal_door_renders_no_fast_track_field(client, seeded):
    html = client.get("/book").get_data(as_text=True)
    assert 'name="is_fast_track"' not in html, (
        "/book must not post is_fast_track — that hidden field is what turned "
        "every booking into a premium Fast Track one")


def test_booking_through_the_normal_door_is_not_fast_track(client, seeded):
    _submit_as_browser(client, seeded, "/book", "door-normal")
    apt = db.session.query(Appointment).first()
    assert apt is not None
    assert apt.is_fast_track is False


def test_fast_track_door_renders_the_flag_and_stores_it(client, seeded):
    html = client.get("/book/fast-track").get_data(as_text=True)
    assert 'name="is_fast_track"' in html, (
        "/book/fast-track must post is_fast_track, or the server cannot tell "
        "this is a premium booking")
    _submit_as_browser(client, seeded, "/book/fast-track", "door-ft",
                       fast_track_consent="1")
    apt = db.session.query(Appointment).first()
    assert apt is not None
    assert apt.is_fast_track is True, (
        "patient tapped the gold Fast Track card and consented, but the booking "
        "was stored as a normal visit")


def test_fast_track_consent_still_enforced_server_side(client, seeded):
    r = _submit_as_browser(client, seeded, "/book/fast-track", "door-ft-noconsent")
    assert b"premium service" in r.data
    assert db.session.query(Appointment).count() == 0


# ------------------------------------------------- the hub points where it says
def test_hub_gold_card_and_plain_tile_use_different_doors(client, seeded):
    html = client.get("/welcome").get_data(as_text=True)
    lux = re.search(r'<a class="lux-card" href="([^"]+)"', html)
    tile = re.search(r'<a class="hub-tile t-book" href="([^"]+)"', html)
    assert lux and tile
    assert lux.group(1).startswith("/book/fast-track"), (
        "the gold Fast Track card must lead to the Fast Track form")
    assert tile.group(1).startswith("/book"), "the plain tile stays on /book"
    assert not tile.group(1).startswith("/book/fast-track")


# ------------------------------------------------------- queue join: no opt-in
def test_queue_join_does_not_opt_anyone_into_a_paid_service(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)
    ft = re.search(r'<input[^>]*name="is_fast_track"[^>]*>', html)
    consent = re.search(r'<input[^>]*name="fast_track_consent"[^>]*>', html)
    assert ft and "checked" not in ft.group(0), (
        "Fast Track is a paid premium service — it cannot arrive pre-ticked")
    assert consent and "required" not in consent.group(0), (
        "consent cannot be compulsory for patients who never chose Fast Track")


def test_queue_join_copy_matches_the_new_routing(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)
    assert "all patients start at Reception" not in html, (
        "stale copy: returning patients now go straight to Records")
    assert "returning patients go straight to Records" in html


# ------------------------------------------------- Request 3: entry routing
def test_first_time_patient_starts_at_reception(client, seeded):
    _join_queue(client, seeded, "New Person", "08099990000")
    sess = db.session.query(PersonalTvSession).order_by(PersonalTvSession.id.desc()).first()
    assert sess is not None
    assert sess.current_stage == "RECEPTION"


def test_returning_patient_starts_at_records(client, seeded):
    p = Patient(org_id=seeded["org"], hospital_number="TEST/2026/00001",
                surname="Obi", first_name="Chinwe", sex="F", phone="08099991111")
    db.session.add(p)
    db.session.commit()

    _join_queue(client, seeded, "Chinwe Obi", "08099991111")
    sess = db.session.query(PersonalTvSession).order_by(PersonalTvSession.id.desc()).first()
    assert sess is not None
    assert sess.patient_id == p.id
    assert sess.current_stage == "HIMS", (
        "a patient with an existing folder should skip the paper Reception stage")
