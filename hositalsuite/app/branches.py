"""Hospital → Branch → Department.

A hospital can have more than one site (main building + annex). Each staff
member and each today's visit can belong to a site, so the annex queue does
not mix with the main one. Hospital-wide jobs (Super Admin, MD) see every
site. Everyone else sees their own.

Existing hospitals get one branch called Main on first boot. Nothing that
worked yesterday stops working — branch_id is optional, and a missing
branch is treated as Main.
"""
from __future__ import annotations

from flask_login import current_user

from .models import Branch, Organization, User, db


HOSPITAL_WIDE = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE",
                 "HEAD_ADMIN_HR", "ADMIN_MANAGER")


def ensure_main_branch(org_id: int) -> Branch:
    row = (db.session.query(Branch)
           .filter_by(org_id=org_id, is_main=True).first())
    if row:
        return row
    any_row = db.session.query(Branch).filter_by(org_id=org_id).first()
    if any_row:
        any_row.is_main = True
        return any_row
    org = db.session.get(Organization, org_id)
    row = Branch(org_id=org_id, code="MAIN", name="Main",
                 address=getattr(org, "address", None) if org else None,
                 phone=getattr(org, "phone", None) if org else None,
                 is_main=True, active=True)
    db.session.add(row)
    db.session.flush()
    return row


def ensure_all_orgs() -> None:
    for org in db.session.query(Organization).all():
        ensure_main_branch(org.id)
    db.session.commit()


def list_active(org_id: int) -> list[Branch]:
    return (db.session.query(Branch)
            .filter_by(org_id=org_id, active=True)
            .order_by(Branch.is_main.desc(), Branch.name).all())


def get_in_org(branch_id: int | None, org_id: int) -> Branch | None:
    if not branch_id:
        return None
    b = db.session.get(Branch, branch_id)
    if not b or b.org_id != org_id:
        return None
    return b


def current_branch_id() -> int | None:
    try:
        if current_user.is_authenticated:
            return getattr(current_user, "branch_id", None)
    except Exception:
        return None
    return None


def sees_all_branches(user=None) -> bool:
    u = user if user is not None else current_user
    try:
        if not getattr(u, "is_authenticated", False):
            return False
    except Exception:
        return False
    return (getattr(u, "role", "") or "") in HOSPITAL_WIDE


def apply_branch_filter(query, column, user=None):
    """Limit a query to the signed-in person's site, unless they see all."""
    u = user if user is not None else current_user
    if sees_all_branches(u):
        return query
    bid = getattr(u, "branch_id", None)
    if not bid:
        return query
    return query.filter(db.or_(column == bid, column.is_(None)))


def stamp_branch(obj, user=None) -> None:
    """Put the clerk's site on a new folder / visit / intake."""
    u = user if user is not None else current_user
    bid = getattr(u, "branch_id", None) if u is not None else None
    if bid and getattr(obj, "branch_id", "missing") != "missing" and not obj.branch_id:
        obj.branch_id = bid
