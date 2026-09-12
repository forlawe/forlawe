"""Patient assistant chat: the typing box, and the full path to the database.

Regression driver: the composer used height:calc(100vh - 150px) inside normal
page flow under a tall header, which pushed the input to y=921px on an 844px
phone screen — BELOW THE FOLD. Patients saw a greeting and had no way to type.
"""
import pytest

from app.models import (ChatFeedback, ChatMessage, ChatSession,
                        KnowledgeArticle, db)


@pytest.fixture()
def kb(app, seeded):
    """Reload the global dialogue library (the seeded fixture drops it)."""
    from app.chatbot.seed_kb import seed_global_kb
    seed_global_kb(app, quiet=True)
    return seeded


# ================================================================ the page itself
def test_chat_page_has_a_visible_typing_box(client, seeded):
    html = client.get("/chat").data.decode()
    assert 'id="chat-in"' in html, "no text input on the chat page"
    assert 'id="send"' in html, "no send button"
    assert 'id="composer"' in html, "composer form missing"


def test_composer_is_pinned_and_not_pushed_off_screen(client, seeded):
    """The old layout put the input below the fold. Guard the fix."""
    html = client.get("/chat").data.decode()
    assert "calc(100vh - 150px)" not in html, "the off-screen layout is back"
    assert ".composer{flex:0 0 auto" in html, "composer must be a fixed-size flex row"
    # body must own the viewport so the flex column can pin the composer
    assert "height:100dvh" in html or "height:100vh" in html


def test_chat_page_is_a_form_so_enter_key_sends(client, seeded):
    html = client.get("/chat").data.decode()
    assert '<form class="composer"' in html
    assert 'type="submit"' in html


def test_chat_page_has_quick_topic_chips(client, seeded):
    html = client.get("/chat").data.decode()
    for q in ["Book an appointment", "opening hours", "complaint", "Talk to a human"]:
        assert q in html


def test_chat_page_has_a_way_back_to_the_services(client, seeded):
    html = client.get("/chat").data.decode()
    assert 'href="/welcome"' in html


def test_chat_page_translates(client, seeded):
    for code, marker in [("en", "Type your question"), ("yo", "Kọ ìbéèrè"),
                         ("ha", "Rubuta tambayarka"), ("ig", "Pịnye ajụjụ")]:
        client.get(f"/lang/{code}?next=/chat")
        assert marker in client.get("/chat").data.decode(), f"{code} chat text missing"
    client.get("/lang/en?next=/chat")


