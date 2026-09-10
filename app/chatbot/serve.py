"""One reply path for the web chat and for WhatsApp.

Rules the founder set:
  1. Links follow the live site address (host / domain can change).
  2. Never invent an offer that is not in the book.
  3. Follow the conversation; if the next question is not in the book, stop.
  4. Strip offers the bot cannot keep.
  5. A miss is a professional hand-off to a human — phone + staff alert.
     Never say "not in my answer book".
"""
from __future__ import annotations

from . import engine
from .honesty import (STOP_REPLY, STOP_REPLY_FOLLOW, hospital_phone,
                      stop_reply, strip_hollow, with_links)
from .links import action_for_intent, links_for, page_url


def staff_links(org) -> list[dict]:
    """Pages and a phone a patient can actually use when we hand off."""
    out = []
    href = page_url("welcome")
    if href:
        out.append({"href": href, "label": "Hospital home", "key": "welcome"})
    phone = hospital_phone(org)
    if phone:
        tel = "tel:" + "".join(ch for ch in phone if ch.isdigit() or ch == "+")
        out.append({"href": tel, "label": f"Call {phone}", "key": "phone"})
    return out


def _merge_links(*groups: list[dict]) -> list[dict]:
    out, seen = [], set()
    for group in groups:
        for item in group or []:
            href = (item or {}).get("href") or ""
            if not href or href in seen:
                continue
            seen.add(href)
            out.append(item)
    return out


def decorate(text: str, action: str | None, org=None, *,
             keep_hollow: bool = False) -> tuple[str, list[dict]]:
    links = links_for(action)
    clean = (text or "") if keep_hollow else strip_hollow(text or "")
    return with_links(clean, links), links


def last_user(session):
    from ..models import ChatMessage, db
    return (db.session.query(ChatMessage)
            .filter_by(session_id=session.id, role="user")
            .order_by(ChatMessage.id.desc())
            .first())


def perform_handoff(org, session) -> bool:
    """Alert the desk once per chat. Safe to call again."""
    from .. import notifications, services
    from ..audit import audit
    from ..models import now_naive

    if session is not None and session.handed_off:
        return False
    if session is not None:
        session.handed_off = True
    if org is None:
        return True
    duty = None
    try:
        duty = services.on_duty(org.id, now_naive().date())
    except Exception:                                    # noqa: BLE001
        duty = None
    ctx = {"ref": f"CHAT-{getattr(session, 'id', 'web')}",
           "dept": "Front Desk", "category": "Chat handoff",
           "hospital": getattr(org, "name", "") or "", "sla": ""}
    if duty:
        try:
            notifications.notify(
                org.id, duty, "complaint_new_admin", ctx,
                channels=["inapp"], entity_type="chat",
                entity_id=getattr(session, "id", 0) or 0)
        except Exception:                                # noqa: BLE001
            pass
    try:
        audit("CHAT_HANDOFF", "chat", getattr(session, "id", 0) or 0, {})
    except Exception:                                    # noqa: BLE001
        pass
    return True


