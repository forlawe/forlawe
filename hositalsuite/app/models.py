"""Database models — multi-tenant (every record carries org_id)."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates as _sa_validates
from werkzeug.security import check_password_hash, generate_password_hash

from .crypto_fields import EncryptedDate, EncryptedString, EncryptedText, blind_index

db = SQLAlchemy()

# Roles, in seniority order. Labels are what staff actually see in the UI.
# STAFF is the role the hospital always had and the software never did: an
# ordinary member of staff. Before it existed, every account had to be given a
# management role just to sign in — which is exactly how HODs kept turning up
# in menus they had no business seeing.
ROLES = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR",
         "ADMIN_MANAGER", "HOD", "STAFF")

ROLE_LABELS = {
    "SUPER_ADMIN":   "Super Administrator",
    "MD_CEO":        "MD / CEO",
    "DMD":           "DMD — Deputy Medical Director",
    "DCST":          "DCST — Director of Clinical Services & Training",
    "APEX_NURSE":    "APEX Nurse — Head of Nursing Services",
    "HEAD_ADMIN_HR": "Head of Admin & HR",
    "ADMIN_MANAGER": "Admin Manager",
    "HOD":           "HOD — Head of Department",
    "STAFF":         "Staff",
}

# Roles with hospital-wide management sight (dashboards, reports, escalation targets).
MANAGEMENT_ROLES = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR")


def role_label(code: str) -> str:
    return ROLE_LABELS.get(code, code)

INSPECTION_STATUSES = ("DRAFT", "SUBMITTED", "AMENDED", "SUPERSEDED")
COMPLAINT_STATUSES = ("NEW", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "CLOSED", "ESCALATED")
CA_STATUSES = ("OPEN", "IN_PROGRESS", "COMPLETED", "OVERDUE", "VERIFIED")


# ---------------------------------------------------------------- helpers
def new_code(n: int = 10) -> str:
    return secrets.token_hex(n)[:n].upper()


def now_naive() -> datetime:
    """Current time as naive local (deployment timezone) datetime."""
    from flask import current_app
    try:
        tz = current_app.config["TIMEZONE"]
    except Exception:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Africa/Lagos")
    return datetime.now(tz).replace(tzinfo=None)


# ---------------------------------------------------------------- tenants
class StoredFile(db.Model):
    """Durable binary storage (see app/storage.py).

    Cheap hosts wipe the container disk on every restart, so uploads, generated
    PDFs and the hospital logo live here instead of on the filesystem.
    """
    __tablename__ = "stored_file"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(300), unique=True, nullable=False, index=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), index=True)
    folder = db.Column(db.String(40), index=True)
    filename = db.Column(db.String(200))
    content_type = db.Column(db.String(80))
    size = db.Column(db.Integer, default=0)
    sha256 = db.Column(db.String(64))
    data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive, index=True)


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), unique=True, nullable=False)       # e.g. HOSP
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(40), unique=True, index=True)   # public-portal tenant key
    logo_path = db.Column(db.String(300))
    email = db.Column(db.String(160))
    phone = db.Column(db.String(32))
    phone_alt = db.Column(db.String(32))
    address = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=now_naive)


# ---------------------------------------------------------------- users
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    # F-021: usernames are scoped PER HOSPITAL, not globally — two hospitals
    # may both have an "admin". Login resolves the hospital first (host / ?h=
    # / single-tenant), then matches the username inside it; a context-free
    # login with an ambiguous username is refused with guidance, never guessed.
    username = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160))
    phone = db.Column(db.String(32))            # E.164, used for WhatsApp/SMS
    role = db.Column(db.String(20), nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint("org_id", "username",
                                          name="uq_user_org_username"),)
    # Which department this member of staff belongs to (bulk uploads, rosters,
    # and "who works where" reporting all need this).
    # use_alter: user->department and department->user reference each other, so
    # the FK is added after both tables exist rather than creating a cycle.
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("department.id", use_alter=True, name="fk_user_department"),
        index=True)
    # Account approval: bulk-uploaded/self-registered accounts start unapproved
    # and cannot sign in until an administrator approves them.
    approved = db.Column(db.Boolean, default=True, nullable=False)
    # Email must be a real mailbox and activated before a new person may enter.
    # Existing staff are back-filled as verified so a deploy does not lock them out.
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    email_verified_at = db.Column(db.DateTime)
    # After the mailbox is proved, the person fills their own staff card.
    # Existing accounts are back-filled as complete so a deploy does not lock them out.
    profile_completed = db.Column(db.Boolean, default=True, nullable=False)
    profile_completed_at = db.Column(db.DateTime)
    section_id = db.Column(
        db.Integer,
        db.ForeignKey("section.id", use_alter=True, name="fk_user_section"),
        index=True)
    unit_id = db.Column(
        db.Integer,
        db.ForeignKey("unit.id", use_alter=True, name="fk_user_unit"),
        index=True)
    cadre = db.Column(db.String(80))
    requested_role = db.Column(db.String(20))
    special_duty = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=now_naive)
    last_login_at = db.Column(db.DateTime)
    # Which site this person works at (Hospital → Branch → Department).
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), index=True)
    # Two-step sign-in. Secret is only used when mfa_enabled is True.
    mfa_secret = db.Column(db.String(64))
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_backup = db.Column(db.Text)                 # hashed backup codes, JSON
    mfa_confirmed_at = db.Column(db.DateTime)

    org = db.relationship("Organization", backref="users")
    department = db.relationship("Department", foreign_keys=[department_id])
    section = db.relationship("Section", foreign_keys=[section_id])
    unit = db.relationship("Unit", foreign_keys=[unit_id])
    branch = db.relationship("Branch", foreign_keys=[branch_id])

    @property
    def is_super(self): return self.role == "SUPER_ADMIN"
    @property
    def is_md(self): return self.role == "MD_CEO"
    @property
    def is_am(self): return self.role == "ADMIN_MANAGER"
    @property
    def is_hod(self): return self.role == "HOD"

    @property
    def is_management(self):
        """Executive sight: MD/CEO, DMD, DCST, APEX Nurse, Head of Admin & HR.

        These roles see the hospital-wide dashboard and are valid escalation
        targets, without being able to administer the system itself.
        """
        return self.role in MANAGEMENT_ROLES

    @property
    def role_name(self):
        return role_label(self.role)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw, method="scrypt")

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def get_id(self):  # flask-login
        return str(self.id)


# ---------------------------------------------------------------- branches (Hospital → Branch → Department)
class Branch(db.Model):
    """One physical site of a hospital.

    A teaching hospital may have a main site and an annex. Staff, today's
    visits and (optionally) departments belong to a branch so Ijede Main
    does not see Ijede Annex's queue. Branding (name on the door, phone,
    address) can differ per site; colours stay hospital-wide so the suite
    still looks like one product.
    """
    __tablename__ = "branch"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(16), nullable=False)          # MAIN, ANNEX
    name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(300))
    phone = db.Column(db.String(64))
    email = db.Column(db.String(160))
    is_main = db.Column(db.Boolean, default=False, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    # Gate pin for staff clock-in. Empty = this site has no fence of its own
    # (the hospital-wide setting is used, or the fence is off).
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    fence_meters = db.Column(db.Integer)          # None = use hospital default
    created_at = db.Column(db.DateTime, default=now_naive)
    org = db.relationship("Organization", backref="branches")
    __table_args__ = (db.UniqueConstraint("org_id", "code", name="uq_branch_org_code"),)


# ---------------------------------------------------------------- structure
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), index=True)
    name = db.Column(db.String(120), nullable=False)
    hod_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    # HOD contact recorded ON the department, so a department can have a named
    # head who is not (yet) a system user — and so the phone survives even if
    # the linked staff account is changed or deactivated.
    hod_name = db.Column(db.String(120))
    hod_phone = db.Column(db.String(32))
    active = db.Column(db.Boolean, default=True, nullable=False)
    # roster design for this department: two 12h shifts/day, or one 24h shift/day
    roster_mode = db.Column(db.String(10), default="two_12h")      # two_12h | 24h
    roster_staff_per_shift = db.Column(db.Integer, default=1)      # 1 or 2 on duty per shift
    sections = db.relationship("Section", backref="department", lazy="select",
                               cascade="all, delete-orphan", order_by="Section.name")
    hod = db.relationship("User", foreign_keys=[hod_user_id])
    branch = db.relationship("Branch", foreign_keys=[branch_id])
    __table_args__ = (db.UniqueConstraint("org_id", "name", name="uq_dept_org_name"),)


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    hod_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    units = db.relationship("Unit", backref="section", lazy="select",
                            cascade="all, delete-orphan", order_by="Unit.name")
    hod = db.relationship("User", foreign_keys=[hod_user_id])


class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    hod_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    hod = db.relationship("User", foreign_keys=[hod_user_id])


# ---------------------------------------------------------------- roster
class DutyRoster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    duty_date = db.Column(db.Date, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    source = db.Column(db.String(16), default="manual")   # manual | import
    note = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now_naive)
    user = db.relationship("User", foreign_keys=[user_id], backref="duties")
    __table_args__ = (db.UniqueConstraint("org_id", "duty_date", name="uq_roster_org_date"),)


# ---------------------------------------------------------------- inspections
class Inspection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    ref = db.Column(db.String(40), unique=True, nullable=False)
    verify_code = db.Column(db.String(24), unique=True, nullable=False, index=True)
    inspector_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    duty_date = db.Column(db.Date, nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"))
    unit_id = db.Column(db.Integer, db.ForeignKey("unit.id"))
    status = db.Column(db.String(16), default="DRAFT", nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=now_naive)
    submitted_at = db.Column(db.DateTime)
    total_score = db.Column(db.Integer)
    percent = db.Column(db.Float)
    rating = db.Column(db.String(30))
    critical_count = db.Column(db.Integer, default=0)
    poor_count = db.Column(db.Integer, default=0)
    gps_mode = db.Column(db.String(12))             # mandatory | optional | disabled
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    gps_captured = db.Column(db.Boolean, default=False)
    device_info = db.Column(db.String(300))
    # Admin Manager's overall closing remark for the whole inspection (distinct
    # from the per-criterion explanations). Appears on the PDF sent to MD/CEO.
    final_comment = db.Column(db.Text)
    amendment_of_id = db.Column(db.Integer, db.ForeignKey("inspection.id"))
    pdf_path = db.Column(db.String(300))
    scores = db.relationship("InspectionScore", backref="inspection", cascade="all, delete-orphan",
                             order_by="InspectionScore.criterion_no")
    inspector = db.relationship("User", foreign_keys=[inspector_id])
    department = db.relationship("Department")
    section = db.relationship("Section")
    unit = db.relationship("Unit")


class InspectionScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("inspection.id"), nullable=False, index=True)
    criterion_no = db.Column(db.Integer, nullable=False)      # 1..5 exactly
    score = db.Column(db.Integer, nullable=False)             # 1..5
    explanation = db.Column(db.Text)                          # mandatory when score <= 2
    evidence_path = db.Column(db.String(300))
    __table_args__ = (db.UniqueConstraint("inspection_id", "criterion_no", name="uq_insp_crit"),)


# ---------------------------------------------------------------- complaints
class ComplaintCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)


class QrLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)          # Reception, Ward A ...
    code = db.Column(db.String(24), unique=True, nullable=False)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    ref = db.Column(db.String(40), unique=True, nullable=False)
    idempotency_key = db.Column(db.String(40), index=True)   # duplicate-submission guard (§41)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    contact_method = db.Column(db.String(20), default="phone")   # phone | whatsapp | either
    attachment_path = db.Column(db.String(300))
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    consent_at = db.Column(db.DateTime)          # NDPA: when the patient agreed
    anonymized_at = db.Column(db.DateTime)       # retention purge / erasure request
    source = db.Column(db.String(12), default="link")            # qr | link | ussd
    qr_location_id = db.Column(db.Integer, db.ForeignKey("qr_location.id"))
    status = db.Column(db.String(16), default="NEW", nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=now_naive, index=True)
    acknowledged_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    escalated_at = db.Column(db.DateTime)
    sla_hours = db.Column(db.Integer, nullable=False)
    sla_deadline_at = db.Column(db.DateTime, nullable=False, index=True)
    sla_extended_at = db.Column(db.DateTime)
    action_taken = db.Column(db.Text)
    resolution_notes = db.Column(db.Text)
    escalated = db.Column(db.Boolean, default=False, nullable=False)
    department = db.relationship("Department")
    qr_location = db.relationship("QrLocation")
    history = db.relationship("ComplaintStatusHistory", backref="complaint",
                              cascade="all, delete-orphan", order_by="ComplaintStatusHistory.at")

    @property
    def sla_breached(self) -> bool:
        return self.escalated or (self.status not in ("RESOLVED", "CLOSED") and self.sla_deadline_at < now_naive())


class ComplaintStatusHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    from_status = db.Column(db.String(16))
    to_status = db.Column(db.String(16), nullable=False)
    note = db.Column(db.Text)
    patient_message = db.Column(db.String(480))   # shown to the patient (status page)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    at = db.Column(db.DateTime, default=now_naive)
    user = db.relationship("User")


# ---------------------------------------------------------------- department rosters
DEPT_SHIFTS = {
    "two_12h": [("DAY", "07:00–19:00"), ("NIGHT", "19:00–07:00")],
    "24h": [("24H", "07:00–07:00 (+1)")],
    # Administrative departments (procurement, audit, finance & accounts, ICT,
    # admin/HR ...) do not run shifts — they work office hours, Monday to Friday.
    "office": [("OFFICE", "08:00–16:00, Mon–Fri")],
    # Three 8-hour tours: the other pattern Nigerian nursing divisions use.
    "three_8h": [("MORNING", "07:00–14:00"), ("AFTERNOON", "14:00–21:00"),
                 ("NIGHT", "21:00–07:00")],
}

ROSTER_MODE_LABELS = {
    "two_12h": "Two 12-hour shifts per day (day / night)",
    "24h": "One 24-hour duty per day",
    "office": "Office hours, Monday to Friday (no shifts)",
    "three_8h": "Three 8-hour shifts per day (morning / afternoon / night)",
}

# Every shift code the system understands, in one flat set — used for validation
# of uploaded files before we know which department a row belongs to.
ALL_SHIFT_CODES = tuple(sorted({s[0] for shifts in DEPT_SHIFTS.values() for s in shifts}))

# Leave is part of the roster, not a separate register: if a nurse is on annual
# leave on Tuesday, the Tuesday roster must SAY so, otherwise someone rosters her.
LEAVE_TYPES = (
    ("ANNUAL", "Annual leave"),
    ("CASUAL", "Casual leave"),
    ("SICK", "Sick leave"),
    ("STUDY", "Study leave"),
    ("MATERNITY", "Maternity leave"),
    ("COMPASSIONATE", "Compassionate leave"),
    ("EXAM", "Examination leave"),
    ("OFF", "Off duty"),
)
LEAVE_CODES = tuple(c for c, _ in LEAVE_TYPES)
LEAVE_LABELS = dict(LEAVE_TYPES)

# Who owns a roster line. ORG = the hospital-wide Admin Manager duty roster.
ROSTER_SCOPES = ("ORG", "DEPARTMENT", "SECTION", "UNIT")
SCOPE_LABELS = {"ORG": "Admin Manager (hospital-wide)", "DEPARTMENT": "Department",
                "SECTION": "Section", "UNIT": "Unit"}

# Placeholder shift code stored on leave rows so the uniqueness constraint works
# on both SQLite and PostgreSQL (NULLs never collide in a UNIQUE index).
LEAVE_SHIFT = "LEAVE"


class DeptRosterEntry(db.Model):
    """LEGACY department roster (two staff columns, department only).

    Superseded by :class:`RosterEntry`, which holds one row per person and can
    also carry sections, units and leave. Kept so that no historical data is
    lost; migrated into RosterEntry once at boot by
    ``app.rosterdata.migrate_legacy_entries``.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    duty_date = db.Column(db.Date, nullable=False, index=True)
    shift = db.Column(db.String(6), nullable=False)              # DAY | NIGHT | 24H
    staff1_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    staff2_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    source = db.Column(db.String(16), default="manual")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now_naive)
    department = db.relationship("Department")
    staff1 = db.relationship("User", foreign_keys=[staff1_user_id])
    staff2 = db.relationship("User", foreign_keys=[staff2_user_id])
    __table_args__ = (db.UniqueConstraint("department_id", "duty_date", "shift",
                                          name="uq_dept_roster_day_shift"),)


