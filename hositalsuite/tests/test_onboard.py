"""Build 3: a new hospital can be opened from a phone, without a developer."""
from app.models import Branch, Department, Organization, User, db
from app.services import get_setting

from conftest import csrf, login


def _payload(**extra):
    data = {
        "name": "Sunrise Clinic",
        "code": "SUN",
        "phone": "08035550001",
        "address": "Ikeja",
        "email": "hello@sunrise.test",
        "admin_name": "Ada Sunrise",
        "username": "sun.admin",
        "admin_phone": "08035550002",
        "password": "SunPass12!",
        "confirm": "SunPass12!",
        "brand_primary": "#112233",
        "brand_accent": "#445566",
        "brand_gold": "#FFCC00",
        "main_name": "Main",
        "annex_name": "Annex",
        "install_departments": "1",
        "voice_lang": "en",
    }
    data.update(extra)
    return data


def test_empty_site_opens_the_setup_walk(app):
    # Empty site — no seeded org, so no code needed
    # Use fresh client without seeded fixture
    from app.models import db
    with app.app_context():
        db.drop_all()
        db.create_all()
    client = app.test_client()
    r = client.get("/start")
    assert r.status_code == 200
    assert b"Set up your hospital" in r.data
    assert b"No code needed" in r.data
    home = client.get("/welcome", follow_redirects=False)
    assert home.status_code == 302
    assert "/start" in home.headers["Location"]


def test_first_hospital_is_created_and_admin_is_signed_in(app):
    from app.models import db as _db
    with app.app_context():
        _db.drop_all()
        _db.create_all()
    client = app.test_client()
    token = csrf(client, "/start")
    r = client.post("/start", data={**_payload(), "_csrf": token}, follow_redirects=False)
    assert r.status_code == 302, f"Expected 302, got {r.status_code} — {r.data.decode()[:2000]}"
    assert r.headers["Location"].endswith("/start/done")
    with app.app_context():
        org = _db.session.query(Organization).filter_by(code="SUN").one()
        admin = _db.session.query(User).filter_by(username="sun.admin").one()
        assert admin.org_id == org.id
        assert admin.role == "SUPER_ADMIN"
        assert admin.check_password("SunPass12!")
        assert get_setting(org.id, "brand_primary") == "#112233"
        assert get_setting(org.id, "onboarding_complete") is True
        sites = _db.session.query(Branch).filter_by(org_id=org.id).all()
        assert {b.code for b in sites} == {"MAIN", "ANNEX"}
        assert _db.session.query(Department).filter_by(org_id=org.id).count() >= 5
    done = client.get("/start/done")
    assert done.status_code == 200
    assert b"Your hospital is ready" in done.data
    with app.app_context():
        org = _db.session.query(Organization).filter_by(code="SUN").one()
        assert get_setting(org.id, "onboard_guide") is True
    dash = client.get("/")
    assert dash.status_code == 200
    assert b"do these next" in dash.data


def test_second_hospital_needs_a_setup_code(client, seeded):
    r = client.get("/start")
    assert b"Setup code" in r.data
    token = csrf(client, "/start")
    bad = client.post("/start", data={**_payload(), "_csrf": token}, follow_redirects=True)
    assert bad.status_code == 422
    assert b"setup code" in bad.data.lower()
    assert db.session.query(Organization).filter_by(code="SUN").first() is None


def test_setup_code_opens_a_second_hospital(client, seeded):
    login(client, "admin")
    token = csrf(client, "/admin/security")
    minted = client.post("/admin/onboard-invite", data={"_csrf": token},
                         follow_redirects=True)
    assert minted.status_code == 200
    # The code is flashed once: "Setup code for a new hospital: ABCD-1234."
    body = minted.data.decode()
    assert "Setup code for a new hospital:" in body
    code = body.split("Setup code for a new hospital:")[1].split(".")[0].strip()
    client.post("/logout", data={"_csrf": csrf(client, "/")})
    token = csrf(client, "/start")
    r = client.post("/start", data={**_payload(), "invite": code, "_csrf": token},
                    follow_redirects=False)
    assert r.status_code == 302
    assert db.session.query(Organization).filter_by(code="SUN").one()
    # code is one-use
    client.post("/logout", data={"_csrf": csrf(client, "/")})
    token = csrf(client, "/start")
    again = client.post("/start", data={**_payload(code="MOO", username="moo.admin"),
                                        "invite": code, "_csrf": token},
                        follow_redirects=True)
    assert again.status_code == 422


def test_sign_in_name_of_another_hospital_is_allowed(client, seeded):
    """F-021: usernames are scoped per hospital — a NEW hospital may choose
    "admin" even though the first hospital already uses it. (Inside one
    hospital the name stays unique; see test_f021_per_tenant_usernames.py.)"""
    login(client, "admin")
    token = csrf(client, "/admin/security")
    minted = client.post("/admin/onboard-invite", data={"_csrf": token},
                         follow_redirects=True)
    code = minted.data.decode().split("Setup code for a new hospital:")[1].split(".")[0].strip()
    client.post("/logout", data={"_csrf": csrf(client, "/")})
    token = csrf(client, "/start")
    r = client.post("/start", data={**_payload(username="admin"), "invite": code,
                                    "_csrf": token}, follow_redirects=True)
    assert r.status_code == 200
    assert b"already taken" not in r.data


def test_short_sign_in_name_is_still_rejected(client, seeded):
    login(client, "admin")
    token = csrf(client, "/admin/security")
    minted = client.post("/admin/onboard-invite", data={"_csrf": token},
                         follow_redirects=True)
    code = minted.data.decode().split("Setup code for a new hospital:")[1].split(".")[0].strip()
    client.post("/logout", data={"_csrf": csrf(client, "/")})
    token = csrf(client, "/start")
    r = client.post("/start", data={**_payload(username="ab"), "invite": code,
                                    "_csrf": token}, follow_redirects=True)
    assert r.status_code == 422
    assert b"at least 3 letters" in r.data


def test_weak_password_is_rejected(client):
    token = csrf(client, "/start")
    r = client.post("/start", data={**_payload(password="short", confirm="short"),
                                    "_csrf": token}, follow_redirects=True)
    assert r.status_code == 422
    assert db.session.query(Organization).filter_by(code="SUN").first() is None


def test_sales_points_at_setup_login_does_not(client):
    """A stranger on Sign in must not see 'open a new hospital'."""
    sales = client.get("/sales")
    assert b"/start" in sales.data
    login_page = client.get("/login")
    assert b"/start" not in login_page.data
    assert b"Sign up" in login_page.data
    assert b"Forgot password" in login_page.data
