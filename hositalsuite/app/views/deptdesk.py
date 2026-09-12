"""My Department — the one screen a member of staff actually lives on.

Shows ONLY their own department: what came in today, who is working on what
right now, and an honest line about whether the department is keeping up with
the flow. An HOD sees the same screen for the department(s) they head.
"""
from __future__ import annotations

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import announce, deptwork
from .. import roles as R
from ..audit import audit
from ..models import (WORK_KINDS, WORK_KIND_LABELS, Department, User,
                      WorkClaim, db, now_naive)

bp = Blueprint("deptdesk", __name__, url_prefix="/my-department")


def _chosen_department() -> Department | None:
    """Which department this page is showing — and may they see it?

    The id may come from the query string (an HOD who heads two places, or a
    manager looking across the hospital), so it is ALWAYS checked against what
    this person is allowed to see. A guessable ?dept=3 must never be a way
    round the whole scoping feature.
    """
    org_id = current_user.org_id
    wanted = request.args.get("dept", type=int)
    allowed = R.visible_department_ids(current_user)

    if wanted:
        d = db.session.get(Department, wanted)
        if d is None or d.org_id != org_id:
            abort(404)
        if not R.can_see_department(current_user, d.id):
            abort(403)
        return d

    if allowed is None:                     # whole-hospital sight, none chosen
        own = getattr(current_user, "department_id", None)
        if own:
            return db.session.get(Department, own)
        return (db.session.query(Department)
                .filter_by(org_id=org_id, active=True)
                .order_by(Department.name).first())
    if not allowed:
        return None
    return db.session.get(Department, allowed[0])


def _switchable() -> list[Department]:
    allowed = R.visible_department_ids(current_user)
    q = db.session.query(Department).filter_by(org_id=current_user.org_id,
                                               active=True)
    if allowed is not None:
        if not allowed:
            return []
        q = q.filter(Department.id.in_(allowed))
    return q.order_by(Department.name).all()


@bp.get("")
@R.require("dept_desk")
def desk():
    org_id = current_user.org_id
    dept = _chosen_department()
    if dept is None:
        return render_template("deptdesk/none.html", note=R.scope_note(current_user))

    flow = deptwork.flow_today(org_id, dept.id)
    effort = deptwork.staff_effort_today(org_id, dept.id)
    claims = deptwork.open_claims(org_id, dept.id)
    mine = deptwork.my_open_claims(org_id, current_user.id)

    # Group the noticeboard by task so "three people on Reception" reads as one
    # line with three names, not as three separate rows.
    grouped: dict[tuple, list] = {}
    for c in claims:
        grouped.setdefault((c.kind, c.entity_type, c.entity_id), []).append(c)
    together = [{"kind": k[0], "label": WORK_KIND_LABELS.get(k[0], k[0]),
                 "entity_type": k[1], "entity_id": k[2], "workers": v}
                for k, v in grouped.items()]
    together.sort(key=lambda t: (-len(t["workers"]), t["label"]))

    from ..models import default_work_for_dept
    is_hod = getattr(current_user, "role", "") in ("HOD", "SUPER_ADMIN", "HEAD_ADMIN_HR") or getattr(current_user, "is_super", False)
    return render_template(
        "deptdesk/desk.html", dept=dept, flow=flow, effort=effort,
        together=together, mine=mine, kinds=WORK_KINDS,
        switchable=_switchable(), note=R.scope_note(current_user),
        min_sample=deptwork.MIN_SAMPLE, now=now_naive(),
        default_work_for_dept=default_work_for_dept, is_hod=is_hod)