class RosterEntry(db.Model):
    """ONE unified roster line: one person, one day, one shift — or one leave day.

    WHY ONE TABLE
    -------------
    The suite used to have two rosters that could not see each other: the
    hospital-wide Admin Manager duty roster (`duty_roster`) and a department
    roster (`dept_roster_entry`) with two fixed staff columns. That design made
    three ordinary things impossible:

      * rostering a SECTION or a UNIT, not just a whole department;
      * putting more than two people on a shift;
      * recording that somebody is on leave, so the roster itself warns you
        before you place them on duty.

    One row per person fixes all three. A ward with nine nurses on nights is
    nine rows, not "staff1 and staff2 and nowhere to put the rest".

    LEAVE
    -----
    A leave row has ``kind='LEAVE'``, a ``leave_type`` and ``shift='LEAVE'``.
    Leave can span days, so a single upload row may expand into one entry per
    calendar day; that keeps every "who is on duty on 14 September" query a
    plain date lookup with no range arithmetic.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    duty_date = db.Column(db.Date, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # DUTY (on the roster, working) or LEAVE (on the roster, NOT working)
    kind = db.Column(db.String(8), nullable=False, default="DUTY", index=True)
    shift = db.Column(db.String(12), nullable=False, default="DAY")
    leave_type = db.Column(db.String(16))                       # ANNUAL | SICK | ...

    # Ownership: ORG for the hospital-wide Admin Manager roster, otherwise the
    # department (and optionally the section / unit inside it).
    scope = db.Column(db.String(12), nullable=False, default="DEPARTMENT", index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), index=True)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("unit.id"), index=True)

    note = db.Column(db.String(200))
    source = db.Column(db.String(16), default="manual")         # manual | import | legacy
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now_naive)

    user = db.relationship("User", foreign_keys=[user_id])
    department = db.relationship("Department")
    section = db.relationship("Section")
    unit = db.relationship("Unit")

    # The same person cannot be placed twice on the same day+shift in the same
    # place. Enforced in the database, not only in Python, so a double-submitted
    # form or two admins uploading the same file cannot create a duplicate.
    __table_args__ = (
        db.UniqueConstraint("org_id", "duty_date", "user_id", "shift", "scope",
                            "department_id", "section_id", "unit_id",
                            name="uq_roster_entry_slot"),
        db.Index("ix_roster_entry_org_date", "org_id", "duty_date"),
    )

    @property
    def place_label(self) -> str:
        if self.scope == "ORG":
            return "Hospital-wide (Admin Manager)"
        bits = [self.department.name if self.department else "—"]
        if self.section:
            bits.append(self.section.name)
        if self.unit:
            bits.append(self.unit.name)
        return " › ".join(bits)

    @property
    def is_leave(self) -> bool:
        return self.kind == "LEAVE"

    @property
    def display_shift(self) -> str:
        if self.is_leave:
            return LEAVE_LABELS.get(self.leave_type or "", "Leave")
        return self.shift



# ---------------------------------------------------------------- leave requests
LEAVE_REQUEST_STATUSES = ("PENDING", "APPROVED", "REJECTED", "CANCELLED")
LEAVE_BALANCE_DEFAULTS = {
    "ANNUAL": 30,
    "CASUAL": 7,
    "SICK": 14,
    "STUDY": 10,
    "MATERNITY": 84,
    "COMPASSIONATE": 7,
    "EXAM": 10,
    "OFF": 0,
}

class LeaveRequest(db.Model):
    """Leave request → approval → roster entry chain.

    Why: recording leave directly skips approval. Hospital needs request,
    HOD/HR approval, and balance tracking so annual leave doesn't exceed quota.
    Plain English: staff asks, boss approves, roster updates automatically.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    leave_type = db.Column(db.String(16), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    days_requested = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(300))
    status = db.Column(db.String(12), default="PENDING", nullable=False, index=True)
    requested_at = db.Column(db.DateTime, default=now_naive)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    review_note = db.Column(db.String(300))
    # When approved, roster entries created
    roster_created = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)

    user = db.relationship("User", foreign_keys=[user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    @property
    def label(self) -> str:
        return LEAVE_LABELS.get(self.leave_type, self.leave_type)

    @property
    def is_pending(self) -> bool:
        return self.status == "PENDING"


class LeaveBalance(db.Model):
    """Yearly leave balance per staff — how many days used / left."""
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    leave_type = db.Column(db.String(16), nullable=False, index=True)
    entitled = db.Column(db.Integer, default=0, nullable=False)
    used = db.Column(db.Integer, default=0, nullable=False)
    remaining = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)

    __table_args__ = (
        db.UniqueConstraint("org_id", "user_id", "year", "leave_type", name="uq_leave_balance"),
    )

    user = db.relationship("User", foreign_keys=[user_id])


# ---------------------------------------------------------------- bookings

APPOINTMENT_STATUSES = ("BOOKED", "ARRIVED", "CANCELLED", "NO_SHOW")


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    ref = db.Column(db.String(40), unique=True, nullable=False)
    idempotency_key = db.Column(db.String(40), index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    appointment_time = db.Column(db.String(5), nullable=False, index=True)   # "HH:MM" slot
    patient_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), index=True)
    status = db.Column(db.String(12), default="BOOKED", nullable=False, index=True)
    source = db.Column(db.String(12), default="link")       # qr | link | ussd | staff | referral
    qr_location_id = db.Column(db.Integer, db.ForeignKey("qr_location.id"))
    referral_id = db.Column(db.Integer, index=True)         # inbound: which share-link brought this booking
    is_repeat = db.Column(db.Boolean, default=False, nullable=False)  # same phone booked before
    # Fast Track — premium service, pay more, executive building, linked to Reception
    is_fast_track = db.Column(db.Boolean, default=False, nullable=False, index=True)
    fast_track_reason = db.Column(db.String(40))
    # Fast Track payment upfront — pay before arrival, premium
    fast_track_paid = db.Column(db.Boolean, default=False, nullable=False, index=True)
    fast_track_payment_ref = db.Column(db.String(80))
    fast_track_amount = db.Column(db.Integer)  # kobo/NGN amount paid, per-tenant price
    fast_track_payment_status = db.Column(db.String(20), default="PENDING", index=True)  # PENDING | PAID | FAILED | WAIVED
    fast_track_paid_at = db.Column(db.DateTime)
    consent_at = db.Column(db.DateTime)
    anonymized_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_naive)
    arrived_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    department = db.relationship("Department")
    qr_location = db.relationship("QrLocation")
    patient = db.relationship("Patient", foreign_keys=[patient_id])


