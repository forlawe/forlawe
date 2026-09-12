"""F-005 regression: the WhatsApp webhook must fail CLOSED.

The signature check used to be skipped entirely when WHATSAPP_APP_SECRET was
unset — a forged POST could inject inbound messages or fake delivery
statuses. These tests pin the two safe behaviors:
  * no secret configured  -> 503, nothing processed
  * secret configured     -> valid Meta signature required (403 otherwise)
"""
import hashlib
import hmac

from conftest import csrf, login


def _signed(body: bytes, secret: str) -> dict:
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}


def _post(client, headers):
    payload = {"entry": [{"changes": [{"value": {"statuses": [], "messages": []}}]}]}
    return client.post("/api/v1/whatsapp/webhook", json=payload, headers=headers)


def test_without_secret_the_webhook_is_not_deployed(client, seeded, monkeypatch):
    monkeypatch.setitem(client.application.config, "WHATSAPP_APP_SECRET", "")
    r = _post(client, {})
    assert r.status_code == 503, (
        "webhook accepted traffic without a configured secret (F-005 fail-open)")


def test_with_a_secret_a_bad_signature_is_rejected(client, seeded, monkeypatch):
    monkeypatch.setitem(client.application.config, "WHATSAPP_APP_SECRET", "shhh")
    r = _post(client, {"X-Hub-Signature-256": "sha256=deadbeef"})
    assert r.status_code == 403


def test_with_a_secret_a_valid_signature_is_accepted(client, seeded, monkeypatch):
    import json
    secret = "shhh"
    monkeypatch.setitem(client.application.config, "WHATSAPP_APP_SECRET", secret)
    payload = {"entry": [{"changes": [{"value": {"statuses": [], "messages": []}}]}]}
    body = json.dumps(payload).encode()
    headers = _signed(body, secret)
    r = client.post("/api/v1/whatsapp/webhook", data=body, headers=headers)
    assert r.status_code == 200
