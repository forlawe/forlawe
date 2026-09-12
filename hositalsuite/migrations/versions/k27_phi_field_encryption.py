"""F-015 field-level encryption: widen PHI columns, add blind search indexes

Revision ID: k27_phi_crypto
Revises: k26_voices
Create Date: 2026-09-04

patient.date_of_birth / address / nok_address / nok_phone and
reception_intake.date_of_birth / address / nok_phone become ciphertext-
capable columns (wider types; DATE becomes VARCHAR via USING cast). New
nok_phone_bx columns hold the blind search index (HMAC) that replaces
LIKE matching while encryption is on. Values are rewritten by
`python -m app.encrypt_phi_backfill` AFTER FIELD_ENCRYPTION_KEY is set —
this migration only makes the storage safe for ciphertext.

SQLite (tests) ignores type alters; create_all builds the new schema.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k27_phi_crypto'
down_revision = 'k26_voices'
branch_labels = None
depends_on = None

# (table, column, old type, new type)
_WIDEN = [
    ('patient', 'date_of_birth', sa.Date(), sa.String(length=256)),
    ('patient', 'address', sa.String(length=300), sa.Text()),
    ('patient', 'nok_address', sa.String(length=300), sa.Text()),
    ('patient', 'nok_phone', sa.String(length=32), sa.String(length=256)),
    ('reception_intake', 'date_of_birth', sa.Date(), sa.String(length=256)),
    ('reception_intake', 'address', sa.String(length=300), sa.Text()),
    ('reception_intake', 'nok_phone', sa.String(length=32), sa.String(length=256)),
]


def upgrade():
    for table, col, _old, new in _WIDEN:
        try:
            using = sa.text(f"{col}::text") if op.get_bind().dialect.name == "postgresql" else None
            op.alter_column(table, col, type_=new,
                            postgresql_using=str(using) if using else None)
        except Exception:
            pass  # SQLite: metadata create_all already builds the new shape
    for table in ('patient', 'reception_intake'):
        try:
            op.add_column(table, sa.Column('nok_phone_bx', sa.String(length=32),
                                           nullable=True))
            op.create_index(f'ix_{table}_nok_phone_bx', table, ['nok_phone_bx'])
        except Exception:
            pass


def downgrade():
    for table in ('patient', 'reception_intake'):
        try:
            op.drop_index(f'ix_{table}_nok_phone_bx', table_name=table)
            op.drop_column(table, 'nok_phone_bx')
        except Exception:
            pass
    # NOTE: values written while encrypted are NOT convertible back to
    # DATE/short-VARCHAR — downgrade widens nothing back. See crypto_fields.
