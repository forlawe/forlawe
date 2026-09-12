"""LAHSMA desk — simple clearance tracking, just flow tracking.

Founder clarification: \"limited to seeing patient together with policy numbers
and attend to them with basic minimum by issuing clearance. just like billing
issues Bill to patients (just patient flow tracking) no serious work because
LAHSMA has their web application for patient and policy management.\"
"""
from app import lahsma
from app.models import Patient, PatientVisit, VisitOnward, db, User
from tests.conftest import csrf, login


def _make_patient(org_id, payer_number="LAS/2026/001", payer_type="LAHSMA"):
    p = Patient(
        org_id=org_id,
        hospital_number=f"IJD/2026/{payer_number[-3:]}",
        surname="ABATAN",
        first_name="Folake",
        sex="F",
        age_years=34,
        payer_type=payer_type,
        payer_number=payer_number,
        payer_name="LAHSMA",
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_visit(org_id, patient_id):
    v = PatientVisit(
        org_id=org_id,
        patient_id=patient_id,
        visit_no=f"V-{patient_id:05d}",
        status="ONWARD",
    )
    db.session.add(v)
    db.session.flush()
    return v


def _make_step(org_id, visit_id, dest="LAHSMA", status="PENDING"):
    s = VisitOnward(org_id=org_id, visit_id=visit_id, destination=dest, status=status)
    db.session.add(s)
    db.session.flush()
    return s


def _login(client, app, seeded, role="ADMIN_MANAGER"):
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"], role=role).first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


# ------------------------------------------------------------------ engine
def test_lahsma_pending_shows_patient_and_policy(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _make_patient(org_id, "LAS/2026/771")
        v = _make_visit(org_id, p.id)
        _make_step(org_id, v.id, "LAHSMA", "PENDING")
        db.session.commit()

        rows = lahsma.pending(org_id)
        assert len(rows) == 1
        assert rows[0]["patient"].payer_number == "LAS/2026/771"
        assert rows[0]["patient"].full_name
        assert rows[0]["waited"] >= 0


def test_lahsma_clearance_marks_done(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _make_patient(org_id)
        v = _make_visit(org_id, p.id)
        step = _make_step(org_id, v.id, "LAHSMA", "PENDING")
        db.session.commit()

        closed = lahsma.issue_clearance(step, user_id=1)
        db.session.commit()
        assert step.status == "DONE"
        assert closed is True
        assert v.status == "CLOSED"


def test_lahsma_does_not_auto_bill(app, seeded):
    """Clearance does NOT create a billing step — just flow tracking."""
    with app.app_context():
        org_id = seeded["org"]
        p = _make_patient(org_id)
        v = _make_visit(org_id, p.id)
        step = _make_step(org_id, v.id, "LAHSMA", "PENDING")
        db.session.commit()

        lahsma.issue_clearance(step)
        db.session.commit()

        # No billing step auto-created
        billing_steps = (
            db.session.query(VisitOnward)
            .filter_by(visit_id=v.id, destination="BILLING")
            .all()
        )
        assert len(billing_steps) == 0


def test_lahsma_holds_no_money(app, seeded):
    banned = {"amount", "price", "cost", "fee", "total", "balance"}
    cols = {c.name for c in VisitOnward.__table__.columns}
    assert not (banned & cols)


# ------------------------------------------------------------------ routes
def test_lahsma_desk_route_answers(app, client, seeded):
    _login(client, app, seeded)
    r = client.get("/lahsma")
    assert r.status_code == 200
    assert "LAHSMA" in r.get_data(as_text=True)


def test_lahsma_clear_route(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        p = _make_patient(org_id, "LAS/2026/999")
        v = _make_visit(org_id, p.id)
        step = _make_step(org_id, v.id, "LAHSMA", "PENDING")
        db.session.commit()
        sid = step.id

    _login(client, app, seeded)
    r = client.post(f"/lahsma/{sid}/clear", data={"_csrf": csrf(client, "/lahsma")}, follow_redirects=True)
    assert r.status_code == 200
    assert "Clearance issued" in r.get_data(as_text=True)

    with app.app_context():
        s = db.session.get(VisitOnward, sid)
        assert s.status == "DONE"


def test_lahsma_requires_login(app, client):
    r = client.get("/lahsma")
    assert r.status_code in (301, 302)


def test_hims_shows_paid_waiting(app, client, seeded):
    """HIMS is most appropriate to open folder after payment — must show PAID list."""
    from app.models import ReceptionIntake

    with app.app_context():
        org_id = seeded["org"]
        intake = ReceptionIntake(
            org_id=org_id,
            ref="RCP-TEST-001",
            surname="Bello",
            first_name="Musa",
            sex="M",
            age_years=40,
            payer_type="LAHSMA",
            payer_number="LAS/2026/123",
            stage="PAID",
            nok_name="Aisha",
            nok_phone="08031112222",
            nok_relationship="Wife",
        )
        db.session.add(intake)
        db.session.commit()

    _login(client, app, seeded)
    r = client.get("/hims/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "PAID" in body
    assert "Bello" in body
    assert "Open folder" in body
