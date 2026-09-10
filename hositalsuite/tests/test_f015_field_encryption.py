"""F-015: field-level encryption for the most sensitive PHI.

With FIELD_ENCRYPTION_KEY set, next-of-kin phone, home address and date of
birth must be UNREADABLE in the database dump (a backup zip, a stolen dump,
another app on the same DB) while the application sees plaintext exactly as
before. With no key, behaviour is byte-for-byte the old plaintext path — a
hospital opts in at deploy time, never in code.
"""
from __future__ import annotations

import datetime as dt

import pytest

FERNET_KEY = "gtoPzrJFNLYjQI4hVv_bArElBgY0GZP4fLbkoDK1FxA="  # random, test-only


@pytest.fixture()
def encrypting_app(app, monkeypatch):
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", FERNET_KEY)
    from app import crypto_fields
    crypto_fields._KEY_CACHE.clear()
    yield app
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
    crypto_fields._KEY_CACHE.clear()


def _raw_column(db, table, col, org_id):
    with db.engine.connect() as conn:
        rows = conn.execute(
            db.text(f"SELECT {col} FROM {table} WHERE org_id = :o"),  # noqa: S608
            {"o": org_id}).fetchall()
    return [r[0] for r in rows]


def test_phi_is_ciphertext_at_rest_and_plaintext_in_the_app(encrypting_app, seeded):
    from app.models import db, Patient, now_naive
    with encrypting_app.app_context():
        p = Patient(org_id=seeded["org"], hospital_number="IJ/2026/F015",
                    surname="OKE", first_name="Tola", sex="F", age_years=29,
                    payer_type="SELF", category="GENERAL",
                    date_of_birth=dt.date(1997, 3, 14),
                    address="12 Ikorodu Road, Agric, Ijede",
                    nok_phone="08012345678", nok_name="Mama Tola")
        db.session.add(p)
        db.session.commit()
        pid = p.id
    with encrypting_app.app_context():
        p = db.session.get(Patient, pid)
        assert p.nok_phone == "08012345678"                 # app sees plaintext
        assert p.address.startswith("12 Ikorodu Road")
        assert p.date_of_birth == dt.date(1997, 3, 14)
        raw_phones = _raw_column(db, "patient", "nok_phone", seeded["org"])
        raw_addr = _raw_column(db, "patient", "address", seeded["org"])
        assert raw_phones and all("08012345678" not in (r or "") for r in raw_phones)
        assert any(r and r.startswith("gAAAA") for r in raw_phones)   # Fernet token
        assert raw_addr and all("Ikorodu Road" not in (r or "") for r in raw_addr)
        raw_dob = _raw_column(db, "patient", "date_of_birth", seeded["org"])
        assert all("1997-03-14" not in (r or "") for r in raw_dob)


def test_legacy_plaintext_rows_still_read_after_enabling(app, seeded, monkeypatch):
    """A hospital turns the key ON with existing plaintext rows — nothing may
    break, and the values stay readable exactly as stored."""
    from app import crypto_fields
    from app.models import db, Patient
    with app.app_context():                                 # key OFF → plaintext row
        p = Patient(org_id=seeded["org"], hospital_number="IJ/2026/OLD",
                    surname="OLD", first_name="Row", sex="F", age_years=51,
                    payer_type="SELF", category="GENERAL",
                    nok_phone="07000000000", address="Old Street")
        db.session.add(p)
        db.session.commit()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", FERNET_KEY)   # the deploy turns it on
    crypto_fields._KEY_CACHE.clear()
    with app.app_context():
        p = Patient.query.filter_by(org_id=seeded["org"], hospital_number="IJ/2026/OLD").first()
        assert p.nok_phone == "07000000000"                 # legacy value passes through
        assert p.address == "Old Street"


def test_blind_index_finds_nok_phone_without_storing_it(encrypting_app, seeded):
    from app.models import db, Patient
    with encrypting_app.app_context():
        p = Patient(org_id=seeded["org"], hospital_number="IJ/2026/BX",
                    surname="BELLO", first_name="Ada", sex="F", age_years=40,
                    payer_type="SELF", category="GENERAL", nok_phone="08099990000")
        db.session.add(p)
        db.session.commit()
        hit = (Patient.query.filter_by(org_id=seeded["org"])
               .filter(Patient.nok_phone_bx.isnot(None)).all())
        assert any(x.hospital_number == "IJ/2026/BX" for x in hit)
        assert all(x.nok_phone_bx != "08099990000" for x in hit)


def test_hims_lookup_matches_full_nok_number_when_encrypted(encrypting_app, seeded):
    """The folder search must still find a patient by NOK number — via the
    blind index now, since LIKE on ciphertext is impossible by design."""
    from app.models import db, Patient
    from app import hims
    with encrypting_app.app_context():
        db.session.add(Patient(org_id=seeded["org"], hospital_number="IJ/2026/NOKQ",
                               surname="NOKQ", first_name="Ada", sex="F", age_years=35,
                               payer_type="SELF", category="GENERAL", nok_phone="08099990000"))
        db.session.commit()
        hits = hims.search(seeded["org"], "08099990000")
        assert any(p.hospital_number == "IJ/2026/NOKQ" for p in hits)
        # partial digits no longer match NOK phone (documented behaviour change)
        hits_partial = hims.search(seeded["org"], "0809999")
        assert not any(p.hospital_number == "IJ/2026/NOKQ" for p in hits_partial)


def test_backfill_command_encrypts_legacy_rows(app, seeded, monkeypatch):
    from app import crypto_fields
    from app.models import db, Patient
    with app.app_context():                                 # legacy plaintext row
        db.session.add(Patient(org_id=seeded["org"], hospital_number="IJ/2026/BF",
                               surname="BACK", first_name="Fill", sex="M", age_years=60,
                               payer_type="SELF", category="GENERAL",
                               nok_phone="08055500011", address="Backfill Close"))
        db.session.commit()
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", FERNET_KEY)
    crypto_fields._KEY_CACHE.clear()
    from app import encrypt_phi_backfill as bf
    assert bf.main() == 0
    with app.app_context():
        raw = _raw_column(db, "patient", "nok_phone", seeded["org"])
        assert any(r and r.startswith("gAAAA") for r in raw)
        assert all("08055500011" not in (r or "") for r in raw)
        p = Patient.query.filter_by(hospital_number="IJ/2026/BF").first()
        assert p.nok_phone == "08055500011"
        assert p.nok_phone_bx


def test_without_key_everything_stays_plaintext(app, seeded, monkeypatch):
    from app import crypto_fields
    from app.models import db, Patient
    monkeypatch.delenv("FIELD_ENCRYPTION_KEY", raising=False)
    crypto_fields._KEY_CACHE.clear()
    with app.app_context():
        p = Patient(org_id=seeded["org"], hospital_number="IJ/2026/PLAIN",
                    surname="PLAIN", first_name="Text", sex="F", age_years=30,
                    payer_type="SELF", category="GENERAL",
                    nok_phone="09011122233", address="Plain Street")
        db.session.add(p)
        db.session.commit()
        raw = _raw_column(db, "patient", "nok_phone", seeded["org"])
        assert any(r == "09011122233" for r in raw)
        assert p.nok_phone_bx is None                       # no key → no index
