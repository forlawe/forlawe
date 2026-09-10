"""Phone look: the PWA must not freeze an old stylesheet, and logos must stay small."""


def test_login_stylesheet_is_versioned(client, seeded):
    html = client.get("/login").get_data(as_text=True)
    assert "app.css?v=" in html
    assert "auth.js?v=" in html
    assert "auth-logo" in html
    assert "pw-eye" in html


def test_service_worker_is_network_first_and_versioned(client, seeded):
    js = client.get("/sw.js").get_data(as_text=True)
    assert "CSS/JS must be network-first" in js
    from flask import current_app
    ver = str(current_app.config.get("APP_VERSION") or "1.7.12").replace(".", "-")
    assert f"hs-shell-{ver}" in js


def test_css_caps_the_logo(client):
    css = client.get("/static/css/app.css").get_data(as_text=True)
    assert "max-width:64px" in css
    assert "nav-toggle" in css


def test_staff_pages_have_a_phone_menu_button(client, seeded):
    from conftest import login
    login(client, "admin")
    page = client.get("/admin/hospital").get_data(as_text=True)
    assert "nav-toggle" in page
    assert "app.css?v=" in page


def test_signup_with_hospital_code_joins_that_hospital(client, seeded, app):
    from app.models import Organization, User, db
    html = client.get("/signup/TEST").get_data(as_text=True)
    assert "Sign up" in html
    assert 'action="/signup/TEST"' in html
    from conftest import csrf
    client.post("/signup/TEST", data={
        "_csrf": csrf(client, "/signup/TEST"),
        "name": "Bola Nurse",
        "username": "bola.nurse",
        "email": "bola.nurse@gmail.com",
        "password": "QuietLake#4",
        "confirm_password": "QuietLake#4",
    }, follow_redirects=True)
    u = db.session.query(User).filter_by(username="bola.nurse").first()
    org = db.session.query(Organization).filter_by(code="TEST").first()
    assert u is not None
    assert u.org_id == org.id


def test_second_hospital_is_not_joined_from_bare_signup(client, seeded, app):
    from app.models import Organization, db
    extra = Organization(code="GHE", name="General Hospital Elepe")
    db.session.add(extra)
    db.session.commit()
    r = client.get("/signup", follow_redirects=False)
    assert r.status_code == 404
    assert b"more than one hospital" in r.data
    ok = client.get("/signup/GHE")
    assert ok.status_code == 200
    assert b"General Hospital Elepe" in ok.data
