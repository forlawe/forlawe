"""Correct a bad answer from inside the chat, in seconds.

WHAT THE FOUNDER ASKED FOR
--------------------------
    "copy a bad response during a chat, edit it, and paste the corrected
     version back with a unique one-word code known to me alone to effect the
     change... for Global and Hospital specific response."

Exactly right, and it is the fastest way to fix a wrong answer: you are already
looking at it, you already know what it should say.

THE ONE CHANGE I MADE TO THE DESIGN, AND WHY
--------------------------------------------
The founder asked for a secret code. A code ALONE is not safe here, because
`/api/chat` is public and CSRF-exempt — the whole internet can post to it. I
tested this against the live site to be sure. A code typed into that box can be:

  * guessed, a few thousand tries at a time, by anyone;
  * read over your shoulder at a busy desk;
  * left behind in a browser on a shared computer.

And the prize for guessing it is the ability to rewrite what a hospital tells
sick people about medicines, fees and emergencies. That is too much to hang on
one word.

So there are TWO locks, and both must be open:

  1. You must be SIGNED IN as the Super Admin, in that browser.
  2. You must know the code.

The code still does the work the founder wanted: it means an ordinary sentence
never gets mistaken for an edit, and a colleague using your signed-in tablet
cannot change an answer by accident. But an outsider who guesses the code gets
nothing at all, because they are not signed in.

Every edit is audit-logged with your name, and the previous wording is kept.

THE FORMAT
----------
    CODE intent-name :: the corrected answer
    CODE global intent-name :: the corrected answer     <- all hospitals

Without `global` the change is saved for THIS hospital only, which is the safe
default: a wrong edit affects one hospital, not every hospital using the suite.
"""
from __future__ import annotations

import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from ..models import KnowledgeArticle, db

# Where the hashed code lives, per hospital.
SETTING_KEY = "kb_quickedit_code_hash"

# The separator between "which answer" and "what it should say". Two colons
# because a single one appears in ordinary sentences ("Note: we are closed").
SEPARATOR = "::"

MIN_CODE_LENGTH = 4
MIN_ANSWER_LENGTH = 15


# ------------------------------------------------------------------ the code
def set_code(org_id: int, raw_code: str) -> tuple[bool, str]:
    """Set (or change) the secret word. Stored hashed, never in plain text."""
    from .. import services
    raw_code = (raw_code or "").strip()
    if len(raw_code) < MIN_CODE_LENGTH:
        return False, (f"The code must be at least {MIN_CODE_LENGTH} characters. "
                       f"Pick something nobody would type by accident.")
    if " " in raw_code:
        return False, "The code must be a single word, with no spaces."
    services.set_setting(org_id, SETTING_KEY,
                         generate_password_hash(raw_code, method="scrypt"))
    return True, "Your correction code is saved."


def has_code(org_id: int) -> bool:
    from .. import services
    return bool(services.get_setting(org_id, SETTING_KEY, ""))


def _code_matches(org_id: int, candidate: str) -> bool:
    from .. import services
    stored = services.get_setting(org_id, SETTING_KEY, "")
    if not stored or not candidate:
        return False
    try:
        return check_password_hash(stored, candidate)
    except Exception:                                    # noqa: BLE001
        return False


def suggest_code() -> str:
    """A code that is easy to type but not guessable."""
    return "fix" + secrets.token_hex(3)


# ------------------------------------------------------------------ parsing
def looks_like_edit(text: str) -> bool:
    """Cheap check before doing anything expensive.

    Deliberately does NOT look at the code — we must not treat "is this the
    right code?" as the same question as "is this an edit?", or a wrong guess
    would be answered as an ordinary chat message and quietly confirm to an
    attacker that the format is right.
    """
    return SEPARATOR in (text or "") and len((text or "").split()) >= 3


