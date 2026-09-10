"""F-015: one-time rewrite of PHI columns from legacy plaintext to ciphertext.

Run AFTER setting FIELD_ENCRYPTION_KEY in the environment:

    python -m app.encrypt_phi_backfill

Safe to run repeatedly (idempotent): values already encrypted are left as
they are; plaintext values are encrypted in place. Rows are also given their
blind search index. Run it again with the key REMOVED to see how many rows
are still plaintext (they will be counted, nothing is changed).
"""
from __future__ import annotations

import sys

from cryptography.fernet import InvalidToken
from sqlalchemy.orm.attributes import flag_modified

from . import create_app, crypto_fields
from .models import db, Patient, ReceptionIntake


def _is_encrypted(value: str | None) -> bool:
    if not value:
        return True                     # empty is fine either way
    f = crypto_fields._fernet()
    if f is None:
        return False
    try:
        f.decrypt(str(value).encode())
        return True
    except InvalidToken:
        return False


def main() -> int:
    if not crypto_fields.encryption_enabled():
        print("FIELD_ENCRYPTION_KEY is not set — refusing to run (nothing to "
              "encrypt with). Set it first, then re-run.")
        return 2
    app = create_app(scheduler=False)
    with app.app_context():
        stats = {}
        for model, fields in (
            (Patient, ("date_of_birth", "address", "nok_phone", "nok_address")),
            (ReceptionIntake, ("date_of_birth", "address", "nok_phone")),
        ):
            done = 0
            rows = model.query.all()
            for row in rows:
                dirty = False
                for field in fields:
                    raw = getattr(row, field)      # legacy plaintext passes through
                    if not _is_encrypted(raw if isinstance(raw, str) else str(raw or "")):
                        setattr(row, field, raw)   # re-set → type encrypts on flush
                        # same-value assignment produces no history, so force
                        # the column into the UPDATE statement
                        flag_modified(row, field)
                        dirty = True
                # make sure the blind index exists
                if getattr(row, "nok_phone", None) and not getattr(row, "nok_phone_bx", None):
                    row.nok_phone = row.nok_phone  # triggers @validates
                    dirty = True
                if dirty:
                    done += 1
                if done and done % 200 == 0:
                    db.session.commit()
            db.session.commit()
            stats[model.__name__] = (done, len(rows))
        for name, (done, total) in stats.items():
            print(f"{name}: {done}/{total} rows rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
