"""F-012: the clinical-tier ordering rule — written down AND code-enforced.

Fast Track is a convenience WITHIN a triage tier. It must never jump ACROSS
tiers. This system is deliberately not an EMR (no vitals, no acuity scores),
so the one clinical tier it records is the EMERGENCY clinic/destination —
the A&E path. The rule every clinical ordering must implement is therefore:

    1. EMERGENCY tier first        (clinical priority always wins)
    2. then Fast Track             (paid priority WITHIN the tier)
    3. then time                   (oldest first)

Applied at: the triage bench (who is triaged next), doctor_queue (who is
seen next), the onward queues (lab/pharmacy/EMERGENCY routing), and the TV
board (which must display the same order the staff act on).

Deliberately NOT applied at administrative desks (reception, cash, LAHSMA,
per-department queue tickets, future appointment lists): there Fast Track
competes only within the same tier, which is the product working as sold.

Pinned by tests/test_fasttrack_tier_guard.py. Do not weaken. If triage one
day records real acuity tiers, extend emergency_tier_expr to a CASE over
them and keep every ordering calling THIS module.
"""
from sqlalchemy import case, func


def emergency_tier_expr(column):
    """1 = this row belongs to the EMERGENCY clinical tier, else 0.

    Tolerant to case and stray spaces — a clinic saved as " emergency "
    is still the emergency department (same reasoning as the doctor-room
    clinic match)."""
    return case(
        (func.upper(func.trim(func.coalesce(column, ""))) == "EMERGENCY", 1),
        else_=0,
    )


def clinical_order(tier_expr, fast_col, time_expr):
    """The only legal clinical ordering, as an order_by tuple.

    `time_expr` is passed pre-wrapped (e.g. Visit.triaged_at.asc().nullsfirst())
    because nullability differs per site; tier and fast-track directions are
    fixed here so no call site can accidentally invert them.
    """
    return (tier_expr.desc(), fast_col.desc(), time_expr)
