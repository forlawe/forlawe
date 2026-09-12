"""v2 Notification System models — Push, Personal TV, Smart Queue, Presence — no breaking changes"""
from __future__ import annotations
from .models import db, now_naive

class PushSubscription(db.Model):
    """Web Push subscription — works even when app closed like alarm."""
    __tablename__ = "push_subscription"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    patient_access_key = db.Column(db.String(24), index=True)
    endpoint = db.Column(db.String(500), unique=True, nullable=False)
    p256dh = db.Column(db.String(200), nullable=False)
    auth = db.Column(db.String(100), nullable=False)
    device_info = db.Column(db.String(200))
    browser = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=now_naive, index=True)
    last_used_at = db.Column(db.DateTime, default=now_naive)
    org = db.relationship("Organization")
    user = db.relationship("User")
    __table_args__ = (
        db.Index("ix_push_org_user", "org_id", "user_id"),
        db.Index("ix_push_org_key", "org_id", "patient_access_key"),
    )

class NotificationPreference(db.Model):
    """Per-user notification prefs — cost saving defaults."""
    __tablename__ = "notification_preference"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    inapp_enabled = db.Column(db.Boolean, default=True, nullable=False)
    voice_enabled = db.Column(db.Boolean, default=True, nullable=False)
    push_enabled = db.Column(db.Boolean, default=False, nullable=False)
    sms_fallback = db.Column(db.Boolean, default=False, nullable=False)
    whatsapp_fallback = db.Column(db.Boolean, default=False, nullable=False)
    quiet_start = db.Column(db.String(5), default="")
    quiet_end = db.Column(db.String(5), default="")
    language = db.Column(db.String(5), default="en")
    created_at = db.Column(db.DateTime, default=now_naive)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)
    org = db.relationship("Organization")
    user = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("org_id", "user_id", name="uq_notif_pref_org_user"),
    )

class PersonalTvSession(db.Model):
    """Personal Patient TV — individual tracker like Domino's, no login."""
    __tablename__ = "personal_tv_session"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    access_key = db.Column(db.String(24), unique=True, nullable=False, index=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("queue_ticket.id"), index=True)
    intake_id = db.Column(db.Integer, db.ForeignKey("reception_intake.id"), index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey("patient_visit.id"), index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), index=True)
    current_stage = db.Column(db.String(20), default="RECEPTION")
    position = db.Column(db.Integer, default=0)
    estimated_wait = db.Column(db.Integer, default=0)
    is_fast_track = db.Column(db.Boolean, default=False, nullable=False)
    fast_track_reason = db.Column(db.String(40))
    preferred_lang = db.Column(db.String(5), default="en")
    push_sub_id = db.Column(db.Integer, db.ForeignKey("push_subscription.id"), index=True)
    last_seen_at = db.Column(db.DateTime, default=now_naive, index=True)
    is_inside_hospital = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive, index=True)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)
    ticket = db.relationship("QueueTicket")
    intake = db.relationship("ReceptionIntake")
    visit = db.relationship("PatientVisit")
    patient = db.relationship("Patient")
    push_sub = db.relationship("PushSubscription")
    org = db.relationship("Organization")
    __table_args__ = (
        db.Index("ix_personal_tv_org_seen", "org_id", "last_seen_at"),
    )

class PushQueue(db.Model):
    """Queue for Web Push — free, works closed like alarm."""
    __tablename__ = "push_queue"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("push_subscription.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(300))
    category = db.Column(db.String(20), default="general")
    priority = db.Column(db.String(10), default="NORMAL")
    require_interaction = db.Column(db.Boolean, default=False)
    vibrate = db.Column(db.String(50))
    actions = db.Column(db.Text)
    status = db.Column(db.String(12), default="QUEUED", index=True)
    attempts = db.Column(db.Integer, default=0)
    last_error = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=now_naive, index=True)
    sent_at = db.Column(db.DateTime)
    subscription = db.relationship("PushSubscription")
    org = db.relationship("Organization")

class QueueEstimate(db.Model):
    """Smart real-time queue time estimator — free AI-like logic."""
    __tablename__ = "queue_estimate"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    stage = db.Column(db.String(20), nullable=False, index=True)
    hour_of_day = db.Column(db.Integer, nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False, index=True)
    avg_seconds = db.Column(db.Integer, default=300)
    min_seconds = db.Column(db.Integer, default=60)
    max_seconds = db.Column(db.Integer, default=1800)
    sample_count = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=now_naive)
    org = db.relationship("Organization")
    __table_args__ = (
        db.UniqueConstraint("org_id", "stage", "hour_of_day", "day_of_week", name="uq_estimate_org_stage_hour_dow"),
        db.Index("ix_estimate_org_stage", "org_id", "stage"),
    )

class UserPresence(db.Model):
    """Last seen tracking for smart SMS routing."""
    __tablename__ = "user_presence"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    patient_access_key = db.Column(db.String(24), index=True)
    last_seen_at = db.Column(db.DateTime, default=now_naive, index=True)
    device_info = db.Column(db.String(200))
    is_inside_hospital = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_naive)
    org = db.relationship("Organization")
    user = db.relationship("User")
    __table_args__ = (
        db.Index("ix_presence_org_user_seen", "org_id", "user_id", "last_seen_at"),
        db.Index("ix_presence_org_key_seen", "org_id", "patient_access_key", "last_seen_at"),
    )