def parse(text: str) -> dict | None:
    """Pull apart `CODE [global] intent :: new answer`. No auth here."""
    if not looks_like_edit(text):
        return None
    head, _, body = (text or "").partition(SEPARATOR)
    parts = head.strip().split()
    if len(parts) < 2:
        return None

    code = parts[0]
    rest = parts[1:]
    scope = "tenant"
    if rest and rest[0].lower() in ("global", "all", "everyone"):
        scope = "global"
        rest = rest[1:]
    if not rest:
        return None

    intent = re.sub(r"[^a-z0-9_]+", "_", "_".join(rest).lower()).strip("_")
    if not intent:
        return None
    return {"code": code, "scope": scope, "intent": intent,
            "answer": body.strip()}


# ------------------------------------------------------------------ applying
def apply(org_id: int, user, text: str) -> tuple[bool, str]:
    """Do the correction. Returns (handled, message shown in the chat).

    `handled` False means "this was not an edit at all" — carry on and answer
    it as a normal question.
    """
    parsed = parse(text)
    if parsed is None:
        return False, ""

    # LOCK 1 — signed in as the Super Admin, in this browser.
    if user is None or not getattr(user, "is_authenticated", False) \
            or getattr(user, "role", "") != "SUPER_ADMIN":
        # Say nothing useful. An outsider who stumbles on the format must not
        # learn that they were close, so this reads like any other unknown
        # question rather than "wrong password".
        return False, ""

    if getattr(user, "org_id", None) != org_id:
        return False, ""

    # LOCK 2 — the code.
    if not has_code(org_id):
        return True, ("No correction code has been set yet. Set one first in "
                      "Admin \u2192 Answer book \u2192 Correction code.")
    if not _code_matches(org_id, parsed["code"]):
        return True, ("That correction code is not right, so nothing has been "
                      "changed.")

    answer = parsed["answer"]
    if len(answer) < MIN_ANSWER_LENGTH:
        return True, (f"That replacement looks too short ({len(answer)} "
                      f"characters). Paste the full corrected answer after "
                      f"\u201c{SEPARATOR}\u201d.")

    intent = parsed["intent"]
    want_global = parsed["scope"] == "global"

    existing_tenant = (db.session.query(KnowledgeArticle)
                       .filter_by(org_id=org_id, intent=intent).first())
    existing_global = (db.session.query(KnowledgeArticle)
                       .filter(KnowledgeArticle.org_id.is_(None),
                               KnowledgeArticle.intent == intent).first())
    template = existing_tenant or existing_global
    if template is None:
        return True, (f"I could not find an answer called \u201c{intent}\u201d. "
                      f"Check the name in the Answer book, or add it there.")

    old_text = (template.en or "")[:400]

    if want_global:
        if existing_global is None:
            return True, (f"\u201c{intent}\u201d only exists for this hospital, "
                          f"so it cannot be changed globally.")
        existing_global.en = answer
        target = existing_global
        where = "every hospital"
    elif existing_tenant is not None:
        existing_tenant.en = answer
        target = existing_tenant
        where = "this hospital"
    else:
        # First correction of a shared answer: copy it for this hospital only.
        # Editing the shared original would change every hospital at once,
        # which is never what "fix this one" means.
        target = KnowledgeArticle(
            org_id=org_id, category=existing_global.category,
            intent=existing_global.intent, keywords=existing_global.keywords,
            en=answer, pidgin=existing_global.pidgin, yo=existing_global.yo,
            ha=existing_global.ha, ig=existing_global.ig,
            cta=existing_global.cta,
            clinical_safe=existing_global.clinical_safe,
            scope="tenant", status="approved",
            submitted_by=getattr(user, "id", None))
        db.session.add(target)
        where = "this hospital"

    db.session.flush()
    return True, {
        "message": (f"\u2705 Updated \u201c{intent}\u201d for {where}. "
                    f"Ask the question again to hear the new answer."),
        "intent": intent,
        "article_id": target.id,
        "scope": "global" if want_global else "tenant",
        "old": old_text,
    }
