"""Billing Point and Megalex / Paying Point — the money desks.

Closes a real control weakness: the receptionist who took a patient's details
was also the only record that their money had arrived.
"""
from app import reception
from app.models import AuditLog, ReceptionIntake, User, db
from tests.conftest import csrf, login

_seq = [0]


def _intake(org_id, stage="BILLING", surname="Abatan", first="Folake"):
    _seq[0] += 1
    row = ReceptionIntake(org_id=org_id, ref=f"RCP-CASH-{_seq[0]:05d}",
                          surname=surname, first_name=first, sex="F",
                          age_years=40, payer_type="LAHSMA",
                          payer_number="LAS/2026/771", stage=stage,
                          needs_blood_sugar=True)
    db.session.add(row)
    db.session.flush()
    return row


def _login(client, app, seeded, role="ADMIN_MANAGER"):
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"], role=role).first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


# ------------------------------------------------------------------ the desks
def test_each_desk_shows_only_its_own_queue(app, client, seeded):
    """A cashier must not have to read the whole hospital's reception list."""
    with app.app_context():
        org_id = seeded["org"]
        _intake(org_id, "BILLING", "Needsbill", "P")
        _intake(org_id, "PAYMENT", "Needspay", "P")
        _intake(org_id, "RECEPTION", "Stillatfront", "P")
        db.session.commit()

    _login(client, app, seeded)
    billing = client.get("/billing").get_data(as_text=True)
    assert "NEEDSBILL" in billing.upper()
    assert "NEEDSPAY" not in billing.upper()
    assert "STILLATFRONT" not in billing.upper()

    pay = client.get("/paypoint").get_data(as_text=True)
    assert "NEEDSPAY" in pay.upper()
    assert "NEEDSBILL" not in pay.upper()