# ---------------------------------------------------------------- patient feedback (§7)
class PatientFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), index=True)
    rating = db.Column(db.Integer, nullable=False, index=True)     # 1..5
    comment = db.Column(db.Text)
    phone = db.Column(db.String(32))
    source = db.Column(db.String(12), default="link")
    status = db.Column(db.String(12), default="NEW", index=True)   # NEW | ROUTED
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"))
    referral_id = db.Column(db.Integer, index=True)         # inbound: arrived via a share-link
    consent_at = db.Column(db.DateTime)
    anonymized_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_naive)
    department = db.relationship("Department")
    complaint = db.relationship("Complaint")


# ---------------------------------------------------------------- queue (§6)
QUEUE_STATUSES = ("WAITING", "CALLED", "DONE", "NO_SHOW", "CANCELLED")


class QueueTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False, index=True)   # public display e.g. "E-014"
    access_key = db.Column(db.String(24), unique=True, index=True)  # private status lookup
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False, index=True)
    queue_date = db.Column(db.Date, nullable=False, index=True)
    patient_name = db.Column(db.String(120))        # staff-only; never shown on public screens
    phone = db.Column(db.String(32))
    status = db.Column(db.String(12), default="WAITING", nullable=False, index=True)
    source = db.Column(db.String(12), default="link")   # qr | link | booking | ussd
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"))
    # --- Unified flow: link to real patient journey (added 2026-08-21)
    # A QR ticket may become a ReceptionIntake, then a Patient + PatientVisit.
    # Keeping these links lets the patient see one journey, not two disconnected tickets.
    # use_alter=True because PatientVisit already FKs to QueueTicket (queue_ticket_id)
    # creating a cycle that SQLite cannot sort for DROP without it.
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), index=True)
    patient_visit_id = db.Column(
        db.Integer, db.ForeignKey("patient_visit.id", use_alter=True, name="fk_qt_visit"), index=True
    )
    intake_id = db.Column(
        db.Integer, db.ForeignKey("reception_intake.id", use_alter=True, name="fk_qt_intake"), index=True
    )
    is_fast_track = db.Column(db.Boolean, default=False, nullable=False, index=True)
    fast_track_reason = db.Column(db.String(40))
    anonymized_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_naive)
    called_at = db.Column(db.DateTime)
    served_at = db.Column(db.DateTime)
    department = db.relationship("Department")
    appointment = db.relationship("Appointment")
    patient = db.relationship("Patient", foreign_keys=[patient_id])
    patient_visit = db.relationship("PatientVisit", foreign_keys=[patient_visit_id])
    intake = db.relationship("ReceptionIntake", foreign_keys=[intake_id])

    @property
    def linked_journey(self) -> str | None:
        """Where this ticket sits in the hospital journey, if linked."""
        if self.patient_visit_id:
            return f"visit:{self.patient_visit_id}"
        if self.intake_id:
            return f"intake:{self.intake_id}"
        if self.patient_id:
            return f"patient:{self.patient_id}"
        return None


# ---------------------------------------------------------------- referrals (§14)
REFERRAL_KINDS = ("patient", "hospital", "staff")
REFERRAL_SOURCES = ("feedback", "booking", "staff", "poster", "link")
REFERRAL_EVENT_KINDS = ("click", "book", "feedback", "queue")


class Referral(db.Model):
    """A shareable, trackable link/QR. No prizes, no pressure — just attribution."""
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(12), default="patient", nullable=False)   # patient | hospital | staff
    source = db.Column(db.String(12), default="link")                    # feedback | booking | staff | poster | link
    feedback_id = db.Column(db.Integer, db.ForeignKey("patient_feedback.id"))
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    referrer_name = db.Column(db.String(120))
    referrer_phone = db.Column(db.String(32))
    note = db.Column(db.String(200))                       # staff label, e.g. "Ward A poster"
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive)
    last_clicked_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    department = db.relationship("Department")
    origin_feedback = db.relationship("PatientFeedback", foreign_keys=[feedback_id])


class ReferralEvent(db.Model):
    """One row per click / booking / feedback / queue join attributed to a code."""
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    referral_id = db.Column(db.Integer, db.ForeignKey("referral.id"), nullable=False, index=True)
    kind = db.Column(db.String(12), nullable=False, index=True)   # click | book | feedback | queue
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"))
    feedback_id = db.Column(db.Integer, db.ForeignKey("patient_feedback.id"))
    created_at = db.Column(db.DateTime, default=now_naive, index=True)
    referral = db.relationship("Referral", backref="events")


# ---------------------------------------------------------------- SMS delivery
class SmsMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    to_number = db.Column(db.String(32), nullable=False)
    body = db.Column(db.String(480), nullable=False)
    kind = db.Column(db.String(30), nullable=False)          # confirmation | reminder | alert | alert_fallback
    entity_type = db.Column(db.String(20))
    entity_id = db.Column(db.Integer)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    provider = db.Column(db.String(16))                      # sandbox | termii | twilio
    status = db.Column(db.String(12), default="QUEUED", index=True)  # QUEUED|SENT|FAILED
    provider_id = db.Column(db.String(80))
    attempts = db.Column(db.Integer, default=0)
    last_error = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=now_naive)
    sent_at = db.Column(db.DateTime)


# ---------------------------------------------------------------- corrective actions
class CorrectiveAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    source_type = db.Column(db.String(16), nullable=False)     # inspection | complaint
    source_id = db.Column(db.Integer, nullable=False)
    finding = db.Column(db.Text, nullable=False)
    action_required = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    deadline = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), default="OPEN", nullable=False, index=True)
    completed_at = db.Column(db.DateTime)
    evidence_path = db.Column(db.String(300))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_naive)
    owner = db.relationship("User", foreign_keys=[owner_id])
    verified_by = db.relationship("User", foreign_keys=[verified_by_id])


# ---------------------------------------------------------------- notifications v2 — premium, smart, cost-saving
class AppNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    channel = db.Column(db.String(12), nullable=False)          # inapp | email | whatsapp | sms | push | station | personal_tv
    template_key = db.Column(db.String(60), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.String(20))
    entity_id = db.Column(db.Integer)
    status = db.Column(db.String(12), default="SENT")           # SENT | FAILED | READ | QUEUED
    error = db.Column(db.String(300))
    # v2 fields — premium, smart routing, alarm-like
    priority = db.Column(db.String(10), default="NORMAL")  # LOW, NORMAL, HIGH, CRITICAL, EMERGENCY
    category = db.Column(db.String(20), default="general")  # queue, booking, complaint, flow, roster, tracking
    actions = db.Column(db.Text)  # JSON [{"action":"view","title":"View"}]
    personal_tv_url = db.Column(db.String(300))
    voice_key = db.Column(db.String(80))
    require_interaction = db.Column(db.Boolean, default=False)  # alarm-like stays until acted
    vibrate = db.Column(db.String(50))  # JSON array
    ttl = db.Column(db.Integer, default=86400)  # seconds
    created_at = db.Column(db.DateTime, default=now_naive, index=True)


class WhatsAppMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    to_number = db.Column(db.String(32), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    kind = db.Column(db.String(30), nullable=False)             # report | reminder | alert
    body = db.Column(db.Text, nullable=False)
    media_path = db.Column(db.String(300))
    entity_type = db.Column(db.String(20))
    entity_id = db.Column(db.Integer)
    status = db.Column(db.String(12), default="QUEUED", index=True)  # QUEUED|SENDING|SENT|DELIVERED|FAILED
    provider_id = db.Column(db.String(80))
    attempts = db.Column(db.Integer, default=0)
    last_error = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=now_naive)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)


# ---------------------------------------------------------------- reports & files
class ReportFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)             # inspection | daily | weekly | monthly | dept | complaints | escalation | ca | compliance
    title = db.Column(db.String(200), nullable=False)
    entity_type = db.Column(db.String(20))
    entity_id = db.Column(db.Integer)
    path = db.Column(db.String(300), nullable=False)
    verify_code = db.Column(db.String(24), unique=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now_naive)


# ---------------------------------------------------------------- audit
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(30))
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.Text)                                 # JSON {old,new,...}
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(250))
    at = db.Column(db.DateTime, default=now_naive, index=True)
    prev_hash = db.Column(db.String(64))
    hash = db.Column(db.String(64), nullable=False)

    user = db.relationship("User")

    @staticmethod
    def chain_hash(prev: str, org_id, user_id, action, entity_type, entity_id, detail, at) -> str:
        payload = json.dumps([prev, org_id, user_id, action, entity_type, entity_id, detail, str(at)],
                             default=str, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- chatbot knowledge base (§SaaS)
KB_STATUSES = ("approved", "pending", "rejected")


class KnowledgeArticle(db.Model):
    """Multi-tenant dialogue library.

    org_id NULL  -> global master library (shared by every tenant)
    org_id set   -> tenant-specific dialogue; status 'pending' until approved.
    Learning loop: unanswered chats + thumbs feed reports; admins may promote a
    good tenant answer to the global master (with approval).
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), index=True)  # NULL = global
    category = db.Column(db.String(40), nullable=False, index=True)
    intent = db.Column(db.String(60), nullable=False, index=True)
    keywords = db.Column(db.Text, nullable=False)          # newline/comma-separated triggers
    en = db.Column(db.Text, nullable=False)                # premium English
    pidgin = db.Column(db.Text)                            # Nigerian Pidgin
    yo = db.Column(db.Text)
    ha = db.Column(db.Text)
    ig = db.Column(db.Text)
    cta = db.Column(db.String(200))                        # soft call-to-action
    clinical_safe = db.Column(db.Boolean, default=True)    # False = refuse/redirect template
    scope = db.Column(db.String(8), default="global")      # global | tenant
    status = db.Column(db.String(10), default="approved", index=True)
    submitted_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    hit_count = db.Column(db.Integer, default=0)
    thumbs_up = db.Column(db.Integer, default=0)
    thumbs_down = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now_naive)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)


class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), index=True)
    lang = db.Column(db.String(4), default="en")
    channel = db.Column(db.String(12), default="web")       # web | whatsapp
    phone = db.Column(db.String(32))                        # WhatsApp thread
    last_intent = db.Column(db.String(60))
    last_action = db.Column(db.String(20))
    started_at = db.Column(db.DateTime, default=now_naive)
    ended_at = db.Column(db.DateTime)
    handed_off = db.Column(db.Boolean, default=False)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), index=True)
    role = db.Column(db.String(8), nullable=False)          # user | bot
    text = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(60))
    confidence = db.Column(db.Float)
    article_id = db.Column(db.Integer, db.ForeignKey("knowledge_article.id"))
    unanswered = db.Column(db.Boolean, default=False)
    at = db.Column(db.DateTime, default=now_naive)


class ChatFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("chat_message.id"), index=True)
    article_id = db.Column(db.Integer, db.ForeignKey("knowledge_article.id"))
    rating = db.Column(db.String(4), nullable=False)        # up | down
    at = db.Column(db.DateTime, default=now_naive)


# ---------------------------------------------------------------- self-service password reset
class PasswordReset(db.Model):
    """Single-use, short-lived OTP for self-service 'forgot password' (§burden off admin)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    otp_hash = db.Column(db.String(256), nullable=False)
    channel = db.Column(db.String(12), default="sms")            # sms | email
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now_naive)
    user = db.relationship("User")


