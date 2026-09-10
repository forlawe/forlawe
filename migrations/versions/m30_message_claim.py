"""F-064: atomic-claim timestamps for the message queues.

Revision ID: m30_message_claim
Revises: l29_criteria_version
Create Date: 2026-09-09

Why
---
Outbound WhatsApp/SMS dispatch used a plain SELECT-then-send: with two web
processes (or two background delivery threads) both could pick up the same
QUEUED row and both send it — duplicate messages. Rows are now claimed with a
conditional UPDATE ... WHERE status='QUEUED' before sending, and the claim
stamps claimed_at so the stuck-SENDING reaper only reclaims rows whose claim
is genuinely old (never a message that is being sent right now).
"""
from alembic import op
import sqlalchemy as sa

revision = 'm30_message_claim'
down_revision = 'l29_criteria_version'
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    # Running twice (Render retries deploys) must be a no-op.
    # NOTE the real table names: Flask-SQLAlchemy derives "whats_app_message"
    # from WhatsAppMessage (no explicit __tablename__). "whatsapp_message" is
    # NOT a table in this app — an earlier draft used it and the existence
    # guard swallowed the miss, leaving a migrated database without claimed_at.
    for table in ("whats_app_message", "sms_message"):
        try:
            if not _column_exists(bind, table, "claimed_at"):
                op.add_column(table, sa.Column("claimed_at", sa.DateTime(),
                                               nullable=True))
        except Exception:                                   # noqa: BLE001
            pass    # table may not exist yet in some synthetic test DBs
    # Match the models (claimed_at … index=True): create_all would make these
    # indexes, so the migration path must too or prod schema drifts from dev.
    for table in ("whats_app_message", "sms_message"):
        insp = sa.inspect(bind)
        try:
            have = {i["name"] for i in insp.get_indexes(table)}
            if f"ix_{table}_claimed_at" not in have:
                op.create_index(f"ix_{table}_claimed_at", table, ["claimed_at"],
                                unique=False)
        except Exception:                                   # noqa: BLE001
            pass    # table may not exist yet in some synthetic test DBs


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("whats_app_message", "sms_message"):
            if _column_exists(bind, table, "claimed_at"):
                op.drop_column(table, "claimed_at")
    else:
        raise NotImplementedError("SQLite downgrade not supported for m30")
