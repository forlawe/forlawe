"""No admin door for a patient or an ordinary staff member."""
from app.models import User, db
from conftest import csrf, login


# Pages a visitor / patient may open. Anything else staff-only must bounce.
PATIENT_OK = (
    "/welcome", "/login", "/signup", "/signup/TEST", "/request-access", "/book", "/queue/join",
    "/complaint", "/feedback", "/chat", "/privacy", "/privacy/request",
    "/book/status", "/complaint/status", "/sales",
)

STAFF_ONLY = (
    "/dashboard", "/admin", "/admin/users", "/admin/settings", "/admin/hospital",
    "/admin/structure", "/admin/security", "/admin/branches", "/admin/tv",
    "/hims/", "/reception/", "/billing", "/paypoint", "/triage/",
    "/consulting-room", "/reports", "/inspections", "/complaints",
    "/attendance/today", "/admin/roles",
)


def test_patient_pages_stay_open(client, seeded):
    for path in PATIENT_OK:
        r = client.get(path, follow_redirects=False)
        assert r.status_code in (200, 302), f"{path} broke for a visitor ({r.status_code})"


def test_staff_pages_refuse_a_visitor(client, seeded):
    for path in STAFF_ONLY:
        r = client.get(path, follow_redirects=False)
        assert r.status_code in (302, 401, 403), (
            f"visitor reached {path} with {r.status_code}")
        if r.status_code == 302:
            loc = r.headers.get("Location", "")
            assert "/login" in loc or loc.endswith("/start"), (
                f"visitor was sent to {loc} from {path}, not sign-in")


def test_ordinary_staff_cannot_open_admin(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    u = User(org_id=seeded["org"], username="plain.staff", name="Plain Staff",
             role="STAFF", approved=True, email_verified=True,
             profile_completed=True)
    u.set_password("QuietLake#4")
    u.must_change_password = False
    db.session.add(u)
    db.session.commit()
    r = client.post("/login", data={
        "_csrf": csrf(client, "/login"),
        "username": "plain.staff",
        "password": "QuietLake#4",
    }, follow_redirects=False)
    assert r.status_code == 302
    for path in ("/admin", "/admin/users", "/admin/settings", "/admin/security",
                 "/admin/tv", "/admin/branches"):
        got = client.get(path, follow_redirects=False)
        assert got.status_code == 403, f"STAFF opened {path} ({got.status_code})"


def test_cannot_self_assign_super_admin(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    from app import accounts
    from app.models import User, db
    r = client.post("/request-access", data={
        "_csrf": csrf(client, "/request-access"),
        "name": "Sneaky Person",
        "username": "sneaky.one",
        "email": "sneaky.one@gmail.com",
        "password": "QuietLake#4",
        "confirm_password": "QuietLake#4",
    }, follow_redirects=True)
    u = db.session.query(User).filter_by(username="sneaky.one").first()
    otp = accounts.issue_email_code(u)
    db.session.commit()
    client.post("/verify-email", data={
        "_csrf": csrf(client, "/verify-email"), "code": otp,
    }, follow_redirects=True)
    tok = csrf(client, "/staff-card")
    client.post("/staff-card", data={
        "_csrf": tok,
        "name": "Sneaky Person",
        "department_id": seeded["dept"],
        "requested_role": "SUPER_ADMIN",
        "cadre": "Clerk",
    }, follow_redirects=True)
    u = db.session.query(User).filter_by(username="sneaky.one").first()
    assert u.role == "STAFF"
    assert u.requested_role != "SUPER_ADMIN"


def test_new_pages_are_linked(client, seeded):
    login_html = client.get("/login").get_data(as_text=True)
    assert "/signup" in login_html
    assert "/forgot-password" in login_html
    assert "/staff-card" not in login_html
    assert "/start" not in login_html
    assert "pw-eye" in login_html
    signup = client.get("/signup")
    assert signup.status_code == 200
    sign_html = signup.get_data(as_text=True)
    assert "Sign up" in sign_html
    assert "pw-eye" in sign_html
    card = client.get("/staff-card", follow_redirects=False)
    assert card.status_code == 302
    assert "/login" in card.headers.get("Location", "")
    users = login(client, "admin")
    assert users.status_code == 302
    page = client.get("/admin/users").get_data(as_text=True)
    assert "staff card" in page.lower() or "Approve" in page
    assert "/signup" in page
    assert "/start" in page