# ---------------------------------------------------------------- brute-force defence
class LoginAttempt(db.Model):
    """Per-username failed-login counter driving temporary account lockout.

    The IP-based rate limiter cannot protect an account when every request
    arrives from the same proxy IP, and it also cannot stop a slow distributed
    guess. This adds a second, account-scoped gate.
    """
    __tablename__ = "login_attempt"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=True,
                       index=True)   # None = login without a hospital context
    username = db.Column(db.String(80), nullable=False, index=True)
    failures = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, index=True)
    last_failure_at = db.Column(db.DateTime)
    last_ip = db.Column(db.String(64))

    __table_args__ = (db.UniqueConstraint("org_id", "username",
                                          name="uq_lock_org_username"),)


# ---------------------------------------------------------------- NDPA data-subject requests
class DataRequest(db.Model):
    """Patient request to access or erase their data (NDPA 2023 rights)."""
    __tablename__ = "data_request"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    ref = db.Column(db.String(40), unique=True, nullable=False)
    kind = db.Column(db.String(12), nullable=False)          # access | erase
    phone = db.Column(db.String(32), nullable=False, index=True)
    note = db.Column(db.Text)
    status = db.Column(db.String(16), default="NEW", nullable=False, index=True)  # NEW|DONE|REJECTED
    created_at = db.Column(db.DateTime, default=now_naive, index=True)
    handled_at = db.Column(db.DateTime)
    handled_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    outcome = db.Column(db.Text)


# ---------------------------------------------------------------- user prefs (§19)
class UserPref(db.Model):
    """Per-user alert preferences: voice reminders, quiet hours, browser push."""
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    key = db.Column(db.String(40), primary_key=True)
    value = db.Column(db.Text)

    DEFAULTS = {
        "voice_enabled": True,
        "voice_min_level": "standard",   # standard | urgent | emergency
        # Quiet hours OFF by default. They used to default to 22:00-07:00,
        # which silenced every announcement for night-shift staff — precisely
        # the people who most need to hear that a patient is waiting. Staff can
        # switch quiet hours on themselves at /alert-settings.
        "quiet_start": "",
        "quiet_end": "",
        "push_enabled": False,
    }

    @staticmethod
    def get(user_id: int, key: str):
        row = db.session.get(UserPref, (user_id, key))
        if row is not None:
            return row.value
        d = UserPref.DEFAULTS.get(key)
        if isinstance(d, bool):
            return d
        return d

    @staticmethod
    def set(user_id: int, key: str, value):
        row = db.session.get(UserPref, (user_id, key))
        if row is None:
            row = UserPref(user_id=user_id, key=key)
            db.session.add(row)
        row.value = str(value)

    @staticmethod
    def bundle(user_id: int) -> dict:
        out = {}
        for k, d in UserPref.DEFAULTS.items():
            v = UserPref.get(user_id, k)
            if isinstance(d, bool):
                out[k] = str(v).lower() in ("true", "1", "on")
            else:
                out[k] = v
        return out


# ---------------------------------------------------------------- HIMS: patient folders
# How the patient pays. LAHSMA is the Lagos State health insurance scheme;
# Megalex is the private payment system Lagos State hospitals use to collect
# revenue. Both are recorded on the folder so Billing and the doctor know the
# route before the patient reaches them.
PAYER_TYPES = (
    ("SELF", "Self-paying (cash / transfer)"),
    ("LAHSMA", "LAHSMA — Lagos State health insurance"),
    ("MEGALEX", "Megalex — Lagos State revenue system"),
    ("NHIS", "NHIS — National Health Insurance"),
    ("HMO", "Private HMO / company retainer"),
    ("EXEMPT", "Exempt / waiver approved"),
)
PAYER_LABELS = dict(PAYER_TYPES)
PAYER_CODES = tuple(c for c, _ in PAYER_TYPES)

SEXES = (("F", "Female"), ("M", "Male"))
SEX_LABELS = dict(SEXES)

MARITAL_STATUSES = ("Single", "Married", "Widowed", "Divorced", "Separated")

# Offered as suggestions, never enforced: a patient may write anything, and a
# hospital must not refuse somebody because their faith is not on a list.
RELIGIONS = ("Christianity", "Islam", "Traditional", "None", "Other")

# All 36 states plus the FCT, so State of Origin is a tap rather than typing.
NIGERIAN_STATES = (
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "FCT - Abuja", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina",
    "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo",
    "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
)

# Patient categories drive Triage in Stage B: a child does not go to the same
# clinic as an antenatal mother, and an elderly patient may be seen sooner.
PATIENT_CATEGORIES = (
    ("GENERAL", "General adult"),
    ("CHILD", "Child (under 12)"),
    ("ANTENATAL", "Antenatal / maternity"),
    ("ELDERLY", "Elderly (65+)"),
    ("CHRONIC", "Chronic condition (follow-up)"),
    ("EMERGENCY", "Emergency"),
)
CATEGORY_LABELS = dict(PATIENT_CATEGORIES)
CATEGORY_CODES = tuple(c for c, _ in PATIENT_CATEGORIES)

# THIS APP IS NOT AN EMR. It exists to make a visit feel calm, quick and
# respectful — so the folder holds only what the FRONT DESK needs to look after
# somebody well. Blood group, genotype, allergies and diagnoses belong in the
# hospital's clinical record, not here.
#
# What we DO keep is what changes how a patient is treated at the door: the
# language they are comfortable in, and any help they need to get through the
# visit without struggling.
ASSISTANCE_NEEDS = (
    ("WHEELCHAIR",  "Needs a wheelchair"),
    ("ELDERLY",     "Elderly — offer a seat"),
    ("PREGNANT",    "Pregnant — offer a seat"),
    ("HEARING",     "Hard of hearing — speak up, face them"),
    ("SIGHT",       "Poor sight — guide them"),
    ("MOBILITY",    "Walks with difficulty"),
    ("CARER",       "Comes with a carer"),
    ("INTERPRETER", "Needs an interpreter"),
)
ASSISTANCE_LABELS = dict(ASSISTANCE_NEEDS)
ASSISTANCE_CODES = tuple(c for c, _ in ASSISTANCE_NEEDS)

# The four languages the rest of the app already speaks.
PATIENT_LANGS = (("en", "English"), ("yo", "Yorùbá"), ("ha", "Hausa"), ("ig", "Igbo"))
PATIENT_LANG_LABELS = dict(PATIENT_LANGS)


