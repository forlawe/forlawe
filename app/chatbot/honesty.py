"""The assistant may only offer what it can actually do.

The preloaded answer book was written warmly, and it promised things the
bot cannot do: text a map, check an HMO, grab a slot, alert A&E, send a
reminder. A patient who says yes to those is let down. We strip those
promises at serve time (so every old and new article is cleaned) and we
only attach a live page we really have.

When the book has no answer, we do not say "not in my answer book".
We hand the person to a human — hospital phone and a staff alert.
"""
from __future__ import annotations

import re

# First-person promises the bot cannot keep. Whole sentence is dropped.
_HOLLOW = re.compile(
    r"(?:^|(?<=[.!?]))\s*"
    r"(?:"
    r"[^.!?\n]*(?:"
    r"I(?:'ll| will|'ve) (?:text|send you|send the|alert|grab|lock in|"
    r"log (?:it|a)|check (?:your|the|it)|confirm your|arrange|"
    r"coordinate|line up|pair your|set a|request|prepare|"
    r"have the billing|let the|start the request|note that you|"
    r"trigger|connect you|link you|set up|give you|"
    r"pick the right|find out|book you|"
    r"get you (?:booked|seen|a)|open the booking|"
    r"take you there|get you a number|make sure it reaches|"
    r"set the search|suggest what's allowed|guide you|"
    r"prep your refill|keep it consistent|align your clinic|"
    r"time your vaccine|bundle it|send your secure|"
    r"match you|match them|pair you|set you up|"
    r"pass your|speak )"
    r"|Shall I (?:book|open|set|alert|arrange|take you|grab|check|"
    r"get a human|get you)"
    r"|Would you like me to (?:book|send|check|confirm|arrange|"
    r"alert|text|request|start|open a review)"
    r"|Want me to (?:grab|book|send|set|check)"
    r"|Make I (?:book|tell|send|open|check|arrange|set|connect)"
    r"|Can I (?:alert|get you a seat|get you water)"
    r"|I can (?:request an itemised|show our standard price|book you|get you booked)"
    r"|I fit book you"
    r"|I'll give you a clear estimate"
    r"|I'll have the (?:billing|records|desk)"
    r"|Say '[^']+' and I(?:'ll| will)"
    r"|Tap '[^']+' and I(?:'ll| will)"
    r")[^.!?\n]*[.!?]?"
    r")",
    re.IGNORECASE,
)

# Soft leftover questions that still promise a bot action.
_HOLLOW_Q = re.compile(
    r"(?:Shall I|Would you like me to|Want me to|Make I|Can I alert)"
    r"[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)

STOP_REPLY = (
    "I want to get this right, so I will not guess. "
    "A person at the hospital can help you with that. "
    "Please call the hospital desk, or tap Talk to a person "
    "and I will alert the staff on duty."
)

STOP_REPLY_FOLLOW = (
    "I want to get this right, so I will not guess. "
    "A person at the hospital can help you with that. "
    "You can still open the page we were talking about below. "
    "Or tap Talk to a person and I will alert the staff on duty."
)


def hospital_phone(org) -> str:
    """The number a patient can actually dial. Empty if none is set."""
    if org is None:
        return ""
    for attr in ("phone", "phone_alt"):
        val = (getattr(org, attr, None) or "").strip()
        if val:
            return val
    return ""


def stop_reply(org=None, *, follow: bool = False) -> str:
    """Professional human hand-off. Never mentions an 'answer book'."""
    phone = hospital_phone(org)
    if follow:
        lead = (
            "I want to get this right, so I will not guess. "
            "A person at the hospital can help you with that. "
            "You can still open the page we were talking about below."
        )
    else:
        lead = (
            "I want to get this right, so I will not guess. "
            "A person at the hospital can help you with that."
        )
    if phone:
        contact = (
            f" Please call the hospital desk on {phone}, "
            "or tap Talk to a person and I will alert the staff on duty."
        )
    else:
        contact = (
            " Please tap Talk to a person and I will alert the staff on duty, "
            "or visit the hospital desk."
        )
    return lead + contact


def strip_hollow(text: str) -> str:
    """Remove offers the bot cannot keep. Leaves the honest facts."""
    out = _HOLLOW.sub(" ", text or "")
    out = _HOLLOW_Q.sub(" ", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"\s+([.!?])", r"\1", out)
    return out.strip()


def with_links(text: str, links: list[dict] | None) -> str:
    """Append live addresses so the reply still works if chips are missed."""
    body = (text or "").strip()
    if not links:
        return body
    already = body.lower()
    extra = []
    for item in links:
        href = item.get("href") or ""
        label = item.get("label") or "Open"
        if not href:
            continue
        if href.lower() in already:
            continue
        extra.append(f"{label}: {href}")
    if not extra:
        return body
    joiner = "\n" if body else ""
    return body + joiner + "\n".join(extra)