def respond(text: str, *, org, lang: str = "en", session) -> dict:
    """Answer from the book only. Never invent.

    Returns {text, action, links, answered, intent, article, confidence,
             unanswered, handoff}.
    """
    org_id = getattr(org, "id", None)

    # Guardrail prefilter — backend enforced, never frontend only. Best-effort
    # filter, not a security boundary; the boundary is that the assistant only
    # ever answers from the hospital's published KB.
    if engine.is_privacy_attack(text) or engine.is_prompt_injection(text):
        body, links = decorate(engine.PRIVACY_REFUSAL if lang != "pcm" else engine.PRIVACY_REFUSAL_PCM, None, org)
        return {"text": body, "action": None, "links": links,
                "answered": True, "intent": "privacy_refusal",
                "article": None, "confidence": 99.0, "unanswered": False,
                "handoff": False}

    if engine.is_teaching(text):
        body, links = decorate(engine.TEACHING_REPLY, None, org)
        return {"text": body, "action": "handoff", "links": links,
                "answered": True, "intent": "teaching_note",
                "article": None, "confidence": 99.0, "unanswered": True,
                "handoff": True}

    prev = last_user(session) if session is not None else None
    prev_intent = (getattr(session, "last_intent", None)
                   or (prev.intent if prev else "") or "")
    prev_action = getattr(session, "last_action", None) or ""

    if engine.is_refusal(text):
        body, links = decorate(
            "No problem at all. I'm here whenever you need me — just ask.",
            None, org)
        return {"text": body, "action": None, "links": links,
                "answered": True, "intent": prev_intent or None,
                "article": None, "confidence": 99.0, "unanswered": False,
                "handoff": False}

    if engine.is_agreement(text):
        res = engine.followup_for(prev_intent, prev_action or prev_intent,
                                  lang=lang, org_id=org_id)
        if res is None:
            body, links = decorate(
                "Happy to help — could you tell me what you'd like me to do? "
                "For example \"book a visit\" or \"talk to a human\".",
                None, org)
            return {"text": body, "action": None, "links": links,
                    "answered": True, "intent": None, "article": None,
                    "confidence": 99.0, "unanswered": False, "handoff": False}
        action = res.get("action") or action_for_intent(
            res["article"].intent if res.get("article") else None)
        keep = (res["article"].intent == "human_handoff"
                if res.get("article") else False)
        body, links = decorate(res["text"], action, org, keep_hollow=keep)
        intent = res["article"].intent if res.get("article") else action
        if action == "handoff":
            perform_handoff(org, session)
        return {"text": body, "action": action, "links": links,
                "answered": True, "intent": intent,
                "article": res.get("article"),
                "confidence": res.get("confidence") or 99.0,
                "unanswered": False, "handoff": action == "handoff"}

    res = engine.answer(text, lang=lang, org_id=org_id)
    if res is None:
        # Not in the book. Keep the last real page if we were mid-flow,
        # and always hand the person to a human. Never invent a new offer.
        fallback_action = prev_action if prev_action in (
            "book", "fasttrack", "queue", "complaint", "feedback",
            "book_status", "complaint_status") else None
        page_links = links_for(fallback_action)
        human = staff_links(org)
        links = _merge_links(page_links, human)
        body = with_links(
            stop_reply(org, follow=bool(fallback_action)), links)
        perform_handoff(org, session)
        return {"text": body,
                "action": fallback_action or "handoff",
                "links": links,
                "answered": False, "intent": None, "article": None,
                "confidence": 0.0, "unanswered": True, "handoff": True}

    article = res.get("article")
    intent = article.intent if article else res.get("action")
    action = res.get("action") or action_for_intent(intent)
    keep = intent == "human_handoff"
    body, links = decorate(res["text"], action, org, keep_hollow=keep)
    handed = False
    if action == "handoff":
        perform_handoff(org, session)
        handed = True
        links = _merge_links(links, staff_links(org))
        body = with_links(strip_hollow(res["text"]) if not keep
                          else (res["text"] or ""), links)
    return {"text": body, "action": action, "links": links,
            "answered": True, "intent": intent, "article": article,
            "confidence": res.get("confidence") or 0.0,
            "unanswered": False, "handoff": handed}


def save_turn(session, text: str, result: dict) -> None:
    from ..models import ChatMessage, db
    db.session.add(ChatMessage(
        session_id=session.id, role="user", text=text,
        intent=result.get("intent"),
        confidence=result.get("confidence"),
        article_id=result["article"].id if result.get("article") else None,
        unanswered=bool(result.get("unanswered"))))
    db.session.add(ChatMessage(
        session_id=session.id, role="bot", text=result["text"],
        article_id=result["article"].id if result.get("article") else None))


def handle_whatsapp(org, phone: str, text: str, lang: str = "en") -> dict:
    """Same answers, live links, and the same human hand-off on WhatsApp."""
    from datetime import timedelta

    from .. import whatsapp
    from ..models import ChatSession, db, now_naive

    phone = (phone or "").strip()[:32]
    if not phone or not (text or "").strip():
        return {"text": "", "answered": False, "links": []}
    cutoff = now_naive() - timedelta(hours=12)
    sess = (db.session.query(ChatSession)
            .filter(ChatSession.org_id == (org.id if org else None),
                    ChatSession.channel == "whatsapp",
                    ChatSession.phone == phone,
                    ChatSession.started_at >= cutoff)
            .order_by(ChatSession.id.desc()).first())
    if sess is None:
        sess = ChatSession(org_id=org.id if org else None, lang=lang,
                           channel="whatsapp", phone=phone)
        db.session.add(sess)
        db.session.flush()
    got = respond(text.strip()[:2000], org=org, lang=lang, session=sess)
    remember(sess, got)
    save_turn(sess, text.strip()[:2000], got)
    if org is not None:
        whatsapp.queue_message(org.id, phone, got["text"], kind="chat",
                               entity_type="chat", entity_id=sess.id)
    db.session.commit()
    return got


def remember(session, result: dict) -> None:
    """Keep the thread so a later 'yes' or a miss can follow it."""
    if session is None:
        return
    if result.get("unanswered") and not result.get("action"):
        session.last_intent = None
        session.last_action = None
        return
    if result.get("intent"):
        session.last_intent = str(result["intent"])[:60]
    if result.get("action"):
        session.last_action = str(result["action"])[:20]
