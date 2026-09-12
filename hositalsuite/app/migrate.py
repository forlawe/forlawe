"""Zero-dependency schema drift fixer.

db.create_all() creates missing tables but cannot add columns to existing
tables. This helper adds known missing columns (idempotent, safe on both
SQLite and PostgreSQL) so existing deployments upgrade without manual SQL.
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import inspect, text

from .models import db

log = logging.getLogger("hms.migrate")


def _bool_true_sql() -> str:
    """Boolean defaulting to TRUE.

    Used for `user.approved`: every account that already exists was created by
    an administrator, so back-filling them as approved is correct. Defaulting
    to FALSE would lock the whole hospital out on the next deploy.
    """
    if str(db.engine.url).startswith("postgres"):
        return "BOOLEAN DEFAULT TRUE"
    return "INTEGER DEFAULT 1"


def _bool_sql() -> str:
    """BOOLEAN on PostgreSQL, INTEGER on SQLite — both accept 0/1 defaults."""
    if str(db.engine.url).startswith("postgres"):
        return "BOOLEAN DEFAULT FALSE"
    return "INTEGER DEFAULT 0"


# (table, column, sql_type) — sql_type may be a callable for dialect-specific types
COLUMNS = [
    ("complaint", "idempotency_key", "VARCHAR(40)"),
    ("department", "roster_mode", "VARCHAR(10) DEFAULT 'two_12h'"),
    ("department", "roster_staff_per_shift", "INTEGER DEFAULT 1"),
    ("appointment", "referral_id", "INTEGER"),
    ("appointment", "patient_id", "INTEGER"),
    ("appointment", "is_repeat", _bool_sql),
    ("patient_feedback", "referral_id", "INTEGER"),
    ("organization", "email", "VARCHAR(160)"),
    ("organization", "phone", "VARCHAR(32)"),
    ("organization", "phone_alt", "VARCHAR(32)"),
    ("organization", "address", "VARCHAR(300)"),
    ("complaint_status_history", "patient_message", "VARCHAR(480)"),
    # --- multi-tenant public portals
    ("organization", "slug", "VARCHAR(40)"),
    # --- NDPA: consent, anonymity, erasure
    ("complaint", "is_anonymous", _bool_sql),
    ("complaint", "consent_at", "TIMESTAMP"),
    ("complaint", "anonymized_at", "TIMESTAMP"),
    ("appointment", "consent_at", "TIMESTAMP"),
    ("appointment", "anonymized_at", "TIMESTAMP"),
    ("patient_feedback", "consent_at", "TIMESTAMP"),
    ("patient_feedback", "anonymized_at", "TIMESTAMP"),
    ("queue_ticket", "anonymized_at", "TIMESTAMP"),
    # --- Day 1 upgrades: HOD contact on the department, staff department + approval
    ("department", "hod_name", "VARCHAR(120)"),
    ("department", "hod_phone", "VARCHAR(32)"),
    ("user", "department_id", "INTEGER"),
    ("user", "approved", _bool_true_sql),
    ("user", "email_verified", _bool_true_sql),
    ("user", "email_verified_at", "TIMESTAMP"),
    ("user", "profile_completed", _bool_true_sql),
    ("user", "profile_completed_at", "TIMESTAMP"),
    ("user", "section_id", "INTEGER"),
    ("user", "unit_id", "INTEGER"),
    ("user", "cadre", "VARCHAR(80)"),
    ("user", "requested_role", "VARCHAR(20)"),
    ("user", "special_duty", "VARCHAR(200)"),
    ("inspection", "final_comment", "TEXT"),
    # --- HIMS patient folder: patient-CARE fields (this app is not an EMR).
    # Belt and braces behind migration b3f81a9d5c22: if Alembic is ever skipped
    # or fails, /hims/ must still not 500 on a missing column.
    ("patient", "photo_path", "VARCHAR(300)"),
    ("work_claim", "suspended", "BOOLEAN DEFAULT FALSE"),
    ("work_claim", "suspended_at", "TIMESTAMP"),
    ("work_claim", "suspended_by", "INTEGER"),
    ("patient", "preferred_lang", "VARCHAR(4)"),
    ("patient", "assistance", "VARCHAR(200)"),
    ("patient", "care_note", "VARCHAR(200)"),
    # --- Unified queue: link QR ticket to real patient journey (2026-08-21)
    ("queue_ticket", "patient_id", "INTEGER"),
    ("queue_ticket", "patient_visit_id", "INTEGER"),
    ("queue_ticket", "intake_id", "INTEGER"),
    # --- TV screens (2026-08-22)
    ("tv_screen", "location", "VARCHAR(120)"),
    ("tv_screen", "screen_type", "VARCHAR(20)"),
    ("tv_screen", "clinic_code", "VARCHAR(20)"),
    ("tv_screen", "show_full_name", "INTEGER DEFAULT 1"),
    ("tv_screen", "show_queue_stats", "INTEGER DEFAULT 1"),
    ("tv_screen", "voice_rotate_daily", "INTEGER DEFAULT 1"),
    ("tv_screen", "voice_languages", "VARCHAR(30)"),
    ("tv_screen", "voice_volume", "INTEGER DEFAULT 100"),
    ("tv_screen", "brightness", "INTEGER DEFAULT 100"),
    ("tv_screen", "night_mode", _bool_sql),
    # --- Fast-track premium executive service (2026-08-22) k25 + fast-track booking
    ("patient_visit", "is_fast_track", _bool_sql),
    ("patient_visit", "fast_track_reason", "VARCHAR(40)"),
    ("reception_intake", "is_fast_track", _bool_sql),
    ("reception_intake", "fast_track_reason", "VARCHAR(40)"),
    ("queue_ticket", "is_fast_track", _bool_sql),
    ("queue_ticket", "fast_track_reason", "VARCHAR(40)"),
    ("appointment", "is_fast_track", _bool_sql),
    ("appointment", "fast_track_reason", "VARCHAR(40)"),
    # --- Fast Track payment upfront + TV executive filter (Aug 23)
    ("appointment", "fast_track_paid", _bool_sql),
    ("appointment", "fast_track_payment_ref", "VARCHAR(80)"),
    ("appointment", "fast_track_amount", "INTEGER"),
    ("appointment", "fast_track_payment_status", "VARCHAR(20)"),
    ("appointment", "fast_track_paid_at", "TIMESTAMP"),
    ("tv_screen", "show_fast_track_only", _bool_sql),
    ("tv_screen", "is_executive", _bool_sql),
    ("sms_message", "to_user_id", "INTEGER"),
    # --- Build 6: MFA + Branch layer
    ("user", "mfa_secret", "VARCHAR(64)"),
    ("user", "mfa_enabled", _bool_sql),
    ("user", "mfa_backup", "TEXT"),
    ("user", "mfa_confirmed_at", "TIMESTAMP"),
    ("user", "branch_id", "INTEGER"),
    ("department", "branch_id", "INTEGER"),
    ("patient", "branch_id", "INTEGER"),
    ("patient_visit", "branch_id", "INTEGER"),
    ("reception_intake", "branch_id", "INTEGER"),
    # --- Attendance geo-fence (per site pin)
    ("branch", "lat", "FLOAT"),
    ("branch", "lng", "FLOAT"),
    ("branch", "fence_meters", "INTEGER"),
    ("staff_attendance", "flagged", _bool_sql),
    ("staff_attendance", "flag_note", "VARCHAR(240)"),
    ("staff_attendance", "mocked", _bool_sql),
    ("staff_attendance", "client_punched_at", "TIMESTAMP"),
    ("staff_attendance", "late_minutes", "INTEGER"),
    ("staff_attendance", "in_grace", _bool_sql),
    ("staff_attendance", "help_reason", "VARCHAR(20)"),
    ("staff_attendance", "evidence_path", "VARCHAR(300)"),
    ("staff_attendance", "reviewed_at", "TIMESTAMP"),
    ("staff_attendance", "reviewed_by_id", "INTEGER"),
    ("staff_attendance", "review_note", "VARCHAR(200)"),
    # --- Assistant conversation thread (web + WhatsApp)
    ("chat_session", "phone", "VARCHAR(32)"),
    ("chat_session", "last_intent", "VARCHAR(60)"),
    ("chat_session", "last_action", "VARCHAR(20)"),
    # --- NDPA G1: separate consent for disability/assistance data
    ("patient", "assistance_consent_at", "TIMESTAMP"),
    ("reception_intake", "assistance_consent_at", "TIMESTAMP"),
]

# unique partial indexes — make idempotency race-proof at the DB level (§41)
UNIQUE_INDEXES = [
    ("uq_complaint_idem", "complaint", "org_id, idempotency_key", "idempotency_key IS NOT NULL"),
    ("uq_appointment_idem", "appointment", "org_id, idempotency_key", "idempotency_key IS NOT NULL"),
]


def run_alembic_upgrade(app) -> bool:
    """Apply Alembic migrations at boot.

    The founder's host (Render free) has no shell and no one-off jobs, so
    migrations cannot be run by hand — they must self-apply on deploy.

    Databases created before Alembic existed are 'stamped' with the baseline
    revision instead of re-running it, so nothing is created twice. Any failure
    is logged and swallowed: ensure_schema() below is the belt-and-braces
    fallback, and a migration problem must never take the hospital offline.
    """
    if os.environ.get("DISABLE_MIGRATIONS") == "1":
        return False
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
    except ImportError:
        app.logger.info("alembic not installed — using ensure_schema() only")
        return False

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini = os.path.join(root, "alembic.ini")
    if not os.path.exists(ini):
        return False

    cfg = AlembicConfig(ini)
    cfg.set_main_option("script_location", os.path.join(root, "migrations"))
    cfg.set_main_option("sqlalchemy.url",
                        str(db.engine.url.render_as_string(hide_password=False)).replace("%", "%%"))
    try:
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        if tables and "alembic_version" not in tables:
            # Pre-Alembic database: record where we are rather than replaying history.
            command.stamp(cfg, "head")
            app.logger.info("alembic: stamped existing database at head")
            return True
        command.upgrade(cfg, "head")
        app.logger.info("alembic: database is at head")
        return True
    except Exception as exc:                     # noqa: BLE001
        # The hospital stays up (ensure_schema covers the known columns), but
        # this MUST be loud and actionable: a skipped upgrade that repeats on
        # every boot means a broken/non-idempotent migration or an unreachable
        # database (e.g. Supabase quota → SSL SYSCALL EOF). Silent repetition
        # here is how schema drift accumulates unnoticed.
        app.logger.error(
            "alembic upgrade FAILED (%s: %s) — falling back to ensure_schema(). "
            "Schema may now be drifting: fix the migration (existence guards, "
            "see migrations/versions/g8h21) or restore database access, then "
            "redeploy. This error repeating on every boot is NOT normal.",
            type(exc).__name__, exc)
        return False


def ensure_schema() -> None:
    added = []
    insp = inspect(db.engine)
    existing_tables = set(insp.get_table_names())
    for table, column, coltype in COLUMNS:
        if table not in existing_tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if column not in cols:
            resolved = coltype() if callable(coltype) else coltype
            with db.engine.begin() as conn:
                # Quote the table name: "user" is a RESERVED WORD in
                # PostgreSQL and an unquoted ALTER TABLE user ... is a syntax
                # error, which would silently skip the migration.
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {resolved}'))
            added.append(f"{table}.{column}")
    for name, table, cols, where in UNIQUE_INDEXES:
        if table not in existing_tables:
            continue
        with db.engine.begin() as conn:
            conn.execute(text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({cols}) WHERE {where}'))
    if added:
        log.info("ensure_schema added %d missing column(s): %s", len(added), ", ".join(added))

    # --- New tables that may not exist on old deployments (leave workflow).
    # db.metadata.create_all is the right tool and replaces the old
    # hand-written CREATE TABLE pair (a Postgres variant wrapped in
    # `except: pass` with a SQLite variant nested inside another bare except).
    # That version was exactly the migration drift it was meant to prevent:
    # if BOTH dialect variants failed, the error vanished and production
    # 500-ed later with no signal why. create_all is dialect-agnostic,
    # checkfirst-idempotent, and always derives the schema from the MODELS —
    # one source of truth instead of three diverging copies. Failures are
    # logged loudly; ensure_schema is a safety net and must never fail silent.
    from .models import LeaveBalance, LeaveRequest
    try:
        db.metadata.create_all(db.engine, tables=[LeaveRequest.__table__,
                                                  LeaveBalance.__table__])
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        log.exception("ensure_schema could not create leave tables — /roster "
                      "leave features WILL 500 until this is fixed. This is "
                      "NOT safe to ignore.")

