"""Hospital assistant: live links, no invented offers, stop when the book is empty."""
from app.chatbot import honesty, links
from app.chatbot.seed_kb import seed_global_kb
from app.models import ChatSession, WhatsAppMessage, db
from tests.conftest import csrf  # noqa: F401


def test_clock_style_links_follow_the_live_host(client, seeded):
    seed_global_kb(client.application, quiet=True)
    body = client.post("/api/chat", json={"text": "I want to book an appointment",
                                          "lang": "en"}).get_json()
    hrefs = [x["href"] for x in (body.get("links") or [])]
    assert hrefs, "booking must send a live page"
    assert all(h.startswith("http") for h in hrefs)
    assert any("/book" in h for h in hrefs)
    assert "/book" in body["reply"]
    assert "hospital-suite.onrender.com" not in body["reply"]


def test_fast_track_is_in_the_answer_book(client, seeded):
    seed_global_kb(client.application, quiet=True)
    body = client.post("/api/chat", json={"text": "I want Fast Track",
                                          "lang": "en"}).get_json()
    assert body["answered"] is True
    assert body.get("action") == "fasttrack"
    assert any("/book" in (x.get("href") or "") for x in body.get("links") or [])
    assert "Fast Track" in body["reply"]


def test_a_price_guess_is_not_offered(client, seeded):
    seed_global_kb(client.application, quiet=True)
    body = client.post("/api/chat", json={"text": "how much is my bill",
                                          "lang": "en"}).get_json()
    low = body["reply"].lower()
    assert "i'll give you a clear estimate" not in low
    assert "i will give you a clear estimate" not in low


def test_map_is_not_promised_by_text(client, seeded):
    seed_global_kb(client.application, quiet=True)
    body = client.post("/api/chat", json={"text": "where is the hospital",
                                          "lang": "en"}).get_json()
    low = body["reply"].lower()
    assert "text you" not in low
    assert "send the map" not in low


def test_unknown_question_hands_off_to_a_person(client, app, seeded):
    from app.models import Organization, db
    with app.app_context():
        org = db.session.get(Organization, seeded["org"])
        org.phone = "08031234567"
        db.session.commit()
    seed_global_kb(client.application, quiet=True)
    body = client.post("/api/chat", json={
        "text": "can you send me a taxi to ikorodu garage",
        "lang": "en"}).get_json()
    assert body["answered"] is False
    low = body["reply"].lower()
    assert "answer book" not in low
    assert "taxi" not in low
    assert "08031234567" in body["reply"]
    assert any(w in low for w in ("person", "staff", "desk", "call"))
    assert body.get("handoff") is True
    assert any((x.get("key") == "phone") or "tel:" in (x.get("href") or "")
               for x in (body.get("links") or []))


def test_yes_after_hours_opens_booking_not_a_guess(client, seeded):
    seed_global_kb(client.application, quiet=True)
    first = client.post("/api/chat", json={"text": "what are your opening hours",
                                           "lang": "en"}).get_json()
    sid = first["session"]
    yes = client.post("/api/chat", json={"text": "yes", "lang": "en",
                                         "session": sid}).get_json()
    assert yes["answered"] is True
    assert any("/book" in (x.get("href") or "") for x in yes.get("links") or [])


def test_off_script_keeps_the_last_page_only(client, seeded):
    seed_global_kb(client.application, quiet=True)
    first = client.post("/api/chat", json={"text": "book an appointment",
                                           "lang": "en"}).get_json()
    sid = first["session"]
    miss = client.post("/api/chat", json={
        "text": "also send a motorbike to my house now please xyzzy",
        "lang": "en", "session": sid}).get_json()
    assert miss["answered"] is False
    assert "motorbike" not in miss["reply"].lower()
    # Still allowed: the page we were already talking about.
    assert any("/book" in (x.get("href") or "") for x in miss.get("links") or [])


def test_hollow_sentences_are_stripped():
    raw = ("The desk can help. Would you like me to send the map to your phone? "
           "Come to reception.")
    out = honesty.strip_hollow(raw).lower()
    assert "send the map" not in out
    assert "reception" in out


def test_links_change_with_the_public_address(app):
    app.config["PUBLIC_BASE_URL"] = "https://new-hospital.example"
    with app.app_context():
        url = links.page_url("book")
    assert url.startswith("https://new-hospital.example")
    assert url.endswith("/book")


def test_whatsapp_gets_the_same_live_link(client, app, seeded):
    seed_global_kb(app, quiet=True)
    from app.chatbot.serve import handle_whatsapp
    from app.models import Organization
    with app.app_context():
        org = db.session.get(Organization, seeded["org"])
        app.config["PUBLIC_BASE_URL"] = "https://clinic.example"
        got = handle_whatsapp(org, "2348012345678", "I want Fast Track")
        assert got["answered"] is True
        assert "clinic.example/book" in got["text"]
        # Number is normalized to +234... in queue, so check contains 8012345678
        queued = db.session.query(WhatsAppMessage).filter(
            WhatsAppMessage.to_number.contains("8012345678")).all()
        assert queued, "WhatsApp queue should have message"
        assert "clinic.example/book" in queued[-1].body
        sess = db.session.query(ChatSession).filter(
            ChatSession.phone.contains("8012345678"), ChatSession.channel == "whatsapp").first()
        assert sess is not None
        assert sess.last_action == "fasttrack"
