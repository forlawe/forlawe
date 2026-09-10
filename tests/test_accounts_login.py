"""Staff sign-in: own hard password, real email, activation, admin OK."""
from app import accounts
from app.accounts import (email_allowed_for_hospital, password_strength_errors)
from app.models import PasswordReset, User, db
from conftest import csrf, login


def test_password_must_be_hard_to_guess():
    assert password_strength_errors("short")
    assert password_strength_errors("NoNumber!!")
    assert password_strength_errors("nonumber1!")
    assert password_strength_errors("NoSymbol12")
    assert password_strength_errors("Password1!")
    assert password_strength_errors("NurseJane1!", username="jane")
    assert not password_strength_errors("BlueGate#19", username="jane")


def test_only_recognised_email_is_accepted():
    assert email_allowed_for_hospital("ada@gmail.com", None) == []
    assert email_allowed_for_hospital("ada@yahoo.com", None) == []
    assert email_allowed_for_hospital("ada@outlook.com", None) == []
    assert email_allowed_for_hospital("ada@health.gov.ng", None) == []
    assert email_allowed_for_hospital("ada@mailinator.com", None)
    assert email_allowed_for_hospital("not-an-email", None)
    assert email_allowed_for_hospital("ada@randomshop.xyz", None)
    assert email_allowed_for_hospital("ada@ijede.hospital",
                                      "info@ijede.hospital") == []


def test_existing_staff_still_sign_in_without_new_email_steps(client, seeded):
    """A deploy must not lock Ijede out."""
    r = login(client, "hod1")
    assert r.status_code == 302
    assert client.get("/dashboard").status_code == 200


def test_sign_in_with_email_works(client, seeded):
    u = db.session.query(User).filter_by(username="hod1").first()
    u.email = "hannah.hod@gmail.com"
    db.session.commit()
    r = client.post("/login", data={
        "_csrf": csrf(client, "/login"),
        "username": "hannah.hod@gmail.com",
        "password": "Passw0rd!x",
    }, follow_redirects=False)
    assert r.status_code == 302


def test_request_access_then_code_then_admin_then_login(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    r = client.get("/request-access")
    assert r.status_code == 200
    r = client.post("/request-access", data={
        "_csrf": csrf(client, "/request-access"),
        "name": "Bisi Nurse",
        "username": "bisi.nurse",
        "email": "bisi.nurse@gmail.com",
        "password": "QuietLake#4",
        "confirm_password": "QuietLake#4",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Activate your email" in r.data
    u = db.session.query(User).filter_by(username="bisi.nurse").first()
    assert u is not None
    assert u.approved is False
    assert u.email_verified is False
    assert u.profile_completed is False
    otp = accounts.issue_email_code(u)
    db.session.commit()

    r = client.post("/verify-email", data={
        "_csrf": csrf(client, "/verify-email"),
        "code": otp,
    }, follow_redirects=False)
    assert r.status_code == 302
    assert "/staff-card" in r.headers.get("Location", "")
    u = db.session.query(User).filter_by(username="bisi.nurse").first()
    assert u.email_verified is True
    assert u.approved is False

    r = client.post("/staff-card", data={
        "_csrf": csrf(client, "/staff-card"),
        "name": "Bisi Adebayo Nurse",
        "department_id": seeded["dept"],
        "cadre": "Nursing Officer",
        "requested_role": "HOD",
        "special_duty": "Night supervisor",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Staff card sent" in r.data
    u = db.session.query(User).filter_by(username="bisi.nurse").first()
    assert u.profile_completed is True
    assert u.role == "STAFF"
    assert u.requested_role == "HOD"
    assert u.approved is False

    r = client.post("/login", data={
        "_csrf": csrf(client, "/login"),
        "username": "bisi.nurse",
        "password": "QuietLake#4",
    }, follow_redirects=True)
    assert r.status_code == 403
    assert b"waiting for administrator approval" in r.data

    login(client, "admin")
    client.post(f"/admin/users/{u.id}/approve",
                data={"_csrf": csrf(client, "/admin/users"), "role": "HOD"},
                follow_redirects=True)
    client.post("/logout", data={"_csrf": csrf(client, "/dashboard")})
    u = db.session.query(User).filter_by(username="bisi.nurse").first()
    assert u.role == "HOD"

    r = client.post("/login", data={
        "_csrf": csrf(client, "/login"),
        "username": "bisi.nurse",
        "password": "QuietLake#4",
    }, follow_redirects=False)
    assert r.status_code == 302
    assert client.get("/dashboard").status_code == 200


def test_unverified_admin_created_user_cannot_enter(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    login(client, "admin")
    client.post("/admin/users/create", data={
        "_csrf": csrf(client, "/admin/users"),
        "username": "kemi.ward",
        "name": "Kemi Ward",
        "role": "STAFF",
        "email": "kemi.ward@yahoo.com",
        "password": "QuietLake#4",
    }, follow_redirects=True)
    u = db.session.query(User).filter_by(username="kemi.ward").first()
    assert u.approved is False
    assert u.email_verified is False
    assert u.profile_completed is False
    client.post("/logout", data={"_csrf": csrf(client, "/dashboard")})

    r = client.post("/login", data={
        "_csrf": csrf(client, "/login"),
        "username": "kemi.ward",
        "password": "QuietLake#4",
    }, follow_redirects=True)
    assert b"Activate your email" in r.data

    login(client, "admin")
    client.post(f"/admin/users/{u.id}/confirm-email",
                data={"_csrf": csrf(client, "/admin/users")},
                follow_redirects=True)
    u = db.session.query(User).filter_by(username="kemi.ward").first()
    assert u.email_verified is True


def test_fake_mailbox_and_weak_password_are_refused(client, seeded):
    r = client.post("/request-access", data={
        "_csrf": csrf(client, "/request-access"),
        "name": "Ghost",
        "username": "ghost.one",
        "email": "ghost@mailinator.com",
        "password": "password",
        "confirm_password": "password",
    })
    assert r.status_code == 422
    assert db.session.query(User).filter_by(username="ghost.one").first() is None
