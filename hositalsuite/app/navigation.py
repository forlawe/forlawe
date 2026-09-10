"""Who may see what. ONE definition, used by the menu AND the routes.

WHY THIS FILE EXISTS
--------------------
An HOD of Theatre signed in and saw the System Administrator's menus. The old
template had a single `if role in (SUPER_ADMIN, MD_CEO, ADMIN_MANAGER, HOD)`
block wrapped round nearly every link, so the most junior management role got
the same menu as the person who runs the hospital.

Hiding a link is presentation, not security — every route still enforces its
own `@require_role`. But the menu and the routes must agree, or staff either
see doors they cannot open (confusing) or miss doors they need (worse). This
module is the one place that decides, so the two cannot drift apart.

PRINCIPLE: LEAST PRIVILEGE, BUT NEVER IN THE WAY OF A PATIENT
-------------------------------------------------------------
A clinical HOD gets the things they actually do — see their patients, run
their room, work their department's roster. They do not get the money desks,
the hospital-wide inspection tool, or the administrator's settings.

Front-desk work (Reception, Billing, Pay Point, HIMS, LAHSMA) is granted by
DEPARTMENT, not by seniority: the HOD of HIMS runs the HIMS desk; the HOD of
Theatre does not. That is closer to how the hospital really works than any
rule based on rank.

FIX 2026-08-21: In Ijede one clerk often does Reception + Billing + Paypoint +
HIMS + LAHSMA. Splitting FRONT vs MONEY caused \"patient sent to billing is
not showing\" — a Reception HOD could not see the Billing desk. Any front match
now grants ALL front desks.
"""
from __future__ import annotations

# Departments whose HOD legitimately works a front-of-house desk. Matched
# loosely (case-insensitive, substring) because hospitals name things
# differently and a receptionist must not be locked out by a spelling.
FRONT_DESK_DEPARTMENTS = (
    "hims", "health information", "medical record", "record",
    "reception", "front desk", "admin", "administration",
)
MONEY_DEPARTMENTS = (
    "billing", "finance", "account", "revenue", "cash", "megalex",
    "lahsma", "insurance", "nhis", "hmo",
)
TRIAGE_DEPARTMENTS = (
    "triage", "accident", "emergency", "a&e", "nursing", "opd",
    "outpatient", "general outpatient",
)

# Everyone with hospital-wide sight.
MANAGEMENT = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "HEAD_ADMIN_HR")


def _has_department(user) -> bool:
    """Is this person's department actually recorded?"""
    return bool((getattr(getattr(user, "department", None), "name", "") or "").strip())


def _dept_matches(user, needles) -> bool:
    dept = getattr(getattr(user, "department", None), "name", "") or ""
    dept = dept.strip().lower()
    if not dept:
        return False
    return any(n in dept for n in needles)


