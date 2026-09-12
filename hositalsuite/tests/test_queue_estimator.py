"""F-013 / F-014 regression: the wait estimate is PERSONAL and the math is
Little's Law applied once.

What the audit found (both confirmed in code before this rewrite):
  F-013 — every journey estimate hardcoded position=0, so every patient in a
          stage saw an identical "12 min" regardless of their real place.
  F-014 — staff count entered the formula twice (a load factor CONTAINING
          staff × a separate staff factor), so low staffing was punished
          twice; the staff factor floored at 0.5, so above ~4 staff nothing
          responded.

These tests pin the corrected behavior: staff monotonicity without a cliff,
position monotonicity, fast-track-within-tier only, and real per-patient
position for both intake and visit journeys.
"""
from datetime import timedelta

from app import queue_estimator as qe
from app.models import JourneySegment, ReceptionIntake, db, now_naive

from conftest import login


# ------------------------------------------------------------------ F-014 math
def _controlled_estimate(monkeypatch, org_id, *, avg_sec, staff, position,
                         fast=False, hour=10):
    monkeypatch.setattr(qe, "get_historical_avg", lambda *a, **k: avg_sec)
    monkeypatch.setattr(qe, "count_staff_available", lambda *a, **k: staff)
    return qe.estimate_wait_minutes(org_id, "WAIT_DOCTOR", position=position,
                                    is_fast_track=fast)


def test_more_staff_means_shorter_wait_with_no_cliff(app, monkeypatch):
    """The old formula stopped responding above 4 staff (floor at 0.5).

    Throughput is now linear in staff, so every extra doctor shortens the
    wait — 8 staff must be measurably faster than 4.
    """
    with app.app_context():
        w1 = _controlled_estimate(monkeypatch, 1, avg_sec=900, staff=1, position=3)
        w2 = _controlled_estimate(monkeypatch, 1, avg_sec=900, staff=2, position=3)
        w4 = _controlled_estimate(monkeypatch, 1, avg_sec=900, staff=4, position=3)
        w8 = _controlled_estimate(monkeypatch, 1, avg_sec=900, staff=8, position=3)
        assert w1 > w2 > w4 > w8 > 0
        # no cliff: 8 staff ≈ half of 4 staff (linear), not equal to it
        assert w8 <= w4 // 2 + 1


def test_low_staffing_is_penalized_once_not_twice(app, monkeypatch):
    """Going from 2 staff to 1 at most doubles the wait (one application of
    throughput). The old dual factor could nearly quadruple it."""
    with app.app_context():
        w2 = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=2, position=3)
        w1 = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=1, position=3)
        assert w1 <= w2 * 2 + 1, (w1, w2)


def test_wait_grows_with_real_position_and_is_capped(app, monkeypatch):
    with app.app_context():
        w0 = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=1, position=0)
        w3 = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=1, position=3)
        big = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=1, position=10_000)
        assert w3 > w0 >= 1
        assert big == 180, "estimate must clamp at 3 hours"


def test_fast_track_shortens_within_tier_only(app, monkeypatch):
    """Fast Track halves the effective position — it never jumps the whole
    queue in the estimate (cross-tier priority is F-012 and is refused
    structurally, see tests/test_fasttrack_tier_guard.py)."""
    with app.app_context():
        normal = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=1, position=6)
        fast = _controlled_estimate(monkeypatch, 1, avg_sec=600, staff=1, position=6, fast=True)
        assert 0 < fast < normal
        # halved effective position → roughly half the wait (± rounding/time factor)
        assert fast <= normal // 2 + 1


# ------------------------------------------------------------------ F-013 position
def _intake(org, patient_id, stage, created_at, n):
    """Minimal valid ReceptionIntake row (ref unique, names required)."""
    return ReceptionIntake(
        org_id=org, patient_id=patient_id, stage=stage, ref=f"EST/{n:05d}",
        surname=f"Test{n}", first_name="Pat", sex="F", age_years=30,
        payer_type="SELF", created_at=created_at)


def _visit(org, patient_id, n, started_at, status="TRIAGED"):
    from app.models import Patient, PatientVisit
    p = Patient(org_id=org, hospital_number=f"ESTV/{n:05d}",
                surname=f"Vtest{n}", first_name="Pat", sex="F",
                age_years=30, payer_type="SELF", category="GENERAL")
    db.session.add(p)
    db.session.flush()
    v = PatientVisit(org_id=org, patient_id=p.id, visit_no=f"V{n:05d}",
                     status=status, started_at=started_at)
    db.session.add(v)
    db.session.flush()
    return v


def test_position_in_stage_counts_only_people_ahead(app, seeded):
    """Two intakes at RECEPTION: the later one must see the earlier one ahead;
    the earlier one sees nobody."""
    with app.app_context():
        org = seeded["org"]
        early = _intake(org, 1, "RECEPTION", now_naive() - timedelta(minutes=20), 1)
        late = _intake(org, 2, "RECEPTION", now_naive(), 2)
        db.session.add_all([early, late])
        db.session.commit()
        assert qe.position_in_stage(org, "RECEPTION", intake=early) == 0
        assert qe.position_in_stage(org, "RECEPTION", intake=late) >= 1


def test_position_in_stage_falls_back_to_open_count_when_patient_unknown(app, seeded):
    with app.app_context():
        org = seeded["org"]
        db.session.add(_intake(org, 9, "BILLING", now_naive(), 3))
        db.session.commit()
        # no intake/visit given for this patient — they join behind everyone
        assert qe.position_in_stage(org, "BILLING") == qe.count_open_segments(org, "BILLING")


def test_journey_estimates_differ_by_real_position(app, seeded):
    """THE F-013 scenario: two patients in the same stage must not see the
    same remaining-wait number — the one further back waits longer."""
    with app.app_context():
        org = seeded["org"]
        now = now_naive()
        early = _intake(org, 11, "RECEPTION", now - timedelta(minutes=30), 4)
        late = _intake(org, 12, "RECEPTION", now, 5)
        db.session.add_all([early, late])
        db.session.commit()
        early_est = qe.estimate_intake_journey(org, early)["total"]
        late_est = qe.estimate_intake_journey(org, late)["total"]
        assert late_est > early_est, (
            f"both patients saw the same wait ({early_est}) — position=0 bug is back")


def test_visit_journey_uses_open_segment_position(app, seeded):
    """Two open WAIT_DOCTOR segments: the one who entered later waits longer."""
    with app.app_context():
        org = seeded["org"]
        now = now_naive()
        v1 = _visit(org, 21, 1, now - timedelta(minutes=40))
        v2 = _visit(org, 22, 2, now - timedelta(minutes=5))
        db.session.add(JourneySegment(org_id=org, visit_id=v1.id,
                                      stage="WAIT_DOCTOR", entered_at=now - timedelta(minutes=40)))
        db.session.add(JourneySegment(org_id=org, visit_id=v2.id,
                                      stage="WAIT_DOCTOR", entered_at=now - timedelta(minutes=5)))
        db.session.commit()
        first = qe.estimate_remaining_journey(org, v1)["total"]
        second = qe.estimate_remaining_journey(org, v2)["total"]
        assert second > first, (
            f"WAIT_DOCTOR patients both saw {first} — the position=0 bug is back")
