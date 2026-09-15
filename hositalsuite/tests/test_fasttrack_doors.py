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

from app.models import (Appointment, JourneySegment, Patient, QueueTicket,
                        ReceptionIntake, db, now_naive)
from app.models_v2 import PersonalTvSession

from conftest import csrf, login

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


def _join_queue(client, seeded, name: str, phone: str = "", **extra):
    data = {
        "_csrf": csrf(client, "/queue/join"),
        "department_id": seeded["dept"],
        "patient_name": name, "phone": phone,
    }
    data.update(extra)
    return client.post("/queue/join", data=data, follow_redirects=True)


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


def test_ordinary_door_does_not_offer_the_paid_lounge(client, seeded):
    """Found end to end, not by reading: 'Fast Track' was the FIRST department in
    the dropdown on BOTH doors, so a patient on the free door picked it and was
    handed a premium booking with no price and no consent on screen."""
    from app.models import Department
    ft = Department(org_id=seeded["org"], name="Fast Track", active=True)
    db.session.add(ft); db.session.commit()

    plain = client.get("/book").get_data(as_text=True)
    gold = client.get("/book/fast-track").get_data(as_text=True)
    assert f'value="{ft.id}"' not in plain, (
        "the free door must not list the paid Fast Track lounge")
    assert f'value="{ft.id}"' in gold, (
        "the Fast Track door is where the lounge belongs")


def test_premium_department_cannot_skip_the_consent(client, seeded):
    """Posting the premium department through the ordinary door — bypassing the
    UI entirely — must still be refused without consent. The rule follows the
    outcome, not whichever field the browser happened to send."""
    from app.models import Department
    ft = Department(org_id=seeded["org"], name="Fast Track", active=True)
    db.session.add(ft); db.session.commit()

    r = _submit_as_browser(client, seeded, "/book", "sneaky-premium",
                           department_id=str(ft.id))
    assert b"premium service" in r.data
    assert db.session.query(Appointment).count() == 0


def test_a_typo_on_the_fast_track_door_keeps_it_gold(client, seeded):
    """A validation error used to re-render the form without the fast_track
    flag, silently downgrading the premium door to the plain one."""
    html = client.get("/book/fast-track").get_data(as_text=True)
    data = _hidden_fields(html)
    data["_csrf"] = csrf(client, "/book/fast-track")
    data["consent"] = "1"
    data["department_id"] = seeded["dept"]
    data["appointment_date"] = "not-a-date"          # force a 422 re-render
    data["appointment_time"] = "09:00"
    data["patient_name"] = "Typo Person"
    data["phone"] = "08033334447"
    r = client.post("/book/submit", data=data)
    assert r.status_code == 422
    assert 'name="is_fast_track"' in r.get_data(as_text=True)


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


# ----------------------------- owner requirement (2026-09-13, Render go-live)
def test_hub_shows_emergency_numbers_on_the_emergency_button(client, seeded):
    """Each hospital's emergency number(s) MUST be visible on the welcome
    page AND attached to the emergency button — a tel: call button beside
    the register button, showing the actual number, plus the help-desk
    block. Found missing on the live deploy: the seeded org had no phone,
    so every number silently vanished from the page."""
    from app.models import Organization, db
    with client.application.app_context():
        org = db.session.get(Organization, seeded["org"])
        org.phone = "0809 111 2222"
        org.phone_alt = "0809 333 4444"
        db.session.commit()

    html = client.get("/welcome").get_data(as_text=True)
    # visible on the page — the actual digits, not a generic "call us"
    assert "0809 111 2222" in html and "0809 333 4444" in html
    # attached to the emergency card as dialable links
    assert 'href="tel:08091112222"' in html
    assert 'href="tel:08093334444"' in html
    # the emergency register button is still there, right beside them
    assert "I&#39;m coming to A&amp;E" in html or "I'm coming to A&E" in html
    # and the help-desk block at the bottom carries both numbers too
    assert html.count('class="help-call"') >= 2


def test_hub_without_phone_keeps_a_graceful_fallback(client, seeded):
    """No number configured: the page must still tell the patient where to
    get help instead of showing a dead emergency card."""
    from app.models import Organization, db
    with client.application.app_context():
        org = db.session.get(Organization, seeded["org"])
        org.phone = None
        org.phone_alt = None
        db.session.commit()

    html = client.get("/welcome").get_data(as_text=True)
    # no call buttons invented out of thin air when no number exists
    assert "Call now:" not in html
    # the emergency register button survives
    assert "I&#39;m coming to A&amp;E" in html or "I'm coming to A&E" in html
    # help desk tells them where a human is (the i18n key renders to a
    # sentence containing "reception")
    assert "eception" in html


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
    # 2026-09-14 copy pass shortened the sentence; the routing promise it
    # pins is unchanged: returning patients (existing folder) go to Records.
    assert "Already have a folder? HIMS / Records." in html


