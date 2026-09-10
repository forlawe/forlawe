"""Role Management — who may do what, and how much of the hospital they see.

THE PROBLEM THIS SOLVES
-----------------------
A person's job used to be one word in a column: HOD, ADMIN_MANAGER,
SUPER_ADMIN. Eight words, hard-coded in Python. Every question a real hospital
asks — "may our Pharmacy Technician see the pharmacy queue?", "should the HOD
of Theatre see A&E's complaints?" — needed a developer, a code change and a
redeploy. That is not a product; that is a permanent consultancy contract.

Three things now come out of this file:

1. WHAT a person may do  — a tick-list the administrator edits on screen.
2. HOW MUCH they may see — hospital-wide, their department, or their unit.
3. WHO ELSE is working alongside them right now, so several people can share
   one department's work without tripping over each other.

TWO RULES THAT MUST NOT BE WEAKENED
-----------------------------------
* **Nothing that worked yesterday may break today.** The eight original roles
  are seeded as BUILT-IN rows with exactly the powers app/navigation.py always
  gave them. A hospital that never opens this screen sees no change at all.

* **Fail CLOSED.** If the role tables are missing, empty or broken, we fall
  back to the OLD hard-coded map rather than granting anything. A bug here must
  never hand somebody the administrator's menu.

SCOPE IS SIGHT, NOT POWER
-------------------------
Permission answers "may you press this button". Scope answers "on whose
patients". They are separate on purpose: a Matron may hold the same ticks as a
ward sister and still see five wards to the sister's one.
"""
from __future__ import annotations

import logging

from .models import (PERMISSION_KEYS, Department, Role, RolePermission, Unit,
                     User, UserRole, db, now_naive)

log = logging.getLogger(__name__)