def test_billing_sends_the_patient_to_the_paying_point(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        iid = _intake(org_id, "BILLING").id
        db.session.commit()

    _login(client, app, seeded)
    r = client.post(f"/billing/{iid}/done",
                    data={"_csrf": csrf(client, "/billing"),
                          "bill_ref": "BILL-2026-001"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "paying point" in r.get_data(as_text=True).lower()

    with app.app_context():
        row = db.session.get(ReceptionIntake, iid)
        assert row.stage == "PAYMENT"
        assert row.bill_ref == "BILL-2026-001"
        assert row.billed_at is not None


def test_the_pay_point_records_payment_and_frees_hims(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        iid = _intake(org_id, "PAYMENT").id
        db.session.commit()

    _login(client, app, seeded)
    r = client.post(f"/paypoint/{iid}/paid",
                    data={"_csrf": csrf(client, "/paypoint"),
                          "payment_ref": "MGX-99887"},
                    follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        row = db.session.get(ReceptionIntake, iid)
        assert row.stage == "PAID"
        assert row.payment_ref == "MGX-99887"
        assert row.paid_at is not None


# ------------------------------------------------------------------ the control
def test_the_payment_is_recorded_under_the_CASHIERS_name(app, client, seeded):
    """Separation of duties — the whole reason these desks exist.

    Whoever handles the money must not be merely implied by the receptionist's
    entry. The audit trail must name the person who pressed "payment received".
    """
    with app.app_context():
        from app.models import Department
        org_id = seeded["org"]
        iid = _intake(org_id, "PAYMENT").id
        # A second person, distinct from whoever took the details.
        # v1.7.18: HOD needs a money department (Finance/Billing) to see cashdesk
        dept = db.session.query(Department).filter_by(org_id=org_id).first()
        if not dept:
            dept = Department(org_id=org_id, name="Finance", code="FIN")
            db.session.add(dept)
            db.session.flush()
        # Ensure department name matches money desk for permission
        if "financ" not in dept.name.lower() and "bill" not in dept.name.lower():
            dept.name = "Finance & Billing"
        cashier = User(org_id=org_id, username="cashier1",
                       name="Ngozi Cashier", role="HOD", department_id=dept.id)
        cashier.set_password("Passw0rd!x")
        cashier.must_change_password = False
        db.session.add(cashier)
        db.session.commit()

    login(client, "cashier1")
    client.post(f"/paypoint/{iid}/paid",
                data={"_csrf": csrf(client, "/paypoint"),
                      "payment_ref": "MGX-12345"},
                follow_redirects=True)

    with app.app_context():
        row = (db.session.query(AuditLog)
               .filter_by(action="PAYPOINT_PAYMENT_RECEIVED").one())
        who = db.session.get(User, row.user_id)
        assert who.username == "cashier1", (
            "the payment was not attributed to the person who took the money")


def test_a_patient_cannot_be_paid_for_twice(app, client, seeded):
    """A double-click must not create a second payment record."""
    with app.app_context():
        iid = _intake(seeded["org"], "PAYMENT").id
        db.session.commit()

    _login(client, app, seeded)
    for _ in range(2):
        client.post(f"/paypoint/{iid}/paid",
                    data={"_csrf": csrf(client, "/paypoint"),
                          "payment_ref": "MGX-1"}, follow_redirects=True)

    with app.app_context():
        assert db.session.query(AuditLog).filter_by(
            action="PAYPOINT_PAYMENT_RECEIVED").count() == 1


def test_a_desk_refuses_a_patient_who_is_not_queued_for_it(app, client, seeded):
    """Order matters: nobody pays before a bill is raised."""
    with app.app_context():
        iid = _intake(seeded["org"], "RECEPTION").id
        db.session.commit()

    _login(client, app, seeded)
    r = client.post(f"/paypoint/{iid}/paid",
                    data={"_csrf": csrf(client, "/paypoint"),
                          "payment_ref": "MGX-1"}, follow_redirects=True)
    assert "not waiting at the paying point" in r.get_data(as_text=True).lower()
    with app.app_context():
        assert db.session.get(ReceptionIntake, iid).stage == "RECEPTION"


def test_the_desks_hold_no_money_amounts(app, seeded):
    """Megalex is the revenue system and must stay the single financial truth.

    Storing amounts here would create a second, divergent set of books that
    nobody reconciles — worse than storing none at all.
    """
    banned = {"amount", "amount_paid", "price", "cost", "fee", "total",
              "balance", "change", "cash", "naira", "ledger"}
    columns = {c.name for c in ReceptionIntake.__table__.columns}
    leaked = banned & columns
    assert not leaked, f"money amounts appeared on the intake: {leaked}"


# ------------------------------------------------------------------ voice
def test_each_desk_calls_the_patient_onward_by_name(app, client, seeded):
    from app.models import AppNotification
    with app.app_context():
        iid = _intake(seeded["org"], "BILLING").id
        db.session.commit()

    _login(client, app, seeded)
    client.post(f"/billing/{iid}/done",
                data={"_csrf": csrf(client, "/billing")}, follow_redirects=True)

    with app.app_context():
        said = " ".join(n.body for n in db.session.query(AppNotification).all()).lower()
        assert "folake" in said, "the patient was not called by name"
        assert "paying point" in said


# ------------------------------------------------------------------ tracking
def test_the_desks_measure_their_own_step(app, client, seeded):
    """Otherwise 'how long does the Paying Point take?' is unanswerable."""
    from app.models import JourneySegment
    with app.app_context():
        iid = _intake(seeded["org"], "BILLING").id
        db.session.commit()

    _login(client, app, seeded)
    client.post(f"/billing/{iid}/done",
                data={"_csrf": csrf(client, "/billing")}, follow_redirects=True)

    with app.app_context():
        stages = {r.stage for r in db.session.query(JourneySegment).all()}
        assert "PAYMENT" in stages, "the Paying Point step is not being measured"


# ------------------------------------------------------------------ security
def test_the_money_desks_require_a_login(app, client):
    for path in ("/billing", "/paypoint"):
        r = client.get(path)
        assert r.status_code in (301, 302), f"{path} was readable logged out"


def test_another_hospitals_patient_is_refused(app, client, seeded):
    from app.models import Organization
    with app.app_context():
        other = Organization(code="OTHER2", name="Other Hospital")
        db.session.add(other)
        db.session.flush()
        iid = _intake(other.id, "PAYMENT").id
        db.session.commit()

    _login(client, app, seeded)
    r = client.post(f"/paypoint/{iid}/paid",
                    data={"_csrf": csrf(client, "/paypoint"),
                          "payment_ref": "X"})
    assert r.status_code == 404


def test_an_empty_bill_box_is_blank_not_the_word_None(app, client, seeded):
    """Jinja renders a Python None as the literal text "None".

    Found by looking at the screen, not by a passing test: the cashier saw a
    box pre-filled with "None" and would have typed the real number after it.
    """
    with app.app_context():
        row = _intake(seeded["org"], "BILLING")
        row.bill_ref = None
        db.session.commit()

    _login(client, app, seeded)
    body = client.get("/billing").get_data(as_text=True)
    assert 'value="None"' not in body, \
        'the bill box was pre-filled with the word "None"'
