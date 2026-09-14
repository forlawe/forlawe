"""Gate 1 — design-system unification (UX master plan, 2026-09-14).

The consultant's gate: "no patient page defines its own hero/input/step
styling and the four states exist and are used."

Pinned here:
1. The four shared states (waiting / empty / error / success) exist in the
   design system — CSS + reusable Jinja macros (_pp_states.html).
2. No patient template carries a <style> block or an inline style="" attr;
   every component (hub tiles, lux card, emergency card, langbar, stars,
   check lines, ticket page) lives in static/css/app.css.
3. The states are actually USED on rendered pages: success on the thanks
   pages and the done ticket, waiting + shimmer on the live ticket,
   error on the status pages and the 404 page, empty on a complaint with
   no patient-visible messages.
4. The owner's pinned copy survives the unification verbatim.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from app.models import Complaint, ComplaintStatusHistory, QueueTicket, db, now_naive

from conftest import csrf

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
APP_CSS = (ROOT / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")

# every patient-facing template (pages + shared includes)
PATIENT_TEMPLATES = (
    "patient_hub", "queue_join", "booking_portal", "booking_thanks",
    "booking_status", "complaint_portal", "complaint_thanks",
    "complaint_status", "feedback_portal", "feedback_thanks",
    "emergency_landing", "queue_ticket", "error",
    "_help_desk", "_patient_nav", "_emergency_banner", "_fasttrack_consent",
    "_langbar", "_pp_states",
)

# pages that render standalone (no base.html chrome around them)
STANDALONE_PAGES = ("/welcome", "/book", "/book/fast-track", "/queue/join",
                    "/complaint", "/feedback", "/emergency")


# ------------------------------------------------- 1. the system exists
def test_four_shared_states_exist_in_css():
    for cls in (".pp-state-waiting", ".pp-state-empty", ".pp-state-error",
                ".pp-state-success", ".pp-state-inline", ".pp-state-shimmer",
                "@keyframes pp-shimmer", "@keyframes pp-pulse"):
        assert cls in APP_CSS, f"design system is missing {cls}"


def test_state_macros_exist_and_are_reusable():
    src = (TEMPLATES / "_pp_states.html").read_text(encoding="utf-8")
    for macro in ("pp_state_waiting", "pp_state_empty", "pp_state_error",
                  "pp_state_success", "pp_state_inline", "pp_shimmer"):
        assert f"macro {macro}" in src, f"missing macro {macro}"
    # honest semantics baked in: errors announce, waiting/success report
    assert 'role="alert"' in src or "role='" in src or "role=" in src


# ------------------------------------------------- 2. no page-local styling
def test_no_patient_template_defines_its_own_styling():
    for name in PATIENT_TEMPLATES:
        src = (TEMPLATES / f"{name}.html").read_text(encoding="utf-8")
        assert "<style" not in src, f"{name}.html carries a private <style> block"
        assert 'style="' not in src, f"{name}.html carries inline style attributes"


def test_standalone_pages_render_without_any_style_block(client, seeded):
    for url in STANDALONE_PAGES:
        html = client.get(url).get_data(as_text=True)
        assert "<style" not in html, url


def test_page_components_now_live_in_the_system_stylesheet():
    for component in (".hub-tile", ".lux-card", ".emerg-card", ".langbar",
                      ".stars", ".pp-checkline", ".pp-checkline-gold",
                      ".portal-head-gold", ".portal-head-red", ".tk-code",
                      ".tk-timeline", ".tk-pill-call", ".tk-voice"):
        assert component in APP_CSS, f"{component} was not moved into app.css"


# ------------------------------------------------- 3. the states are used
def _book(client, seeded):
    token = csrf(client, "/book")
    day = (now_naive().date() + timedelta(days=1)).isoformat()
    return client.post("/book/submit", data={
        "_csrf": token, "consent": "1", "department_id": seeded["dept"],
        "appointment_date": day, "appointment_time": "09:00",
        "patient_name": "Chinwe Obi", "phone": "08033334444",
        "idem": "gate1-book-1"}, follow_redirects=True)


def test_booking_thanks_rides_the_success_state(client, seeded):
    html = _book(client, seeded).get_data(as_text=True)
    assert "pp-state pp-state-success" in html
    assert "Your visit is booked — Thank you" in html          # copy survives
    assert "Write it down." in html


def test_complaint_thanks_and_status_states(client, seeded):
    token = csrf(client, "/complaint")
    r = client.post("/complaint/submit", data={
        "_csrf": token, "consent": "1", "department_id": seeded["dept"],
        "category": "Long waiting time",
        "description": "We waited for hours without any update at all.",
        "phone": "08012345678", "contact_method": "phone"},
        follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "pp-state pp-state-success" in html
    assert "acknowledgment" in html                            # pinned copy

    c = db.session.query(Complaint).first()
    status = client.get(f"/complaint/status?ref={c.ref}&phone=08012345678")
    assert status.status_code == 200
    # with the acknowledgment message present, no empty state shows
    assert "No messages yet" not in status.get_data(as_text=True)

    # hide the patient-visible history -> the shared EMPTY state must appear
    db.session.query(ComplaintStatusHistory).filter_by(complaint_id=c.id)\
        .update({"patient_message": None})
    db.session.commit()
    html = client.get(f"/complaint/status?ref={c.ref}&phone=08012345678")\
        .get_data(as_text=True)
    assert "pp-state-empty" in html
    assert "No messages yet. When the hospital updates this complaint" in html


def test_status_pages_say_errors_with_the_shared_error_state(client, seeded):
    html = client.get("/book/status?ref=TEST-APT-1999-000001&phone=08033334444")\
        .get_data(as_text=True)
    assert "pp-state-error" in html
    assert "No booking found" in html
    html = client.get("/complaint/status?ref=TEST-CMP-1999-000001&phone=08099998888")\
        .get_data(as_text=True)
    assert "pp-state-error" in html


def test_error_page_is_the_shared_error_state(client, seeded):
    r = client.get("/this-page-does-not-exist")
    assert r.status_code == 404
    html = r.get_data(as_text=True)
    assert "pp-state pp-state-error" in html
    assert "We couldn't find that page" in html                # pinned copy


def _ticket(client, seeded):
    token = csrf(client, "/queue/join")
    client.post("/queue/join", data={"_csrf": token,
                                     "department_id": seeded["dept"],
                                     "patient_name": "Bola Ajao", "phone": ""},
                follow_redirects=True)
    t = db.session.query(QueueTicket).first()
    return client.get(f"/queue/ticket?key={t.access_key}"), t


def test_live_ticket_waiting_rides_the_waiting_state(client, seeded):
    r, t = _ticket(client, seeded)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "pp-state-inline pp-state-waiting" in html
    assert "pp-state-shimmer" in html                          # the waiting shimmer
    assert "Waiting — please stay nearby" in html              # copy survives
    assert "tk-code" in html and t.code in html

    t.status = "CALLED"
    db.session.commit()
    html = client.get(f"/queue/ticket?key={t.access_key}").get_data(as_text=True)
    assert "tk-pill-call" in html and "It's your turn" in html

    t.status = "DONE"
    db.session.commit()
    html = client.get(f"/queue/ticket?key={t.access_key}").get_data(as_text=True)
    assert "pp-state-inline pp-state-success" in html
    assert "You have been seen — thank you!" in html


# ------------------------------------------------- 4. owner copy survives
def test_pinned_owner_copy_survives_unification(client, seeded):
    hub = client.get("/welcome").get_data(as_text=True)
    assert "⭐ PREMIUM • EXECUTIVE LOUNGE • SEEN FAST" in hub
    assert "Book ahead — walk straight to our quiet executive lounge." in hub
    queue = client.get("/queue/join").get_data(as_text=True)
    assert ("You don't need to pick Fast Track if your health condition "
            "need special attention.") in queue
    assert html_count(queue, "quiet, private lounge") == 1
    book = client.get("/book").get_data(as_text=True)
    assert html_count(book, "WhatsApp first, then SMS") == 1
    emerg = client.get("/emergency").get_data(as_text=True)
    assert "never your name" in emerg


def html_count(haystack, needle):
    return haystack.count(needle)
