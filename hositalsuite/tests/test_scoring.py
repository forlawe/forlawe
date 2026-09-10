"""Unit tests: scoring, ratings, SLA, escalation, recurring detection."""
from datetime import datetime, timedelta

from app import scoring


def test_exactly_five_criteria():
    assert len(scoring.CRITERIA) == 5
    assert set(scoring.CRITERIA.keys()) == {1, 2, 3, 4, 5}


def test_total_and_percent():
    scores = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
    assert scoring.calc_total(scores) == 15
    assert scoring.calc_percent(15) == 60.0
    assert scoring.calc_total({n: 5 for n in range(1, 6)}) == 25


def test_rating_boundaries():
    assert scoring.rating_for(25) == "EXCELLENT"
    assert scoring.rating_for(22) == "EXCELLENT"
    assert scoring.rating_for(21) == "GOOD"
    assert scoring.rating_for(18) == "GOOD"
    assert scoring.rating_for(17) == "FAIR / NEEDS IMPROVEMENT"
    assert scoring.rating_for(13) == "FAIR / NEEDS IMPROVEMENT"
    assert scoring.rating_for(12) == "POOR"
    assert scoring.rating_for(8) == "POOR"
    assert scoring.rating_for(7) == "CRITICAL"
    assert scoring.rating_for(5) == "CRITICAL"


def test_explanation_required_only_for_low_scores():
    assert scoring.explanation_required(1) is True
    assert scoring.explanation_required(2) is True
    assert scoring.explanation_required(3) is False
    assert scoring.explanation_required(4) is False
    assert scoring.explanation_required(5) is False


def test_validate_scores_rejects_out_of_range_and_missing():
    errs = scoring.validate_scores({1: 5, 2: 5, 3: 5, 4: 5, 5: 6})
    assert errs
    errs = scoring.validate_scores({1: 5, 2: 5, 3: 5, 4: 5})
    assert errs
    assert scoring.validate_scores({n: 3 for n in range(1, 6)}) == []


def test_sla_deadline_and_escalation_logic():
    t0 = datetime(2026, 8, 11, 9, 0)
    deadline = scoring.sla_deadline(t0, 24)
    assert deadline == t0 + timedelta(hours=24)
    # before deadline, unresolved -> no escalation
    assert scoring.should_escalate("NEW", False, deadline, t0 + timedelta(hours=1)) is False
    # after deadline, unresolved -> escalate
    assert scoring.should_escalate("NEW", False, deadline, t0 + timedelta(hours=25)) is True
    assert scoring.should_escalate("ACKNOWLEDGED", False, deadline, t0 + timedelta(hours=25)) is True
    # resolved/closed/already-escalated -> never
    assert scoring.should_escalate("RESOLVED", False, deadline, t0 + timedelta(hours=25)) is False
    assert scoring.should_escalate("CLOSED", False, deadline, t0 + timedelta(hours=25)) is False
    assert scoring.should_escalate("NEW", True, deadline, t0 + timedelta(hours=25)) is False


def test_recurring_findings_detection():
    history = [{"criterion_scores": {1: 4, 2: 4, 3: 2, 4: 4, 5: 4}} for _ in range(6)]
    history += [{"criterion_scores": {n: 4 for n in range(1, 6)}} for _ in range(4)]
    msgs = scoring.recurring_findings(history, window=10, threshold=3)
    assert len(msgs) == 1
    # Criterion 3 is Cleanliness / Environment under the criteria the founder
    # set on 18 Aug 2026 (CRITERIA_VERSION 2).
    assert "Cleanliness / Environment" in msgs[0]
    assert "6 of the last 10" in msgs[0]


def test_recurring_findings_needs_minimum_history():
    history = [{"criterion_scores": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}}] * 2
    assert scoring.recurring_findings(history, window=10, threshold=3) == []


def test_alert_conditions():
    alerts = scoring.alert_conditions({1: 1, 2: 4, 3: 4, 4: 4, 5: 4})
    assert any("Critical" in a for a in alerts)
    alerts = scoring.alert_conditions({1: 2, 2: 2, 3: 5, 4: 5, 5: 5}, multiple_two_threshold=2)
    assert any("scored 2" in a for a in alerts)
    assert scoring.alert_conditions({n: 5 for n in range(1, 6)}) == []


def test_trend():
    assert scoring.trend(20, 18) == "improving"
    assert scoring.trend(15, 18) == "declining"
    assert scoring.trend(18, 18) == "stable"
    assert scoring.trend(18, None) == "baseline"
