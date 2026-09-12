"""Full-system smoke crawl: every page, every role, every export.

Catches 500s, template errors and broken variables anywhere in the app.
"""
from datetime import timedelta

from app.models import (Appointment, Complaint, CorrectiveAction, DutyRoster,
                        Inspection, PatientFeedback, QrLocation, QueueTicket,
                        Referral, db, now_naive)

from conftest import csrf, login


def _setup_world(client, app, seeded):
    """Create one of every major record so detail pages have data."""
    today = now_naive().date()
    # complaint (public)
    tok = csrf(client, "/complaint")
    client.post("/complaint/submit", data={"consent": "1", 
        "_csrf": tok, "department_id": seeded["dept"], "category": "Long waiting time",
        "description": "Smoke test complaint for crawl coverage purposes.",
        "phone": "08011112222", "idem": "smoke-c1"}, follow_redirects=True)
    # booking (public)
    tok = csrf(client, "/book")
    client.post("/book/submit", data={"consent": "1", 
        "_csrf": tok, "department_id": seeded["dept"],
        "appointment_date": (today + timedelta(days=1)).isoformat(),
        "appointment_time": "09:00", "patient_name": "Smoke Patient",
        "phone": "08022223333", "idem": "smoke-b1"}, follow_redirects=True)
    # queue ticket (public)
    tok = csrf(client, "/queue/join")
    client.post("/queue/join", data={"_csrf": tok, "department_id": seeded["dept"],
                                     "patient_name": "Queue Smoke"}, follow_redirects=True)
    # feedback low (routes to recovery) + high
    tok = csrf(client, "/feedback")
    client.post("/feedback/submit", data={"consent": "1", "_csrf": tok, "rating": "1",
                                          "department_id": seeded["dept"],
                                          "comment": "Smoke low rating"}, follow_redirects=True)
    client.post("/feedback/submit", data={"consent": "1", "_csrf": csrf(client, "/feedback"), "rating": "5",
                                          "comment": "Smoke high rating"}, follow_redirects=True)
    # inspection (am1 on duty today)
    login(client, "am1")
    tok = csrf(client, "/inspections/new")
    client.post("/inspections/submit", data={
        "_csrf": tok, "department_id": seeded["dept"],
        "score_1": "4", "score_2": "2", "score_3": "4", "score_4": "4", "score_5": "4",
        "explanation_2": "Smoke test: toilets not clean during inspection."},
        follow_redirects=True)
    # corrective action
    insp = db.session.query(Inspection).first()
    with app.app_context():
        db.session.add(CorrectiveAction(org_id=seeded["org"], source_type="inspection",
                                        source_id=insp.id if insp else 0,
                                        finding="Smoke finding", action_required="Smoke action",
                                        owner_id=seeded["am"], deadline=today + timedelta(days=3)))
        db.session.commit()


def _assert_ok(resp, path):
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    assert b"Internal Server Error" not in resp.data, f"{path} raised a 500 template"


def test_admin_crawl(client, app, seeded):
    _setup_world(client, app, seeded)
    login(client, "admin")
    insp = db.session.query(Inspection).first()
    comp = db.session.query(Complaint).first()
    dept_report_id = seeded["dept"]
    loc = db.session.query(QrLocation).first()
    ref = db.session.query(Referral).first()
    paths = [
        "/", "/inspections", "/inspections/new", f"/inspections/{insp.id}",
        "/complaints", "/complaints?status=OPEN&escalated=1", f"/complaints/{comp.id}",
        "/corrective-actions", "/corrective-actions?mine=1", "/roster", "/roster/export",
        "/reports", "/bookings", "/queue", "/queue/screen", "/feedbacks",
        "/referrals",
        "/notifications", "/alert-settings",
        "/admin", "/admin/hospital", "/admin/users", "/admin/structure", "/admin/settings",
        "/admin/notifications", "/admin/audit", "/admin/audit?action=COMPLAINT",
        "/admin/health", "/admin/posters",
        f"/reports/departments/{dept_report_id}",
        f"/verify/{insp.verify_code}",
        f"/complaint/qr/{loc.code}.png",
        f"/r/{ref.code}",
        f"/r/{ref.code}.png",
    ]
    for p in paths:
        _assert_ok(client.get(p), p)