# ------------------------------------------------------------------ teamwork
@bp.post("/claim")
@R.require("dept_claim")
def claim():
    org_id = current_user.org_id
    kind = request.form.get("kind") or "OTHER"
    note = request.form.get("note") or ""
    dept_id = request.form.get("department_id", type=int)
    if dept_id and not R.can_see_department(current_user, dept_id):
        abort(403)

    row, others = deptwork.claim(org_id, current_user, kind,
                                 department_id=dept_id, note=note)
    audit("WORK_CLAIMED", "work_claim", row.id,
          {"kind": kind, "department_id": dept_id})
    db.session.commit()

    if others:
        names = ", ".join(o.user.name for o in others if o.user)
        flash(f"You are on '{WORK_KIND_LABELS.get(kind, kind)}'. "
              f"{names} {'is' if len(others) == 1 else 'are'} already on it — "
              f"share the work so nobody is called twice.", "success")
    else:
        flash(f"You are on '{WORK_KIND_LABELS.get(kind, kind)}'. "
              f"Anyone else who joins will see your name.", "success")
    return redirect(url_for("deptdesk.desk", dept=dept_id or None))


@bp.post("/claim/<int:cid>/done")
@R.require("dept_claim")
def done(cid: int):
    row = db.session.get(WorkClaim, cid)
    if row is None or row.org_id != current_user.org_id:
        abort(404)
    # You may step yourself off anything. Stepping SOMEBODY ELSE off needs the
    # power to run the department — otherwise one tap could wipe a colleague's
    # record of the work they did.
    if row.user_id != current_user.id and not R.has_permission(current_user, "dept_manage"):
        abort(403)
    deptwork.release(row)
    audit("WORK_RELEASED", "work_claim", row.id,
          {"minutes": row.minutes, "by_other": row.user_id != current_user.id})
    db.session.commit()
    flash("Marked as done. Your time on it has been recorded.", "success")
    return redirect(url_for("deptdesk.desk", dept=row.department_id or None))

@bp.post("/claim/<int:cid>/edit")
@R.require("dept_claim")
def edit_claim(cid: int):
    row = db.session.get(WorkClaim, cid)
    if row is None or row.org_id != current_user.org_id:
        abort(404)
    if row.user_id != current_user.id and not R.has_permission(current_user, "dept_manage"):
        abort(403)
    new_kind = request.form.get("kind") or row.kind
    new_note = (request.form.get("note") or "").strip()[:200]
    if new_kind in WORK_KIND_LABELS:
        row.kind = new_kind
    row.note = new_note
    audit("WORK_EDITED", "work_claim", row.id, {"kind": row.kind, "note": new_note})
    db.session.commit()
    flash(f"Updated work to '{WORK_KIND_LABELS.get(row.kind, row.kind)}'.", "success")
    return redirect(url_for("deptdesk.desk", dept=row.department_id or None))


@bp.post("/claim/<int:cid>/suspend")
@R.require("dept_manage")
def suspend_claim(cid: int):
    row = db.session.get(WorkClaim, cid)
    if row is None or row.org_id != current_user.org_id:
        abort(404)
    row.suspended = not row.suspended
    if row.suspended:
        from ..models import now_naive
        row.suspended_at = now_naive()
        row.suspended_by = current_user.id
        audit("WORK_SUSPENDED", "work_claim", row.id, {"by": current_user.id})
        flash(f"Suspended '{row.label}' — team will see it paused.", "info")
    else:
        row.suspended_at = None
        row.suspended_by = None
        audit("WORK_RESUMED", "work_claim", row.id, {})
        flash(f"Resumed '{row.label}'.", "success")
    db.session.commit()
    return redirect(url_for("deptdesk.desk", dept=row.department_id or None))


@bp.post("/claim/<int:cid>/delete")
@R.require("dept_manage")
def delete_claim(cid: int):
    row = db.session.get(WorkClaim, cid)
    if row is None or row.org_id != current_user.org_id:
        abort(404)
    dept_id = row.department_id
    audit("WORK_DELETED", "work_claim", row.id, {"kind": row.kind, "user": row.user_id})
    db.session.delete(row)
    db.session.commit()
    flash("Work entry deleted.", "info")
    return redirect(url_for("deptdesk.desk", dept=dept_id or None))

