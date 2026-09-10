"""HOD escalation — raise a complaint to a higher authority BEFORE it times out.

THE GAP THIS FILLS
------------------
Until now, escalation only ever happened TO an HOD, automatically, when the
clock ran out. That is a punishment, not a process. It also told the MD/CEO
about a problem at the exact moment it was too late to help.

A real HOD knows within twenty minutes whether a complaint is theirs to fix.
"The generator is down and I have no budget" is not something a Head of
Theatre can resolve — it needs the MD, and it needs him now, not in four hours
when the SLA expires and the system reports the HOD as having failed.

So an HOD may now escalate DELIBERATELY, upward, with a reason, at any time
before the deadline. Three things follow from that:

1. It is **early**, so the higher authority can still act.
2. It carries a **reason in the HOD's own words**, so the MD is not reading a
   status code.
3. It is **recorded as a choice**, distinct from an automatic timeout, so the
   HOD who spotted it early is not scored as the HOD who let it lapse. Getting
   that distinction wrong would teach every HOD to sit on problems.

WHO YOU MAY ESCALATE TO
-----------------------
Only UPWARD, and only to somebody who actually exists in this hospital. An
escalation to an empty chair is a complaint that quietly dies, which is worse
than no escalation at all — so the list is built from real, active accounts.
"""
from __future__ import annotations

import logging

from . import announce, notifications
from .audit import audit
from .models import (Complaint, ComplaintStatusHistory, Department,
                     Organization, User, db, now_naive)

log = logging.getLogger(__name__)

# Who counts as "higher authority", in order of seniority. An HOD escalates up
# this ladder; nobody escalates sideways or down.
AUTHORITY_LADDER = ("MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR",
                    "ADMIN_MANAGER")


def authorities(org_id: int) -> list[User]:
    """Real, active people an HOD may escalate to, most senior first."""
    rows = (db.session.query(User)
            .filter(User.org_id == org_id, User.active.is_(True),
                    User.role.in_(AUTHORITY_LADDER)).all())
    order = {code: i for i, code in enumerate(AUTHORITY_LADDER)}
    rows.sort(key=lambda u: (order.get(u.role, 99), u.name or ""))
    return rows


def hours_left(complaint: Complaint) -> float:
    """How long before this complaint breaches. Negative means already late."""
    return (complaint.sla_deadline_at - now_naive()).total_seconds() / 3600


def may_escalate(user, complaint: Complaint) -> bool:
    """May THIS person escalate THIS complaint?

    An HOD may escalate a complaint in their own department. Management may
    escalate anything. Nobody escalates something already closed — there is
    nothing left to escalate, and allowing it would let a resolved complaint
    be re-opened by the back door with no resolution note.
    """
    from .roles import can_see_department, has_permission
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if complaint.status in ("RESOLVED", "CLOSED"):
        return False
    if not has_permission(user, "escalate"):
        return False
    return can_see_department(user, complaint.department_id)


