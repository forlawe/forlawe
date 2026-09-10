"""Twilio as the WhatsApp fallback.

Meta's Cloud API is free and is the right primary, but approval can lapse and
business accounts get suspended with little notice. When the MD/CEO is waiting
for an inspection report, "our Meta approval lapsed" is not an answer.
"""
import pytest

from app import whatsapp
from app.models import WhatsAppMessage, db


def _msg(org_id, body="Inspection report ready."):
    m = WhatsAppMessage(org_id=org_id, to_number="+2348031234567",
                        kind="report", body=body, status="QUEUED", attempts=0)
    db.session.add(m)
    db.session.commit()
    return m


def test_twilio_mode_sends_through_twilio(app, seeded, monkeypatch):
    sent = {}

    class Resp:
        status_code = 201

        @staticmethod
        def json():
            return {"sid": "SM123"}

    def fake_post(url, **kw):
        sent["url"] = url
        sent["data"] = kw.get("data")
        return Resp()

    with app.app_context():
        app.config["WHATSAPP_MODE"] = "twilio"
        app.config["TWILIO_ACCOUNT_SID"] = "AC123"
        app.config["TWILIO_AUTH_TOKEN"] = "tok"
        app.config["TWILIO_WHATSAPP_FROM"] = "+14155238886"
        monkeypatch.setattr(whatsapp.requests, "post", fake_post)

        msg = _msg(seeded["org"])
        whatsapp.send_message(msg)

        assert msg.status == "SENT"
        assert msg.provider_id == "SM123"
        # Twilio requires the whatsapp: prefix — easy to get wrong by hand.
        assert sent["data"]["From"] == "whatsapp:+14155238886"
        assert sent["data"]["To"] == "whatsapp:+2348031234567"


def test_a_nigerian_number_is_formatted_correctly(app, seeded, monkeypatch):
    """08031234567 must become whatsapp:+8031234567-style E.164, not be sent raw."""
    seen = {}

    class Resp:
        status_code = 201

        @staticmethod
        def json():
            return {"sid": "SM1"}

    monkeypatch.setattr(whatsapp.requests, "post",
                        lambda url, **kw: (seen.update(kw.get("data", {})), Resp())[1])
    with app.app_context():
        app.config.update(WHATSAPP_MODE="twilio", TWILIO_ACCOUNT_SID="AC1",
                          TWILIO_AUTH_TOKEN="t", TWILIO_WHATSAPP_FROM="+1415")
        out = whatsapp._send_twilio("08031234567", "hello")
        assert out == "SM1"
        assert seen["To"].startswith("whatsapp:+"), seen["To"]


def test_twilio_without_credentials_says_so_plainly(app, seeded):
    with app.app_context():
        app.config.update(WHATSAPP_MODE="twilio", TWILIO_ACCOUNT_SID="",
                          TWILIO_AUTH_TOKEN="", TWILIO_WHATSAPP_FROM="")
        with pytest.raises(whatsapp.WhatsAppError) as err:
            whatsapp._send_twilio("+2348031234567", "hi")
        assert "TWILIO_ACCOUNT_SID" in str(err.value)


def test_meta_cloud_failing_falls_back_to_twilio(app, seeded, monkeypatch):
    """THE POINT OF ALL THIS. Meta goes down; the report still arrives."""
    calls = []

    def boom(*a, **kw):
        calls.append("cloud")
        raise RuntimeError("Meta: account suspended")

    def twilio_ok(to, body):
        calls.append("twilio")
        return "SM-FALLBACK"

    with app.app_context():
        app.config.update(WHATSAPP_MODE="cloud", TWILIO_ACCOUNT_SID="AC1",
                          TWILIO_AUTH_TOKEN="t", TWILIO_WHATSAPP_FROM="+1415")
        monkeypatch.setattr(whatsapp, "_send_text", boom)
        monkeypatch.setattr(whatsapp, "_send_twilio", twilio_ok)

        msg = _msg(seeded["org"])
        whatsapp.send_message(msg)

        assert calls == ["cloud", "twilio"], calls
        assert msg.status == "SENT", "the report was never delivered"
        assert msg.provider_id == "SM-FALLBACK"
        # The operator must be able to SEE that the fallback was used.
        assert "cloud failed" in (msg.last_error or "")


def test_a_failure_is_recorded_and_never_kills_the_queue(app, seeded,
                                                          monkeypatch):
    """A silent failure is worse than a visible one — but a CRASH is worse
    still: it would leave every other queued message stuck behind this one."""
    def boom(*a, **kw):
        raise RuntimeError("Meta is down")

    with app.app_context():
        app.config.update(WHATSAPP_MODE="cloud", TWILIO_ACCOUNT_SID="")
        monkeypatch.setattr(whatsapp, "_send_text", boom)
        msg = _msg(seeded["org"])
        whatsapp.send_message(msg)
        assert msg.status != "SENT"
        assert "Meta is down" in (msg.last_error or "")