class Patient(db.Model):
    """A patient folder — the hospital record that everything else hangs on.

    WHY THIS EXISTS
    ---------------
    Until now the suite stored a loose ``patient_name`` and ``phone`` on each
    booking and each queue ticket. Two visits by the same woman were two
    unrelated strings. Nothing could answer "has this patient been here
    before?", nothing could carry her payment route to Billing, and the doctor
    had no record to open.

    A folder is opened ONCE, on a first visit, and found again on every return
    visit — which is exactly what the founder described:

        "HIMS Register: i. open folder for new/first visit patient,
         ii. Search for the folder of returning patient"

    IDENTIFIERS
    -----------
    ``hospital_number`` is the number written on the paper folder and called
    out at the desk. It is generated per hospital as ``IJD/2026/00001`` and is
    unique within the tenant, never across tenants.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), index=True)
    hospital_number = db.Column(db.String(32), nullable=False, index=True)

    # --- identity
    surname = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    other_names = db.Column(db.String(80))
    sex = db.Column(db.String(1), nullable=False)                 # F | M
    # F-015: date_of_birth, address and next-of-kin contact are field-level
    # encrypted (ciphertext at rest without FIELD_ENCRYPTION_KEY; plaintext
    # passthrough while the key is unset — see app/crypto_fields.py).
    date_of_birth = db.Column(EncryptedDate())
    # Many patients genuinely do not know their date of birth. Recording a
    # stated age is honest; inventing a birthday is not.
    age_years = db.Column(db.Integer)
    occupation = db.Column(db.String(80))

    # --- contact
    # Patient.phone stays a plain, indexed column on purpose: it is the
    # number the hospital dials and searches by partial match every day.
    # The audit's field-encryption scope (F-015) is next-of-kin contact and
    # addresses — the fields nobody needs to search by substring.
    phone = db.Column(db.String(32), index=True)
    phone_alt = db.Column(db.String(32))
    address = db.Column(EncryptedText())
    lga = db.Column(db.String(80))                                # local government area
    state = db.Column(db.String(80))

    # --- next of kin (required: somebody must be reachable in an emergency)
    nok_name = db.Column(db.String(120))
    nok_relationship = db.Column(db.String(40))
    nok_phone = db.Column(EncryptedString(32))
    nok_address = db.Column(EncryptedText())
    # Blind search index (HMAC) so staff can still find a patient by NOK
    # number without the DB storing a readable copy — see crypto_fields.
    nok_phone_bx = db.Column(db.String(32), index=True)

    @_sa_validates("nok_phone")
    def _hash_nok_phone(self, _key, value):
        self.nok_phone_bx = blind_index("patient.nok_phone", value)
        return value

    # --- from the hospital's paper admission form. Demographic, never clinical.
    marital_status = db.Column(db.String(16))
    religion = db.Column(db.String(40))
    state_of_origin = db.Column(db.String(60))
    town = db.Column(db.String(80))
    tribe = db.Column(db.String(60))
    ethnic_group = db.Column(db.String(60))

    # --- how they pay
    payer_type = db.Column(db.String(16), default="SELF", nullable=False, index=True)
    payer_number = db.Column(db.String(60))                       # LAHSMA/NHIS/HMO number
    payer_name = db.Column(db.String(120))                        # HMO or employer

    # --- looking after them well (NOT a clinical record)
    category = db.Column(db.String(16), default="GENERAL", nullable=False, index=True)
    preferred_lang = db.Column(db.String(4), default="en")
    assistance = db.Column(db.String(200))        # comma-separated ASSISTANCE_CODES
    care_note = db.Column(db.String(200))         # anything else the desk should know

    # --- housekeeping
    photo_path = db.Column(db.String(300))
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)
    # NDPA: the patient consented to the hospital holding these details.
    consent_at = db.Column(db.DateTime)
    # G1 FIX: separate explicit consent for disability/assistance-need data (more sensitive)
    assistance_consent_at = db.Column(db.DateTime)
    anonymized_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now_naive, index=True)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)
    last_visit_at = db.Column(db.DateTime, index=True)

    creator = db.relationship("User", foreign_keys=[created_by])
    branch = db.relationship("Branch", foreign_keys=[branch_id])
    visits = db.relationship("PatientVisit", backref="patient", lazy="select",
                             order_by="PatientVisit.started_at.desc()")

    __table_args__ = (
        db.UniqueConstraint("org_id", "hospital_number", name="uq_patient_org_number"),
        db.Index("ix_patient_org_surname", "org_id", "surname"),
    )

    @property
    def full_name(self) -> str:
        """Register order: SURNAME Firstname. Correct on a folder and a list."""
        bits = [(self.surname or "").upper(), self.first_name]
        if self.other_names:
            bits.append(self.other_names)
        return " ".join(b for b in bits if b)

    @property
    def spoken_name(self) -> str:
        """Speaking order: Firstname Surname.

        A folder reads "ABATAN Folake" because that is how a register is
        written. But a person is CALLED by their first name, and Reception
        already announced her as "Folake". Announcing "Abatan" later would be
        calling the same patient two different names across one visit, which
        is exactly the confusion this app exists to remove.
        """
        bits = [self.first_name, self.other_names, self.surname]
        return " ".join(b for b in bits if b).strip()

    @property
    def age(self) -> int | None:
        """Age today, computed from the birthday when we have one."""
        if self.date_of_birth:
            t = now_naive().date()
            return (t.year - self.date_of_birth.year
                    - ((t.month, t.day) < (self.date_of_birth.month, self.date_of_birth.day)))
        return self.age_years

    @property
    def age_display(self) -> str:
        a = self.age
        return f"{a} yrs" if a is not None else "age not known"

    @property
    def payer_label(self) -> str:
        return PAYER_LABELS.get(self.payer_type, self.payer_type)

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)

    @property
    def is_returning(self) -> bool:
        return bool(self.last_visit_at)

    @property
    def assistance_list(self) -> list[str]:
        return [a for a in (self.assistance or "").split(",") if a]

    @property
    def care_flags(self) -> list[str]:
        """How to look after this person well — shown at the top of the folder.

        Courtesy, not medicine: offer a seat, fetch a wheelchair, speak up,
        greet them in their own language.
        """
        out = [ASSISTANCE_LABELS[a] for a in self.assistance_list
               if a in ASSISTANCE_LABELS]
        if self.preferred_lang and self.preferred_lang != "en":
            out.append(f"Prefers {PATIENT_LANG_LABELS.get(self.preferred_lang, self.preferred_lang)}"
                       " — greet them in it")
        if self.care_note:
            out.append(self.care_note)
        return out

    @property
    def lang_label(self) -> str:
        return PATIENT_LANG_LABELS.get(self.preferred_lang or "en", "English")


VISIT_STATUSES = ("REGISTERED", "TRIAGED", "IN_CONSULTATION", "ONWARD", "CLOSED", "CANCELLED")
VISIT_TYPES = (("NEW", "First visit"), ("FOLLOW_UP", "Follow-up"),
               ("EMERGENCY", "Emergency"), ("ANTENATAL", "Antenatal"))


class PatientVisit(db.Model):
    """One attendance. Opened at the HIMS desk, then carried through the flow.

    Stage A only creates it and marks it REGISTERED. Triage (Stage B), the
    consulting room (Stage C) and onward routing (Stage D) each move it along,
    which is why the clinic/room/destination columns already exist but are left
    empty for now — so those stages add behaviour, not another migration.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False, index=True)
    visit_no = db.Column(db.String(40), nullable=False, index=True)
    visit_type = db.Column(db.String(16), default="FOLLOW_UP", nullable=False)
    status = db.Column(db.String(16), default="REGISTERED", nullable=False, index=True)

    reason = db.Column(db.String(300))            # what the patient says is wrong
    payer_type = db.Column(db.String(16))         # how THIS visit is being paid for
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"))
    queue_ticket_id = db.Column(
        db.Integer, db.ForeignKey("queue_ticket.id", use_alter=True, name="fk_visit_ticket"), index=True
    )

    # filled in by later stages — deliberately created now, used later
    clinic = db.Column(db.String(20))             # OPD | SOPD | MOPD | EMERGENCY
    consulting_room = db.Column(db.String(20))
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    # Fast-track: elderly / pregnant / child / wheelchair — premium patient care
    is_fast_track = db.Column(db.Boolean, default=False, nullable=False, index=True)
    fast_track_reason = db.Column(db.String(40))  # ELDERLY | PREGNANT | CHILD | WHEELCHAIR | ANTENATAL

    started_at = db.Column(db.DateTime, default=now_naive, nullable=False, index=True)
    triaged_at = db.Column(db.DateTime)
    seen_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    registered_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    department = db.relationship("Department")
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    registrar = db.relationship("User", foreign_keys=[registered_by])
    branch = db.relationship("Branch", foreign_keys=[branch_id])

    __table_args__ = (db.UniqueConstraint("org_id", "visit_no", name="uq_visit_org_no"),)


# ---------------------------------------------------------------- settings
class Setting(db.Model):
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), primary_key=True)
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text)

    @staticmethod
    def get(org_id: int, key: str, default=None):
        row = db.session.get(Setting, (org_id, key))
        if row is None or row.value is None:
            return default
        try:
            return json.loads(row.value)
        except Exception:
            return row.value

    @staticmethod
    def set(org_id: int, key: str, value):
        row = db.session.get(Setting, (org_id, key))
        if row is None:
            row = Setting(org_id=org_id, key=key)
            db.session.add(row)
        row.value = json.dumps(value)
        return row


# ---------------------------------------------------------------- reception
# Reception is the FIRST desk a new patient meets, before any folder exists.
# The receptionist takes the details, finds out what help the person needs,
# records their insurance, then sends them to Billing and the Paying Point.
# HIMS later turns a PAID intake into a real patient folder.
#
# WHY A SEPARATE TABLE AND NOT JUST A PATIENT ROW
# -----------------------------------------------
# A folder is the hospital's permanent record and it carries a hospital number.
# Somebody who walks in, is quoted a fee and leaves without paying must NOT
# consume a hospital number or sit in the register as a patient forever. The
# intake is the waiting room; the folder is the record.
INTAKE_STAGES = (
    ("RECEPTION", "At Reception — details being taken"),
    ("BILLING",   "Sent to Billing — collecting the bill"),
    ("PAYMENT",   "At Megalex / Paying Point — paying"),
    ("PAID",      "Paid — waiting for HIMS to open the folder"),
    ("REGISTERED", "Folder opened by HIMS — sent to Triage"),
    ("CANCELLED", "Left without completing"),
)
INTAKE_STAGE_LABELS = dict(INTAKE_STAGES)
INTAKE_STAGE_CODES = tuple(c for c, _ in INTAKE_STAGES)


