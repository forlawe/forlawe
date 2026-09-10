"""Activation mail must actually try a web van, not a blocked SMTP port."""
from app import accounts, mailer
from app.models import User, db

from conftest import csrf, login


def test_mail_is_off_until_a_key_is_set(app):
    with app.app_context():
        assert mailer.active_provider() == "off"
        assert mailer.is_configured() is False
        ok, why = mailer.send_mail("a@gmail.com", "Hi", "body 123456")
        assert ok is False
        assert "not set up" in why


def test_resend_is_used_when_the_key_is_present(app, monkeypatch):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["MAIL_FROM"] = "Hospital <noreply@hospital.ng>"
    seen = {}

    class _R:
        status_code = 200
        text = "{}"

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["json"] = json
        seen["auth"] = (headers or {}).get("Authorization")
        return _R()

    monkeypatch.setattr("requests.post", fake_post)
    with app.app_context():
        assert mailer.active_provider() == "resend"
        assert mailer.is_configured() is True
        ok, via = mailer.send_mail("nurse@gmail.com", "Your code", "Your sign-in code is 847291.")
        assert ok is True
        assert via == "resend"
        assert seen["url"] == "https://api.resend.com/emails"
        assert seen["json"]["to"] == ["nurse@gmail.com"]
        assert "847291" in seen["json"]["text"]
        assert "847291" in seen["json"]["html"]


def test_resend_without_from_address_is_honest(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["MAIL_FROM"] = ""
    app.config["SMTP_FROM"] = "no-reply@localhost"
    with app.app_context():
        assert mailer.is_configured() is False
        ok, why = mailer.send_mail("a@gmail.com", "Hi", "x")
        assert ok is False
        assert "MAIL_FROM" in why


def test_signup_tells_the_truth_when_mail_cannot_leave(client, seeded):
    r = client.post("/signup", data={
        "_csrf": csrf(client, "/signup"),
        "name": "Ada Nurse",
        "username": "ada.nurse",
        "email": "ada.nurse@gmail.com",
        "password": "QuietLake#4",
        "confirm_password": "QuietLake#4",
    }, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "could not be sent" in html or "did" in html.lower()
    assert "ada.nurse@gmail.com" in html
    u = db.session.query(User).filter_by(username="ada.nurse").first()
    assert u is not None
    assert u.email_verified is False


def test_send_activation_returns_a_reason(app, seeded):
    with app.app_context():
        u = db.session.query(User).filter_by(username="admin").first()
        u.email = "admin@gmail.com"
        db.session.commit()
        result = accounts.send_activation(u, "123456", hospital_name="Test Hospital")
        assert result["ok"] is False
        assert result["error"]


def test_health_reports_mail_off(client, seeded):
    body = client.get("/api/v1/health").get_json()
    assert body["mail"] == "off"


def test_admin_health_shows_mail_van(client, seeded):
    login(client, "admin")
    page = client.get("/admin/health").get_data(as_text=True)
    assert "Mail van" in page
    assert "off" in page.lower()
    assert "empty" in page.lower()


def test_brevo_is_used_when_only_the_os_has_the_key(app, monkeypatch):
    """Render puts keys in the process environment. Do not trust only app.config."""
    app.config["BREVO_API_KEY"] = ""
    app.config["RESEND_API_KEY"] = ""
    app.config["MAIL_FROM"] = ""
    monkeypatch.setenv("BREVO_API_KEY", "  xkeysib-test  ")
    monkeypatch.setenv("MAIL_FROM", 'Hospital Suite <hcareproapp@gmail.com>')
    seen = {}

    class _R:
        status_code = 201
        text = "{}"

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return _R()

    monkeypatch.setattr("requests.post", fake_post)
    with app.app_context():
        assert mailer.active_provider() == "brevo"
        assert mailer.is_configured() is True
        ok, via = mailer.send_mail("nurse@gmail.com", "Test", "code 111222")
        assert ok is True
        assert via == "brevo"
        assert "api.brevo.com" in seen["url"]
        assert seen["headers"]["api-key"] == "xkeysib-test"
        assert seen["json"]["sender"]["email"] == "hcareproapp@gmail.com"


def test_brevo_unknown_key_is_explained(app, monkeypatch):
    app.config["BREVO_API_KEY"] = "xkeysib-not-real-but-long-enough-xxxxxxxxxxxx"
    app.config["MAIL_FROM"] = "Hospital Suite <hcareproapp@gmail.com>"

    class _R:
        status_code = 401
        text = '{"message":"Key not found","code":"unauthorized"}'

    monkeypatch.setattr("requests.post", lambda *a, **k: _R())
    with app.app_context():
        ok, why = mailer.send_mail("a@gmail.com", "Hi", "x")
        assert ok is False
        assert "does not recognise this key" in why
        assert "xkeysib-" in why
