"""Emergency arrivals get a shorter, care-first journey on the personal TV.

A patient registered from the emergency landing page (ticket source
'emergency') must never see Billing and Payment standing between them and a
doctor. Routine patients keep the full journey and the always-open QR card.
"""
import secrets

from app import personal_tv as ptv
from app.models import Department, QueueTicket, db, now_naive


def _ticket(org_id, dept_id, source):
    t = QueueTicket(org_id=org_id, code=f"T-00{abs(hash(source)) % 10}",
                    access_key=secrets.token_urlsafe(12),
                    department_id=dept_id, queue_date=now_naive().date(),
                    patient_name="Jane Doe", status="WAITING", source=source)
    db.session.add(t)
    db.session.flush()
    return t


def test_emergency_ticket_gets_the_short_care_first_journey(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        t = _ticket(seeded["org"], dept.id, "emergency")
        sess = ptv.ensure_personal_session(seeded["org"], ticket=t)
        feed = ptv.build_personal_feed(seeded["org"], sess)
        assert feed["is_emergency"] is True
        stages = [s["stage"] for s in feed["timeline"]]
        assert stages == ["RECEPTION", "TRIAGE", "WAIT_DOCTOR", "CONSULTATION", "DONE"]
        # No paperwork between an A&E patient and a doctor.
        assert not any(s in stages for s in ("BILLING", "PAYMENT", "HIMS"))


def test_routine_ticket_keeps_the_full_journey(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        t = _ticket(seeded["org"], dept.id, "link")
        sess = ptv.ensure_personal_session(seeded["org"], ticket=t)
        feed = ptv.build_personal_feed(seeded["org"], sess)
        assert feed["is_emergency"] is False
        stages = [s["stage"] for s in feed["timeline"]]
        assert stages == ptv.STAGES_ORDER


def test_emergency_page_condenses_header_and_collapses_qr(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        t = _ticket(seeded["org"], dept.id, "emergency")
        sess = ptv.ensure_personal_session(seeded["org"], ticket=t)
        key = sess.access_key
        db.session.commit()
    html = client.get(f"/t/{key}").data.decode()
    assert 'class="ptv-header ptv-header-emergency"' in html
    assert "ptv-emergency-badge" in html
    # The greeting line and the big default header are gone for emergencies.
    assert "👋" not in html
    # QR collapsed by default: no `open` attribute on the details element.
    assert '<details class="ptv-qr">' in html
    assert '<details class="ptv-qr" open>' not in html
    assert "Save this page for another device" in html


def test_routine_page_keeps_open_qr_and_greeting(app, client, seeded):
    with app.app_context():
        dept = db.session.get(Department, seeded["dept"])
        t = _ticket(seeded["org"], dept.id, "link")
        sess = ptv.ensure_personal_session(seeded["org"], ticket=t)
        key = sess.access_key
        db.session.commit()
    html = client.get(f"/t/{key}").data.decode()
    # No emergency modifier on the header element (the CSS rule is always in
    # the page; only the class application on the element is what matters).
    assert 'class="ptv-header ptv-header-emergency"' not in html
    assert '<details class="ptv-qr" open>' in html
    assert "Keep this page — scan QR" in html
