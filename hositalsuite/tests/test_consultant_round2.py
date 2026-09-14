"""Consultant round-2 diff sheet (2026-09-14) — pinned outcomes.

1. HIMS direct registration / desk-started visits enter the journey tracker
   at the HIMS stage (they used to open a visit with no tracking segment, so
   the patient's tracker/TV showed nothing until another desk touched them).
2. The hub tile is "My Visit Journey" (the page delivers a live tracker with
   voice updates — the old "Join the queue" label undersold it).
3. Emergency registrations are tagged source="emergency" (the separate
   /emergency page itself is pinned in tests/test_emergency_landing.py).
6. One shared patient-portal design system: .pp-* classes in app.css, used by
   every patient page; the gold hero belongs to the gold door only.

Items 4 and 5 of the sheet were already implemented in earlier rounds of this
branch (three-service dropdown; copy removals/replacements) and stay pinned by
tests/test_patient_places.py, tests/test_emergency_landing.py and
tests/test_owner_copy_2026_09_13.py.
"""
from __future__ import annotations

import pathlib

from app.models import JourneySegment, QueueTicket, db

from conftest import csrf, login

CSS = pathlib.Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "app.css"


def _folder(client, **over):
    data = {
        "_csrf": csrf(client, "/hims/register"),
        "surname": "ADEYEMI", "first_name": "Bola", "sex": "F",
        "age_years": "40", "phone": "08059826800",
        "nok_name": "Mr Adeyemi", "nok_relationship": "husband",
        "nok_phone": "08033901100", "payer_type": "SELF",
    }
    data.update(over)
    return client.post("/hims/register", data=data, follow_redirects=True)


# ---------------------------------------------------- 1 · HIMS auto-queue
def test_hims_direct_registration_with_visit_enters_the_tracker(client, seeded):
    login(client, "admin")
    r = _folder(client, start_visit="1", reason="cough")
    assert r.status_code == 200
    seg = db.session.query(JourneySegment).filter_by(stage="HIMS").first()
    assert seg is not None, "a HIMS-started visit must open a HIMS tracking segment"
    assert seg.visit_id is not None and seg.patient_id is not None
    assert seg.staff_id is not None, "desk-started segments carry the clerk"


def test_hims_desk_started_visit_for_returning_patient_enters_the_tracker(client, seeded):
    login(client, "admin")
    _folder(client)  # folder, no visit
    from app.models import Patient
    p = db.session.query(Patient).first()
    pid = p.id
    r = client.post(f"/hims/folder/{pid}/visit",
                    data={"_csrf": csrf(client, f"/hims/folder/{pid}"),
                          "reason": "follow-up"},
                    follow_redirects=True)
    assert r.status_code == 200
    seg = db.session.query(JourneySegment).filter_by(stage="HIMS").first()
    assert seg is not None and seg.visit_id is not None


def test_hims_folder_without_visit_still_opens_no_segment(client, seeded):
    """A folder with no visit started is not a patient in the building yet."""
    login(client, "admin")
    _folder(client)
    assert db.session.query(JourneySegment).count() == 0


# ---------------------------------------------------- 2 · hub tile rename
def test_hub_tile_is_my_visit_journey(client, seeded):
    html = client.get("/").get_data(as_text=True)
    assert "My Visit Journey" in html
    assert "Live tracker with your position, wait time, and voice updates." in html
    assert ">Join the queue<" not in html


# ---------------------------------------------------- 3 · emergency source tag
def test_emergency_registration_is_tagged_emergency(client, seeded):
    html = client.get("/emergency").get_data(as_text=True)
    import re
    data = {}
    for tag in re.findall(r'<input[^>]*type="hidden"[^>]*>', html):
        import re as _re
        name = _re.search(r'name="([^"]+)"', tag)
        value = _re.search(r'value="([^"]*)"', tag)
        if name:
            data[name.group(1)] = value.group(1) if value else ""
    data["_csrf"] = csrf(client, "/emergency")
    data["patient_name"] = "Susa Lawal"
    client.post("/queue/join", data=data, follow_redirects=True)
    t = db.session.query(QueueTicket).first()
    assert t is not None and t.source == "emergency"


# ---------------------------------------------------- 6 · one design system
def test_shared_design_system_exists_in_app_css():
    css = CSS.read_text()
    for cls in (".pp-hero{", ".pp-hero.pp-hero-gold", ".pp-hero.pp-hero-emergency",
                ".pp-step-label", ".pp-input", ".pp-gold-box", ".pp-btn-primary",
                ".pp-btn-gold", ".pp-btn-emergency"):
        assert cls in css, cls
    # built on the shared tokens, not fresh hex drift
    assert "var(--primary-light)" in css and "var(--line-soft)" in css


def test_gold_hero_only_on_the_gold_door(client, seeded):
    plain = client.get("/book").get_data(as_text=True)
    gold = client.get("/book/fast-track").get_data(as_text=True)
    assert "pp-hero-gold" not in plain, "the free door must not wear the gold hero"
    assert "pp-hero-gold" in gold
    # the old page-local hero class is gone from both doors
    assert 'class="hero-gold"' not in plain and 'class="hero-gold"' not in gold


def test_every_patient_page_uses_the_shared_classes(client, seeded):
    for url in ("/queue/join", "/book", "/book/fast-track", "/emergency",
                "/complaint", "/feedback"):
        html = client.get(url).get_data(as_text=True)
        assert 'class="pp-input"' in html, url
        assert "pp-step-label" in html, url
        assert "pp-btn" in html, url
        # the old page-local systems are gone
        assert 'class="input-big"' not in html, url
        assert 'class="step-label"' not in html, url
        assert 'class="hero-gold"' not in html, url


def test_migrated_pages_carry_no_local_hero_style_block(client, seeded):
    for url in ("/queue/join", "/book", "/emergency"):
        html = client.get(url).get_data(as_text=True)
        assert ".hero{" not in html and ".hero-gold{" not in html and ".hero-red{" not in html, url


def test_unstyled_portals_now_match_the_family(client, seeded):
    for url in ("/complaint", "/feedback"):
        html = client.get(url).get_data(as_text=True)
        assert 'class="pp-hero"' in html, url