def legacy_permissions_for(user) -> dict:
    """The ORIGINAL hard-coded map. Kept as the fail-closed fallback.

    Role Management (app/roles.py) now answers this question from the database
    so a hospital can change it without a developer. This function stays for
    one reason: if those tables are missing, empty or broken, the app must
    degrade to yesterday's known-good behaviour rather than to a blank menu or
    an open door. It is also the specification the built-in roles are seeded
    from, so the two can be compared in a test.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {k: False for k in (
            "inspections", "reception", "cashdesk", "hims", "lahsma", "triage",
            "consulting", "onward", "tracking", "bookings", "complaints",
            "referrals", "corrective", "roster", "reports", "admin",
            "attendance", "attendance_admin")}

    role = getattr(user, "role", "") or ""
    is_super = role == "SUPER_ADMIN"
    is_mgmt = role in MANAGEMENT
    is_am = role == "ADMIN_MANAGER"
    is_apex = role == "APEX_NURSE"
    is_hod = role == "HOD"

    # A clinical HOD sees patients; a front-desk HOD works the desks.
    # Any front match grants ALL front desks (reception, cashdesk, hims, lahsma)
    front_desk = is_hod and _dept_matches(user, FRONT_DESK_DEPARTMENTS)
    money_desk = is_hod and _dept_matches(user, MONEY_DEPARTMENTS)
    any_front = front_desk or money_desk
    triage_desk = is_hod and _dept_matches(user, TRIAGE_DEPARTMENTS)

    return {
        # Hospital-wide inspection tool: the Admin Manager's own job.
        "inspections": is_super or is_am or role == "MD_CEO",

        # Front of house — by department, not by rank.
        #
        # Management is included because the MD/CEO and DMD must be able to
        # LOOK at any desk; they are stopped from acting by the per-route
        # @require_role, which is the correct place for that distinction.
        #
        # An HOD with NO department set also gets through: in a small hospital
        # the record is often incomplete, and locking a real clerk out of the
        # desk they staff every day is a worse failure than letting a surgeon
        # see a reception list. Set the department to tighten it.
        #
        # FIX: any_front grants ALL front desks, because one clerk often does
        # Reception + Billing + Pay Point + HIMS + LAHSMA.
        "reception":   (is_super or is_am or is_mgmt
                        or (is_hod and (any_front or not _has_department(user)))),
        "cashdesk":    (is_super or is_am or is_mgmt
                        or (is_hod and (any_front or not _has_department(user)))),
        "hims":        (is_super or is_am or is_mgmt
                        or (is_hod and (any_front or not _has_department(user)))),
        "lahsma":      (is_super or is_am or is_mgmt
                        or (is_hod and (any_front or not _has_department(user)))),

        # Clinical flow. Any HOD may run their own consulting room — that is
        # the point of the room — but only triage/nursing areas run the bench.
        "triage":      is_super or is_am or is_apex or triage_desk or is_mgmt,
        "consulting":  is_super or is_hod or is_apex or is_mgmt,
        "onward":      is_super or is_am or is_apex or is_hod,

        # Measurement and reporting.
        "tracking":    is_super or is_mgmt or is_am or is_apex or is_hod,
        "bookings":    is_super or is_am or is_apex or front_desk or is_mgmt,
        "complaints":  is_super or is_am or is_hod or is_mgmt,
        "referrals":   is_super or is_am or is_mgmt,
        "corrective":  is_super or is_am or is_hod or is_mgmt,
        "roster":      True,                       # everyone checks their duty
        "reports":     is_super or role == "MD_CEO" or is_mgmt,
        # Clock-in is for every signed-in person. The board is for people
        # who already run the hospital or HR.
        "attendance":       True,
        "attendance_admin": is_super or is_mgmt or is_am,

        # The administrator's settings. Nobody else, ever.
        "admin":       is_super,
    }



# ============================================================ the live answer
# Keys the MENU asks about. Role Management owns most of them; a few are
# derived, because the menu asks slightly different questions from the
# permission list ("show the Complaints link" vs "may escalate").
MENU_KEYS = ("inspections", "reception", "cashdesk", "hims", "lahsma", "triage",
             "consulting", "onward", "tracking", "bookings", "complaints",
             "referrals", "corrective", "roster", "reports", "admin",
             "dept_desk", "dept_claim", "dept_staff", "dept_manage", "escalate",
             "roster_edit", "roles_admin", "attendance", "attendance_admin")


def permissions_for(user) -> dict:
    """What this person may see and do — read from Role Management.

    v1.7.18 STRICT RULES:
    - HOD and APEX_NURSE: LIMITED to own Department/Section/Unit Activities, Roster C/E/D/Upload, Attendance sign-in of own staff.
      System Admin upgrades via Role Management.
    - STAFF: ONLY own Department/Section/Unit Activities and Department Roster view/read only, no roster edit/delete/upload, no sign-in co-staff.
    - ADMIN_MANAGER: ONLY on-duty Admin Manager of TODAY has full ADMIN_MANAGER privileges (Roster & Day-On-Duty).
    - Falls back to legacy map if role tables broken (fail-closed).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {k: False for k in MENU_KEYS}

    from .roles import permissions_of

    granted = permissions_of(user)
    can = {k: (k in granted) for k in MENU_KEYS}

    # The administrator's key is the master key: never let a mis-tick lock the
    # only person who can fix a mis-tick out of the screen that fixes it.
    if can["admin"]:
        for k in MENU_KEYS:
            can[k] = True
        return can

    role = (getattr(user, "role", "") or "")

    # v1.7.18: ADMIN_MANAGER day-on-duty enforcement
    if role == "ADMIN_MANAGER":
        try:
            from .services import on_duty
            from .models import now_naive
            today = now_naive().date()
            duty = on_duty(user.org_id, today)
            is_on_duty = duty and duty.id == user.id
            if not is_on_duty:
                # Off-duty Admin Manager loses ADMIN_MANAGER privileges for today
                # Keeps only basic staff powers: dept_desk, roster view, attendance (self)
                for k in ("inspections", "reception", "cashdesk", "hims", "lahsma",
                          "triage", "consulting", "onward", "bookings", "complaints",
                          "referrals", "corrective", "reports", "admin", "roles_admin",
                          "roster_edit", "attendance_admin", "dept_manage", "escalate"):
                    can[k] = False
                # Still can see roster (view) and own dept desk
                can["roster"] = True
                can["attendance"] = True
                can["dept_desk"] = can.get("dept_desk", False)
        except Exception:
            pass

    # v1.7.18: HOD and APEX_NURSE limited to own Dept/Section/Unit
    if role in ("HOD", "APEX_NURSE"):
        if _has_department(user):
            is_front = (_dept_matches(user, FRONT_DESK_DEPARTMENTS)
                        or _dept_matches(user, MONEY_DEPARTMENTS))
            if not is_front:
                can["reception"] = can["hims"] = can["cashdesk"] = can["lahsma"] = False
        else:
            # No department set: fail closed to only dept_desk/roster/attendance (own dept none)
            # Prevents HOD with no dept seeing all front desks (old bug)
            can["reception"] = can["hims"] = can["cashdesk"] = can["lahsma"] = False
            can["bookings"] = False
        # Triage only if works in triage/nursing area
        can["triage"] = can["triage"] or _dept_matches(user, TRIAGE_DEPARTMENTS)
        can["bookings"] = can["bookings"] or _dept_matches(user, FRONT_DESK_DEPARTMENTS)
        # HOD/APEX_NURSE cannot have admin, reports, referrals unless explicitly granted by System Admin via extra role
        # Keep as per tick-list, but ensure scope limited via visible_department_ids
        # No hospital-wide sight unless System Admin upgrades scope to HOSPITAL
        pass

    # v1.7.18: STAFF limited to ONLY own Dept/Section/Unit Activities and Dept Roster view only
    if role == "STAFF":
        # Remove all powers except dept_desk, dept_claim, dept_staff, roster (view), attendance (self)
        allowed_staff = {"dept_desk", "dept_claim", "dept_staff", "roster", "attendance"}
        for k in list(can.keys()):
            if k not in allowed_staff:
                can[k] = False
        # Explicitly no roster_edit, no attendance_admin, no dept_manage
        can["roster_edit"] = False
        can["attendance_admin"] = False
        can["dept_manage"] = False

    return can

# ------------------------------------------------------------------ enforcement
def require_permission(key: str):
    """Route guard using the SAME permission map as the menu.

    Hiding a link is not security. An HOD of Theatre could still type
    /reception/new and reach the desk, because the routes only asked \"are you
    an HOD?\". This decorator asks the one question that matters — \"may THIS
    person use THIS desk?\" — and it is the same answer the menu gives, so the
    two can never disagree.
    """
    from functools import wraps

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import abort, redirect, request, url_for
            from flask_login import current_user
            if not getattr(current_user, "is_authenticated", False):
                return redirect(url_for("auth.login", next=request.path))
            if not permissions_for(current_user).get(key, False):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
