"""Time-based one-time passwords (TOTP) — no extra library.

Staff sign in with a password AND a 6-digit code from their phone
(Google Authenticator, Microsoft Authenticator, or any similar app).
Backup codes let them in if the phone is lost.

The algorithm is RFC 6238 (the same one every authenticator app uses).
We implement it here so the hospital does not depend on another package.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import secrets
import struct
import time

from werkzeug.security import check_password_hash, generate_password_hash

ISSUER = "CareQueue"
STEP = 30
DIGITS = 6
BACKUP_COUNT = 8


def new_secret() -> str:
    """20 random bytes as a base32 secret (no padding — apps prefer that)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key_bytes(secret: str) -> bytes:
    pad = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret.upper() + pad, casefold=True)


def totp(secret: str, for_time: float | None = None, *, step: int = STEP,
         digits: int = DIGITS) -> str:
    counter = int((time.time() if for_time is None else for_time) // step)
    digest = hmac.new(_key_bytes(secret), struct.pack(">Q", counter),
                      hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, token: str, *, window: int = 1) -> bool:
    """Accept the current step and one step either side (clock drift)."""
    token = "".join(ch for ch in (token or "") if ch.isdigit())
    if not secret or len(token) != DIGITS:
        return False
    now = time.time()
    for i in range(-window, window + 1):
        expected = totp(secret, now + i * STEP)
        if hmac.compare_digest(expected, token):
            return True
    return False


def otpauth_uri(secret: str, username: str, issuer: str = ISSUER) -> str:
    from urllib.parse import quote
    label = quote(f"{issuer}:{username}")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
            f"&period={STEP}&digits={DIGITS}&algorithm=SHA1")


def qr_data_uri(uri: str) -> str:
    """PNG data-URI of the otpauth QR — no extra HTTP request."""
    import qrcode
    img = qrcode.make(uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def new_backup_codes(n: int = BACKUP_COUNT) -> list[str]:
    """Readable 8-character codes. Shown ONCE. Stored only as hashes."""
    return [secrets.token_hex(4).upper() for _ in range(n)]


def hash_backup_codes(codes: list[str]) -> str:
    return json.dumps([generate_password_hash(c, method="scrypt") for c in codes])


def consume_backup_code(stored: str | None, typed: str) -> tuple[bool, str | None]:
    """Return (ok, remaining_hashes_json). A used code is removed."""
    typed = (typed or "").strip().upper().replace(" ", "")
    if not stored or not typed:
        return False, stored
    try:
        hashes = json.loads(stored)
    except (TypeError, ValueError):
        return False, stored
    kept = []
    matched = False
    for h in hashes:
        if not matched and check_password_hash(h, typed):
            matched = True
            continue
        kept.append(h)
    return matched, (json.dumps(kept) if matched else stored)


def role_must_use_mfa(role: str, required_roles) -> bool:
    if not required_roles:
        return False
    if isinstance(required_roles, str):
        required_roles = [r.strip() for r in required_roles.split(",") if r.strip()]
    return role in set(required_roles)