# ============================================================ BUILT-IN ROLES
# These mirror app/navigation.py EXACTLY as it behaved before this feature
# existed. They are the safety net: seeded on first use, never deleted, and
# used as the fallback if the tables cannot be read.
#
# Front-desk work stays granted by DEPARTMENT for the HOD role — see
# navigation.py for why that is closer to how a hospital really works than any
# rule based on rank. That department nuance is applied on top of these ticks.
BUILTIN_ROLES: dict[str, dict] = {
    "SUPER_ADMIN": {
        "name": "Super Administrator",
        "scope": "HOSPITAL",
        "description": "Full control of the system and its settings.",
        "permissions": set(PERMISSION_KEYS),
    },
    "MD_CEO": {
        "name": "MD / CEO",
        "scope": "HOSPITAL",
        "description": "Runs the hospital. Sees everything, administers nothing.",
        "permissions": {
            "reception", "cashdesk", "hims", "lahsma", "triage", "consulting",
            "bookings", "complaints", "escalate", "corrective", "inspections",
            "tracking", "reports", "referrals", "roster",
            "dept_desk", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    "DMD": {
        "name": "DMD — Deputy Medical Director",
        "scope": "HOSPITAL",
        "description": "Deputises for the MD across the whole hospital.",
        "permissions": {
            "reception", "cashdesk", "hims", "lahsma", "triage", "consulting",
            "bookings", "complaints", "escalate", "corrective",
            "tracking", "reports", "referrals", "roster",
            "dept_desk", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    "DCST": {
        "name": "DCST — Director of Clinical Services & Training",
        "scope": "HOSPITAL",
        "description": "Clinical services and training, hospital-wide.",
        "permissions": {
            "reception", "cashdesk", "hims", "lahsma", "triage", "consulting",
            "bookings", "complaints", "escalate", "corrective",
            "tracking", "reports", "referrals", "roster",
            "dept_desk", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    "APEX_NURSE": {
        "name": "APEX Nurse — Head of Nursing Services",
        "scope": "DEPARTMENT",
        "description": "Heads nursing — limited to own Department/Section/Unit by default (v1.7.18). System Admin upgrades for wider sight.",
        # v1.7.18 STRICT: HOD and APEX_NURSE limited to own Dept/Section/Unit Activities, Roster C/E/D/Upload, Attendance sign-in of own staff.
        # Previously HOSPITAL scope gave APEX_NURSE whole hospital sight, violating least privilege. Now DEPARTMENT scope, same as HOD.
        # System Admin can grant extra departments via Role Management or make scope HOSPITAL.
        "permissions": {
            "triage", "consulting", "onward", "bookings", "tracking", "roster", "roster_edit",
            "dept_desk", "dept_claim", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    "HEAD_ADMIN_HR": {
        "name": "Head of Admin & HR",
        "scope": "HOSPITAL",
        "description": "Administration and human resources, hospital-wide.",
        "permissions": {
            "reception", "cashdesk", "hims", "lahsma", "triage", "consulting",
            "bookings", "complaints", "escalate", "corrective",
            "tracking", "reports", "referrals", "roster",
            "dept_desk", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    "ADMIN_MANAGER": {
        "name": "Admin Manager",
        "scope": "HOSPITAL",
        "description": "Walks the hospital — BUT ONLY on-duty Admin Manager of TODAY has full privileges (Roster & Day-On-Duty permission v1.7.18).",
        # v1.7.18 STRICT: Admin Manager access limited to Roster & Day-On-Duty. Only Admin Manager rostered for TODAY via DutyRoster can assume all ADMIN_MANAGER privileges.
        # System Admin and HEAD_ADMIN_HR can still manage roster. Others get 403 if not on duty.
        "permissions": {
            "reception", "cashdesk", "hims", "lahsma", "triage", "onward",
            "bookings", "complaints", "escalate", "corrective", "inspections",
            "tracking", "roster", "roster_edit", "referrals",
            "dept_desk", "dept_claim", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    "HOD": {
        "name": "HOD — Head of Department",
        "scope": "DEPARTMENT",
        "description": "Runs one department only — Dept/Section/Unit Activities, Roster C/E/D/Upload, Attendance sign-in of own staff (v1.7.18). System Admin upgrades.",
        # v1.7.18 STRICT: HOD limited to own Dept/Section/Unit by default. Roster creation/edit/delete/uploading allowed for own dept only (via can_manage).
        # Attendance sign-in of own staff when issue allowed. System Admin upgrades via Role Management.
        "permissions": {
            "reception", "cashdesk", "hims", "lahsma",
            "consulting", "onward", "complaints", "escalate", "corrective",
            "tracking", "roster", "roster_edit",
            "dept_desk", "dept_claim", "dept_staff", "dept_manage",
            "attendance", "attendance_admin",
        },
    },
    # ------------------------------------------------------------------ NEW
    # The role the hospital has always had and the software never did: an
    # ordinary member of staff. Before this, every single account had to be
    # given a management role just to sign in, which is why HODs kept turning
    # up where they should not have been.
    "STAFF": {
        "name": "Staff",
        "scope": "DEPARTMENT",
        "description": "Works in one department only — view/read only roster, no edit/delete/upload, no sign-in co-staff (v1.7.18).",
        # v1.7.18 STRICT: Staff sees ONLY own Dept/Section/Unit Activities and Dept Roster view only.
        # NO roster_edit, NO dept_manage, NO attendance_admin — so cannot create/edit/delete roster, cannot sign-in co-staff.
        # Deliberately NO dept_manage: may step themselves off task, not wipe colleague's record.
        "permissions": {"dept_desk", "dept_claim", "dept_staff", "roster", "attendance"},
    },
}

# Roles that must never lose the ability to administer, whatever anybody ticks.
UNDELETABLE = tuple(BUILTIN_ROLES)


# ============================================================ seeding
def ensure_builtin_roles(org_id: int) -> int:
    """Create the built-in roles for a hospital if they are not there yet.

    Idempotent: safe to call on every boot and in every request path. It only
    ADDS what is missing, so an administrator who has re-ticked a built-in role
    does not have their edit silently undone on the next restart. That was a
    real risk worth naming — a settings screen that quietly reverts is worse
    than no settings screen.
    """
    added = 0
    existing = {r.code: r for r in db.session.query(Role).filter_by(org_id=org_id).all()}
    for code, spec in BUILTIN_ROLES.items():
        role = existing.get(code)
        if role is None:
            role = Role(org_id=org_id, code=code, name=spec["name"],
                        description=spec["description"], scope=spec["scope"],
                        builtin=True, active=True)
            db.session.add(role)
            db.session.flush()
            for key in sorted(spec["permissions"]):
                db.session.add(RolePermission(role_id=role.id, permission=key,
                                              allowed=True))
            added += 1
        elif not role.builtin:
            role.builtin = True                 # repair a mislabelled row
    return added


# ============================================================ reading a person
def _legacy_permissions(user) -> set:
    """The OLD hard-coded answer. Used when the role tables cannot be read.

    This is the fail-closed path. It deliberately calls the original
    navigation map rather than guessing, so a database problem degrades to
    yesterday's behaviour instead of to a blank or an open door.
    """
    from .navigation import legacy_permissions_for
    return {k for k, v in legacy_permissions_for(user).items() if v}


def roles_of(user) -> list[Role]:
    """Every hat this person is wearing. Their staff-record role counts too."""
    if user is None or not getattr(user, "id", None):
        return []
    out: list[Role] = []
    seen: set[int] = set()

    # 1. The role written on the staff record — the original, still authoritative.
    base = (db.session.query(Role)
            .filter_by(org_id=user.org_id, code=user.role, active=True).first())
    if base is not None:
        out.append(base)
        seen.add(base.id)

    # 2. Extra hats granted on the Role Management screen.
    for ur in (db.session.query(UserRole)
               .filter_by(org_id=user.org_id, user_id=user.id, active=True).all()):
        r = ur.role
        if r is not None and r.active and r.id not in seen:
            out.append(r)
            seen.add(r.id)
    return out


def permissions_of(user) -> set:
    """Everything this person may do — the UNION of all their roles.

    Union, not intersection. A nurse who is also acting HOD keeps both sets of
    powers; taking a power away because a second, narrower hat was added would
    be a nasty surprise for whoever granted it.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    try:
        roles = roles_of(user)
        if not roles:
            return _legacy_permissions(user)
        granted: set = set()
        for r in roles:
            granted |= r.permission_keys
        return granted
    except Exception:                                      # noqa: BLE001
        log.exception("role lookup failed for user %s — falling back",
                      getattr(user, "id", "?"))
        db.session.rollback()
        try:
            return _legacy_permissions(user)
        except Exception:                                  # noqa: BLE001
            return set()


def has_permission(user, key: str) -> bool:
    return key in permissions_of(user)


# ============================================================ how much they see
def scope_of(user) -> str:
    """The WIDEST scope any of this person's roles gives. Never narrower."""
    if user is None or not getattr(user, "is_authenticated", False):
        return "UNIT"
    try:
        roles = roles_of(user)
    except Exception:                                      # noqa: BLE001
        log.exception("scope lookup failed")
        db.session.rollback()
        roles = []
    if not roles:
        # Unknown role written on the staff record. Management roles kept their
        # hospital-wide sight before this feature existed; everyone else is
        # narrowed to their own department, which is the safer default.
        from .models import MANAGEMENT_ROLES
        return "HOSPITAL" if getattr(user, "role", "") in MANAGEMENT_ROLES else "DEPARTMENT"
    order = {"UNIT": 0, "DEPARTMENT": 1, "HOSPITAL": 2}
    return max((r.scope for r in roles), key=lambda s: order.get(s, 0))


def sees_whole_hospital(user) -> bool:
    return scope_of(user) == "HOSPITAL"


def visible_department_ids(user) -> list[int] | None:
    """Which departments this person may see. None means "all of them".

    None rather than "every id" on purpose: a hospital-wide viewer must not
    silently lose a department that was created after their session started,
    and callers can skip the filter entirely instead of building a huge IN list.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    if sees_whole_hospital(user):
        return None
    ids: set[int] = set()
    own = getattr(user, "department_id", None)
    if own:
        ids.add(own)
    try:
        for ur in (db.session.query(UserRole)
                   .filter_by(org_id=user.org_id, user_id=user.id, active=True).all()):
            if ur.department_id:
                ids.add(ur.department_id)
        # An HOD is the head of their department even if their staff record was
        # never filled in — the department itself names them. Missing this was
        # how a real HOD ended up seeing nothing at all.
        for d in (db.session.query(Department)
                  .filter_by(org_id=user.org_id, hod_user_id=user.id).all()):
            ids.add(d.id)
    except Exception:                                      # noqa: BLE001
        log.exception("department sight lookup failed")
        db.session.rollback()
    return sorted(ids)


def can_see_department(user, department_id) -> bool:
    if department_id is None:
        # Something not attached to any department (a hospital-wide complaint,
        # say). Only whole-hospital sight covers it.
        return sees_whole_hospital(user)
    allowed = visible_department_ids(user)
    return allowed is None or department_id in allowed


def can_see_department_audit(user, department_id, action: str = "ACCESS") -> bool:
    """Check department sight + audit when blocked — for scope enforcement audit (feature 5).

    Returns True if allowed, False if blocked and audit logged.
    """
    if can_see_department(user, department_id):
        return True
    # Blocked — audit scope violation
    try:
        from .audit import audit
        from .models import db as _db
        detail = {
            "blocked_dept_id": department_id,
            "user_role": getattr(user, "role", ""),
            "user_dept_id": getattr(user, "department_id", None),
            "scope": scope_of(user),
            "visible": visible_department_ids(user),
            "action": action,
        }
        audit("SCOPE_BLOCKED", "department", department_id or 0, detail, org_id=getattr(user, "org_id", None))
        _db.session.commit()
    except Exception:
        try:
            from .models import db as _db
            _db.session.rollback()
        except Exception:
            pass
    return False


def scope_note(user) -> str:
    """One honest sentence for the top of a filtered page.

    Staff must never wonder whether a short list means "quiet day" or "the
    system is hiding things from me". Ambiguity there destroys trust in every
    other number on the screen.
    """
    if sees_whole_hospital(user):
        return "You are seeing the whole hospital."
    ids = visible_department_ids(user)
    if not ids:
        return ("No department has been set on your account yet, so there is "
                "nothing to show. Ask the administrator to set your department.")
    names = [d.name for d in db.session.query(Department)
             .filter(Department.id.in_(ids)).order_by(Department.name).all()]
    if not names:
        return "You are seeing your own department only."
    if len(names) == 1:
        return f"You are seeing {names[0]} only — your own department."
    return "You are seeing your own departments only: " + ", ".join(names) + "."


# ============================================================ enforcement
def require(key: str):
    """Route guard: may THIS person do THIS thing?

    Hiding a link is presentation. This is the security. It reads the same
    permission set the menu reads, so the two can never drift apart.
    """
    from functools import wraps

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import abort, redirect, request, url_for
            from flask_login import current_user
            if not getattr(current_user, "is_authenticated", False):
                return redirect(url_for("auth.login", next=request.path))
            if not has_permission(current_user, key):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_department_sight(get_department_id):
    """Route guard for one record: is it in a department you may see?

    `get_department_id` is given the view's own kwargs and returns the
    department the record belongs to, or None.
    """
    from functools import wraps

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import abort
            from flask_login import current_user
            if not getattr(current_user, "is_authenticated", False):
                abort(403)
            dept_id = get_department_id(**kwargs)
            if not can_see_department(current_user, dept_id):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================ granting
def grant(user: User, role: Role, *, department_id=None, unit_id=None,
          granted_by=None) -> UserRole:
    """Give somebody another hat. Idempotent — granting twice is not an error."""
    existing = (db.session.query(UserRole)
                .filter_by(user_id=user.id, role_id=role.id,
                           department_id=department_id, unit_id=unit_id).first())
    if existing is not None:
        existing.active = True
        return existing
    row = UserRole(org_id=user.org_id, user_id=user.id, role_id=role.id,
                   department_id=department_id, unit_id=unit_id,
                   granted_by_id=getattr(granted_by, "id", None))
    db.session.add(row)
    db.session.flush()
    return row


def revoke(user_role: UserRole) -> None:
    """Take a hat back. Kept as an inactive row, not deleted.

    An account that quietly loses a power with no trace is exactly the kind of
    thing an investigation needs to be able to reconstruct months later.
    """
    user_role.active = False


def set_permissions(role: Role, keys) -> dict:
    """Replace a role's tick-list. Returns what changed, for the audit trail."""
    wanted = {k for k in keys if k in PERMISSION_KEYS}
    current = role.permission_keys
    for g in list(role.grants):
        g.allowed = g.permission in wanted
    have = {g.permission for g in role.grants}
    for key in sorted(wanted - have):
        db.session.add(RolePermission(role_id=role.id, permission=key, allowed=True))
    return {"added": sorted(wanted - current), "removed": sorted(current - wanted)}
