"""Row-Level Security: the database must refuse to leak between hospitals.

These tests are the seatbelt test. They deliberately write the bug a tired
developer would write — a query with NO org_id filter — and prove PostgreSQL
returns nothing instead of another hospital's patients.

POSTGRESQL ONLY. SQLite has no row-level security, so these skip there. That is
not a gap being waved away: production is Supabase (PostgreSQL), and the full
suite is run against real PostgreSQL 17 before every push precisely so these
run for real.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app import rls
from app.models import (Complaint, Organization, Patient, db, new_code,
                        now_naive)

pytestmark = pytest.mark.usefixtures("app")


def _pg_only():
    if not rls.is_postgres():
        pytest.skip("row-level security is a PostgreSQL feature")


def _two_hospitals():
    """Two tenants, one patient each. RLS must keep them apart."""
    rls.all_orgs()
    a = Organization(code="RLSA", name="Ijede Hospital")
    b = Organization(code="RLSB", name="Rival Hospital")
    db.session.add_all([a, b])
    db.session.flush()
    db.session.add(Patient(org_id=a.id, hospital_number="A/1", surname="ABATAN",
                           first_name="Folake", sex="F", payer_type="SELF",
                           category="GENERAL"))
    db.session.add(Patient(org_id=b.id, hospital_number="B/1", surname="SECRET",
                           first_name="Rival", sex="M", payer_type="SELF",
                           category="GENERAL"))
    db.session.commit()
    return a.id, b.id


# ================================================================ THE SEATBELT
def test_a_forgotten_org_filter_returns_nothing_not_someone_elses_patients(app):
    """THE test. This exact query leaked before RLS existed.

    We verified the danger rather than assuming it: with RLS off, this returned
    ['ABATAN', 'SECRET'] — one hospital reading another's patient list.
    """
    _pg_only()
    with app.app_context():
        rls.enable()
        a_id, b_id = _two_hospitals()

        rls.set_org(a_id)
        # A developer forgets `.filter(Patient.org_id == ...)`. One line.
        leaked = db.session.query(Patient).all()
        names = sorted(p.surname for p in leaked)

        assert "SECRET" not in names, (
            "CATASTROPHIC: a query with no org filter returned another "
            f"hospital's patients: {names}")
        assert names == ["ABATAN"], names


def test_the_table_owner_cannot_bypass_the_policy(app):
    """FORCE ROW LEVEL SECURITY, or this whole feature is decoration.

    PostgreSQL exempts a table's owner from its own policies by default, and
    Supabase connects as the owner. Without FORCE, every test above would pass
    while protecting nothing in production. This reads the catalogue directly.
    """
    _pg_only()
    with app.app_context():
        rls.enable()
        row = db.session.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = 'patient'")).first()
        assert row is not None, "the patient table is missing"
        assert row[0] is True, "row-level security is not enabled on patient"
        assert row[1] is True, (
            "FORCE ROW LEVEL SECURITY is off — Supabase connects as the table "
            "owner and would bypass every policy. The protection would be fake.")


def test_an_unset_tenant_sees_nothing_rather_than_everything(app):
    """Unset must fail CLOSED. The opposite default is how RLS rollouts leak."""
    _pg_only()
    with app.app_context():
        rls.enable()
        _two_hospitals()
        rls.clear()
        assert db.session.query(Patient).count() == 0, (
            "an unset tenant could read every hospital's patients — unset must "
            "mean 'see nothing', never 'see everything'")


def test_a_hospital_cannot_write_a_row_into_another_hospital(app):
    """WITH CHECK: stops planting rows as well as reading them."""
    _pg_only()
    with app.app_context():
        rls.enable()
        a_id, b_id = _two_hospitals()
        rls.set_org(a_id)
        db.session.add(Patient(org_id=b_id, hospital_number="X/1",
                               surname="PLANTED", first_name="Bad", sex="M",
                               payer_type="SELF", category="GENERAL"))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_complaints_are_protected_too_not_just_patients(app):
    """A patient list is not the only thing worth leaking."""
    _pg_only()
    with app.app_context():
        rls.enable()
        a_id, b_id = _two_hospitals()
        rls.all_orgs()
        from app.models import Department
        for oid, name in ((a_id, "A Dept"), (b_id, "B Dept")):
            d = Department(org_id=oid, name=name)
            db.session.add(d)
            db.session.flush()
            db.session.add(Complaint(
                org_id=oid, ref="C" + new_code(8), department_id=d.id,
                category="Long waiting time",
                description="A complaint that must not cross hospitals.",
                phone="08012345678", sla_hours=24,
                sla_deadline_at=now_naive()))
        db.session.commit()

        rls.set_org(a_id)
        assert db.session.query(Complaint).count() == 1, \
            "complaints leaked between hospitals"


def test_background_jobs_can_still_see_every_hospital(app):
    """The scheduler and the nightly backup legitimately span tenants.

    If this broke, SLA escalation would silently stop and the backup would
    write an empty archive that LOOKS like a success — a worse failure than a
    loud crash, because nobody would notice for months.
    """
    _pg_only()
    with app.app_context():
        rls.enable()
        _two_hospitals()
        rls.all_orgs()
        assert db.session.query(Patient).count() == 2, \
            "background jobs lost their cross-hospital sight"


def test_the_tenant_does_not_leak_onto_the_next_pooled_connection(app):
    """set_config(..., true) keeps it LOCAL to the transaction.

    A tenant id left behind on a pooled connection that the next hospital picks
    up would be worse than having no RLS at all.
    """
    _pg_only()
    with app.app_context():
        rls.enable()
        a_id, _ = _two_hospitals()
        rls.set_org(a_id)
        assert rls.current() == str(a_id)
        db.session.commit()                 # transaction ends
        leftover = rls.current()
        assert leftover in (None, "", "0"), \
            f"the tenant survived the transaction as {leftover!r}"


def test_enabling_is_idempotent(app):
    """Boot runs on every restart and every deploy retry."""
    _pg_only()
    with app.app_context():
        first = rls.enable()
        second = rls.enable()
        assert first == second and first > 0


# ================================================================ NO REGRESSION
def test_normal_signed_in_work_is_unaffected(app, client, seeded):
    """The seatbelt must not stop the car.

    Runs on BOTH engines: on SQLite it proves the no-op path is harmless, on
    PostgreSQL it proves real policies do not break ordinary use.
    """
    from tests.conftest import login
    login(client, "admin")
    for path in ("/", "/hims/", "/complaints", "/tracking", "/roster"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} broke under RLS ({r.status_code})"
        assert b"Something went wrong" not in r.data, f"{path} rendered a 500"


def test_rls_is_a_harmless_no_op_on_sqlite(app):
    """Local development must not need PostgreSQL installed."""
    with app.app_context():
        if rls.is_postgres():
            pytest.skip("this asserts the SQLite fallback")
        assert rls.enable() == 0
        rls.set_org(1)
        rls.all_orgs()
        rls.clear()
        assert rls.current() is None


# ================================================================ GUARDS
def test_the_protected_list_covers_the_data_that_matters():
    """A table quietly dropped from the list is a silent hole."""
    must_cover = ("patient", "patient_visit", "complaint", "reception_intake",
                  "journey_segment", "audit_log", "stored_file", "work_claim",
                  "user", "setting", "department", "section", "unit")
    for table in must_cover:
        assert table in rls.PROTECTED_TABLES, \
            f"'{table}' is no longer protected by row-level security"


def test_the_tenant_is_never_taken_from_the_browser():
    """Accepting a tenant id from a header or query string would hand an
    attacker the exact switch this feature exists to remove."""
    source = open(rls.__file__, encoding="utf-8").read()
    body = source[source.index("def register("):]
    for danger in ("request.args", "request.headers", "request.form",
                   "request.cookies"):
        assert danger not in body, \
            f"the tenant is being read from {danger} — it must come from the session"
    # Locking `user` without opening the door first logs everyone out.
    open_at = body.index("all_orgs()")
    load_at = body.index("current_user")
    assert open_at < load_at, \
        "the account must be loaded AFTER all_orgs(), or signed-in staff vanish"
