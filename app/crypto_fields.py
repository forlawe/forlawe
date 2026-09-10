"""Field-level encryption for the most sensitive PHI columns (F-015).

Provider-level at-rest encryption protects the database against someone
stealing a disk. Field-level encryption protects the columns that hurt most
— next-of-kin phone numbers, home addresses, dates of birth — even against
someone holding a DATABASE DUMP: a backup zip, a support engineer, another
app sharing the database. Without the key the dump shows only ciphertext.

Design (deliberately conservative — a hospital must never lose its data):

* Key: the ``FIELD_ENCRYPTION_KEY`` env var, a Fernet key (urlsafe base64,
  32 bytes). Generate one:  ``python -c "from cryptography.fernet import
  Fernet; print(Fernet.generate_key().decode())"`` — and NEVER rotate it
  casually: values are only readable under the key that encrypted them.

* Opt-in and reversible-by-design: if the key is NOT set, columns store and
  return plaintext exactly as before — enabling encryption is a deploy-time
  decision, not a code-path fork hospital code must know about.

* Legacy rows: ``process_result_value`` returns the stored value unchanged
  when it isn't valid ciphertext, so a hospital that turns the key on keeps
  working instantly (mixed plaintext/ciphertext) and the
  ``flask encrypt-phi-backfill`` command rewrites legacy rows afterwards.

* Search: encryption kills LIKE. Equality lookups use a BLIND INDEX — an
  unkeyed-to-the-DB HMAC of the normalised phone stored beside the
  ciphertext, so the DB can match without ever seeing the number. Active
  only while the key is set; the old LIKE search keeps working until then
  (see app/hims.py).

Covered columns (both Patient and ReceptionIntake, per the audit):
``date_of_birth``, ``address``, ``nok_phone``, ``nok_address`` (intake has
no nok_address).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac as _hmac
import logging
import os

from sqlalchemy import Date, String, Text, TypeDecorator

log = logging.getLogger(__name__)

_KEY_CACHE: list = []


def _fernet():
    """The Fernet instance for FIELD_ENCRYPTION_KEY, or None when unset."""
    if _KEY_CACHE:
        return _KEY_CACHE[0]
    raw = (os.environ.get("FIELD_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            from cryptography.fernet import Fernet
            _KEY_CACHE.append(Fernet(raw.encode()))
        except Exception:                                    # noqa: BLE001
            log.exception("FIELD_ENCRYPTION_KEY is set but not a valid Fernet "
                          "key — PHI field encryption is OFF")
            _KEY_CACHE.append(None)
    else:
        _KEY_CACHE.append(None)
    return _KEY_CACHE[0]


def encryption_enabled() -> bool:
    """True once a valid FIELD_ENCRYPTION_KEY is configured."""
    return _fernet() is not None


def blind_index(namespace: str, value: str | None) -> str | None:
    """Deterministic, non-reversible search index for an encrypted value.

    HMAC-SHA256(key, namespace + normalised value), truncated — the DB can
    answer "which row has this exact phone number?" without storing or
    seeing the number itself. Returns None while encryption is off (the
    plaintext LIKE search covers lookups then).
    """
    f = _fernet()
    if f is None or not value:
        return None
    norm = "".join(ch for ch in str(value) if ch.isdigit())
    if not norm:
        return None
    dig = _hmac.new(f._signing_key, f"{namespace}:{norm}".encode(),  # noqa: SLF001
                    hashlib.sha256).hexdigest()
    return dig[:32]


class _EncryptedMixin:
    def _encrypt(self, value):
        f = _fernet()
        if value is None or f is None:
            return value
        return f.encrypt(str(value).encode()).decode()

    def _decrypt(self, value):
        f = _fernet()
        if value is None or f is None:
            return value
        try:
            return f.decrypt(str(value).encode()).decode()
        except Exception:                                    # noqa: BLE001
            # Legacy plaintext row (encryption was switched on after this
            # value was written) or a value encrypted under a different key.
            # Return as stored — never break a hospital over one bad row.
            return value


class EncryptedString(_EncryptedMixin, TypeDecorator):
    """A string column stored as Fernet ciphertext when a key is configured."""

    impl = String
    cache_ok = True

    def __init__(self, length=256, **kw):
        super().__init__(length, **kw)

    def process_bind_param(self, value, dialect):
        return self._encrypt(value)

    def process_result_value(self, value, dialect):
        return self._decrypt(value)


class EncryptedText(_EncryptedMixin, TypeDecorator):
    """A long free-text column (addresses) stored as Fernet ciphertext."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return self._encrypt(value)

    def process_result_value(self, value, dialect):
        return self._decrypt(value)


class EncryptedDate(_EncryptedMixin, TypeDecorator):
    """A Date column stored as an encrypted ISO string ("2026-09-04")."""

    impl = String
    cache_ok = True

    def __init__(self, length=256, **kw):
        super().__init__(length, **kw)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, _dt.date):
            value = value.isoformat()
        return self._encrypt(value)

    def process_result_value(self, value, dialect):
        plain = self._decrypt(value)
        if plain is None:
            return None
        try:
            return _dt.date.fromisoformat(str(plain)[:10])
        except (ValueError, TypeError):
            return value  # legacy raw value we couldn't parse


def backfill_needed() -> bool:
    """True when encryption is on (legacy plaintext rows may still exist)."""
    return encryption_enabled()
