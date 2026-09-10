"""F-074 — first-run seeding must NEVER fall back to hardcoded passwords.

The rebuild spec (Phase 1) requires: "Seed/demo data generation never falls
back to a hardcoded password for a privileged role under any code path. If no
strong password/env override is supplied, generation must fail loudly rather
than default to a known string."

These tests pin that rule: seeding with NO override must produce fresh random
passwords (printed once), never any member of the historical known-password
set, and the seed module itself must not contain those strings.
"""
import re

from app import create_app
from app.models import Organization, User, db
from app.seeddata import seed_data

# The historical "famous" passwords that used to be baked into the code.
# They are listed HERE ONLY so the test can prove they no longer work.
LEGACY_KNOWN = [
    "Admin#2026!", "Mdceo#2026!", "Amfunke#2026!", "Amemeka#2026!",
    "Hodmed#2026!", "Hodsurg#2026!", "Hodpaeds#2026!", "Hoder#2026!",
    "Hodpharm#2026!", "Hodlab#2026!",
]

SEED_USERNAMES = [
    "admin", "md", "am.funke", "am.emeka",
    "hod.medicine", "hod.surgery", "hod.paeds", "hod.emergency",
    "hod.pharmacy", "hod.lab",
]


def _seed_and_capture(app, capsys, **kwargs):
    """Run seed_data on the empty test DB and parse the printed credentials."""
    with app.app_context():
        assert db.session.query(Organization).count() == 0
        org = seed_data(app, **kwargs)
        assert org is not None, "seed_data should have created an org"
    out = capsys.readouterr().out
    creds = {}
    for line in out.splitlines():
        m = re.match(r"^\s*([\w.\-]+)\s+/\s+(\S+)\s*$", line)
        if m:
            creds[m.group(1)] = m.group(2)
    return creds


def test_seed_without_overrides_generates_random_passwords(app, capsys):
    creds = _seed_and_capture(app, capsys)
    assert set(creds) == set(SEED_USERNAMES), "every seed account printed once"
    with app.app_context():
        for uname, printed_pw in creds.items():
            u = db.session.query(User).filter_by(username=uname).first()
            assert u is not None and u.must_change_password is True
            assert u.check_password(printed_pw), \
                f"printed credential should log in for {uname}"
            for legacy in LEGACY_KNOWN:
                assert not u.check_password(legacy), \
                    f"{uname} still accepts the famous password {legacy!r}!"
            assert len(printed_pw) >= 16, \
                f"generated password for {uname} too short to be strong"


def test_seed_honours_explicit_override_and_randomizes_the_rest(app, capsys):
    creds = _seed_and_capture(app, capsys, passwords={"admin": "MyOwn#2026x!"})
    assert creds["admin"] == "MyOwn#2026x!"
    with app.app_context():
        admin = db.session.query(User).filter_by(username="admin").first()
        assert admin.check_password("MyOwn#2026x!")
        # even with a partial override, the non-overridden accounts must NOT
        # fall back to known strings (this exact bug existed in auto_seed).
        md = db.session.query(User).filter_by(username="md").first()
        for legacy in LEGACY_KNOWN:
            assert not md.check_password(legacy), "md leaked a legacy password"


def test_seed_source_contains_no_known_password_strings():
    src = open("app/seeddata.py", encoding="utf-8").read()
    assert "DEFAULT_PASSWORDS" not in src
    for legacy in LEGACY_KNOWN:
        assert legacy not in src, f"hardcoded password {legacy!r} found in seeddata.py"


def test_auto_seed_without_env_overrides_uses_random(app, monkeypatch, capsys):
    """Production AUTO_SEED path: no SEED_* env vars -> random, not famous."""
    import os
    for uname in SEED_USERNAMES:
        env_key = "SEED_" + uname.upper().replace(".", "_").replace("-", "_")
        monkeypatch.delenv(env_key, raising=False)
    monkeypatch.setenv("AUTO_SEED", "1")
    with app.app_context():
        assert db.session.query(Organization).count() == 0
    app2 = create_app(scheduler=False)
    with app2.app_context():
        # boot enabled RLS on the protected tables (user is one); reading the
        # seeded accounts is a cross-hospital read — declare all-orgs scope
        from app import rls
        rls.all_orgs()
        assert db.session.query(Organization).count() == 1
        for uname in ("admin", "md", "am.funke"):
            u = db.session.query(User).filter_by(username=uname).first()
            assert u is not None
            for legacy in LEGACY_KNOWN:
                assert not u.check_password(legacy), \
                    f"AUTO_SEED created {uname} with famous password {legacy!r}"
