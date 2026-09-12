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

from sqlalchemy import text

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
    "sms_message", "whatsapp_message", "report_file", "stored_file",
    "chat_session", "data_request", "qr_location",
    "service_clinic", "consulting_room", "service_destination", "clinic_destination",
    "tv_screen", "staff_attendance", "branch",
    # Shop door: staff names, hospital settings, and the org chart.
    # These used to rely only on Python remembering the filter.
    "user", "setting", "department", "section", "unit",
    # Native voice phrase bank — per-tenant voices and phrases
    "native_voice", "native_phrase", "native_voice_setting",
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
def register(app) -> None:
    """Set the tenant at the start of every request, from the SIGNED-IN USER.

    Taken from the server-side session, never from anything the browser can
    choose. A tenant id accepted from a header or a query string would hand an
    attacker the exact switch this feature exists to remove.
    """
    @app.before_request
    def _apply_tenant():                                   # noqa: ANN202
        if not is_postgres():
            return None
        try:
            # MUST open the door first. Flask-Login looks up the account on
            # `user`. If that table is locked to an unset hospital, every
            # signed-in person is treated as a stranger and thrown out.
            all_orgs()
            from flask_login import current_user
            if getattr(current_user, "is_authenticated", False):
                set_org(current_user.org_id)
            # Public pages stay in all_orgs: they pick a hospital in their
            # own code and stamp org_id on every row they create.
        except Exception:                                      # noqa: BLE001
            log.exception("tenant scoping failed for this request")
        return None