class ReceptionIntake(db.Model):
    """A new patient being walked from the front door to the Triage bench.

    Deliberately NOT a medical record: no complaint, no symptoms, no
    observations. Only who the person is, who to call in an emergency, how they
    will pay, and what help they need to get through the building.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), index=True)
    ref = db.Column(db.String(40), unique=True, nullable=False, index=True)

    # --- identity (what Reception actually asks for)
    surname = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    other_names = db.Column(db.String(80))
    sex = db.Column(db.String(1))
    age_years = db.Column(db.Integer)
    occupation = db.Column(db.String(80))

    # --- contact
    phone = db.Column(db.String(32), index=True)
    address = db.Column(EncryptedText())               # F-015 field-encrypted

    # --- the rest of the hospital's paper admission form (Aug 2026).
    # These are IDENTITY and DEMOGRAPHIC details, not clinical ones. Religion
    # and tribe are on the paper form for real reasons: dietary needs, burial
    # rites, and finding an interpreter who actually speaks the language.
    date_of_birth = db.Column(EncryptedDate())         # F-015 field-encrypted
    marital_status = db.Column(db.String(16))
    religion = db.Column(db.String(40))
    state_of_origin = db.Column(db.String(60))
    town = db.Column(db.String(80))
    tribe = db.Column(db.String(60))
    ethnic_group = db.Column(db.String(60))

    # --- next of kin: name, phone AND relationship, as the founder specified
    nok_name = db.Column(db.String(120))
    nok_phone = db.Column(EncryptedString(32))         # F-015 field-encrypted
    nok_phone_bx = db.Column(db.String(32), index=True)
    nok_relationship = db.Column(db.String(40))

    @_sa_validates("nok_phone")
    def _hash_nok_phone(self, _key, value):
        self.nok_phone_bx = blind_index("intake.nok_phone", value)
        return value

    # --- health insurance / how they will pay
    payer_type = db.Column(db.String(16), default="SELF", nullable=False)
    payer_number = db.Column(db.String(60))
    payer_name = db.Column(db.String(120))

    # --- SPECIAL NEEDS. Moved here from the HIMS folder form: the person who
    # first meets the patient is the one who can see they need a wheelchair.
    preferred_lang = db.Column(db.String(4), default="en")
    assistance = db.Column(db.String(200))        # comma-separated ASSISTANCE_CODES
    assistance_consent_at = db.Column(db.DateTime)  # G1: separate consent for disability data
    care_note = db.Column(db.String(200))

    # --- where they are in the walk
    stage = db.Column(db.String(12), default="RECEPTION", nullable=False, index=True)
    bill_ref = db.Column(db.String(40))           # written by Billing
    payment_ref = db.Column(db.String(40))        # receipt from Megalex/Pay-Point
    needs_blood_sugar = db.Column(db.Boolean, default=True, nullable=False)

    # Fast-track: identified at reception (elderly/pregnant/child/wheelchair)
    is_fast_track = db.Column(db.Boolean, default=False, nullable=False, index=True)
    fast_track_reason = db.Column(db.String(40))

    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), index=True)
    visit_id = db.Column(
        db.Integer,
        db.ForeignKey("patient_visit.id", use_alter=True, name="fk_intake_visit"),
        index=True,
    )

    created_at = db.Column(db.DateTime, default=now_naive, nullable=False, index=True)
    billed_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    registered_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    patient = db.relationship("Patient")
    receptionist = db.relationship("User", foreign_keys=[created_by])

    @property
    def full_name(self) -> str:
        bits = [self.first_name, self.other_names, self.surname]
        return " ".join(b for b in bits if b).strip()

    @property
    def spoken_name(self) -> str:
        """How this person is CALLED. Matches Patient.spoken_name so one
        patient is never announced two different ways across a visit."""
        return self.full_name

    @property
    def care_flags(self) -> list[str]:
        """Plain-English list of what this person needs. Spoken aloud."""
        out = [ASSISTANCE_LABELS[c] for c in (self.assistance or "").split(",")
               if c and c in ASSISTANCE_LABELS]
        if (self.preferred_lang or "en") != "en":
            out.append(f"Prefers {PATIENT_LANG_LABELS.get(self.preferred_lang, self.preferred_lang)}"
                       " — greet them in it")
        if self.care_note:
            out.append(self.care_note)
        return out

    @property
    def stage_label(self) -> str:
        return INTAKE_STAGE_LABELS.get(self.stage, self.stage)


# ---------------------------------------------------------------- triage
# Where Triage can place a patient. These are the clinics the founder named.
CLINICS = (
    ("OPD",       "OPD — General Outpatient"),
    ("SOPD",      "SOPD — Surgical Outpatient"),
    ("MOPD",      "MOPD — Medical Outpatient"),
    ("EMERGENCY", "Accident & Emergency"),
)
CLINIC_LABELS = dict(CLINICS)
CLINIC_CODES = tuple(c for c, _ in CLINICS)

CONSULTING_ROOMS = ("Room 1", "Room 2", "Room 3", "Room 4", "Emergency Room")


class ServiceClinic(db.Model):
    """A clinic where Triage can place a patient and where doctors consult.

    WHY ROWS NOT TUPLES
    -------------------
    Clinics were hard-coded Python tuples. Adding \"Dental Clinic\" needed a
    developer and a deploy — the same trap Role Management was built to escape.
    They are now rows, seeded from the original tuples so nothing that worked
    yesterday changes, but Admin can add/edit/suspend/delete more.

    UPGRADE 2026-08-21: Dental, ANC, O&G, Ophthalmology/Eye, Pediatrics, etc.
    """
    __tablename__ = "service_clinic"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)  # OPD, DENTAL, ANC, O&G, EYE
    name = db.Column(db.String(120), nullable=False)  # Dental Clinic
    description = db.Column(db.String(300))
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now_naive)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)

    # Shortlist: which destinations this clinic's doctors may send patients to.
    # Empty shortlist = show everything (empty must never mean nothing, or doctors
    # get empty dropdown and cannot move patients).
    # FIX for reviewer edge: if shortlist non-empty but all items suspended,
    # show warning not everything.
    destinations = db.relationship(
        "ClinicDestination",
        backref="clinic",
        cascade="all, delete-orphan",
        order_by="ClinicDestination.destination_id",
    )

    __table_args__ = (
        db.UniqueConstraint("org_id", "code", name="uq_clinic_org_code"),
        db.Index("ix_clinic_org_active", "org_id", "active"),
    )

    @property
    def label(self) -> str:
        return f"{self.code} — {self.name}" if self.code != self.name else self.name


class ConsultingRoom(db.Model):
    """A physical consulting room where a doctor sits.

    UPGRADE 2026-08-21: Up to 8 rooms, admin editable (add/edit/delete/suspend).
    Previously hard-coded 5 rooms. Now rows, seeded so existing sessions still work.
    """
    __tablename__ = "consulting_room"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)  # ROOM1, ROOM8, ER
    name = db.Column(db.String(120), nullable=False)  # Room 1, Room 8, Emergency Room
    clinic_id = db.Column(db.Integer, db.ForeignKey("service_clinic.id"), index=True)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now_naive)

    clinic = db.relationship("ServiceClinic", backref="rooms")

    __table_args__ = (
        db.UniqueConstraint("org_id", "code", name="uq_room_org_code"),
        db.Index("ix_room_org_active", "org_id", "active"),
    )

    @property
    def label(self) -> str:
        return self.name


class ServiceDestination(db.Model):
    """Where a doctor can send a patient after consultation.

    UPGRADE 2026-08-21: Previously 6 hard-coded destinations. Now admin editable,
    with many more: HIMS, MOPD, SOPD, OPD, O&G, MSSD/Welfare, Pediatrics,
    Physiotherapy, Radiology/Imaging, Dental, Nutrition & Dietetics,
    Ophthalmology, Maternity, Casualty, Dressing Room, Theater, Male Ward,
    Female Ward, etc.

    Suspend ≠ delete. Used destinations cannot be deleted, only suspended.
    """
    __tablename__ = "service_destination"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(30), nullable=False)  # LAB, PHARMACY, DENTAL, MSSD, etc
    name = db.Column(db.String(120), nullable=False)  # Laboratory, Dental Clinic
    place = db.Column(db.String(120))  # where physically: the Laboratory
    description = db.Column(db.String(300))
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now_naive)

    __table_args__ = (
        db.UniqueConstraint("org_id", "code", name="uq_dest_org_code"),
        db.Index("ix_dest_org_active", "org_id", "active"),
    )

    @property
    def label(self) -> str:
        return f"{self.name} — {self.description}" if self.description else self.name


class ClinicDestination(db.Model):
    """Shortlist: which destinations a clinic's doctors are offered.

    Empty shortlist for a clinic = show everything (not configured yet).
    Non-empty shortlist where all items suspended = show warning, not everything.
    """
    __tablename__ = "clinic_destination"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey("service_clinic.id"), nullable=False, index=True)
    destination_id = db.Column(
        db.Integer, db.ForeignKey("service_destination.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=now_naive)

    destination = db.relationship("ServiceDestination")

    __table_args__ = (
        db.UniqueConstraint("clinic_id", "destination_id", name="uq_clinic_dest"),
        db.Index("ix_clinic_dest_org", "org_id", "clinic_id"),
    )


class TvScreen(db.Model):
    """A TV / monitor in the hospital showing live queue + doctor calls.

    WHY THIS TABLE
    --------------
    Founder wants NIGERIA NATIVE VOICES, 2 male 2 female recycled daily,
    multiple TVs but waiting area shows MORE, full name + queue stats,
    more than doctor calls, English + Yoruba, friendly attractive.

    One row per physical TV. Waiting area main TV shows everything,
    clinic TVs show only their clinic, department TVs show only their desk.

    Per-tenant, admin editable, no EMR columns.
    """
    __tablename__ = "tv_screen"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)  # e.g. MAIN, DENTAL1, PHARM
    name = db.Column(db.String(120), nullable=False)  # Waiting Area Main TV
    location = db.Column(db.String(120))  # e.g. General Waiting Hall
    # What to show
    screen_type = db.Column(db.String(20), default="WAITING_MAIN", nullable=False)  # WAITING_MAIN | CLINIC | DEPARTMENT | WARD | EXECUTIVE
    clinic_code = db.Column(db.String(20))  # filter: only show this clinic (DENTAL) - null = all
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))  # filter: only this department
    # Display options
    show_full_name = db.Column(db.Boolean, default=True, nullable=False)  # True = Folake Abatan, False = D-012 only
    show_queue_stats = db.Column(db.Boolean, default=True, nullable=False)
    show_reception = db.Column(db.Boolean, default=True, nullable=False)
    show_triage = db.Column(db.Boolean, default=True, nullable=False)
    show_consulting = db.Column(db.Boolean, default=True, nullable=False)
    show_onward = db.Column(db.Boolean, default=True, nullable=False)
    # Fast Track filter — executive TV shows only Fast Track gold lane
    show_fast_track_only = db.Column(db.Boolean, default=False, nullable=False)
    is_executive = db.Column(db.Boolean, default=False, nullable=False)  # True = executive building TV, gold theme
    # Voice options - Nigeria native voices, 2 male 2 female recycled daily
    voice_enabled = db.Column(db.Boolean, default=True, nullable=False)
    voice_rotate_daily = db.Column(db.Boolean, default=True, nullable=False)  # True = 2M2F recycled daily
    voice_languages = db.Column(db.String(30), default="en,yo,ha,ig")  # en,yo,ha,ig = 4 Nigerian languages
    voice_volume = db.Column(db.Integer, default=100, nullable=False)  # 0-100 slider per TV
    # Brightness / night mode — per TV, per-tenant, premium UX
    brightness = db.Column(db.Integer, default=100, nullable=False)  # 0-100 brightness slider per TV
    night_mode = db.Column(db.Boolean, default=False, nullable=False)  # auto dim at night 19:00-07:00
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=now_naive)

    department = db.relationship("Department")

    __table_args__ = (
        db.UniqueConstraint("org_id", "code", name="uq_tv_org_code"),
        db.Index("ix_tv_org_active", "org_id", "active"),
    )

    @property
    def languages(self) -> list[str]:
        return [l.strip() for l in (self.voice_languages or "en").split(",") if l.strip()]


class DoctorSession(db.Model):
    """A doctor saying "I am in this room and ready to see patients".

    WHY THIS EXISTS
    ---------------
    The founder was explicit: a doctor is available only when they are BOTH
    rostered AND have clicked "ready to consult". The roster says who is
    supposed to be in the building; this says who is actually sitting in a
    consulting room with the door open. Triage must never send a patient to an
    empty room because the roster said someone should be there.

    Ending a session (going to lunch, going home) closes it. Triage then stops
    offering that room immediately.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    duty_date = db.Column(db.Date, nullable=False, index=True)
    clinic = db.Column(db.String(20), nullable=False)          # OPD | SOPD | MOPD | EMERGENCY
    consulting_room = db.Column(db.String(20), nullable=False)
    ready = db.Column(db.Boolean, default=True, nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=now_naive, nullable=False)
    ended_at = db.Column(db.DateTime)

    doctor = db.relationship("User", foreign_keys=[doctor_id])

    __table_args__ = (
        db.Index("ix_doctor_session_org_date", "org_id", "duty_date"),
    )

    @property
    def is_open(self) -> bool:
        return bool(self.ready) and self.ended_at is None


# ---------------------------------------------------------------- onward (Stage D)
# Where a doctor sends the patient after the consultation. The founder listed
# these exactly, and was clear it can be MORE THAN ONE:
#
#   "The Doctor after attending to the patient would now push the patient to
#    one, two or three out of the following
#    (LAHSMA/Billing/Megalek/Laboratory/Pharmacy/Emergency)"
#
# Hence a separate table rather than a single column on the visit: one visit
# can legitimately owe a lab test AND a pharmacy collection AND a bill.
ONWARD_DESTINATIONS = (
    ("LABORATORY", "Laboratory — tests"),
    ("PHARMACY",   "Pharmacy / Dispensary — collect medicines"),
    ("BILLING",    "Billing Point — settle the bill"),
    ("MEGALEX",    "Megalex / Paying Point — make payment"),
    ("LAHSMA",     "LAHSMA — insurance claim"),
    ("EMERGENCY",  "Accident & Emergency — urgent"),
)
ONWARD_LABELS = dict(ONWARD_DESTINATIONS)
ONWARD_CODES = tuple(c for c, _ in ONWARD_DESTINATIONS)

# Where a patient physically goes for each destination — used by the voice
# call-out so it names a place the patient can actually walk to.
ONWARD_PLACES = {
    "LABORATORY": "the Laboratory",
    "PHARMACY":   "the Pharmacy",
    "BILLING":    "the Billing Point",
    "MEGALEX":    "the Megalex Paying Point",
    "LAHSMA":     "the LAHSMA desk",
    "EMERGENCY":  "Accident and Emergency",
}