# ------------------------------------------------- Request 3: entry routing
# These assert the RECORDS, not just the stage shown on the tracker. A display
# flag that nothing else knows about is how a tracker ends up promising
# "you are at Records" while no Records row exists.
def test_first_time_patient_starts_at_reception_with_a_real_record(client, seeded):
    _join_queue(client, seeded, "New Person", "08099990000")

    sess = db.session.query(PersonalTvSession).order_by(PersonalTvSession.id.desc()).first()
    assert sess is not None
    assert sess.current_stage == "RECEPTION"

    # a first-time patient needs a paper folder, so Reception gets a real intake
    intake = db.session.query(ReceptionIntake).one()
    assert intake.ref.startswith("RCP-")
    assert intake.stage == "RECEPTION"
    assert intake.surname and intake.first_name
    assert intake.created_by is None, (
        "self-service queue join must not invent a staff member in the audit trail")

    # ticket, tracker and journey all point at that same intake
    ticket = db.session.query(QueueTicket).one()
    assert ticket.intake_id == intake.id
    assert sess.intake_id == intake.id

    seg = db.session.query(JourneySegment).filter_by(stage="RECEPTION").one()
    assert seg.intake_id == intake.id


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

    # their folder already exists — minting a second intake would put a
    # duplicate name on the Reception desk list
    assert db.session.query(ReceptionIntake).count() == 0

    seg = db.session.query(JourneySegment).filter_by(stage="HIMS").one()
    assert seg.patient_id == p.id


def test_fast_track_choice_survives_onto_the_reception_record(client, seeded):
    """The premium flag must reach Reception, not just the ticket."""
    _join_queue(client, seeded, "Premium Person", "08099992222",
                is_fast_track="1", fast_track_consent="1", fast_track_reason="PREMIUM")
    intake = db.session.query(ReceptionIntake).one()
    assert intake.is_fast_track is True
    assert intake.fast_track_reason == "PREMIUM"


# ------------------------------------- staff pages must tell the same story
# These five tests exist because of a process gap, not a typo.
#
# Request 3 (entry routing) and the two booking doors were both changed and
# test-pinned on the PATIENT side — and the staff page that describes the same
# behaviour was never opened again. The result was a desk that promised
# "all patients start at Reception" and a bookings list that called every
# booking Fast Track, both quietly false for weeks.
#
# So: whenever patient flow changes, the staff page that describes it is part
# of the change. These tests are that checklist item, written down.

def _row_for(html: str, name: str) -> str:
    """The <tr> of the bookings table that mentions this patient."""
    for chunk in html.split("<tr")[1:]:
        row = chunk.split("</tr>")[0]
        if name in row:
            return row
    raise AssertionError(f"no bookings row was rendered for {name}")


def test_queue_staff_copy_matches_the_new_routing(client, seeded):
    login(client, "am1")
    html = client.get("/queue").get_data(as_text=True)
    assert "all patients start at Reception" not in html, (
        "stale staff copy — Request 3 sends returning patients straight to "
        "Records; only the patient-facing sentence was updated")
    # the routing promise, in staff words
    assert "New patients" in html and "HIMS / Records" in html


def test_queue_staff_to_reception_does_not_mint_a_second_intake(client, seeded):
    """Request 3 mints the Reception intake when the patient joins, so by the
    time a desk taps "To Reception" the intake already exists. Adding another
    one would put the same patient on the Reception list twice and open a
    second journey — the duplicate the routing work set out to remove."""
    _join_queue(client, seeded, "One Folder Only", "08077770000")
    assert db.session.query(ReceptionIntake).count() == 1

    ticket = db.session.query(QueueTicket).one()
    login(client, "am1")
    r = client.post(f"/queue/{ticket.id}/to-reception",
                    data={"_csrf": csrf(client, "/queue")},
                    follow_redirects=True)
    assert b"already at Reception" in r.data
    assert db.session.query(ReceptionIntake).count() == 1, (
        "one patient, one folder — the desk button must not open a second journey")


def test_bookings_staff_banner_does_not_call_every_booking_fast_track(client, seeded):
    login(client, "am1")
    html = client.get("/bookings").get_data(as_text=True)
    assert "All bookings here are Fast Track" not in html, (
        "bookings now arrive from two doors; only the Fast Track one is premium")


def test_bookings_staff_marks_fast_track_per_booking(client, seeded):
    """The crown and the gold check-in belong to the Fast Track booking only —
    not to every row on the page."""
    _submit_as_browser(client, seeded, "/book", "staff-plain-row",
                       patient_name="Plain Person")
    _submit_as_browser(client, seeded, "/book/fast-track", "staff-gold-row",
                       patient_name="Gold Person", fast_track_consent="1")

    login(client, "am1")
    html = client.get("/bookings").get_data(as_text=True)

    gold_row = _row_for(html, "Gold Person")
    plain_row = _row_for(html, "Plain Person")

    assert "👑" in gold_row and "Check in — Fast Track" in gold_row
    assert "👑" not in plain_row, (
        "a patient who never chose Fast Track must not be crowned on the list")
    assert "Check in — Fast Track" not in plain_row
    assert "Check in → Queue" in plain_row


def test_checking_in_a_standard_booking_does_not_claim_the_gold_lane(client, seeded):
    _submit_as_browser(client, seeded, "/book", "staff-plain-checkin",
                       patient_name="Plain Person")
    apt = db.session.query(Appointment).filter_by(patient_name="Plain Person").one()

    login(client, "am1")
    r = client.post(f"/bookings/{apt.id}/checkin-queue",
                    data={"_csrf": csrf(client, "/bookings")},
                    follow_redirects=True)
    assert db.session.get(Appointment, apt.id).status == "ARRIVED"
    assert b"gold lane" not in r.data, (
        "staff were told a standard booking entered the paid lane")
