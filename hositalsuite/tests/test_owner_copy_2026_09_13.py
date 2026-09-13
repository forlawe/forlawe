"""Owner copy round 2 — 2026-09-13 (five points, pinned).

1. Language names (English / Yorùbá / Hausa / Igbo) must be WHITE and visible
   on the patient welcome page and associated pages.
2. "Please pay before you arrive…" is gone from the Fast-Track banners,
   everywhere a patient sees it.
3. "Today's queue only — priority patients … seen first automatically" is gone
   from the patient pages.
4. The old "Elderly, pregnant … seen first automatically — no need to pick
   Fast Track…" sentence is replaced by the owner's new wording.
5. The "Need help booking?" card is gone — the help-desk block already carries
   the hospital numbers on every page.

Deliberate scope: staff desk pages (queue staff, reception, consulting,
triage, LAHSMA, cash desk, Fast-Track desk, TV) KEEP their priority-lane
notes — the priority lane is a real, implemented desk workflow
(PatientVisit.fast_track_reason: ELDERLY | PREGNANT | CHILD | WHEELCHAIR),
and the owner's quoted sentences are patient-facing promises. The last test
below pins that scope so nobody silently strips the staff guidance.
"""
from __future__ import annotations

from datetime import timedelta

from app import services
from app.models import db, now_naive

from conftest import csrf

PATIENT_PAGES = ("/", "/welcome", "/queue/join", "/book", "/book/fast-track",
                 "/emergency")

PAY_SENTENCE = "Please pay before you arrive"
OLD_PRIORITY_SENTENCE = "seen first automatically"
NEW_SENTENCE = "You don't need to pick Fast Track if your health condition need special attention."


# --------------------------------------------------------------- 1 · white lang bar
def test_language_names_are_white_on_every_patient_page(client, seeded):
    for url in PATIENT_PAGES:
        html = client.get(url).get_data(as_text=True)
        bar = html.split("English", 1)[0].rsplit("<div", 1)[-1] + "English"
        # every language pill carries white text
        assert "color:#fff!important" in html, url
        # the old dark-on-white active pill is gone
        assert "color:#0a4468" not in html, url
        # all four names still present and clickable
        for name in ("English", "Yorùbá", "Hausa", "Igbo"):
            assert name in html, (url, name)
        assert bar  # the bar itself rendered


# ------------------------------------------- 2 · no pay-before-arrive on banners
def test_pay_before_you_arrive_is_gone_from_fast_track_banners(client, seeded):
    for url in ("/book", "/book/fast-track"):
        html = client.get(url).get_data(as_text=True)
        assert PAY_SENTENCE not in html, url
        assert "fast_track_payment_instructions" not in html, url


def test_pay_before_you_arrive_gone_from_thanks_page_even_when_payment_required(client, seeded):
    """The old thanks page showed an amber '⏳ Please pay before you arrive'
    badge plus the payment instructions when the hospital required upfront
    payment — that was the last patient-facing place the sentence lived."""
    services.set_setting(seeded["org"], "fast_track_booking_requires_payment", True)
    db.session.commit()
    from app.patient_places import ensure_fast_track
    ft = ensure_fast_track(seeded["org"])
    db.session.commit()
    token = csrf(client, "/book/fast-track")
    r = client.post("/book/submit", data={
        "_csrf": token,
        "idem": "copy-round-thanks",
        "is_fast_track": "1",
        "fast_track_reason": "PREMIUM",
        "fast_track_consent": "1",
        "consent": "1",
        "department_id": ft.id,
        "appointment_date": (now_naive().date() + timedelta(days=1)).isoformat(),
        "appointment_time": "09:00",
        "patient_name": "Chidi Eze",
        "phone": "08022221111",
    }, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert PAY_SENTENCE not in html
    # the patient is still told what to do at the desk
    assert "Show this reference at reception" in html


# --------------------------------------------- 3+4 · priority wording on queue page
def test_automatic_priority_promise_is_gone_from_patient_pages(client, seeded):
    for url in PATIENT_PAGES:
        html = client.get(url).get_data(as_text=True)
        assert OLD_PRIORITY_SENTENCE not in html, url
        assert "Today's queue only" not in html, url


def test_new_special_attention_wording_is_on_the_queue_page(client, seeded):
    html = client.get("/queue/join").get_data(as_text=True)
    assert NEW_SENTENCE in html
    assert "Just tell Reception/HIMS how we can help you, and we will prioritize your care." in html
    # the old wording it replaced is gone
    assert "no need to pick Fast Track. Just tell reception" not in html


# ------------------------------------------------------- 5 · no duplicate help card
def test_need_help_booking_card_is_gone(client, seeded):
    html = client.get("/book").get_data(as_text=True)
    assert "Need help booking?" not in html
    assert "Our staff will help you book and guide you to the right place." not in html
    # the help desk block that replaces it is still there, numbers and all
    assert 'class="help-desk"' in html


# --------------------------------------------------- deliberate scope: staff pages
def test_staff_desk_pages_keep_the_priority_lane_guidance(client, seeded):
    """Staff need the priority-lane note: it describes a real desk workflow
    (ELDERLY / PREGNANT / CHILD / WHEELCHAIR on the visit), not a patient
    promise. Pinning the scope so a future cleanup cannot strip it silently."""
    from conftest import login
    login(client, "am1")
    html = client.get("/queue").get_data(as_text=True)
    assert "Priority lane" in html or "Priority Lane" in html