def escalate(complaint: Complaint, *, by_user, to_user: User, reason: str) -> dict:
    """Raise it up the ladder, on purpose, with a reason. Returns a summary.

    The SLA deadline is deliberately NOT reset. An escalated complaint is still
    the same complaint with the same promise to the same patient; letting an
    escalation buy four more hours would turn "escalate" into the button
    everybody presses to make the red light go away.
    """
    reason = (reason or "").strip()
    old_status = complaint.status
    now = now_naive()

    complaint.escalated = True
    complaint.status = "ESCALATED"
    complaint.escalated_at = now

    org = db.session.get(Organization, complaint.org_id)
    dept = db.session.get(Department, complaint.department_id)
    dept_name = dept.name if dept else "the hospital"
    left = hours_left(complaint)
    in_time = left > 0

    note = (f"Escalated by {by_user.name} to {to_user.name} "
            f"({'before' if in_time else 'after'} the deadline). {reason}")[:1000]
    pmsg = notifications.patient_update_text("escalated", org.name if org else "",
                                             complaint.ref)
    db.session.add(ComplaintStatusHistory(
        complaint_id=complaint.id, from_status=old_status, to_status="ESCALATED",
        note=note, user_id=by_user.id, patient_message=pmsg))

    # Recorded as a DELIBERATE act, not a timeout. The distinction matters:
    # an HOD who spots a problem early must never be scored as one who let it
    # lapse, or every HOD learns to sit on problems.
    # user= and org_id= are passed EXPLICITLY. audit() otherwise falls back to
    # flask_login's current_user, which is anonymous when this runs from the
    # scheduler or a background job — and an audit row with no org_id is
    # invisible to the hospital that needs it.
    audit("COMPLAINT_ESCALATED_BY_HOD", "complaint", complaint.id,
          {"by": by_user.name, "to": to_user.name, "to_role": to_user.role,
           "reason": reason[:300], "hours_left": round(left, 1),
           "before_deadline": in_time, "manual": True},
          user=by_user, org_id=complaint.org_id)

    ctx = {"ref": complaint.ref, "dept": dept_name,
           "hospital": org.name if org else "", "reason": reason[:200]}
    try:
        # WhatsApp-first then SMS fallback
        notifications.notify(complaint.org_id, to_user, "complaint_escalated", ctx,
                             channels=["inapp", "email", "whatsapp"],
                             entity_type="complaint", entity_id=complaint.id)
        # Also alert MD/CEO on escalation — feature 6
        for md in db.session.query(User).filter(User.org_id==complaint.org_id, User.role=="MD_CEO", User.active.is_(True)).all():
            if md.id != to_user.id:
                notifications.notify(complaint.org_id, md, "complaint_escalated", ctx,
                                     channels=["inapp", "whatsapp"],
                                     entity_type="complaint", entity_id=complaint.id)
    except Exception:                                      # noqa: BLE001
        log.exception("could not notify the escalation target")

    # Voice, because a message nobody opens is a message nobody acts on — feature 6 with WhatsApp voice.
    # Keep complaint_for_you for backward compat (tests) + add escalated_voice for premium.
    try:
        announce.to_user(complaint.org_id, to_user, "complaint_for_you",
                         place=dept_name,
                         detail=(f"{by_user.name} has escalated {complaint.ref} to you with "
                                 f"{round(left)} hours left. Reason: {reason[:150]}"
                                 if in_time else
                                 f"{by_user.name} has escalated {complaint.ref} to you and it "
                                 f"is already past its deadline. Reason: {reason[:150]}"),
                         entity_type="complaint", entity_id=complaint.id)
        announce.to_user(complaint.org_id, to_user, "complaint_escalated_voice",
                         place=dept_name,
                         detail=(f"{by_user.name} escalated {complaint.ref} to you with "
                                 f"{round(left)} hours left. Reason: {reason[:150]}"
                                 if in_time else
                                 f"{by_user.name} escalated {complaint.ref} to you and it "
                                 f"is already past its deadline. Reason: {reason[:150]}"),
                         entity_type="complaint", entity_id=complaint.id)
        # Voice also to MD/CEO
        for md in db.session.query(User).filter(User.org_id==complaint.org_id, User.role=="MD_CEO", User.active.is_(True)).all():
            if md.id != to_user.id:
                announce.to_user(complaint.org_id, md, "complaint_escalated_voice",
                                 place=dept_name,
                                 detail=f"Complaint {complaint.ref} for {dept_name} escalated by {by_user.name} to {to_user.name}. {reason[:150]}",
                                 entity_type="complaint", entity_id=complaint.id)
    except Exception:                                      # noqa: BLE001
        log.exception("could not announce the escalation")

    return {"to": to_user.name, "in_time": in_time, "hours_left": round(left, 1)}


# ------------------------------------------------------------------ early warning
def warn_hods_running_out(org_id: int, warn_hours: float = 4.0) -> int:
    """Speak to an HOD BEFORE their complaint times out, not after + WhatsApp voice reminder (feature 6).

    The automatic escalation already existed and already fired at the deadline.
    By then the HOD has lost the chance to act, and the first they hear of it
    is the MD asking why. This says it out loud while there is still time to
    either answer it or escalate it on purpose, plus WhatsApp voice alert.
    """
    from . import services
    said = 0
    now = now_naive()
    rows = (db.session.query(Complaint)
            .filter(Complaint.org_id == org_id,
                    Complaint.status.in_(("NEW", "ACKNOWLEDGED", "IN_PROGRESS")),
                    Complaint.escalated.is_(False)).all())
    for c in rows:
        left = (c.sla_deadline_at - now).total_seconds() / 3600
        if not (0 < left <= warn_hours):
            continue
        hod = services.route_hod(c.department)
        if hod is None:
            continue
        try:
            org_obj = db.session.get(Organization, org_id)
            org_name = org_obj.name if org_obj else ""
            # Keep old key for backward compat + new voice key for feature 6
            announce.to_user(org_id, hod, "complaint_running_out",
                             place=c.department.name if c.department else "",
                             detail=f"{round(left)} hour(s) left on {c.ref}. Answer it, or escalate it to higher authority.",
                             entity_type="complaint", entity_id=c.id)
            announce.to_user(org_id, hod, "complaint_sla_warning_voice",
                             place=c.department.name if c.department else "",
                             detail=f"{c.ref} — {round(left)} hour(s) left. Answer it, or escalate it to higher authority. Voice reminder.",
                             entity_type="complaint", entity_id=c.id)
            # WhatsApp voice alert — WhatsApp first, Twilio fallback
            notifications.notify(org_id, hod, "complaint_sla_warning",
                                 {"ref": c.ref, "dept": c.department.name if c.department else "",
                                  "hours": round(left,1), "hospital": org_name},
                                 channels=["whatsapp","inapp"],
                                 entity_type="complaint", entity_id=c.id)
            said += 1
        except Exception:                                  # noqa: BLE001
            log.exception("could not warn an HOD about a complaint running out")
    return said