class VisitOnward(db.Model):
    """One place the doctor is sending this patient after the consultation.

    A visit has one row per destination. Each is completed independently — the
    laboratory can finish while the pharmacy is still waiting — and the visit
    is only closed when every destination is done.

    NOT AN EMR: this records WHERE the patient was sent and whether they got
    there. It never records what the test was for, what was prescribed, or
    why. "Send to Laboratory" is a direction, not a clinical order.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey("patient_visit.id"), nullable=False, index=True)
    destination = db.Column(db.String(16), nullable=False, index=True)
    status = db.Column(db.String(12), default="PENDING", nullable=False, index=True)  # PENDING | DONE
    note = db.Column(db.String(200))               # e.g. "bring the card back"
    sent_at = db.Column(db.DateTime, default=now_naive, nullable=False)
    completed_at = db.Column(db.DateTime)
    sent_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    completed_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    visit = db.relationship("PatientVisit", backref=db.backref(
        "onward_steps", cascade="all, delete-orphan", order_by="VisitOnward.id"))
    doctor = db.relationship("User", foreign_keys=[sent_by])

    __table_args__ = (
        db.UniqueConstraint("visit_id", "destination", name="uq_visit_onward_dest"),
        db.Index("ix_visit_onward_org_status", "org_id", "status"),
    )

    @property
    def label(self) -> str:
        return ONWARD_LABELS.get(self.destination, self.destination)

    @property
    def place(self) -> str:
        return ONWARD_PLACES.get(self.destination, self.destination)


# ---------------------------------------------------------------- tracking
# Every place a patient stands still, and for how long. This is what turns the
# suite from "software that works" into "proof the hospital got better".
JOURNEY_STAGES = (
    ("RECEPTION",  "Reception"),
    ("BILLING",    "Billing Point"),
    ("PAYMENT",    "Megalex / Paying Point"),
    ("HIMS",       "HIMS — folder"),
    ("TRIAGE",     "Triage"),
    ("WAIT_DOCTOR", "Waiting for the doctor"),
    ("CONSULTATION", "With the doctor"),
    ("LABORATORY", "Laboratory"),
    ("PHARMACY",   "Pharmacy"),
    ("BILLING_OUT", "Billing (after consultation)"),
    ("MEGALEX",    "Megalex (after consultation)"),
    ("LAHSMA",     "LAHSMA desk"),
    ("EMERGENCY",  "Accident & Emergency"),
)
JOURNEY_STAGE_LABELS = dict(JOURNEY_STAGES)
JOURNEY_STAGE_CODES = tuple(c for c, _ in JOURNEY_STAGES)


class JourneySegment(db.Model):
    """One stretch of time a patient spent at one place.

    WHY SEGMENTS AND NOT JUST EVENT POINTS
    --------------------------------------
    A row that says "arrived at Triage 09:14" needs the NEXT row to work out
    how long Triage took, and the last row of the day can never be measured at
    all. A segment carries its own start, end and duration, so every question
    ("how long does the pharmacy take?") is a plain average over closed rows —
    no pairing, no gaps, no arithmetic that breaks when a row is missing.

    An OPEN segment (ended_at IS NULL) is where the patient is standing right
    now. That is how the live board knows who is waiting where.

    NOT AN EMR: this records WHERE a patient was and for HOW LONG. Never why.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)

    # A journey starts at Reception, before a folder or a visit exists, so both
    # links are optional and at least one is always set.
    intake_id = db.Column(db.Integer, db.ForeignKey("reception_intake.id"), index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey("patient_visit.id"), index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), index=True)

    stage = db.Column(db.String(20), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), index=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)

    entered_at = db.Column(db.DateTime, default=now_naive, nullable=False, index=True)
    ended_at = db.Column(db.DateTime, index=True)
    # Stored, not computed on read: a year of reports must not re-do this
    # arithmetic on every page load over a slow connection.
    seconds = db.Column(db.Integer)

    patient = db.relationship("Patient")
    staff = db.relationship("User", foreign_keys=[staff_id])
    department = db.relationship("Department")

    __table_args__ = (
        db.Index("ix_journey_org_stage", "org_id", "stage"),
        db.Index("ix_journey_org_entered", "org_id", "entered_at"),
        db.Index("ix_journey_open", "org_id", "ended_at"),
    )

    @property
    def label(self) -> str:
        return JOURNEY_STAGE_LABELS.get(self.stage, self.stage)

    @property
    def minutes(self) -> int:
        if self.seconds is None:
            return 0
        return int(self.seconds // 60)

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


# ================================================================ ROLE MANAGEMENT
# WHY A TABLE AND NOT A FIXED LIST
# --------------------------------
# Until now a person's job was one word in a column: HOD, ADMIN_MANAGER,
# SUPER_ADMIN. That worked while the hospital had eight kinds of person. It
# breaks the moment a real hospital says "our Pharmacy Technician may see the
# pharmacy queue but must not open a folder" — because there was nowhere to
# write that down without a developer editing Python and redeploying.
#
# A SaaS product cannot ask a developer to change code every time a tenant
# hires a new kind of staff. So a role is now a ROW, owned by the hospital,
# with a tick-list of permissions the administrator can edit from the screen.
#
# The old one-word roles still work exactly as before. They are seeded as
# BUILT-IN roles, are marked as such, and cannot be deleted. Nothing that
# worked yesterday stops working today.

# A permission is a plain, boring English sentence about one thing a person may
# do. The KEY is what code checks; the LABEL is what the administrator ticks.
PERMISSION_GROUPS = (
    ("Front of house", (
        ("reception",   "Work the Reception desk"),
        ("cashdesk",    "Work Billing and the Paying Point"),
        ("hims",        "Open and search patient folders (HIMS)"),
        ("lahsma",      "Work the LAHSMA desk — issue insurance clearance"),
    )),
    ("Patient flow", (
        ("triage",      "Run the Triage bench and assign doctors"),
        ("consulting",  "Run a consulting room and see patients"),
        ("onward",      "Send a patient onward after consultation"),
        ("bookings",    "Manage bookings and the queue"),
    )),
    ("Department work", (
        ("dept_desk",   "See my department's own desk and today's work"),
        ("dept_claim",  "Take on a task in my department"),
        ("dept_staff",  "See who in my department is working on what"),
        ("dept_manage", "Step a colleague off a task on their behalf"),
    )),
    ("Quality & complaints", (
        ("complaints",  "See and answer complaints"),
        ("escalate",    "Escalate a complaint to higher authority"),
        ("corrective",  "Manage corrective actions"),
        ("inspections", "Carry out the Admin Manager's walk-round"),
    )),
    ("Management", (
        ("tracking",    "See patient-flow figures and staff efficiency"),
        ("reports",     "Open the reports centre"),
        ("referrals",   "Manage referrals"),
        ("roster",      "See the duty roster"),
        ("roster_edit", "Change the duty roster"),
    )),
    ("Staff time", (
        ("attendance",       "Clock in and out of work"),
        ("attendance_admin", "See who is at work today and accept an outside clock-in"),
    )),
    ("Administration", (
        ("admin",       "Open the Administrator settings (full control)"),
        ("roles_admin", "Create roles and decide who may do what"),
    )),
)
PERMISSION_LABELS = {k: v for _, pairs in PERMISSION_GROUPS for k, v in pairs}
PERMISSION_KEYS = tuple(PERMISSION_LABELS)

# How WIDE a role can see. This is the answer to "HOD and Staff should see only
# what is happening in their own department".
ROLE_SCOPES = (
    ("HOSPITAL",   "The whole hospital"),
    ("DEPARTMENT", "Only their own department"),
    ("UNIT",       "Only their own unit or station"),
)
ROLE_SCOPE_LABELS = dict(ROLE_SCOPES)
ROLE_SCOPE_CODES = tuple(c for c, _ in ROLE_SCOPES)


class Role(db.Model):
    """A named job, owned by ONE hospital, with its own tick-list of powers."""
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False)          # STABLE, uppercase
    name = db.Column(db.String(120), nullable=False)         # what staff read
    description = db.Column(db.String(300))
    scope = db.Column(db.String(16), default="DEPARTMENT", nullable=False)
    # Built-in roles mirror the original eight. They may be RE-TICKED (a
    # hospital can decide its HODs may not touch the roster) but never deleted,
    # because deleting one would strand every account that holds it.
    builtin = db.Column(db.Boolean, default=False, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive)

    grants = db.relationship("RolePermission", backref="role",
                             cascade="all, delete-orphan", lazy="select")
    __table_args__ = (db.UniqueConstraint("org_id", "code", name="uq_role_org_code"),)

    @property
    def permission_keys(self) -> set:
        return {g.permission for g in self.grants if g.allowed}

    @property
    def scope_label(self) -> str:
        return ROLE_SCOPE_LABELS.get(self.scope, self.scope)


class RolePermission(db.Model):
    """One tick on one role. A row per power, so the audit trail is readable."""
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False, index=True)
    permission = db.Column(db.String(40), nullable=False)
    allowed = db.Column(db.Boolean, default=True, nullable=False)
    __table_args__ = (db.UniqueConstraint("role_id", "permission", name="uq_roleperm"),)


