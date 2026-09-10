"""Pure business logic: scoring, ratings, SLA, recurring-issue detection.

No framework dependencies so it can be unit tested directly.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

# ----------------------------------------------------------- THE FIVE CRITERIA
# Exactly five primary evaluation criteria — do not add a sixth.
# The Admin Manager inspects PLACES (a ward, the laundry, the theatre), so the
# criteria are the five things that make a place work. Version 2 was set by the
# founder on 18 Aug 2026. Version 1 is kept below so inspections recorded under
# the old wording still read correctly in old reports - an inspection is a
# signed record and its criteria must never silently change meaning.
CRITERIA_VERSION = 2

CRITERIA: Dict[int, dict] = {
    1: {
        "code": "staff",
        "title": "Staff / Personnel",
        "items": ["Staff on duty as rostered", "Punctuality", "Conduct and courtesy",
                  "Responsiveness to patients", "Adequate numbers for the workload",
                  "Handover done properly"],
    },
    2: {
        "code": "equipment",
        "title": "Equipment / Tools & Consumables",
        "items": ["Required equipment present", "Everything working", "Consumables in stock",
                  "Furniture sound", "Faulty items reported", "Nothing expired"],
    },
    3: {
        "code": "cleanliness",
        "title": "Cleanliness / Environment",
        "items": ["General cleanliness", "Toilets", "Handwashing points", "Waste disposal",
                  "Bed and clinical-area hygiene", "Infection prevention", "Tidiness of surroundings"],
    },
    4: {
        "code": "power",
        "title": "Power & Engineering Service",
        "items": ["Mains power", "Generator / inverter backup", "Lighting", "Water supply",
                  "Air conditioning and ventilation", "Plumbing", "Outstanding repairs"],
    },
    5: {
        "code": "safety",
        "title": "Safety, Security & Record-Keeping",
        "items": ["Patient safety", "Staff safety", "Security of the area", "Fire safety",
                  "Emergency preparedness and access", "Registers and records up to date",
                  "Previous corrective actions closed out"],
    },
}

# Version 1 - the wording used before 18 Aug 2026. Read-only history.
LEGACY_CRITERIA_V1: Dict[int, dict] = {
    1: {"code": "staff", "title": "Staff & Service Delivery"},
    2: {"code": "cleanliness", "title": "Cleanliness & Infection Prevention"},
    3: {"code": "equipment", "title": "Equipment, Facilities & Supplies"},
    4: {"code": "records", "title": "Records, Compliance & Accountability"},
    5: {"code": "safety", "title": "Safety, Security & Overall Condition"},
}


def criteria_for(version: int | None) -> Dict[int, dict]:
    """The criteria wording that applied when an inspection was recorded."""
    if version is not None and int(version) <= 1:
        return LEGACY_CRITERIA_V1
    return CRITERIA


CRITERIA_COUNT = 5
MAX_SCORE = CRITERIA_COUNT * 5          # 25

SCORE_LABELS = {
    5: "Excellent — Fully compliant",
    4: "Good — Minor issues requiring attention",
    3: "Fair — Improvement required",
    2: "Poor — Significant deficiency",
    1: "Critical — Immediate intervention required",
}


def validate_scores(scores: Dict[int, int]) -> List[str]:
    """Return a list of validation errors (empty = OK)."""
    errors: List[str] = []
    for no in range(1, CRITERIA_COUNT + 1):
        v = scores.get(no)
        if v is None:
            errors.append(f"Criterion {no} ({CRITERIA[no]['title']}) has no score.")
        elif not (1 <= int(v) <= 5):
            errors.append(f"Criterion {no} score must be between 1 and 5.")
    return errors


def explanation_required(score: int) -> bool:
    """Business rule: score 1 or 2 MUST have an explanation."""
    return int(score) <= 2


def calc_total(scores: Dict[int, int]) -> int:
    return sum(int(scores[n]) for n in range(1, CRITERIA_COUNT + 1))


def calc_percent(total: int) -> float:
    return round(total / MAX_SCORE * 100.0, 1)


def rating_for(total: int) -> str:
    if total >= 22:
        return "EXCELLENT"
    if total >= 18:
        return "GOOD"
    if total >= 13:
        return "FAIR / NEEDS IMPROVEMENT"
    if total >= 8:
        return "POOR"
    return "CRITICAL"


RATING_COLORS = {
    "EXCELLENT": "#1a7f37",
    "GOOD": "#4d9e3f",
    "FAIR / NEEDS IMPROVEMENT": "#b58900",
    "POOR": "#d97706",
    "CRITICAL": "#c0262c",
}


def flagged_criteria(scores: Dict[int, int]) -> List[int]:
    return [n for n in range(1, CRITERIA_COUNT + 1) if int(scores[n]) <= 2]


def critical_count(scores: Dict[int, int]) -> int:
    return sum(1 for n in scores if int(scores[n]) == 1)


def poor_count(scores: Dict[int, int]) -> int:
    return sum(1 for n in scores if int(scores[n]) == 2)


def evaluate(scores: Dict[int, int]) -> dict:
    """Full evaluation of a five-criterion scorecard."""
    total = calc_total(scores)
    return {
        "total": total,
        "percent": calc_percent(total),
        "rating": rating_for(total),
        "flagged": flagged_criteria(scores),
        "critical_count": critical_count(scores),
        "poor_count": poor_count(scores),
    }


def trend(current_total: int, previous_total: Optional[int]) -> str:
    if previous_total is None:
        return "baseline"
    if current_total > previous_total:
        return "improving"
    if current_total < previous_total:
        return "declining"
    return "stable"


# ----------------------------------------------------------- SLA / escalation
def sla_deadline(submitted_at: datetime, sla_hours: int) -> datetime:
    return submitted_at + timedelta(hours=sla_hours)


def should_escalate(status: str, escalated: bool, deadline: datetime, now: datetime) -> bool:
    """Escalate when SLA expired and complaint not resolved/closed/already escalated."""
    if escalated or status in ("RESOLVED", "CLOSED"):
        return False
    return now > deadline


# ----------------------------------------------------------- recurring issues
def recurring_findings(history: Iterable[dict], window: int = 10, threshold: int = 3) -> List[str]:
    """history: newest-first list of dicts {criterion_scores: {1..5: int}}.

    Returns human-readable management-attention messages, e.g.
    'Equipment, Facilities & Supplies has scored 1–2 in 6 of the last 10 inspections.'
    """
    recent = list(history)[:window]
    if len(recent) < 3:
        return []
    messages = []
    for no in range(1, CRITERIA_COUNT + 1):
        bad = sum(1 for h in recent if int(h.get("criterion_scores", {}).get(no, 5)) <= 2)
        if bad >= threshold:
            title = CRITERIA[no]["title"]
            messages.append(f"{title} has scored 1\u20132 in {bad} of the last {len(recent)} inspections.")
    return messages


def alert_conditions(scores: Dict[int, int], multiple_two_threshold: int = 2) -> List[str]:
    """Executive alert triggers for a single inspection."""
    alerts = []
    if critical_count(scores) >= 1:
        alerts.append("Score 1 (Critical) recorded — immediate intervention required.")
    if poor_count(scores) >= multiple_two_threshold:
        alerts.append(f"{poor_count(scores)} criteria scored 2 (Poor) in a single inspection.")
    total = calc_total(scores)
    if rating_for(total) == "CRITICAL":
        alerts.append("Overall inspection rating is CRITICAL.")
    return alerts