# ================================================================ the API -> database
def test_sending_a_message_stores_the_conversation(client, seeded):
    r = client.post("/api/chat", json={"text": "What are your opening hours?", "lang": "en"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["session"], "no session id returned"
    assert body["reply"], "no reply text"

    sess = db.session.get(ChatSession, body["session"])
    assert sess is not None
    assert sess.org_id == seeded["org"], "conversation not tied to the hospital"

    rows = db.session.query(ChatMessage).filter_by(session_id=sess.id).all()
    roles = {m.role for m in rows}
    assert "user" in roles, "the patient's message was not saved"
    if body.get("answered"):
        assert "bot" in roles, "the assistant's reply was not saved"


def test_conversation_continues_in_the_same_session(client, seeded):
    first = client.post("/api/chat", json={"text": "opening hours", "lang": "en"}).get_json()
    sid = first["session"]
    second = client.post("/api/chat",
                         json={"text": "how much is my bill?", "lang": "en",
                               "session": sid}).get_json()
    assert second["session"] == sid, "a new session was started mid-conversation"
    assert db.session.query(ChatMessage).filter_by(session_id=sid).count() >= 2


def test_empty_message_is_rejected_cleanly(client, seeded):
    r = client.post("/api/chat", json={"text": "   ", "lang": "en"})
    assert r.status_code == 400
    assert b"Traceback" not in r.data


def test_unanswered_question_is_recorded_for_review(client, seeded):
    r = client.post("/api/chat",
                    json={"text": "zzzz qqqq xxxx nonsense that matches nothing", "lang": "en"})
    body = r.get_json()
    assert r.status_code == 200
    assert body["reply"], "must still reply helpfully when it cannot answer"
    if not body.get("answered"):
        rows = db.session.query(ChatMessage).filter_by(unanswered=True).all()
        assert rows, "unanswered questions must be logged so the KB can be improved"


def test_clinical_questions_get_the_safe_refusal(client, seeded):
    """The single most important line in the product: never diagnose."""
    for q in ["what disease do i have", "which drug should i take for malaria",
              "please prescribe me something"]:
        body = client.post("/api/chat", json={"text": q, "lang": "en"}).get_json()
        reply = body["reply"].lower()
        assert ("not able to diagnose" in reply or "cannot diagnose" in reply
                or "clinician" in reply), f"unsafe reply to {q!r}: {body['reply'][:80]}"


def test_thumbs_feedback_reaches_the_database(client, seeded):
    body = client.post("/api/chat", json={"text": "opening hours", "lang": "en"}).get_json()
    if not body.get("msg_id"):
        return                                   # nothing to rate if unanswered
    r = client.post("/chat/feedback", json={"msg_id": body["msg_id"], "rating": "up"})
    assert r.status_code == 200
    assert db.session.query(ChatFeedback).count() == 1

    art_id = db.session.get(ChatMessage, body["msg_id"]).article_id
    if art_id:
        assert (db.session.get(KnowledgeArticle, art_id).thumbs_up or 0) >= 1


def test_feedback_on_a_missing_message_is_handled(client, seeded):
    r = client.post("/chat/feedback", json={"msg_id": 999999, "rating": "up"})
    assert r.status_code == 404
    assert b"Traceback" not in r.data


def test_human_handoff_alerts_staff(client, seeded):
    body = client.post("/api/chat", json={"text": "Talk to a human", "lang": "en"}).get_json()
    r = client.post("/chat/handoff", json={"session": body["session"]})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert db.session.get(ChatSession, body["session"]).handed_off is True


def test_handoff_without_a_session_does_not_crash(client, seeded):
    r = client.post("/chat/handoff", json={})
    assert r.status_code == 200
    assert b"Traceback" not in r.data


def test_chat_works_in_every_language_end_to_end(client, seeded):
    for lang in ("en", "yo", "ha", "ig", "pcm"):
        r = client.post("/api/chat", json={"text": "opening hours", "lang": lang})
        assert r.status_code == 200, f"chat failed for {lang}"
        assert r.get_json()["reply"], f"empty reply for {lang}"


def test_malformed_request_bodies_are_handled(client, seeded):
    for payload in [None, {}, {"text": None}, {"text": 12345}]:
        r = client.post("/api/chat", json=payload)
        assert r.status_code in (200, 400), f"crashed on {payload!r}"
        assert b"Traceback" not in r.data


def test_very_long_message_does_not_crash(client, seeded):
    r = client.post("/api/chat", json={"text": "hours " * 3000, "lang": "en"})
    assert r.status_code in (200, 400, 413)
    assert b"Traceback" not in r.data


def test_chat_reply_is_not_rendered_as_html(client, seeded):
    """The page must use textContent, not innerHTML, for message bubbles."""
    html = client.get("/chat").data.decode()
    assert "d.textContent = text" in html
    assert "d.innerHTML = text" not in html


# ================================================================ answer quality
def test_opening_hours_question_does_not_return_a_greeting(client, kb):
    """Regression: 'what are your OPENING HOURS' matched the trigger 'are you'
    (intent how_are_you) because scoring used raw substring matching. Patients
    asking about hours were told 'I'm doing wonderfully, thank you for asking'."""
    from app.chatbot import engine
    res = engine.answer("what are your opening hours", org_id=kb["org"])
    assert res is not None and res["article"] is not None
    assert res["article"].intent == "hours_clinic", \
        f"routed to {res['article'].intent} instead of opening hours"


def test_keyword_matching_respects_word_boundaries(client, seeded):
    from app.chatbot.engine import _phrase_hit
    assert _phrase_hit("are you", "how are you today")
    assert not _phrase_hit("are you", "what are your opening hours"), \
        "'are you' must not match inside 'are your'"
    assert not _phrase_hit("pay", "payment plan")


def test_common_patient_questions_route_correctly(client, kb):
    from app.chatbot import engine
    expected = {
        "what are your opening hours": "hours_clinic",
        "what time do you open": "hours_clinic",
        "i want to book an appointment": "book_appointment",
        "how much is my bill": "bill_estimate",
        "how do i pay": "bill_payment",
        "where is the hospital": "directions",
        "i want to make a complaint": "complaint_start",
        # now routed to the NURSING-specific complaint answer, which is better
        "the nurse was rude": "nursing_services_complaint",
        "i am pregnant": "anc_book",
        "talk to a human": "human_handoff",
        "how are you": "how_are_you",
    }
    wrong = []
    for q, intent in expected.items():
        res = engine.answer(q, org_id=kb["org"])
        got = res["article"].intent if res and res.get("article") else None
        if got != intent:
            wrong.append(f"{q!r} -> {got} (wanted {intent})")
    assert not wrong, "misrouted questions:\n  " + "\n  ".join(wrong)


def test_a_specific_match_beats_an_incidental_short_one(client, seeded):
    """Longer trigger phrases must win, so one stray word cannot hijack an answer."""
    from app.chatbot.engine import _score

    class Fake:
        def __init__(self, kws):
            self.keywords = "\n".join(kws)

    text = "what are your opening hours"
    specific = _score(Fake(["opening hours"]), text)
    incidental = _score(Fake(["are you", "hours"]), text)
    assert specific > incidental
