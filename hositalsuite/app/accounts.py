"""Staff sign-in rules: strong password, real email, activation, admin OK.

WHY
---
A hospital account is a door into real people's records. A password a guest
can guess, a fake email, or a first-time user walking in without the System
Admin's say-so, is a hole. This file is the one place those rules live.
"""
from __future__ import annotations

import re
import secrets
from datetime import timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from .models import PasswordReset, User, db, now_naive

PASSWORD_MIN_LEN = 10

COMMON_PASSWORDS = frozenset({
    "password", "password1", "password12", "password123", "passw0rd",
    "1234567890", "12345678", "qwerty123", "qwertyuiop", "admin1234",
    "welcome1", "welcome12", "letmein12", "hospital1", "hospital12",
    "nigeria12", "ijede1234", "ghijede12", "changeme1", "abc1234567",
    "iloveyou1", "football1", "monkey123", "dragon123", "sunshine1",
})

# Public mailboxes people actually use. Plus Nigerian government / school mail.
KNOWN_MAIL = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.uk", "yahoo.co.ng", "ymail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com",
    "zoho.com", "aol.com", "mail.com",
    "gmx.com", "gmx.net", "fastmail.com", "yandex.com",
})
KNOWN_SUFFIX = (".gov.ng", ".edu.ng", ".mil.ng", ".org.ng", ".gov.uk")
DISPOSABLE = (
    "mailinator.", "tempmail.", "temp-mail.", "10minutemail.", "guerrillamail.",
    "trashmail.", "yopmail.", "throwaway.", "fakeinbox.", "getnada.",
    "sharklasers.", "discard.email",
)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
USER_RE = re.compile(r"^[a-z][a-z0-9._]{2,31}$")

VERIFY_MINUTES = 15
VERIFY_MAX_TRIES = 5

# What a person may ASK to be. Super Admin is never self-picked.
REQUESTABLE_ROLES = (
    "STAFF", "HOD", "ADMIN_MANAGER", "APEX_NURSE",
    "HEAD_ADMIN_HR", "DCST", "DMD", "MD_CEO",
)


def password_strength_errors(pw: str, *, username: str = "", email: str = "") -> list[str]:
    """Plain-English reasons this password is too easy to guess."""
    errors: list[str] = []
    raw = pw or ""
    if len(raw) < PASSWORD_MIN_LEN:
        errors.append(f"Password must be at least {PASSWORD_MIN_LEN} characters.")
    if not re.search(r"[A-Z]", raw):
        errors.append("Add at least one CAPITAL letter.")
    if not re.search(r"[a-z]", raw):
        errors.append("Add at least one small letter.")
    if not re.search(r"\d", raw):
        errors.append("Add at least one number.")
    if not re.search(r"[^A-Za-z0-9]", raw):
        errors.append("Add at least one symbol (for example ! @ # $ %).")
    lowered = raw.lower()
    if lowered in COMMON_PASSWORDS or lowered.replace("!", "") in COMMON_PASSWORDS:
        errors.append("That password is too common. Pick one a stranger could not guess.")
    uname = (username or "").strip().lower()
    if uname and len(uname) >= 3 and uname in lowered:
        errors.append("Do not put your username inside the password.")
    local = (email or "").split("@")[0].strip().lower()
    if local and len(local) >= 3 and local in lowered:
        errors.append("Do not put your email name inside the password.")
    if raw and len(set(raw.lower())) < 4:
        errors.append("Use a mix of different characters — not the same ones repeated.")
    return errors


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def email_errors(raw: str) -> list[str]:
    email = normalize_email(raw)
    if not email:
        return ["A real email is required (Gmail, Yahoo, Outlook, or your work mail)."]
    if " " in email or not EMAIL_RE.match(email):
        return ["That does not look like an email. Example: name@gmail.com"]
    if ".." in email or email.startswith(".") or email.endswith("."):
        return ["That email has a typing mistake."]
    domain = email.split("@", 1)[1]
    if any(bad in domain for bad in DISPOSABLE):
        return ["Temporary / fake mailboxes are not allowed. Use Gmail, Yahoo, Outlook or work mail."]
    if domain in KNOWN_MAIL:
        return []
    if domain.endswith(KNOWN_SUFFIX):
        return []
    # Hospital's own domain (whatever is on the hospital profile) is allowed.
    return []


def email_allowed_for_hospital(raw: str, hospital_email: str | None) -> list[str]:
    errs = email_errors(raw)
    if errs:
        return errs
    email = normalize_email(raw)
    domain = email.split("@", 1)[1]
    if domain in KNOWN_MAIL or domain.endswith(KNOWN_SUFFIX):
        return []
    hosp = normalize_email(hospital_email or "")
    if hosp and "@" in hosp and domain == hosp.split("@", 1)[1]:
        return []
    return ["Use Gmail, Yahoo, Outlook, iCloud, or a government / hospital email. "
            "Ask Admin if your work mail is not on that list."]


def username_available(org_id: int, username: str, *, ignore_user_id: int | None = None) -> bool:
    """F-021: a username may be reused by DIFFERENT hospitals, never twice
    inside the same one."""
    name = (username or "").strip().lower()
    if not name:
        return False
    q = db.session.query(User).filter(User.org_id == org_id,
                                      User.username == name)
    if ignore_user_id:
        q = q.filter(User.id != ignore_user_id)
    return q.first() is None


