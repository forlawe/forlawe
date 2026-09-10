"""Create a new hospital from the public setup walk.

A hospital can be born without a developer. The walk asks only what a
person can answer on a phone: name, a short code for folder numbers,
who the first administrator is, colours, and whether to install the
usual departments.

Safety
------
* The first hospital on an empty database needs no invite.
* After that, a Super Admin must mint a one-time setup code. That keeps
  Ijede's live site from growing random extra hospitals.
* The password is never written into the browser cookie (Flask's session
  is signed, not secret).
* Hospital code and sign-in name are unique across the whole product.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import timedelta

from flask import current_app
from flask_login import current_user

from . import services
from .models import (ComplaintCategory, Organization, QrLocation, User, db,
                     new_code, now_naive)
from .security import clean_phone, password_strength_errors, valid_phone

INVITE_HOURS = 48
RESERVED_CODES = {
    "WWW", "API", "SALES", "LOGIN", "ADMIN", "START", "STATIC", "TV",
    "BOOK", "QUEUE", "CHAT", "HIMS", "MFA", "ADMINCP",
}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

CATEGORIES = (
    "Staff attitude / conduct",
    "Long waiting time",
    "Billing / charges",
    "Cleanliness / hygiene",
    "Equipment / facility issue",
    "Medication / pharmacy",
    "Communication",
    "Lost document / records",
    "Other",
)

QR_PLACES = (
    "Reception",
    "Emergency Unit",
    "Outpatient Department",
    "Pharmacy",
    "Ward",
)


def hospital_count() -> int:
    return db.session.query(Organization).count()


def needs_invite() -> bool:
    if hospital_count() == 0:
        return False
    try:
        if current_user.is_authenticated and current_user.role == "SUPER_ADMIN":
            return False
    except Exception:
        pass
    return True


def suggest_code(name: str) -> str:
    letters = re.sub(r"[^A-Z]", "", (name or "").upper())
    if len(letters) >= 3:
        return letters[:3]
    return (letters + "HOS")[:3]


def suggest_username(code: str) -> str:
    stem = re.sub(r"[^a-z0-9]", "", (code or "").lower()) or "hosp"
    return f"{stem}.admin"


def suggest_slug(code: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", (code or "").lower())[:40]


def safe_hex(raw: str, fallback: str) -> str:
    s = (raw or "").strip()
    return s.upper() if HEX.fullmatch(s) else fallback


def _invite_hash(code: str) -> str:
    secret = current_app.config.get("SECRET_KEY") or ""
    return hashlib.sha256(f"{secret}:{code.strip().upper()}".encode()).hexdigest()


def mint_invite(org_id: int) -> str:
    """One-time code, shown once. Previous unused code is replaced."""
    raw = secrets.token_hex(4).upper()
    code = f"{raw[:4]}-{raw[4:]}"
    services.set_setting(org_id, "onboard_invite", {
        "hash": _invite_hash(code),
        "exp": (now_naive() + timedelta(hours=INVITE_HOURS)).isoformat(),
        "uses": 1,
    })
    return code


def consume_invite(code: str) -> bool:
    typed = (code or "").strip().upper()
    if not typed:
        return False
    digest = _invite_hash(typed)
    now = now_naive()
    for org in db.session.query(Organization).all():
        row = services.get_setting(org.id, "onboard_invite") or {}
        if not isinstance(row, dict):
            continue
        if row.get("hash") != digest:
            continue
        exp = row.get("exp") or ""
        try:
            from datetime import datetime
            if datetime.fromisoformat(exp) < now:
                return False
        except ValueError:
            return False
        if int(row.get("uses") or 0) < 1:
            return False
        row["uses"] = 0
        row["used_at"] = now.isoformat()
        services.set_setting(org.id, "onboard_invite", row)
        return True
    return False


def validate(form) -> tuple[dict, list[str]]:
    errors: list[str] = []
    v: dict = {}

    v["name"] = (form.get("name") or "").strip()[:160]
    if len(v["name"]) < 3:
        errors.append("Hospital name is required (at least 3 letters).")

    code = re.sub(r"[^A-Z0-9]", "", (form.get("code") or "").upper())[:12]
    v["code"] = code
    if len(code) < 2 or len(code) > 12:
        errors.append("Give a short hospital code of 2–12 letters (e.g. IJD).")
    elif code in RESERVED_CODES:
        errors.append("That code is reserved. Try the first letters of the hospital name.")
    elif db.session.query(Organization).filter_by(code=code).first():
        errors.append("Another hospital already uses that code. Pick a different one.")

    slug = suggest_slug(code)
    if slug and db.session.query(Organization).filter_by(slug=slug).first():
        slug = f"{slug}-{new_code(3).lower()}"
    v["slug"] = slug or None

    phone = clean_phone(form.get("phone") or "")
    if phone and not valid_phone(phone):
        errors.append("Hospital phone does not look like a Nigerian number.")
    v["phone"] = phone or None
    v["email"] = (form.get("email") or "").strip()[:160] or None
    v["address"] = (form.get("address") or "").strip()[:300] or None

    v["admin_name"] = (form.get("admin_name") or "").strip()[:120]
    if len(v["admin_name"]) < 2:
        errors.append("Your full name is required.")

    username = (form.get("username") or "").strip().lower()
    username = re.sub(r"[^a-z0-9._-]", "", username)[:64]
    v["username"] = username
    if len(username) < 3:
        errors.append("Pick a sign-in name of at least 3 letters (e.g. ijd.admin).")
    # F-021: no global-username check — usernames are scoped per hospital,
    # and this onboarding is creating a brand-new hospital's namespace.

    password = form.get("password") or ""
    confirm = form.get("confirm") or ""
    if password != confirm:
        errors.append("The two passwords do not match.")
    for e in password_strength_errors(password):
        errors.append(e)
    v["password"] = password

    admin_phone = clean_phone(form.get("admin_phone") or "")
    if admin_phone and not valid_phone(admin_phone):
        errors.append("Your phone number does not look like a Nigerian number.")
    v["admin_phone"] = admin_phone or None

    v["brand_primary"] = safe_hex(form.get("brand_primary"), "#0E5A8A")
    v["brand_accent"] = safe_hex(form.get("brand_accent"), "#12B5A5")
    v["brand_gold"] = safe_hex(form.get("brand_gold"), "#FFD700")

    v["main_name"] = (form.get("main_name") or "Main").strip()[:160] or "Main"
    annex = (form.get("annex_name") or "").strip()[:160]
    v["annex_name"] = annex or None

    v["install_departments"] = bool(form.get("install_departments"))
    lang = (form.get("voice_lang") or "en").strip()
    from . import i18n
    v["voice_lang"] = lang if lang in i18n.LANGS else "en"

    if needs_invite():
        invite = (form.get("invite") or "").strip()
        v["invite"] = invite
        if not invite:
            errors.append("This site already has a hospital. Ask the administrator for a setup code.")
        elif not _invite_exists(invite):
            errors.append("That setup code is not right, or it has already been used.")
    else:
        v["invite"] = (form.get("invite") or "").strip()

    return v, errors


def _invite_exists(code: str) -> bool:
    """Check without consuming — consume happens only on successful create."""
    typed = (code or "").strip().upper()
    if not typed:
        return False
    digest = _invite_hash(typed)
    now = now_naive()
    for org in db.session.query(Organization).all():
        row = services.get_setting(org.id, "onboard_invite") or {}
        if not isinstance(row, dict) or row.get("hash") != digest:
            continue
        try:
            from datetime import datetime
            if datetime.fromisoformat(row.get("exp") or "") < now:
                return False
        except ValueError:
            return False
        return int(row.get("uses") or 0) >= 1
    return False


def create_hospital(values: dict, *, actor=None) -> tuple[Organization, User]:
    """All-or-nothing. Caller must commit."""
    if needs_invite():
        if not consume_invite(values.get("invite") or ""):
            raise ValueError("That setup code is not right, or it has already been used.")

    org = Organization(
        code=values["code"],
        name=values["name"],
        slug=values.get("slug"),
        phone=values.get("phone"),
        email=values.get("email"),
        address=values.get("address"),
    )
    db.session.add(org)
    db.session.flush()

    from .roles import ensure_builtin_roles
    ensure_builtin_roles(org.id)

    from . import branches as br
    main = br.ensure_main_branch(org.id)
    main.name = values.get("main_name") or "Main"
    main.address = values.get("address")
    main.phone = values.get("phone")
    if values.get("annex_name"):
        from .models import Branch
        if not db.session.query(Branch).filter_by(org_id=org.id, code="ANNEX").first():
            db.session.add(Branch(
                org_id=org.id, code="ANNEX", name=values["annex_name"],
                is_main=False, active=True,
            ))

    admin = User(
        org_id=org.id,
        username=values["username"],
        name=values["admin_name"],
        role="SUPER_ADMIN",
        phone=values.get("admin_phone"),
        email=values.get("email"),
        approved=True,
        email_verified=True,
        profile_completed=True,
        must_change_password=False,
        branch_id=main.id,
    )
    admin.set_password(values["password"])
    db.session.add(admin)
    db.session.flush()

    services.set_setting(org.id, "brand_primary", values["brand_primary"])
    services.set_setting(org.id, "brand_accent", values["brand_accent"])
    services.set_setting(org.id, "brand_gold", values["brand_gold"])
    services.set_setting(org.id, "onboarding_complete", True)
    services.set_setting(org.id, "onboard_guide", True)
    services.set_setting(org.id, "voice_lang", values.get("voice_lang") or "en")

    if values.get("install_departments"):
        from .standard_departments import install
        install(org.id, only_missing=True)

    for name in CATEGORIES:
        db.session.add(ComplaintCategory(org_id=org.id, name=name))
    for name in QR_PLACES:
        db.session.add(QrLocation(org_id=org.id, name=name, code=new_code(6)))

    from .audit import audit
    audit("HOSPITAL_ONBOARDED", "organization", org.id,
          {"name": org.name, "code": org.code, "username": admin.username},
          user=actor or admin, org_id=org.id)
    return org, admin
