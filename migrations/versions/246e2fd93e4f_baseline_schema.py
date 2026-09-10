"""baseline schema

Captures the schema as of v1.2.0. Existing deployments were created with
db.create_all(), so this migration is written to be SAFE TO STAMP OR RUN on a
database that already has some or all of these tables: it inspects first and
creates only what is missing. New databases get everything.

Revision ID: 246e2fd93e4f
Revises:
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '246e2fd93e4f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_indexes(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    try:
        return {i["name"] for i in insp.get_indexes(table)}
    except Exception:
        return set()


def upgrade() -> None:
    """Create only the tables/indexes that are missing."""
    have = _existing()
    if 'login_attempt' not in have:
        op.create_table('login_attempt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        sa.Column('last_ip', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
    if 'login_attempt' not in have:
      with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_attempt_locked_until'), ['locked_until'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempt_username'), ['username'], unique=True)

    if 'organization' not in have:
        op.create_table('organization',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=12), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('slug', sa.String(length=40), nullable=True),
        sa.Column('logo_path', sa.String(length=300), nullable=True),
        sa.Column('email', sa.String(length=160), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('phone_alt', sa.String(length=32), nullable=True),
        sa.Column('address', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
        )
    if 'organization' not in have:
      with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_organization_slug'), ['slug'], unique=True)

    if 'chat_session' not in have:
        op.create_table('chat_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('lang', sa.String(length=4), nullable=True),
        sa.Column('channel', sa.String(length=12), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('handed_off', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'chat_session' not in have:
      with op.batch_alter_table('chat_session', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_session_org_id'), ['org_id'], unique=False)

    if 'complaint_category' not in have:
        op.create_table('complaint_category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'complaint_category' not in have:
      with op.batch_alter_table('complaint_category', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_complaint_category_org_id'), ['org_id'], unique=False)

    if 'qr_location' not in have:
        op.create_table('qr_location',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
        )
    if 'qr_location' not in have:
      with op.batch_alter_table('qr_location', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_qr_location_org_id'), ['org_id'], unique=False)

    if 'setting' not in have:
        op.create_table('setting',
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('org_id', 'key')
        )
    if 'sms_message' not in have:
        op.create_table('sms_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('to_number', sa.String(length=32), nullable=False),
        sa.Column('body', sa.String(length=480), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=16), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=True),
        sa.Column('provider_id', sa.String(length=80), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.String(length=400), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'sms_message' not in have:
      with op.batch_alter_table('sms_message', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sms_message_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sms_message_status'), ['status'], unique=False)

    if 'stored_file' not in have:
        op.create_table('stored_file',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=300), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('folder', sa.String(length=40), nullable=True),
        sa.Column('filename', sa.String(length=200), nullable=True),
        sa.Column('content_type', sa.String(length=80), nullable=True),
        sa.Column('size', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'stored_file' not in have:
      with op.batch_alter_table('stored_file', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stored_file_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_stored_file_folder'), ['folder'], unique=False)
        batch_op.create_index(batch_op.f('ix_stored_file_key'), ['key'], unique=True)
        batch_op.create_index(batch_op.f('ix_stored_file_org_id'), ['org_id'], unique=False)

    if 'user' not in have:
        op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=160), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'user' not in have:
      with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_role'), ['role'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_username'), ['username'], unique=True)

    if 'app_notification' not in have:
        op.create_table('app_notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(length=12), nullable=False),
        sa.Column('template_key', sa.String(length=60), nullable=False),
        sa.Column('subject', sa.String(length=200), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=True),
        sa.Column('error', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'app_notification' not in have:
      with op.batch_alter_table('app_notification', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_app_notification_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_app_notification_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_app_notification_user_id'), ['user_id'], unique=False)

    if 'audit_log' not in have:
        op.create_table('audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('entity_type', sa.String(length=30), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=250), nullable=True),
        sa.Column('at', sa.DateTime(), nullable=True),
        sa.Column('prev_hash', sa.String(length=64), nullable=True),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'audit_log' not in have:
      with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_log_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_at'), ['at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_user_id'), ['user_id'], unique=False)

    if 'corrective_action' not in have:
        op.create_table('corrective_action',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=16), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('finding', sa.Text(), nullable=False),
        sa.Column('action_required', sa.Text(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('evidence_path', sa.String(length=300), nullable=True),
        sa.Column('verified_by_id', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['verified_by_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'corrective_action' not in have:
      with op.batch_alter_table('corrective_action', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_corrective_action_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_corrective_action_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_corrective_action_status'), ['status'], unique=False)

    if 'data_request' not in have:
        op.create_table('data_request',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('ref', sa.String(length=40), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('handled_at', sa.DateTime(), nullable=True),
        sa.Column('handled_by_id', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['handled_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ref')
        )
    if 'data_request' not in have:
      with op.batch_alter_table('data_request', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_data_request_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_data_request_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_data_request_phone'), ['phone'], unique=False)
        batch_op.create_index(batch_op.f('ix_data_request_status'), ['status'], unique=False)

    if 'department' not in have:
        op.create_table('department',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('hod_user_id', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('roster_mode', sa.String(length=10), nullable=True),
        sa.Column('roster_staff_per_shift', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['hod_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'name', name='uq_dept_org_name')
        )
    if 'department' not in have:
      with op.batch_alter_table('department', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_department_org_id'), ['org_id'], unique=False)

    if 'duty_roster' not in have:
        op.create_table('duty_roster',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('duty_date', sa.Date(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'duty_date', name='uq_roster_org_date')
        )
    if 'duty_roster' not in have:
      with op.batch_alter_table('duty_roster', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_duty_roster_duty_date'), ['duty_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_duty_roster_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_duty_roster_user_id'), ['user_id'], unique=False)

    if 'knowledge_article' not in have:
        op.create_table('knowledge_article',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('intent', sa.String(length=60), nullable=False),
        sa.Column('keywords', sa.Text(), nullable=False),
        sa.Column('en', sa.Text(), nullable=False),
        sa.Column('pidgin', sa.Text(), nullable=True),
        sa.Column('yo', sa.Text(), nullable=True),
        sa.Column('ha', sa.Text(), nullable=True),
        sa.Column('ig', sa.Text(), nullable=True),
        sa.Column('cta', sa.String(length=200), nullable=True),
        sa.Column('clinical_safe', sa.Boolean(), nullable=True),
        sa.Column('scope', sa.String(length=8), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=True),
        sa.Column('submitted_by', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('hit_count', sa.Integer(), nullable=True),
        sa.Column('thumbs_up', sa.Integer(), nullable=True),
        sa.Column('thumbs_down', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['submitted_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'knowledge_article' not in have:
      with op.batch_alter_table('knowledge_article', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_knowledge_article_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_article_intent'), ['intent'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_article_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_knowledge_article_status'), ['status'], unique=False)

    if 'password_reset' not in have:
        op.create_table('password_reset',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('otp_hash', sa.String(length=256), nullable=False),
        sa.Column('channel', sa.String(length=12), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'password_reset' not in have:
      with op.batch_alter_table('password_reset', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_password_reset_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_password_reset_user_id'), ['user_id'], unique=False)

    if 'report_file' not in have:
        op.create_table('report_file',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('path', sa.String(length=300), nullable=False),
        sa.Column('verify_code', sa.String(length=24), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'report_file' not in have:
      with op.batch_alter_table('report_file', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_report_file_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_report_file_verify_code'), ['verify_code'], unique=True)

    if 'user_pref' not in have:
        op.create_table('user_pref',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'key')
        )
    if 'whats_app_message' not in have:
        op.create_table('whats_app_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('to_number', sa.String(length=32), nullable=False),
        sa.Column('to_user_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('media_path', sa.String(length=300), nullable=True),
        sa.Column('entity_type', sa.String(length=20), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=True),
        sa.Column('provider_id', sa.String(length=80), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.String(length=400), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['to_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'whats_app_message' not in have:
      with op.batch_alter_table('whats_app_message', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_whats_app_message_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_whats_app_message_status'), ['status'], unique=False)

    if 'appointment' not in have:
        op.create_table('appointment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('ref', sa.String(length=40), nullable=False),
        sa.Column('idempotency_key', sa.String(length=40), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('appointment_date', sa.Date(), nullable=False),
        sa.Column('appointment_time', sa.String(length=5), nullable=False),
        sa.Column('patient_name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('source', sa.String(length=12), nullable=True),
        sa.Column('qr_location_id', sa.Integer(), nullable=True),
        sa.Column('referral_id', sa.Integer(), nullable=True),
        sa.Column('is_repeat', sa.Boolean(), nullable=False),
        sa.Column('consent_at', sa.DateTime(), nullable=True),
        sa.Column('anonymized_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('arrived_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['qr_location_id'], ['qr_location.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ref')
        )
    if 'appointment' not in have:
      with op.batch_alter_table('appointment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_appointment_appointment_date'), ['appointment_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_appointment_time'), ['appointment_time'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_idempotency_key'), ['idempotency_key'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_referral_id'), ['referral_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_status'), ['status'], unique=False)

    if 'chat_message' not in have:
        op.create_table('chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(length=8), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=60), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('unanswered', sa.Boolean(), nullable=True),
        sa.Column('at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['knowledge_article.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['chat_session.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'chat_message' not in have:
      with op.batch_alter_table('chat_message', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_message_session_id'), ['session_id'], unique=False)

    if 'complaint' not in have:
        op.create_table('complaint',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('ref', sa.String(length=40), nullable=False),
        sa.Column('idempotency_key', sa.String(length=40), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('contact_method', sa.String(length=20), nullable=True),
        sa.Column('attachment_path', sa.String(length=300), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False),
        sa.Column('consent_at', sa.DateTime(), nullable=True),
        sa.Column('anonymized_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(length=12), nullable=True),
        sa.Column('qr_location_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('sla_hours', sa.Integer(), nullable=False),
        sa.Column('sla_deadline_at', sa.DateTime(), nullable=False),
        sa.Column('sla_extended_at', sa.DateTime(), nullable=True),
        sa.Column('action_taken', sa.Text(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('escalated', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['qr_location_id'], ['qr_location.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ref')
        )
    if 'complaint' not in have:
      with op.batch_alter_table('complaint', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_complaint_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_complaint_idempotency_key'), ['idempotency_key'], unique=False)
        batch_op.create_index(batch_op.f('ix_complaint_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_complaint_sla_deadline_at'), ['sla_deadline_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_complaint_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_complaint_submitted_at'), ['submitted_at'], unique=False)

    if 'dept_roster_entry' not in have:
        op.create_table('dept_roster_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('duty_date', sa.Date(), nullable=False),
        sa.Column('shift', sa.String(length=6), nullable=False),
        sa.Column('staff1_user_id', sa.Integer(), nullable=False),
        sa.Column('staff2_user_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['staff1_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['staff2_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('department_id', 'duty_date', 'shift', name='uq_dept_roster_day_shift')
        )
    if 'dept_roster_entry' not in have:
      with op.batch_alter_table('dept_roster_entry', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dept_roster_entry_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dept_roster_entry_duty_date'), ['duty_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_dept_roster_entry_org_id'), ['org_id'], unique=False)

    if 'section' not in have:
        op.create_table('section',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('hod_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['hod_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'section' not in have:
      with op.batch_alter_table('section', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_section_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_section_org_id'), ['org_id'], unique=False)

    if 'chat_feedback' not in have:
        op.create_table('chat_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.String(length=4), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['knowledge_article.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['chat_message.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'chat_feedback' not in have:
      with op.batch_alter_table('chat_feedback', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chat_feedback_message_id'), ['message_id'], unique=False)

    if 'complaint_status_history' not in have:
        op.create_table('complaint_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=16), nullable=True),
        sa.Column('to_status', sa.String(length=16), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('patient_message', sa.String(length=480), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaint.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'complaint_status_history' not in have:
      with op.batch_alter_table('complaint_status_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_complaint_status_history_complaint_id'), ['complaint_id'], unique=False)

    if 'patient_feedback' not in have:
        op.create_table('patient_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('source', sa.String(length=12), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=True),
        sa.Column('complaint_id', sa.Integer(), nullable=True),
        sa.Column('referral_id', sa.Integer(), nullable=True),
        sa.Column('consent_at', sa.DateTime(), nullable=True),
        sa.Column('anonymized_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaint.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'patient_feedback' not in have:
      with op.batch_alter_table('patient_feedback', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_patient_feedback_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_patient_feedback_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_patient_feedback_rating'), ['rating'], unique=False)
        batch_op.create_index(batch_op.f('ix_patient_feedback_referral_id'), ['referral_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_patient_feedback_status'), ['status'], unique=False)

    if 'queue_ticket' not in have:
        op.create_table('queue_ticket',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('access_key', sa.String(length=24), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('queue_date', sa.Date(), nullable=False),
        sa.Column('patient_name', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('source', sa.String(length=12), nullable=True),
        sa.Column('appointment_id', sa.Integer(), nullable=True),
        sa.Column('anonymized_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('called_at', sa.DateTime(), nullable=True),
        sa.Column('served_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'queue_ticket' not in have:
      with op.batch_alter_table('queue_ticket', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_queue_ticket_access_key'), ['access_key'], unique=True)
        batch_op.create_index(batch_op.f('ix_queue_ticket_code'), ['code'], unique=False)
        batch_op.create_index(batch_op.f('ix_queue_ticket_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_queue_ticket_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_queue_ticket_queue_date'), ['queue_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_queue_ticket_status'), ['status'], unique=False)

    if 'unit' not in have:
        op.create_table('unit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('hod_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['hod_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'unit' not in have:
      with op.batch_alter_table('unit', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_unit_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_unit_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_unit_section_id'), ['section_id'], unique=False)

    if 'inspection' not in have:
        op.create_table('inspection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('ref', sa.String(length=40), nullable=False),
        sa.Column('verify_code', sa.String(length=24), nullable=False),
        sa.Column('inspector_id', sa.Integer(), nullable=False),
        sa.Column('duty_date', sa.Date(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=True),
        sa.Column('unit_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('total_score', sa.Integer(), nullable=True),
        sa.Column('percent', sa.Float(), nullable=True),
        sa.Column('rating', sa.String(length=30), nullable=True),
        sa.Column('critical_count', sa.Integer(), nullable=True),
        sa.Column('poor_count', sa.Integer(), nullable=True),
        sa.Column('gps_mode', sa.String(length=12), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('gps_captured', sa.Boolean(), nullable=True),
        sa.Column('device_info', sa.String(length=300), nullable=True),
        sa.Column('amendment_of_id', sa.Integer(), nullable=True),
        sa.Column('pdf_path', sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(['amendment_of_id'], ['inspection.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['inspector_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['section_id'], ['section.id'], ),
        sa.ForeignKeyConstraint(['unit_id'], ['unit.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ref')
        )
    if 'inspection' not in have:
      with op.batch_alter_table('inspection', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inspection_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspection_duty_date'), ['duty_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspection_inspector_id'), ['inspector_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspection_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspection_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspection_verify_code'), ['verify_code'], unique=True)

    if 'referral' not in have:
        op.create_table('referral',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('source', sa.String(length=12), nullable=True),
        sa.Column('feedback_id', sa.Integer(), nullable=True),
        sa.Column('appointment_id', sa.Integer(), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('referrer_name', sa.String(length=120), nullable=True),
        sa.Column('referrer_phone', sa.String(length=32), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_clicked_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['department.id'], ),
        sa.ForeignKeyConstraint(['feedback_id'], ['patient_feedback.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'referral' not in have:
      with op.batch_alter_table('referral', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_referral_code'), ['code'], unique=True)
        batch_op.create_index(batch_op.f('ix_referral_org_id'), ['org_id'], unique=False)

    if 'inspection_score' not in have:
        op.create_table('inspection_score',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inspection_id', sa.Integer(), nullable=False),
        sa.Column('criterion_no', sa.Integer(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('evidence_path', sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspection.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inspection_id', 'criterion_no', name='uq_insp_crit')
        )
    if 'inspection_score' not in have:
      with op.batch_alter_table('inspection_score', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inspection_score_inspection_id'), ['inspection_id'], unique=False)

    if 'referral_event' not in have:
        op.create_table('referral_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('referral_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=True),
        sa.Column('feedback_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.id'], ),
        sa.ForeignKeyConstraint(['feedback_id'], ['patient_feedback.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['referral_id'], ['referral.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'referral_event' not in have:
      with op.batch_alter_table('referral_event', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_referral_event_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_referral_event_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_referral_event_org_id'), ['org_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_referral_event_referral_id'), ['referral_id'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    if 'referral_event' not in have:
      with op.batch_alter_table('referral_event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_referral_event_referral_id'))
        batch_op.drop_index(batch_op.f('ix_referral_event_org_id'))
        batch_op.drop_index(batch_op.f('ix_referral_event_kind'))
        batch_op.drop_index(batch_op.f('ix_referral_event_created_at'))

    op.drop_table('referral_event')
    if 'inspection_score' not in have:
      with op.batch_alter_table('inspection_score', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inspection_score_inspection_id'))

    op.drop_table('inspection_score')
    if 'referral' not in have:
      with op.batch_alter_table('referral', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_referral_org_id'))
        batch_op.drop_index(batch_op.f('ix_referral_code'))

    op.drop_table('referral')
    if 'inspection' not in have:
      with op.batch_alter_table('inspection', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inspection_verify_code'))
        batch_op.drop_index(batch_op.f('ix_inspection_status'))
        batch_op.drop_index(batch_op.f('ix_inspection_org_id'))
        batch_op.drop_index(batch_op.f('ix_inspection_inspector_id'))
        batch_op.drop_index(batch_op.f('ix_inspection_duty_date'))
        batch_op.drop_index(batch_op.f('ix_inspection_department_id'))

    op.drop_table('inspection')
    if 'unit' not in have:
      with op.batch_alter_table('unit', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_unit_section_id'))
        batch_op.drop_index(batch_op.f('ix_unit_org_id'))
        batch_op.drop_index(batch_op.f('ix_unit_department_id'))

    op.drop_table('unit')
    if 'queue_ticket' not in have:
      with op.batch_alter_table('queue_ticket', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_queue_ticket_status'))
        batch_op.drop_index(batch_op.f('ix_queue_ticket_queue_date'))
        batch_op.drop_index(batch_op.f('ix_queue_ticket_org_id'))
        batch_op.drop_index(batch_op.f('ix_queue_ticket_department_id'))
        batch_op.drop_index(batch_op.f('ix_queue_ticket_code'))
        batch_op.drop_index(batch_op.f('ix_queue_ticket_access_key'))

    op.drop_table('queue_ticket')
    if 'patient_feedback' not in have:
      with op.batch_alter_table('patient_feedback', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_patient_feedback_status'))
        batch_op.drop_index(batch_op.f('ix_patient_feedback_referral_id'))
        batch_op.drop_index(batch_op.f('ix_patient_feedback_rating'))
        batch_op.drop_index(batch_op.f('ix_patient_feedback_org_id'))
        batch_op.drop_index(batch_op.f('ix_patient_feedback_department_id'))

    op.drop_table('patient_feedback')
    if 'complaint_status_history' not in have:
      with op.batch_alter_table('complaint_status_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_complaint_status_history_complaint_id'))

    op.drop_table('complaint_status_history')
    if 'chat_feedback' not in have:
      with op.batch_alter_table('chat_feedback', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_feedback_message_id'))

    op.drop_table('chat_feedback')
    if 'section' not in have:
      with op.batch_alter_table('section', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_section_org_id'))
        batch_op.drop_index(batch_op.f('ix_section_department_id'))

    op.drop_table('section')
    if 'dept_roster_entry' not in have:
      with op.batch_alter_table('dept_roster_entry', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dept_roster_entry_org_id'))
        batch_op.drop_index(batch_op.f('ix_dept_roster_entry_duty_date'))
        batch_op.drop_index(batch_op.f('ix_dept_roster_entry_department_id'))

    op.drop_table('dept_roster_entry')
    if 'complaint' not in have:
      with op.batch_alter_table('complaint', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_complaint_submitted_at'))
        batch_op.drop_index(batch_op.f('ix_complaint_status'))
        batch_op.drop_index(batch_op.f('ix_complaint_sla_deadline_at'))
        batch_op.drop_index(batch_op.f('ix_complaint_org_id'))
        batch_op.drop_index(batch_op.f('ix_complaint_idempotency_key'))
        batch_op.drop_index(batch_op.f('ix_complaint_department_id'))

    op.drop_table('complaint')
    if 'chat_message' not in have:
      with op.batch_alter_table('chat_message', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_message_session_id'))

    op.drop_table('chat_message')
    if 'appointment' not in have:
      with op.batch_alter_table('appointment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_appointment_status'))
        batch_op.drop_index(batch_op.f('ix_appointment_referral_id'))
        batch_op.drop_index(batch_op.f('ix_appointment_org_id'))
        batch_op.drop_index(batch_op.f('ix_appointment_idempotency_key'))
        batch_op.drop_index(batch_op.f('ix_appointment_department_id'))
        batch_op.drop_index(batch_op.f('ix_appointment_appointment_time'))
        batch_op.drop_index(batch_op.f('ix_appointment_appointment_date'))

    op.drop_table('appointment')
    if 'whats_app_message' not in have:
      with op.batch_alter_table('whats_app_message', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_whats_app_message_status'))
        batch_op.drop_index(batch_op.f('ix_whats_app_message_org_id'))

    op.drop_table('whats_app_message')
    op.drop_table('user_pref')
    if 'report_file' not in have:
      with op.batch_alter_table('report_file', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_report_file_verify_code'))
        batch_op.drop_index(batch_op.f('ix_report_file_org_id'))

    op.drop_table('report_file')
    if 'password_reset' not in have:
      with op.batch_alter_table('password_reset', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_password_reset_user_id'))
        batch_op.drop_index(batch_op.f('ix_password_reset_expires_at'))

    op.drop_table('password_reset')
    if 'knowledge_article' not in have:
      with op.batch_alter_table('knowledge_article', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_knowledge_article_status'))
        batch_op.drop_index(batch_op.f('ix_knowledge_article_org_id'))
        batch_op.drop_index(batch_op.f('ix_knowledge_article_intent'))
        batch_op.drop_index(batch_op.f('ix_knowledge_article_category'))

    op.drop_table('knowledge_article')
    if 'duty_roster' not in have:
      with op.batch_alter_table('duty_roster', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_duty_roster_user_id'))
        batch_op.drop_index(batch_op.f('ix_duty_roster_org_id'))
        batch_op.drop_index(batch_op.f('ix_duty_roster_duty_date'))

    op.drop_table('duty_roster')
    if 'department' not in have:
      with op.batch_alter_table('department', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_department_org_id'))

    op.drop_table('department')
    if 'data_request' not in have:
      with op.batch_alter_table('data_request', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_data_request_status'))
        batch_op.drop_index(batch_op.f('ix_data_request_phone'))
        batch_op.drop_index(batch_op.f('ix_data_request_org_id'))
        batch_op.drop_index(batch_op.f('ix_data_request_created_at'))

    op.drop_table('data_request')
    if 'corrective_action' not in have:
      with op.batch_alter_table('corrective_action', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_corrective_action_status'))
        batch_op.drop_index(batch_op.f('ix_corrective_action_owner_id'))
        batch_op.drop_index(batch_op.f('ix_corrective_action_org_id'))

    op.drop_table('corrective_action')
    if 'audit_log' not in have:
      with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_log_user_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_org_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_at'))
        batch_op.drop_index(batch_op.f('ix_audit_log_action'))

    op.drop_table('audit_log')
    if 'app_notification' not in have:
      with op.batch_alter_table('app_notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_app_notification_user_id'))
        batch_op.drop_index(batch_op.f('ix_app_notification_org_id'))
        batch_op.drop_index(batch_op.f('ix_app_notification_created_at'))

    op.drop_table('app_notification')
    if 'user' not in have:
      with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_username'))
        batch_op.drop_index(batch_op.f('ix_user_role'))
        batch_op.drop_index(batch_op.f('ix_user_org_id'))

    op.drop_table('user')
    if 'stored_file' not in have:
      with op.batch_alter_table('stored_file', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stored_file_org_id'))
        batch_op.drop_index(batch_op.f('ix_stored_file_key'))
        batch_op.drop_index(batch_op.f('ix_stored_file_folder'))
        batch_op.drop_index(batch_op.f('ix_stored_file_created_at'))

    op.drop_table('stored_file')
    if 'sms_message' not in have:
      with op.batch_alter_table('sms_message', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sms_message_status'))
        batch_op.drop_index(batch_op.f('ix_sms_message_org_id'))

    op.drop_table('sms_message')
    op.drop_table('setting')
    if 'qr_location' not in have:
      with op.batch_alter_table('qr_location', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_qr_location_org_id'))

    op.drop_table('qr_location')
    if 'complaint_category' not in have:
      with op.batch_alter_table('complaint_category', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_complaint_category_org_id'))

    op.drop_table('complaint_category')
    if 'chat_session' not in have:
      with op.batch_alter_table('chat_session', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_session_org_id'))

    op.drop_table('chat_session')
    if 'organization' not in have:
      with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_organization_slug'))

    op.drop_table('organization')
    if 'login_attempt' not in have:
      with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_attempt_username'))
        batch_op.drop_index(batch_op.f('ix_login_attempt_locked_until'))

    op.drop_table('login_attempt')
    # ### end Alembic commands ###