def username_errors(raw: str) -> list[str]:
    name = (raw or "").strip().lower()
    if not USER_RE.match(name):
        return ["Username: start with a letter, 3–32 characters, only letters, numbers, dot or underscore."]
    return []


def find_login_user(identifier: str, org_id: int | None = None) -> User | None:
    """Resolve a login identifier to ONE user.

    F-021: usernames are per-hospital. When the hospital is known (host,
    ?h= code, or a single-tenant server) the match happens INSIDE it. When
    it is not known and the identifier matches users in SEVERAL hospitals,
    the answer is None — never a guess — and the login page explains that
    the user should enter through their own hospital's page.
    """
    ident = (identifier or "").strip()
    if not ident:
        return None
    q = db.session.query(User)
    if org_id is not None:
        q = q.filter(User.org_id == org_id)
        u = q.filter(User.username == ident.lower()).first()
        if u:
            return u
    else:
        matches = q.filter(User.username == ident.lower()).all()
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None            # ambiguous across hospitals — refuse, never guess
    email = normalize_email(ident)
    if "@" in email:
        hits = q.filter(db.func.lower(User.email) == email).all()
        if len(hits) == 1:
            return hits[0]
    return None


def find_login_user_ambiguous(identifier: str, org_id: int | None = None) -> bool:
    """True when the identifier matches users in several hospitals and no
    hospital context was given (F-021) — the caller should show guidance."""
    ident = (identifier or "").strip().lower()
    if not ident or org_id is not None:
        return False
    usernames = (db.session.query(User)
                 .filter(User.username == ident).count())
    if usernames > 1:
        return True
    email = normalize_email(identifier or "")
    if "@" in email:
        return db.session.query(User).filter(
            db.func.lower(User.email) == email).count() > 1
    return False


def email_taken(org_id: int, email: str, *, ignore_user_id: int | None = None) -> bool:
    email = normalize_email(email)
    if not email:
        return False
    q = db.session.query(User).filter(User.org_id == org_id,
                                      db.func.lower(User.email) == email)
    if ignore_user_id:
        q = q.filter(User.id != ignore_user_id)
    return q.first() is not None


def is_email_verified(user: User) -> bool:
    if user is None:
        return False
    return bool(getattr(user, "email_verified", True))


def can_enter(user: User) -> tuple[bool, str]:
    """May this person use the app right now? (password already checked)."""
    if user is None:
        return False, "Invalid username or password."
    if not user.active:
        return False, "This account is switched off. Ask the System Admin."
    if not is_email_verified(user):
        return False, "VERIFY"
    if not getattr(user, "profile_completed", True):
        return False, "PROFILE"
    if not getattr(user, "approved", True):
        return False, "Your account is waiting for administrator approval. Please ask your hospital administrator to approve it."
    return True, ""


def issue_email_code(user: User) -> str:
    """Create a 6-digit activation code. Returns the digits (caller sends them)."""
    otp = f"{secrets.randbelow(1_000_000):06d}"
    db.session.query(PasswordReset).filter_by(user_id=user.id, used_at=None).filter(
        PasswordReset.channel == "verify"
    ).update({"used_at": now_naive()})
    db.session.add(PasswordReset(
        user_id=user.id,
        otp_hash=generate_password_hash(otp),
        channel="verify",
        expires_at=now_naive() + timedelta(minutes=VERIFY_MINUTES),
    ))
    db.session.flush()
    return otp


def check_email_code(user: User, otp: str) -> str | None:
    """None if OK. Else a plain-English error. Does not commit."""
    row = (db.session.query(PasswordReset)
           .filter_by(user_id=user.id, used_at=None, channel="verify")
           .order_by(PasswordReset.id.desc()).first())
    if row is None:
        return "No activation code is waiting. Ask for a new one."
    if row.expires_at < now_naive():
        return "That code has died. Ask for a new one."
    if (row.attempts or 0) >= VERIFY_MAX_TRIES:
        return "Too many tries. Ask for a new code."
    row.attempts = (row.attempts or 0) + 1
    if not check_password_hash(row.otp_hash, (otp or "").strip()):
        return "That code is wrong. Check the 6 digits."
    row.used_at = now_naive()
    user.email_verified = True
    user.email_verified_at = now_naive()
    return None


def send_activation(user: User, otp: str, hospital_name: str = "the hospital") -> dict:
    """Email first, SMS spare. Never raises. Never logs the digits.

    Returns {ok, via, error} so the screen can tell the truth.
    """
    from . import sms_pack
    class _O:
        name = hospital_name
        code = ""
        phone = None
        id = getattr(user, "org_id", None)
    body = sms_pack.signin_code(_O(), otp, VERIFY_MINUTES)
    subject = f"Your {hospital_name} sign-in code"
    result = {"ok": False, "via": "", "error": "Nothing sent"}
    try:
        from .notifications import _send_email
        if user.email:
            err = _send_email(user, subject, body)
            if err is None:
                result = {"ok": True, "via": "email", "error": ""}
            else:
                result = {"ok": False, "via": "", "error": err}
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "via": "", "error": str(exc)[:200]}
    if not result["ok"] and getattr(user, "phone", None):
        try:
            from . import sms as sms_engine
            sms_engine.queue_sms(user.org_id, user.phone, body, kind="alert",
                                 entity_type="email_verify", entity_id=user.id)
            from .tasks import dispatch_delivery
            dispatch_delivery()
            result = {"ok": True, "via": "sms", "error": ""}
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "via": "", "error": result["error"] or str(exc)[:200]}
    return result
