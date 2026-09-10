"""Role Management screens — the administrator decides who may do what.

Everything on these pages is a tick-box and a sentence in English. There is no
place to type a permission code, because the person using this screen has zero
technical background and a mistyped code that silently grants nothing is the
worst possible failure mode for a security screen.
"""
from __future__ import annotations

import re

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import roles as R
from ..audit import audit
from ..models import (PERMISSION_GROUPS, PERMISSION_KEYS, ROLE_SCOPES,
                      Department, Role, Unit, User, UserRole, db)

bp = Blueprint("rolesadmin", __name__, url_prefix="/admin/roles")


def _org():
    return current_user.org_id


def _acting_super() -> bool:
    """True when the current user holds EVERY permission (Super Admin).

    The escalation guard below only binds delegated role managers: a Super
    Administrator is the ceiling already and may do anything.
    """
    return (getattr(current_user, "role", "") == "SUPER_ADMIN"
            or getattr(current_user, "is_super", False))


def _role_or_404(rid: int) -> Role:
    r = db.session.get(Role, rid)
    if r is None or r.org_id != _org():
        abort(404)
    return r


# ------------------------------------------------------------------ list
@bp.get("")
@R.require("roles_admin")
def index():
    R.ensure_builtin_roles(_org())
    db.session.commit()
    items = (db.session.query(Role).filter_by(org_id=_org())
             .order_by(Role.builtin.desc(), Role.name).all())
    # How many people hold each role: the one written on their staff record
    # PLUS any extra hats granted here.
    counts = {}
    for r in items:
        counts[r.id] = (
            db.session.query(User).filter_by(org_id=_org(), role=r.code).count()
            + db.session.query(UserRole)
              .filter_by(org_id=_org(), role_id=r.id, active=True).count())
    return render_template("admin/roles.html", items=items, counts=counts,
                           groups=PERMISSION_GROUPS, scopes=ROLE_SCOPES)


# ------------------------------------------------------------------ create
@bp.post("/create")
@R.require("roles_admin")
def create():
    name = (request.form.get("name") or "").strip()
    scope = request.form.get("scope") or "DEPARTMENT"
    description = (request.form.get("description") or "").strip()[:300]
    if len(name) < 2:
        flash("Give the role a name, for example 'Pharmacy Technician'.", "error")
        return redirect(url_for("rolesadmin.index"))
    if scope not in dict(ROLE_SCOPES):
        scope = "DEPARTMENT"

    # The CODE is generated, never typed. A human-typed code is a typo waiting
    # to silently grant nothing at all.
    code = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:40] or "ROLE"
    base, n = code, 2
    while db.session.query(Role).filter_by(org_id=_org(), code=code).first():
        code = f"{base[:36]}_{n}"
        n += 1

    role = Role(org_id=_org(), code=code, name=name, description=description,
                scope=scope, builtin=False, active=True)
    db.session.add(role)
    db.session.flush()
    audit("ROLE_CREATED", "role", role.id,
          {"name": name, "code": code, "scope": scope})
    db.session.commit()
    flash(f"Role '{name}' created. Now tick what this role may do.", "success")
    return redirect(url_for("rolesadmin.edit", rid=role.id))


# ------------------------------------------------------------------ edit
@bp.get("/<int:rid>")
@R.require("roles_admin")
def edit(rid: int):
    role = _role_or_404(rid)
    holders = (db.session.query(User)
               .filter_by(org_id=_org(), role=role.code).order_by(User.name).all())
    extra = (db.session.query(UserRole)
             .filter_by(org_id=_org(), role_id=role.id, active=True).all())
    return render_template("admin/role_edit.html", role=role,
                           groups=PERMISSION_GROUPS, scopes=ROLE_SCOPES,
                           ticked=role.permission_keys, holders=holders,
                           extra=extra)


