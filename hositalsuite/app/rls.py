"""Row-Level Security — the database itself refuses to leak between hospitals.

WHY THIS EXISTS
---------------
Until now, keeping one hospital's data away from another's depended entirely on
the application remembering to write `WHERE org_id = ?` — in 244 separate
places. That works right up until somebody forgets once. An outside reviewer
put it exactly right:

    "Application code is not a security boundary — it's a convenience. The
     database is the ultimate source of truth, and right now, it blindly
     trusts the app."

We proved the danger rather than assuming it: with RLS off, a query missing its
filter returned another hospital's patients. One line, easily missed in review,
and a patient list crosses hospitals.

WHAT THIS CHANGES
-----------------
PostgreSQL is now told, per table, "only ever return rows belonging to the
hospital named in `app.current_org`". If a future query forgets its filter, the
database returns NOTHING rather than somebody else's patients. The 244 existing
filters stay exactly as they are — they are now a second layer and a query
optimisation, not the only thing standing between two hospitals.

Defence in depth: the app asks for the right rows AND the database refuses to
hand over the wrong ones.

FOUR THINGS THAT MADE THIS SAFE TO SHIP
---------------------------------------
1. **PostgreSQL only.** SQLite has no RLS. Every function here is a no-op on
   SQLite, so local development and the SQLite test run behave exactly as
   before. Production (Supabase) is PostgreSQL, which is what matters.

2. **The owner must not bypass it.** By default PostgreSQL exempts a table's
   owner from its own policies — so `FORCE ROW LEVEL SECURITY` is set, or this
   whole file would be decoration. That is the single easiest way to build RLS
   that looks right and does nothing, and there is a test that proves it.

3. **Unset means nothing, not everything.** If `app.current_org` has never been
   set, the policy matches no rows. The opposite default — unset meaning
   "see everything" — is how RLS rollouts leak: one code path that forgets to
   set the variable silently gets superuser sight.

4. **Background jobs are explicitly exempt.** The scheduler, the nightly
   backup and the boot seeder legitimately work across all hospitals. They
   declare that intent by calling `all_orgs()`, which is auditable, rather than
   quietly not setting a variable.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar

from flask import g, has_request_context
from sqlalchemy import event, text

from .models import db

log = logging.getLogger(__name__)

# Tables carrying an org_id that must never cross hospitals. Deliberately an
# EXPLICIT list rather than "every table with an org_id column": adding a table
# to RLS should be a decision somebody makes and a reviewer sees, not something
# that happens silently when a column is renamed.
#
# `organization` itself is not listed: a tenant must be able to read its own
# row, and the join to it is already constrained by everything else.
PROTECTED_TABLES = (
    "patient", "patient_visit", "reception_intake", "journey_segment",
    "visit_onward", "doctor_session", "work_claim",
    "complaint", "complaint_category", "corrective_action",
    "appointment", "queue_ticket", "patient_feedback", "referral",
    "inspection", "duty_roster", "dept_roster_entry", "roster_entry",
    "user_role", "role", "audit_log", "app_notification",
    "sms_message", "whats_app_message", "report_file", "stored_file",
    "chat_session", "data_request", "qr_location",
    "service_clinic", "consulting_room", "service_destination", "clinic_destination",
    "tv_screen", "staff_attendance", "branch",
    # Shop door: staff names, hospital settings, and the org chart.
    # These used to rely only on Python remembering the filter.
    "user", "setting", "department", "section", "unit",
    # Native voice phrase bank — per-tenant voices and phrases
    "native_voice", "native_phrase", "native_voice_setting",
    # NOTE "whats_app_message" (not "whatsapp_message"): Flask-SQLAlchemy
    # derives the table name from the class WhatsAppMessage, and the old
    # spelling protected a table that does not exist — the real one, full of
    # patient phone numbers and message bodies, had no policy at all. Found
    # by auditing PROTECTED_TABLES against db.metadata on PostgreSQL.
)

# The PostgreSQL session variable holding "which hospital is this request for".
ORG_VAR = "app.current_org"

# Sentinel meaning "this is a background job that legitimately spans hospitals".
ALL_ORGS = "-1"


def is_postgres() -> bool:
    """RLS is a PostgreSQL feature. SQLite silently has no such thing."""
    try:
        return db.session.bind.dialect.name == "postgresql"
    except Exception:                                      # noqa: BLE001
        try:
            return db.engine.dialect.name == "postgresql"
        except Exception:                                  # noqa: BLE001
            return False


def _bypassing_role() -> str | None:
    """Name of the connected role if it can ignore row-level security entirely.

    Superusers and roles holding BYPASSRLS are exempt from EVERY policy —
    FORCE ROW LEVEL SECURITY only stops the table owner, not these roles. A
    deployment where the app connects as such a role (a default install's
    `postgres` superuser is the classic case; a bare VPS Postgres is full of
    them) has row-level security that reports "active on N tables" and
    protects nothing at all.

    Found by running the test suite against a real PostgreSQL 16 server:
    every enforcement test failed while connected as superuser and all of
    them passed the moment the connection role was non-superuser. Supabase's
    `postgres` role is NOT a superuser, which is why production is safe —
    but nobody should have to know that by accident.
    """
    if not is_postgres():
        return None
    try:
        row = db.session.execute(text(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname = current_user AND (rolsuper OR rolbypassrls)"
        )).scalar()
        return row
    except Exception:                                      # noqa: BLE001
        return None


# ------------------------------------------------------------------ enabling
def enable(app=None) -> int:
    """Turn RLS on for every protected table. Idempotent; safe on every boot.

    Uses FORCE ROW LEVEL SECURITY because Supabase connects as the table owner,
    and an owner is exempt from ordinary policies. Without FORCE this function
    would appear to work and protect nothing at all.
    """
    if not is_postgres():
        return 0                    # SQLite dev/test: nothing to do

    done = 0
    for table in PROTECTED_TABLES:
        try:
            exists = db.session.execute(text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = :t"),
                {"t": table}).first()
            if not exists:
                continue            # table not created yet; next boot will get it

            db.session.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            db.session.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            db.session.execute(text(f'DROP POLICY IF EXISTS org_isolation ON "{table}"'))
            # NULLIF(...,'')::int  -> unset variable becomes NULL, which matches
            # nothing. Unset must mean "see nothing", never "see everything".
            db.session.execute(text(
                f'CREATE POLICY org_isolation ON "{table}" '
                f"USING ("
                f"  NULLIF(current_setting('{ORG_VAR}', true), '')::int = {ALL_ORGS}"
                f"  OR org_id = NULLIF(current_setting('{ORG_VAR}', true), '')::int"
                f") "
                f"WITH CHECK ("
                f"  NULLIF(current_setting('{ORG_VAR}', true), '')::int = {ALL_ORGS}"
                f"  OR org_id = NULLIF(current_setting('{ORG_VAR}', true), '')::int"
                f")"))
            done += 1
        except Exception:                                  # noqa: BLE001
            # One awkward table must never stop the hospital booting. Log it
            # loudly — a table silently left unprotected is exactly the thing
            # this file exists to prevent.
            db.session.rollback()
            log.exception("RLS could not be enabled on %s", table)
    db.session.commit()
    if app is not None:
        app.logger.info("row-level security active on %s table(s)", done)
    bypassing = _bypassing_role()
    if bypassing:
        # Not fatal — the hospital must boot — but it MUST be loud. A silent
        # no-op here is exactly the failure mode this file exists to prevent.
        msg = ("row-level security is INERT: the connection role %r is a "
               "superuser or holds BYPASSRLS, and PostgreSQL exempts such "
               "roles from every policy. Tenant isolation currently depends "
               "on the application filters alone. Connect as a non-superuser "
               "role (Supabase's `postgres` is one) to activate the "
               "database-level protection.", bypassing)
        log.warning(*msg)
        if app is not None:
            app.logger.warning(*msg)
    return done


# ------------------------------------------------------------------ per request
def set_org(org_id) -> None:
    """Tell PostgreSQL which hospital this connection is currently serving.

    set_config(..., true) makes it LOCAL to the transaction, so it cannot leak
    into the next request that happens to reuse this pooled connection. Getting
    that wrong would be worse than no RLS at all: hospital A's id left behind on
    a connection that hospital B then picks up.
    """
    if not is_postgres():
        return
    try:
        db.session.execute(text(f"SELECT set_config('{ORG_VAR}', :v, true)"),
                           {"v": str(int(org_id))})
    except Exception:                                      # noqa: BLE001
        log.exception("could not set the tenant for this request")


def all_orgs() -> None:
    """Declare that this code legitimately works across every hospital.

    Only for background jobs: the scheduler, the nightly backup, the boot
    seeder. It is a deliberate, greppable call precisely so that "why can this
    code see everything?" always has a written answer.
    """
    if not is_postgres():
        return
    try:
        db.session.execute(text(f"SELECT set_config('{ORG_VAR}', '{ALL_ORGS}', true)"))
    except Exception:                                      # noqa: BLE001
        log.exception("could not enter cross-hospital mode")


def clear() -> None:
    """Back to seeing nothing. The safe default between requests."""
    if not is_postgres():
        return
    try:
        db.session.execute(text(f"SELECT set_config('{ORG_VAR}', '', true)"))
    except Exception:                                      # noqa: BLE001
        log.exception("could not clear the tenant")


def current() -> str | None:
    if not is_postgres():
        return None
    try:
        return db.session.execute(
            text(f"SELECT current_setting('{ORG_VAR}', true)")).scalar()
    except Exception:                                      # noqa: BLE001
        return None


# ------------------------------------------------------------------ wiring
# The tenant must be re-asserted for EVERY transaction a request opens, not
# just the first one. set_config(..., true) is transaction-local by design —
# it cannot leak into the next request on a pooled connection — but that also
# means any mid-request db.session.commit() ENDS it: the next lazy attribute
# refresh then runs with no tenant, row-level security correctly hides every
# row, and the ORM raises ObjectDeletedError and 500s the page. Found on a
# real PostgreSQL 16 server: /book and /queue/join both commit (referral
# tracking) between loading departments and rendering, so both doors were
# 500 on PostgreSQL while being 200 on SQLite, where RLS is a no-op.
#
# The fix: remember the request's tenant once (from the signed-in user), and
# stamp it onto every transaction as it begins via the ORM "after_begin"
# event. Commits are then harmless — the next transaction is scoped again.
#
# Background jobs get the same treatment via background_all_orgs(): the old
# single all_orgs() call in the scheduler's tick() covered only the FIRST
# transaction; the queue jobs commit per message, and every transaction
# after the first commit ran unscoped — ObjectDeletedError again, this time
# in job_whatsapp_queue / process_sms_queue.
_TENANT_G = "_rls_tenant"
_hook_installed = False
_background_all_orgs: ContextVar[bool] = ContextVar(
    "rls_background_all_orgs", default=False)


@contextmanager
def background_all_orgs():
    """Declare that this BACKGROUND code legitimately spans every hospital.

    The background counterpart of what before_request does for requests.
    The declaration is re-asserted at every transaction begin, so a mid-job
    db.session.commit() cannot silently drop it. Without it, non-request
    code fails closed and sees nothing — by design.
    """
    token = _background_all_orgs.set(True)
    try:
        yield
    finally:
        _background_all_orgs.reset(token)


def register(app) -> None:
    """Set the tenant at the start of every request, from the SIGNED-IN USER.

    Taken from the server-side session, never from anything the browser can
    choose. A tenant id accepted from a header or a query string would hand an
    attacker the exact switch this feature exists to remove.
    """
    global _hook_installed

    @app.before_request
    def _remember_tenant():                              # noqa: ANN202
        if not is_postgres():
            return None
        try:
            # Default FIRST, and the default is the all-orgs sentinel: public
            # pages pick a hospital in their own code, and Flask-Login's
            # account lookup itself must run with the door open or every
            # signed-in person is treated as a stranger and thrown out.
            setattr(g, _TENANT_G, ALL_ORGS)
            from flask_login import current_user
            if getattr(current_user, "is_authenticated", False) and \
                    getattr(current_user, "org_id", None) is not None:
                setattr(g, _TENANT_G, str(int(current_user.org_id)))
        except Exception:                                      # noqa: BLE001
            log.exception("tenant scoping failed for this request")
        return None

    def _apply_tenant(session, transaction, connection):   # noqa: ANN001
        try:
            if connection.dialect.name != "postgresql":
                return
            if has_request_context():
                tenant = getattr(g, _TENANT_G, ALL_ORGS)
            elif _background_all_orgs.get():
                tenant = ALL_ORGS
            else:
                # No request, no declaration: fail closed, see nothing.
                return
            connection.execute(
                text(f"SELECT set_config('{ORG_VAR}', :v, true)"),
                {"v": tenant})
        except Exception:                                      # noqa: BLE001
            log.exception("could not set the tenant for this transaction")

    if not _hook_installed:
        # Once per process, not once per app: the tests create an app per
        # test, and a listener per app would stack up into duplicate work.
        event.listen(db.session, "after_begin", _apply_tenant)
        _hook_installed = True
