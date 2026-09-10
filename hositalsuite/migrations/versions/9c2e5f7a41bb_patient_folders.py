"""HIMS patient folders and visits (Stage A of the patient flow)

Adds `patient` (the folder) and `patient_visit` (one attendance). Nothing
existing is altered: bookings and queue tickets keep their loose name/phone
columns, so no current feature changes behaviour. Later stages link to these.

Revision ID: 9c2e5f7a41bb
Revises: 7a1c4b9e2d10
Create Date: 2026-08-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9c2e5f7a41bb"
down_revision: Union[str, Sequence[str], None] = "7a1c4b9e2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())

    if "patient" not in have:
        op.create_table(
            "patient",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("hospital_number", sa.String(length=32), nullable=False),
            sa.Column("surname", sa.String(length=80), nullable=False),
            sa.Column("first_name", sa.String(length=80), nullable=False),
            sa.Column("other_names", sa.String(length=80), nullable=True),
            sa.Column("sex", sa.String(length=1), nullable=False),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("age_years", sa.Integer(), nullable=True),
            sa.Column("occupation", sa.String(length=80), nullable=True),
            sa.Column("phone", sa.String(length=32), nullable=True),
            sa.Column("phone_alt", sa.String(length=32), nullable=True),
            sa.Column("address", sa.String(length=300), nullable=True),
            sa.Column("lga", sa.String(length=80), nullable=True),
            sa.Column("state", sa.String(length=80), nullable=True),
            sa.Column("nok_name", sa.String(length=120), nullable=True),
            sa.Column("nok_relationship", sa.String(length=40), nullable=True),
            sa.Column("nok_phone", sa.String(length=32), nullable=True),
            sa.Column("nok_address", sa.String(length=300), nullable=True),
            sa.Column("payer_type", sa.String(length=16), nullable=False),
            sa.Column("payer_number", sa.String(length=60), nullable=True),
            sa.Column("payer_name", sa.String(length=120), nullable=True),
            sa.Column("category", sa.String(length=16), nullable=False),
            sa.Column("preferred_lang", sa.String(length=4), nullable=True),
            sa.Column("assistance", sa.String(length=200), nullable=True),
            sa.Column("care_note", sa.String(length=200), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("consent_at", sa.DateTime(), nullable=True),
            sa.Column("anonymized_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("last_visit_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id", "hospital_number", name="uq_patient_org_number"),
        )
        with op.batch_alter_table("patient", schema=None) as b:
            b.create_index("ix_patient_org_surname", ["org_id", "surname"], unique=False)
            for col in ("org_id", "hospital_number", "phone", "payer_type",
                        "category", "created_at", "last_visit_at"):
                b.create_index(b.f(f"ix_patient_{col}"), [col], unique=False)

    if "patient_visit" not in have:
        op.create_table(
            "patient_visit",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("visit_no", sa.String(length=40), nullable=False),
            sa.Column("visit_type", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("reason", sa.String(length=300), nullable=True),
            sa.Column("payer_type", sa.String(length=16), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("appointment_id", sa.Integer(), nullable=True),
            sa.Column("queue_ticket_id", sa.Integer(), nullable=True),
            sa.Column("clinic", sa.String(length=20), nullable=True),
            sa.Column("consulting_room", sa.String(length=20), nullable=True),
            sa.Column("doctor_id", sa.Integer(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("triaged_at", sa.DateTime(), nullable=True),
            sa.Column("seen_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("registered_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
            sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
            sa.ForeignKeyConstraint(["doctor_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
            sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
            sa.ForeignKeyConstraint(["queue_ticket_id"], ["queue_ticket.id"]),
            sa.ForeignKeyConstraint(["registered_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id", "visit_no", name="uq_visit_org_no"),
        )
        with op.batch_alter_table("patient_visit", schema=None) as b:
            for col in ("org_id", "patient_id", "visit_no", "status",
                        "department_id", "started_at"):
                b.create_index(b.f(f"ix_patient_visit_{col}"), [col], unique=False)


def downgrade() -> None:
    op.drop_table("patient_visit")
    op.drop_table("patient")