@bp.post("/<int:rid>")
@R.require("roles_admin")
def save(rid: int):
    role = _role_or_404(rid)
    keys = [k for k in request.form.getlist("perm") if k in PERMISSION_KEYS]

    # Privilege-escalation guard: a DELEGATED role manager (granted
    # roles_admin but not Super Admin) must never be able to hand out powers
    # they do not hold themselves — otherwise "manage the role screen"
    # quietly becomes "make myself Super Admin". Custom roles only, and only
    # within the editor's own permission set; Super Admin is the ceiling and
    # is exempt.
    if not _acting_super():
        if role.builtin:
            flash("Only a Super Administrator may change the permissions of a "
                  "built-in role. Ask them, or manage your own custom roles.",
                  "error")
            return redirect(url_for("rolesadmin.edit", rid=role.id))
        mine = R.permissions_of(current_user)
        overflow = [k for k in keys if k not in mine]
        if overflow:
            keys = [k for k in keys if k in mine]
            flash("You cannot grant powers you do not hold yourself — removed: "
                  f"{', '.join(overflow[:5])}{'…' if len(overflow) > 5 else ''}. "
                  "Ask a Super Administrator for powers beyond your own.",
                  "error")

    # THE ONE THING THIS SCREEN MUST NEVER ALLOW: the administrator untick-ing
    # their own way back in. Locking the only person who can fix a mistake out
    # of the screen that fixes it needs a database engineer to undo.
    if role.code == "SUPER_ADMIN":
        for must in ("admin", "roles_admin"):
            if must not in keys:
                keys.append(must)
                flash("The Super Administrator must keep full control — "
                      "otherwise nobody could ever undo a mistake here.", "error")

    scope = request.form.get("scope") or role.scope
    if scope in dict(ROLE_SCOPES):
        role.scope = scope
    if not role.builtin:
        role.name = (request.form.get("name") or role.name).strip()[:120]
        role.description = (request.form.get("description") or "").strip()[:300]

    changed = R.set_permissions(role, keys)
    audit("ROLE_PERMISSIONS_CHANGED", "role", role.id,
          {"role": role.name, "scope": role.scope, **changed})
    db.session.commit()

    bits = []
    if changed["added"]:
        bits.append(f"{len(changed['added'])} power(s) added")
    if changed["removed"]:
        bits.append(f"{len(changed['removed'])} power(s) removed")
    flash(f"'{role.name}' saved" + (" — " + ", ".join(bits) if bits else "") + ".",
          "success")
    return redirect(url_for("rolesadmin.edit", rid=role.id))


@bp.post("/<int:rid>/toggle")
@R.require("roles_admin")
def toggle(rid: int):
    role = _role_or_404(rid)
    if role.code in R.UNDELETABLE and role.active:
        flash("A built-in role cannot be switched off — every account holding "
              "it would lose its way in. Change what it may do instead.", "error")
        return redirect(url_for("rolesadmin.index"))
    role.active = not role.active
    audit("ROLE_TOGGLED", "role", role.id, {"active": role.active})
    db.session.commit()
    flash(f"'{role.name}' is now {'active' if role.active else 'switched off'}.",
          "success")
    return redirect(url_for("rolesadmin.index"))


# ------------------------------------------------------------------ granting
@bp.get("/assign")
@R.require("roles_admin")
def assign_form():
    R.ensure_builtin_roles(_org())
    db.session.commit()
    users = (db.session.query(User).filter_by(org_id=_org(), active=True)
             .order_by(User.name).all())
    items = (db.session.query(Role).filter_by(org_id=_org(), active=True)
             .order_by(Role.name).all())
    depts = (db.session.query(Department).filter_by(org_id=_org(), active=True)
             .order_by(Department.name).all())
    grants = (db.session.query(UserRole)
              .filter_by(org_id=_org(), active=True).all())
    return render_template("admin/role_assign.html", users=users, roles=items,
                           depts=depts, grants=grants)


@bp.post("/assign")
@R.require("roles_admin")
def assign():
    uid = request.form.get("user_id", type=int)
    rid = request.form.get("role_id", type=int)
    dept_id = request.form.get("department_id", type=int) or None
    user = db.session.get(User, uid) if uid else None
    role = db.session.get(Role, rid) if rid else None
    if not user or user.org_id != _org() or not role or role.org_id != _org():
        flash("Choose a member of staff and a role.", "error")
        return redirect(url_for("rolesadmin.assign_form"))
    if dept_id:
        d = db.session.get(Department, dept_id)
        if not d or d.org_id != _org():
            flash("Unknown department.", "error")
            return redirect(url_for("rolesadmin.assign_form"))

    # Privilege-escalation guard: never grant a hat carrying powers the
    # granter does not wear themselves (delegated role managers only).
    if not _acting_super():
        mine = R.permissions_of(current_user)
        overflow = [k for k in role.permission_keys if k not in mine]
        if overflow:
            flash(f"You cannot hand out '{role.name}' — it carries powers you "
                  "do not hold yourself. Ask a Super Administrator.", "error")
            return redirect(url_for("rolesadmin.assign_form"))

    R.grant(user, role, department_id=dept_id, granted_by=current_user)
    audit("ROLE_GRANTED", "user", user.id,
          {"role": role.name, "department_id": dept_id})
    db.session.commit()
    flash(f"{user.name} now also holds '{role.name}'. "
          f"Their powers add up — they keep everything they already had.",
          "success")
    return redirect(url_for("rolesadmin.assign_form"))


@bp.post("/assign/<int:grant_id>/remove")
@R.require("roles_admin")
def unassign(grant_id: int):
    ur = db.session.get(UserRole, grant_id)
    if ur is None or ur.org_id != _org():
        abort(404)
    R.revoke(ur)
    audit("ROLE_REVOKED", "user", ur.user_id,
          {"role": ur.role.name if ur.role else ur.role_id})
    db.session.commit()
    flash("Role taken back. The record of it having been granted is kept.",
          "success")
    return redirect(url_for("rolesadmin.assign_form"))
