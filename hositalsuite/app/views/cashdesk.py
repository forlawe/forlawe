"""Billing Point and Megalex / Paying Point — the money desks.

WHY THESE EXIST SEPARATELY FROM RECEPTION
-----------------------------------------
Reception could already push a patient through Billing and the Paying Point,
which worked but was wrong in two ways:

  1. NO SEPARATION OF DUTIES. The same person who took the patient's details
     also recorded that money had been received. In a hospital collecting Lagos
     State revenue through Megalex that is a control weakness: whoever handles
     the cash should not also be the only record that the cash arrived. Each
     desk now records its own step, under its own name, in the audit log.

  2. THE CASHIER HAD NOWHERE TO LOOK. A cashier needs one screen showing who is
     queued for THEM, oldest first — not the whole hospital's reception list.

Reception keeps its buttons: a small hospital where one clerk does everything
must still work, and taking that away would break the very users we built for.
These desks are the same actions, surfaced where the cashier actually stands.

NOT AN EMR, AND NOT AN ACCOUNTING SYSTEM
----------------------------------------
This records that a bill was raised and that a payment reference was entered.
It holds no amounts, no prices and no ledger — Megalex is the revenue system
and must remain the single source of financial truth. A guard test enforces it.
"""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import reception, tracking
from ..audit import audit
from ..models import (PAYER_LABELS, ReceptionIntake, db, now_naive)
from ..navigation import require_permission
from ..security import require_role

bp = Blueprint("cashdesk", __name__)

# Cashiers and revenue staff are HODs of Finance/Billing in this hospital's
# structure. Management can see the desks without being able to work them.
DESK = ("SUPER_ADMIN", "HEAD_ADMIN_HR", "ADMIN_MANAGER", "HOD")
VIEWERS = DESK + ("MD_CEO", "DMD", "DCST")


def _get(intake_id: int) -> ReceptionIntake:
    row = db.session.get(ReceptionIntake, intake_id)
    if row is None or row.org_id != current_user.org_id:
        from flask import abort
        abort(404)
    return row


def _waiting(stage: str):
    """Patients queued for one desk, priority first, then longest wait first — premium patient care."""
    now = now_naive()
    rows = (db.session.query(ReceptionIntake)
            .filter(ReceptionIntake.org_id == current_user.org_id,
                    ReceptionIntake.stage == stage)
            .order_by(ReceptionIntake.is_fast_track.desc(),
                      ReceptionIntake.created_at.asc()).limit(200).all())
    out = []
    for r in rows:
        since = (r.billed_at if stage == "PAYMENT" else r.created_at) or r.created_at
        try:
            from .. import tracking as tracking_engine
            # Estimate journey for each intake — shows total time left, premium
            journey = tracking_engine.estimate_intake_journey(current_user.org_id, r)
        except Exception:
            journey = {"total": 0, "stages": [], "fast_track": bool(r.is_fast_track)}
        out.append({"intake": r,
                    "waited": max(0, int((now - since).total_seconds() // 60)),
                    "journey": journey})
    return out


# ================================================================ Billing
@bp.get("/billing")
@require_role(*VIEWERS)
@require_permission("cashdesk")
def billing():
    rows = _waiting("BILLING")
    return render_template(
        "cashdesk/desk.html", rows=rows,
        title="Billing Point", icon="🧾",
        blurb=("Patients sent here to collect their bill for the folder and "
               "the blood sugar test. Enter the bill number and send them on "
               "to the Paying Point."),
        action_url="/billing/{id}/done", action_label="➡ Bill raised — send to Paying Point",
        ref_field="bill_ref", ref_label="Bill number (optional)",
        payer_labels=PAYER_LABELS, empty="Nobody is waiting for a bill.")


@bp.post("/billing/<int:intake_id>/done")
@require_role(*DESK)
@require_permission("cashdesk")
def billing_done(intake_id: int):
    intake = _get(intake_id)
    if intake.stage != "BILLING":
        flash("That patient is not waiting at Billing.", "error")
        return redirect(url_for("cashdesk.billing"))

    reception.advance(intake, "PAYMENT", ref=(request.form.get("bill_ref") or ""))
    tracking.safely(tracking.enter, intake.org_id, "PAYMENT",
                    intake_id=intake.id, staff_id=current_user.id)
    reception.announce_stage(intake)
    audit("BILLING_BILL_RAISED", "reception_intake", intake.id,
          {"ref": intake.ref, "bill": intake.bill_ref})
    db.session.commit()
    flash(f"{intake.full_name} sent to the Megalex Paying Point.", "success")
    return redirect(url_for("cashdesk.billing"))


# ================================================================ Pay Point
@bp.get("/paypoint")
@require_role(*VIEWERS)
@require_permission("cashdesk")
def paypoint():
    rows = _waiting("PAYMENT")
    return render_template(
        "cashdesk/desk.html", rows=rows,
        title="Megalex / Paying Point", icon="💳",
        blurb=("Patients here are paying for the folder and the blood sugar "
               "test. Enter the Megalex receipt number so HIMS can open the "
               "folder. Amounts stay in Megalex — this only records that "
               "payment was made."),
        action_url="/paypoint/{id}/paid", action_label="✅ Payment received — send to HIMS",
        ref_field="payment_ref", ref_label="Megalex receipt number",
        payer_labels=PAYER_LABELS, empty="Nobody is waiting to pay.")


@bp.post("/paypoint/<int:intake_id>/paid")
@require_role(*DESK)
@require_permission("cashdesk")
def paypoint_paid(intake_id: int):
    intake = _get(intake_id)
    if intake.stage != "PAYMENT":
        flash("That patient is not waiting at the Paying Point.", "error")
        return redirect(url_for("cashdesk.paypoint"))

    reception.advance(intake, "PAID", ref=(request.form.get("payment_ref") or ""))
    tracking.safely(tracking.enter, intake.org_id, "HIMS",
                    intake_id=intake.id, staff_id=current_user.id)
    reception.announce_stage(intake)
    # Recorded under the CASHIER's name, not the receptionist's — that is the
    # whole point of a separate desk.
    audit("PAYPOINT_PAYMENT_RECEIVED", "reception_intake", intake.id,
          {"ref": intake.ref, "receipt": intake.payment_ref})
    db.session.commit()
    flash(f"Payment recorded for {intake.full_name}. HIMS can now open the "
          f"folder.", "success")
    return redirect(url_for("cashdesk.paypoint"))
