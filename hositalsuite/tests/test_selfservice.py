"""Self-service forgot/reset password — lifts the burden off the admin."""
import secrets as pysecrets
from datetime import timedelta

from app.models import PasswordReset, User, db, now_naive

from conftest import csrf, login


def _request_code(client, monkeypatch, otp="123456"):
    monkeypatch.setattr(pysecrets, "randbelow", lambda n: int(otp))
    return client.post("/forgot-password",
                       data={"_csrf": csrf(client, "/forgot-password"),
                             "identifier": "am2"}, follow_redirects=True)


def test_full_self_service_reset_flow(client, seeded, monkeypatch):
    r = _request_code(client, monkeypatch)
    assert b"on the way" in r.data          # generic, no enumeration
    row = db.session.query(PasswordReset).first()
    assert row is not None and row.used_at is None

    r = client.post("/reset-password", data={
        "_csrf": csrf(client, "/reset-password"), "identifier": "am2", "otp": "123456",
        "new_password": "FreshPass#9x", "confirm_password": "FreshPass#9x"},
        follow_redirects=True)
    assert b"Password updated" in r.data
    with client.session_transaction():
        pass
    # old password dead, new one works
    login_ok = client.post("/login", data={
        "_csrf": csrf(client, "/login"), "username": "am2",
        "password": "FreshPass#9x"}, follow_redirects=False)
    assert login_ok.status_code == 302
    u = db.session.query(User).filter_by(username="am2").first()
    assert u.must_change_password is False
    assert db.session.query(PasswordReset).first().used_at is not None
    # code is single-use
    r = client.post("/reset-password", data={
        "_csrf": csrf(client, "/reset-password"), "identifier": "am2", "otp": "123456",
        "new_password": "Another#9x", "confirm_password": "Another#9x"})
    assert r.status_code == 401


def test_wrong_otp_and_expired_rejected(client, seeded, monkeypatch):
    _request_code(client, monkeypatch, otp="654321")
    r = client.post("/reset-password", data={
        "_csrf": csrf(client, "/reset-password"), "identifier": "am2", "otp": "000000",
        "new_password": "FreshPass#9x", "confirm_password": "FreshPass#9x"})
    assert r.status_code == 401
    # expiry enforced
    row = db.session.query(PasswordReset).first()
    row.expires_at = now_naive() - timedelta(minutes=1)
    db.session.commit()
    r = client.post("/reset-password", data={
        "_csrf": csrf(client, "/reset-password"), "identifier": "am2", "otp": "654321",
        "new_password": "FreshPass#9x", "confirm_password": "FreshPass#9x"})
    assert r.status_code == 401 and b"expired" in r.data


def test_no_enumeration_and_weak_password_rejected(client, seeded, monkeypatch):
    r = client.post("/forgot-password", data={
        "_csrf": csrf(client, "/forgot-password"), "identifier": "ghost-user"},
        follow_redirects=True)
    assert b"on the way" in r.data            # same generic message
    assert db.session.query(PasswordReset).count() == 0     # but nothing created

    _request_code(client, monkeypatch)
    r = client.post("/reset-password", data={
        "_csrf": csrf(client, "/reset-password"), "identifier": "am2", "otp": "123456",
        "new_password": "weak", "confirm_password": "weak"})
    assert r.status_code == 422


def test_forgot_password_uses_the_mail_van_not_fake_sms(client, seeded, monkeypatch, app):
    """Sandbox SMS must not pretend a letter left and skip email."""
    from app.models import User
    u = db.session.query(User).filter_by(username="am2").first()
    u.email = "am2@gmail.com"
    u.phone = "08031112222"
    db.session.commit()
    seen = {}

    def fake_send(to, subject, text, **kwargs):
        seen["to"] = to
        seen["text"] = text
        return True, "brevo"

    monkeypatch.setattr("app.mailer.is_configured", lambda: True)
    monkeypatch.setattr("app.mailer.send_mail", fake_send)
    r = _request_code(client, monkeypatch)
    assert r.status_code == 200
    assert seen.get("to") == "am2@gmail.com"
    assert "123456" in (seen.get("text") or "")
    row = db.session.query(PasswordReset).first()
    assert row.channel == "email"


def test_admin_still_can_reset_and_login_link_present(client, seeded):
    r = client.get("/login")
    assert b"Forgot password" in r.data
    login(client, "admin")
    tok = csrf(client, "/admin/users")
    r = client.post(f"/admin/users/{seeded['am']}/reset-password",
                    data={"_csrf": tok, "password": "ResetByAdmin#1x"},
                    follow_redirects=True)
    assert b"must change it at next login" in r.data