class UserRole(db.Model):
    """This person holds this role — optionally only inside one department.

    A person may hold MORE THAN ONE. A senior nurse can be Staff in Theatre on
    Monday and Acting HOD of A&E on Tuesday, and the system must let her be
    both at once instead of forcing somebody to edit her account twice a week.
    Powers ADD UP; sight is the union of the places each role can see.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False, index=True)
    # Where this particular hat applies. NULL department on a DEPARTMENT-scoped
    # role falls back to the person's own department on their staff record.
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("unit.id"), index=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    granted_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    granted_at = db.Column(db.DateTime, default=now_naive)

    role = db.relationship("Role")
    user = db.relationship("User", foreign_keys=[user_id])
    department = db.relationship("Department")
    unit = db.relationship("Unit")
    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", "department_id", "unit_id",
                            name="uq_userrole"),
        db.Index("ix_userrole_org_user", "org_id", "user_id"),
    )


# ---------------------------------------------------------------- teamwork
WORK_KINDS = (
    ("RECEPTION",   "Taking patients in at Reception"),
    ("BILLING",     "Raising bills"),
    ("PAYMENT",     "Collecting payment"),
    ("HIMS",        "Opening and finding folders"),
    ("TRIAGE",      "Placing patients with doctors"),
    ("CONSULT",     "Seeing patients in a consulting room"),
    ("LABORATORY",  "Laboratory work"),
    ("LAB_SAMPLE",  "Collecting lab samples"),
    ("LAB_RESULT",  "Entering lab results"),
    ("PHARMACY",    "Dispensing"),
    ("PHARM_STOCK", "Pharmacy stock check"),
    ("THEATER",     "Theater / Surgery"),
    ("THEATER_PREP","Theater preparation"),
    ("WARD_ROUND",  "Ward round"),
    ("WARD_CARE",   "Ward patient care"),
    ("ANC",         "Antenatal care"),
    ("IMMUNIZATION","Immunization"),
    ("FAST_TRACK",  "Fast Track — premium quick care"),
    ("EMERGENCY",   "Accident & Emergency"),
    ("RADIOLOGY",   "X-ray / Radiology"),
    ("PHYSIO",      "Physiotherapy"),
    ("DENTAL",      "Dental care"),
    ("MORTUARY",    "Mortuary"),
    ("RECORDS",     "Records & filing"),
    ("COMPLAINT",   "Answering a complaint"),
    ("CLEANING",    "Cleaning and environment"),
    ("SECURITY",    "Security / Gate"),
    ("MAINTENANCE", "Maintenance"),
    ("OTHER",       "Other department work"),
)

# Department-specific defaults — what work does this department usually do?
DEPT_DEFAULT_WORK = {
    "RECEPTION": ["RECEPTION", "FAST_TRACK"],
    "BILLING": ["BILLING", "FAST_TRACK"],
    "PAYMENT": ["PAYMENT", "FAST_TRACK"],
    "MEGALEX": ["PAYMENT", "FAST_TRACK"],
    "HIMS": ["HIMS", "RECORDS", "FAST_TRACK"],
    "TRIAGE": ["TRIAGE", "WARD_CARE", "FAST_TRACK"],
    "CONSULT": ["CONSULT", "WARD_ROUND", "FAST_TRACK"],
    "LABORATORY": ["LABORATORY", "LAB_SAMPLE", "LAB_RESULT"],
    "PHARMACY": ["PHARMACY", "PHARM_STOCK", "FAST_TRACK"],
    "THEATER": ["THEATER", "THEATER_PREP", "WARD_CARE", "CLEANING"],
    "WARD": ["WARD_CARE", "WARD_ROUND", "CLEANING"],
    "ANC": ["ANC", "WARD_CARE"],
    "ACCIDENT": ["EMERGENCY", "TRIAGE", "WARD_CARE"],
    "EMERGENCY": ["EMERGENCY", "TRIAGE", "WARD_CARE"],
    "RADIOLOGY": ["RADIOLOGY", "RECORDS"],
    "PHYSIO": ["PHYSIO", "WARD_CARE"],
    "DENTAL": ["DENTAL", "RECORDS"],
    "MORTUARY": ["MORTUARY", "RECORDS"],
    "ADMIN": ["OTHER", "RECORDS", "CLEANING"],
    "CLEANING": ["CLEANING", "OTHER"],
    "SECURITY": ["SECURITY", "OTHER"],
}

def default_work_for_dept(dept_name: str) -> list[str]:
    name = (dept_name or "").upper()
    for key, kinds in DEPT_DEFAULT_WORK.items():
        if key in name:
            return kinds
    return ["OTHER", "CLEANING"]

WORK_KIND_LABELS = dict(WORK_KINDS)
WORK_KIND_CODES = tuple(c for c, _ in WORK_KINDS)


class WorkClaim(db.Model):
    """"I am on this." One row per person per task, NEVER an exclusive lock.

    THE POINT
    ---------
    The founder asked for several staff to be able to work at the same time —
    on the same task or on different ones — inside one department. The obvious
    software answer is a lock: one person claims a job, everybody else is
    refused. That is exactly wrong for a hospital. Two porters really do move
    one trolley; three nurses really do clear one queue together; a second
    clerk joining a long reception line is help, not a conflict.

    So this is a NOTICEBOARD, not a lock. Anybody may join anything. What the
    system guarantees is that everybody can SEE who else is on it, so two
    people never silently duplicate the same call to the same patient.

    The one thing it refuses is the same PERSON claiming the same task twice,
    which is a double-tap on a phone, not a second worker.
    """
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("unit.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    kind = db.Column(db.String(20), nullable=False, index=True)
    # What is being worked on, if it is one identifiable thing. A shared task
    # ("clear the reception queue") has no entity at all — that is normal.
    entity_type = db.Column(db.String(30))
    entity_id = db.Column(db.Integer)
    note = db.Column(db.String(200))

    started_at = db.Column(db.DateTime, default=now_naive, nullable=False, index=True)
    ended_at = db.Column(db.DateTime, index=True)
    seconds = db.Column(db.Integer)
    suspended = db.Column(db.Boolean, default=False, nullable=False, index=True)
    suspended_at = db.Column(db.DateTime)
    suspended_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    user = db.relationship("User", foreign_keys=[user_id])
    department = db.relationship("Department")
    __table_args__ = (
        db.Index("ix_claim_open", "org_id", "ended_at"),
        db.Index("ix_claim_task", "org_id", "kind", "entity_type", "entity_id"),
    )

    @property
    def label(self) -> str:
        return WORK_KIND_LABELS.get(self.kind, self.kind)

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def minutes(self) -> int:
        if self.seconds is not None:
            return int(self.seconds // 60)
        return max(0, int((now_naive() - self.started_at).total_seconds() // 60))


# ---------------------------------------------------------------- staff clock-in
class StaffAttendance(db.Model):
    """One clock-in / clock-out for one person on one day.

    NOT a patient record. This is only \"was this member of staff at the
    hospital gate\". No clinical columns, ever.
    """
    __tablename__ = "staff_attendance"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    duty_date = db.Column(db.Date, nullable=False, index=True)

    clock_in_at = db.Column(db.DateTime, nullable=False, default=now_naive)
    clock_out_at = db.Column(db.DateTime)

    in_lat = db.Column(db.Float)
    in_lng = db.Column(db.Float)
    in_accuracy_m = db.Column(db.Integer)
    in_distance_m = db.Column(db.Integer)
    in_inside = db.Column(db.Boolean)

    out_lat = db.Column(db.Float)
    out_lng = db.Column(db.Float)
    out_accuracy_m = db.Column(db.Integer)
    out_distance_m = db.Column(db.Integer)
    out_inside = db.Column(db.Boolean)

    mode = db.Column(db.String(12), default="off")          # off | optional | required
    override_reason = db.Column(db.String(200))
    override_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    device_info = db.Column(db.String(200))
    # Honest clock-in: cheat marks, grace, helped punch, offline time
    flagged = db.Column(db.Boolean, default=False)
    flag_note = db.Column(db.String(240))
    mocked = db.Column(db.Boolean, default=False)
    client_punched_at = db.Column(db.DateTime)
    late_minutes = db.Column(db.Integer)
    in_grace = db.Column(db.Boolean, default=False)
    help_reason = db.Column(db.String(20))
    evidence_path = db.Column(db.String(300))
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_note = db.Column(db.String(200))

    user = db.relationship("User", foreign_keys=[user_id])
    branch = db.relationship("Branch", foreign_keys=[branch_id])
    override_by = db.relationship("User", foreign_keys=[override_by_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (
        db.Index("ix_staff_att_org_date", "org_id", "duty_date"),
        db.Index("ix_staff_att_open", "org_id", "user_id", "clock_out_at"),
    )

    @property
    def is_open(self) -> bool:
        return self.clock_out_at is None


# ---------------------------------------------------------------- native voice phrase bank (v1.7.16)
# Chrome/Google TTS sounds foreign. Native recorded phrase bank — phrase, not clone.
# 2 male 2 female recycled daily, 4 languages (en, yo, ha, ig), dynamic time/name.
class NativeVoice(db.Model):
    """One recorded human voice — e.g., Ada Female1 Nigerian English.

    WHY PHRASE BANK NOT CLONE
    -------------------------
    Founder rule: phrase bank, not clone. Clone needs AI model, licensing,
    and sounds uncanny. Phrase bank is real humans recording real phrases,
    stitched for dynamic parts (names, numbers, places, times).

    DYNAMIC HANDLING
    ----------------
    - Time changes: greeting_morning / afternoon / evening based on now_naive().hour
    - Name changes: {name} placeholder replaced via speech_name(), not hardcoded
    - Count changes: number_1, number_2... recordings + TTS fallback
    - Place changes: place_laboratory, place_pharmacy... recordings per language
    """
    __tablename__ = "native_voice"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)  # FEMALE1, MALE1, FEMALE2, MALE2
    name = db.Column(db.String(80), nullable=False)  # Ada, Emeka, Folake, Chinedu
    gender = db.Column(db.String(10), nullable=False)  # female | male
    language = db.Column(db.String(10), nullable=False, default="en")  # en, yo, ha, ig, en-NG
    sample_key = db.Column(db.String(300))  # stored_file key for sample audio
    is_default = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive)

    org = db.relationship("Organization", backref="native_voices")

    __table_args__ = (
        db.UniqueConstraint("org_id", "code", "language", name="uq_voice_org_code_lang"),
        db.Index("ix_voice_org_active", "org_id", "active"),
    )

    @property
    def display_name(self) -> str:
        return f"{self.name} — {self.gender} — {self.language.upper()} ({self.code})"


class NativePhrase(db.Model):
    """One recorded phrase — e.g., go_to_billing in Yoruba by Ada.

    Dynamic placeholders: {name}, {count}, {place}, {room}, {time}, {detail}
    Text template stored for reference, audio_key is actual recording.

    For dynamic parts, we have separate number and place recordings:
    - number_0 ... number_100, number_many
    - place_laboratory, place_pharmacy, place_billing, etc.
    - greeting_morning, greeting_afternoon, greeting_evening
    - time_ formats: today, tomorrow, etc.

    If audio missing, fallback to TTS phrase() from announce.py.
    """
    __tablename__ = "native_phrase"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    voice_id = db.Column(db.Integer, db.ForeignKey("native_voice.id"), nullable=False, index=True)
    key = db.Column(db.String(80), nullable=False, index=True)  # e.g., queue_waiting, go_to_billing, number_3, place_lab
    language = db.Column(db.String(10), nullable=False, default="en")
    text_template = db.Column(db.String(500))  # e.g., "{name}, {count} patients waiting at {place}"
    audio_key = db.Column(db.String(300))  # stored_file key for mp3/wav
    duration_ms = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now_naive)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)

    voice = db.relationship("NativeVoice", backref="phrases")
    org = db.relationship("Organization", backref="native_phrases")

    __table_args__ = (
        db.UniqueConstraint("org_id", "voice_id", "key", "language", name="uq_phrase_org_voice_key_lang"),
        db.Index("ix_phrase_org_key_lang", "org_id", "key", "language"),
    )


class NativeVoiceSetting(db.Model):
    """Per-hospital settings for native voice bank.

    Dynamic: enabled per org, fallback to TTS, volume, languages, daily rotation.
    """
    __tablename__ = "native_voice_setting"
    org_id = db.Column(db.Integer, db.ForeignKey("organization.id"), primary_key=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)  # master switch
    use_native = db.Column(db.Boolean, default=True, nullable=False)  # prefer native over TTS
    fallback_to_tts = db.Column(db.Boolean, default=True, nullable=False)  # if native missing, use TTS
    languages = db.Column(db.String(30), default="en,yo,ha,ig")
    volume = db.Column(db.Integer, default=100)
    # JSON mapping slot->voice_id for daily rotation override
    rotation_map = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=now_naive)
    updated_at = db.Column(db.DateTime, default=now_naive, onupdate=now_naive)

    org = db.relationship("Organization", backref="native_voice_setting")

    @property
    def language_list(self) -> list[str]:
        return [l.strip() for l in (self.languages or "en").split(",") if l.strip()]