def test_admin_pdf_exports(client, app, seeded):
    _setup_world(client, app, seeded)
    login(client, "admin")
    exports = [
        "/reports/inspection-daily?format=pdf",
        "/reports/inspection-daily?format=csv",
        "/reports/weekly?format=pdf",
        "/reports/weekly?format=csv",
        "/reports/monthly?format=pdf",
        "/reports/complaints?format=pdf",
        "/reports/complaints?format=csv",
        "/reports/escalations?format=csv",
        "/reports/corrective-actions?format=csv",
        "/reports/corrective-actions?format=pdf",
        "/reports/compliance?format=pdf",
        "/reports/compliance?format=csv",
        f"/reports/departments/{seeded['dept']}?format=pdf",
        f"/reports/departments/{seeded['dept']}?format=csv",
        "/admin/posters/download?services=complaint,booking,queue,feedback",
        "/reports/referrals?format=csv",
        "/reports/referrals?format=pdf",
        "/admin/posters/download?services=referral",
    ]
    for p in exports:
        r = client.get(p)
        assert r.status_code == 200, f"{p} -> {r.status_code}"
        if "format=pdf" in p or "posters" in p:
            assert r.data[:4] == b"%PDF", f"{p} is not a PDF"
        else:
            assert len(r.data) > 0 and (b"," in r.data), f"{p} is not a CSV"


def test_md_crawl(client, app, seeded):
    _setup_world(client, app, seeded)
    login(client, "md")
    comp = db.session.query(Complaint).first()
    for p in ["/", "/reports", "/complaints", f"/complaints/{comp.id}", "/inspections",
              "/corrective-actions", "/feedbacks", "/referrals", "/roster", "/bookings", "/queue",
              "/notifications", "/alert-settings"]:
        _assert_ok(client.get(p), p)
    # MD must NOT reach super-admin pages
    for p in ["/admin", "/admin/users"]:
        assert client.get(p).status_code == 403, f"MD reached {p}"


def test_am_crawl(client, app, seeded):
    _setup_world(client, app, seeded)
    login(client, "am1")
    for p in ["/", "/inspections/new", "/inspections", "/complaints", "/bookings", "/queue",
              "/corrective-actions", "/feedbacks", "/referrals", "/roster", "/notifications",
              "/alert-settings"]:
        _assert_ok(client.get(p), p)
    assert client.get("/admin").status_code == 403


def test_hod_crawl(client, app, seeded):
    _setup_world(client, app, seeded)
    login(client, "hod1")
    comp = db.session.query(Complaint).first()
    # HOD of Emergency is triage, not front desk — bookings/queue/referrals/reports limited per v1.7.18
    for p in ["/", "/complaints", f"/complaints/{comp.id}", "/corrective-actions",
              "/feedbacks", "/roster", "/notifications"]:
        _assert_ok(client.get(p), p)
    # These may be 403 for clinical HOD — correct per v1.7.18 scope (front desk / management only)
    for p in ["/bookings", "/queue", "/referrals", "/reports"]:
        r = client.get(p)
        assert r.status_code in (200, 403), f"{p} -> {r.status_code} (HOD Emergency should be limited)"
    for p in ["/admin", "/inspections/new"]:
        assert client.get(p).status_code == 403, f"HOD reached {p}"


def test_public_pages_crawl(client, seeded):
    for p in ["/login", "/complaint", "/complaint/status", "/complaint/status?ref=NOPE",
              "/book", "/book/status", "/feedback", "/feedback/thanks?rating=5",
              "/queue/join", "/queue/screen", "/api/v1/health"]:
        _assert_ok(client.get(p), p)
    # verification with a bad code is a clean 404 page, not a crash
    assert client.get("/verify/DOESNOTEXIST").status_code == 404
    # 404 page renders gracefully
    assert client.get("/no/such/page").status_code == 404


def test_session_expiry_and_bad_input(client, seeded):
    # expired/unknown ids return clean 404s, not crashes
    login(client, "admin")
    for p in ["/inspections/999999", "/complaints/999999", "/reports/archive/999999/download"]:
        assert client.get(p).status_code == 404, p
    # POST-only routes with unknown ids also 404 cleanly
    tok = csrf(client, "/queue")
    for p in ["/bookings/999999/arrive", "/queue/999999/finish",
              "/complaints/999999/update"]:
        r = client.post(p, data={"_csrf": tok, "action_type": "acknowledge"})
        assert r.status_code == 404, f"{p} -> {r.status_code}"
    # invalid filters don't crash
    for p in ["/inspections?from=not-a-date&to=also-bad", "/complaints?status=BOGUS",
              "/bookings?date=garbage", "/reports/monthly?month=9999-99"]:
        assert client.get(p).status_code == 200, p
