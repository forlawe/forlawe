"""Public patient-assistant chat (web) + feedback + human handoff."""
from __future__ import annotations

from flask import (Blueprint, current_app, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from .. import services
from ..audit import audit
from ..chatbot import engine, quickedit
from ..models import (ChatFeedback, ChatMessage, ChatSession, Organization, db,
                      now_naive)
from ..security import csrf_exempt, rate_limit

bp = Blueprint("chat", __name__)


def _org():
    """Tenant for this request (see services.current_org)."""
    from ..services import current_org
    return current_org()


@bp.get("/chat")
@rate_limit(limit=60, window=60.0)
def chat_page():
    org = _org()
    return render_template("chat.html", org=org)


@bp.post("/api/chat")
@csrf_exempt("chat.chat_api")
@rate_limit(limit=40, window=60.0)
def chat_api():
    org = _org()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    # Coerce defensively: a non-string "text" (a number, a list, null) used to
    # raise AttributeError and return a 500 to the patient.
    raw = data.get("text")
    text = (raw if isinstance(raw, str) else ("" if raw is None else str(raw))).strip()
    text = text[:2000]                     # bound the work the retrieval engine does
    lang = data.get("lang")
    lang = lang if isinstance(lang, str) and lang in ("en", "yo", "ha", "ig", "pcm") else "en"
    session_id = data.get("session")
    session_id = session_id if isinstance(session_id, int) else None
    if not text:
        return jsonify(error="empty"), 400
    sess = db.session.get(ChatSession, session_id) if session_id else None
    if sess is None:
        sess = ChatSession(org_id=org.id if org else None, lang=lang, channel="web")
        db.session.add(sess)
        db.session.flush()

    # ---- SUPER ADMIN CORRECTING AN ANSWER, IN THE CHAT.
    # Checked before ANYTHING else so a correction is never mistaken for a
    # question. Two locks: signed in as Super Admin AND the secret code. This
    # endpoint is public and CSRF-exempt, so a code on its own would put the
    # hospital's answers one lucky guess away from a stranger.
    if quickedit.looks_like_edit(text):
        handled, result = quickedit.apply(org.id if org else None,
                                          current_user, text)
        if handled:
            if isinstance(result, dict):
                audit("KB_QUICK_EDIT", "knowledge_article",
                      result.get("article_id"),
                      {"intent": result.get("intent"),
                       "scope": result.get("scope"),
                       "replaced": result.get("old", "")[:200]})
                reply = result["message"]
            else:
                reply = result
            bot = ChatMessage(session_id=sess.id, role="bot", text=reply)
            db.session.add(bot)
            db.session.commit()
            return jsonify(session=sess.id, answered=True, reply=reply,
                           msg_id=bot.id, intent="kb_quick_edit")

    # ---- SOMEBODY TEACHING THE ASSISTANT.
    # "Ai please learn this... store it permanently" used to score against
    # whatever article shared a word with it (an OPD lecture, in the founder's
    # case). The assistant cannot learn from a chat message, and pretending it
    # can is a promise it will silently break. Say so, and record it.
    if engine.is_teaching(text):
        db.session.add(ChatMessage(session_id=sess.id, role="user", text=text,
                                   intent="teaching_note", unanswered=True))
        db.session.flush()
        bot = ChatMessage(session_id=sess.id, role="bot",
                          text=engine.TEACHING_REPLY)
        db.session.add(bot)
        db.session.commit()
        return jsonify(session=sess.id, answered=True,
                       reply=engine.TEACHING_REPLY, msg_id=bot.id,
                       intent="teaching_note")

    # Answer book only. A language model must not invent a suggestion the
    # hospital never wrote. If the book has nothing, we stop.
    from ..chatbot.serve import remember, respond
    got = respond(text, org=org, lang=lang, session=sess)
    remember(sess, got)

    msg = ChatMessage(session_id=sess.id, role="user", text=text,
                      intent=got.get("intent"),
                      confidence=got.get("confidence"),
                      article_id=got["article"].id if got.get("article") else None,
                      unanswered=bool(got.get("unanswered")))
    db.session.add(msg)
    db.session.flush()
    bot = ChatMessage(session_id=sess.id, role="bot", text=got["text"],
                      article_id=got["article"].id if got.get("article") else None)
    db.session.add(bot)
    db.session.commit()
    return jsonify(session=sess.id, answered=bool(got.get("answered")),
                   reply=got["text"], action=got.get("action"),
                   links=got.get("links") or [], msg_id=bot.id,
                   intent=got.get("intent"),
                   handoff=bool(got.get("handoff")))


@bp.post("/chat/feedback")
@csrf_exempt("chat.chat_feedback")
@rate_limit(limit=60, window=60.0)
def chat_feedback():
    data = request.get_json(silent=True) or {}
    msg_id = data.get("msg_id")
    rating = "up" if data.get("rating") == "up" else "down"
    msg = db.session.get(ChatMessage, msg_id or 0)
    if not msg:
        return jsonify(error="not found"), 404
    db.session.add(ChatFeedback(message_id=msg.id, article_id=msg.article_id, rating=rating))
    if msg.article_id:
        from ..models import KnowledgeArticle
        art = db.session.get(KnowledgeArticle, msg.article_id)
        if art:
            if rating == "up":
                art.thumbs_up = (art.thumbs_up or 0) + 1
            else:
                art.thumbs_down = (art.thumbs_down or 0) + 1
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/chat/handoff")
@csrf_exempt("chat.chat_handoff")
@rate_limit(limit=10, window=120.0)
def chat_handoff():
    """Human handoff: notify the Admin Manager on duty once per chat."""
    from ..chatbot.serve import perform_handoff
    org = _org()
    data = request.get_json(silent=True) or {}
    session_id = data.get("session")
    sess = db.session.get(ChatSession, session_id or 0)
    fresh = perform_handoff(org, sess)
    db.session.commit()
    return jsonify(
        ok=True, already=not fresh,
        message=("Thank you for your patience — I've alerted our front desk and a team "
                 "member will be with you shortly. You're in good hands."))
