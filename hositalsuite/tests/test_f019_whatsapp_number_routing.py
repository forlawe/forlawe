"""F-019: inbound WhatsApp routes by the BUSINESS NUMBER that received it.

The webhook used to hand every inbound message to `current_org()` — which on
a multi-hospital server resolves to hospital #1 by fallback. Now each
hospital records its Meta number identity (`whatsapp_phone_number_id` /
`whatsapp_display_number` settings) and the webhook routes on it; a message
for an unmapped number on a multi-hospital server is logged and NOT guessed.
Single-hospital deployments keep working with zero configuration.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.models import db, Organization, Setting


@pytest.fixture()
def two_org_world(app, seeded, monkeypatch):
    """Two hospitals; B claims Meta number id 'PNB' / display '+2348012223344'."""
    monkeypatch.setitem(app.config, "WHATSAPP_APP_SECRET", "test-secret")
    from werkzeug.security import generate_password_hash
    from app.models import User
    with app.app_context():
        b = Organization(code="WAB", name="WhatsApp Second Hospital")
        db.session.add(b)
        db.session.flush()
        Setting.set(b.id, "whatsapp_phone_number_id", "PNB")
        Setting.set(b.id, "whatsapp_display_number", "+234 801 222 3344")
        u = User(org_id=b.id, username="wab.admin", name="WAB Admin", role="ADMIN_MANAGER",
                 password_hash=generate_password_hash("Passw0rd!x"), active=True,
                 approved=True, email_verified=True)
        db.session.add(u)
        db.session.commit()
        yield {"a": seeded["org"], "b": b.id}


def _post(client, app, payload):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    return client.post("/api/v1/whatsapp/webhook", data=body,
                       headers={"X-Hub-Signature-256": sig,
                                "Content-Type": "application/json"})


def _payload(number_id, display):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": number_id, "display_phone_number": display},
        "messages": [{"type": "text", "from": "234801111111",
                      "text": {"body": "what time do you open?"}}]}}]}]}


@pytest.fixture()
def captured(monkeypatch):
    calls = []

    def fake_handle(org_id, frm, body, lang="en"):
        calls.append((org_id, frm, body))
        return {}

    import app.chatbot.serve as serve
    monkeypatch.setattr(serve, "handle_whatsapp", fake_handle)
    # api.py imports handle_whatsapp inside the function → patch the source module
    import app.chatbot.serve
    monkeypatch.setattr("app.chatbot.serve.handle_whatsapp", fake_handle)
    yield calls


def test_message_routes_to_the_hospital_that_owns_the_number(client, app, two_org_world, captured):
    r = _post(client, app, _payload("PNB", "+2348012223344"))
    assert r.status_code == 200
    assert captured and captured[0][0] == two_org_world["b"]


def test_single_hospital_server_needs_no_mapping(client, app, seeded, captured, monkeypatch):
    """Only ONE org exists → the webhook still works with zero configuration."""
    monkeypatch.setitem(app.config, "WHATSAPP_APP_SECRET", "test-secret")
    r = _post(client, app, _payload("PN-UNKNOWN", "+2348000000000"))
    assert r.status_code == 200
    assert captured and captured[0][0] == seeded["org"]


def test_unmapped_number_on_multi_hospital_server_is_not_guessed(client, app, two_org_world, captured):
    r = _post(client, app, _payload("PN-NOMATCH", "+2349999999999"))
    assert r.status_code == 200          # Meta must not retry-storm
    assert captured == []                # ...but nothing was routed


def test_org_for_number_unit(app, two_org_world):
    from app import whatsapp
    with app.app_context():
        assert whatsapp.org_for_number("PNB").id == two_org_world["b"]
        assert whatsapp.org_for_number(None, "234 801 222 3344").id == two_org_world["b"]
        assert whatsapp.org_for_number("PN-OTHER") is None
        assert whatsapp.org_for_number(None, None) is None
