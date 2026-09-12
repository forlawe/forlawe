"""Places a patient actually visits — not the whole hospital organogram.

The public pickers (queue, book, feedback, complaint) used to dump every
department: Laundry, Internal Audit, Store, ICT. A patient cannot join
those queues. If a list is shown at all, it is the clinical / patient
services plus Fast Track (which is a real department, first in the list).
"""
from __future__ import annotations

from .models import Department, db

FAST_TRACK_NAME = "Fast Track"

# Hide back-office / support names even if they also contain a clinical word.
_DENY = (
    "laundry",
    "internal audit",
    "audit unit",
    "store unit",
    "procurement",
    "finance",
    "accounts",
    "planning, research",
    "public affairs",
    "ict",
    "engineering",
    "maintenance",
    "environmental health",
    "catering",
    "security",
    "mortuary",
    "administration",
    "human resource",
    "health information",
    "hims",
    "nursing services",
)

# Names a patient can reasonably pick.
_ALLOW = (
    "fast track",
    "accident",
    "emergency",
    "a&e",
    "family medicine",
    "outpatient",
    "gopd",
    "internal medicine",
    "surgery",
    "theatre",
    "theater",
    "obstetric",
    "gynaec",
    "gynec",
    "antenatal",
    "labour",
    "paediat",
    "pediatr",
    "dental",
    "ophthal",
    "eye clinic",
    "ear, nose",
    "orthop",
    "physio",
    "mental health",
    "psychiatr",
    "laborat",
    "radiolog",
    "imaging",
    "pharmacy",
    "public health",
    "immunis",
    "nutrition",
    "dietetic",
    "triage",
)

_ALLOW_EXACT = frozenset({
    "ent", "eye", "lab", "opd", "anc", "a&e", "gopd", "fast track",
})


def is_fast_track_dept(dept: Department | None) -> bool:
    if dept is None:
        return False
    return (dept.name or "").strip().lower() == FAST_TRACK_NAME.lower()


def is_patient_place(name: str | None) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False
    if any(bad in n for bad in _DENY):
        return False
    if n in _ALLOW_EXACT:
        return True
    return any(ok in n for ok in _ALLOW)


def ensure_fast_track(org_id: int) -> Department:
    """Create the Fast Track department for this hospital if it is missing."""
    existing = (db.session.query(Department)
                .filter(Department.org_id == org_id,
                        Department.name.ilike(FAST_TRACK_NAME))
                .first())
    if existing:
        if not existing.active:
            existing.active = True
        return existing
    row = Department(org_id=org_id, name=FAST_TRACK_NAME, active=True)
    db.session.add(row)
    db.session.flush()
    return row

def ensure_reception(org_id: int) -> Department:
    """Create Reception department if missing — queue links only to Reception per founder."""
    existing = (db.session.query(Department)
                .filter(Department.org_id == org_id,
                        Department.name.ilike("Reception"))
                .first())
    if existing:
        if not existing.active:
            existing.active = True
        return existing
    row = Department(org_id=org_id, name="Reception", active=True)
    db.session.add(row)
    db.session.flush()
    return row


def _normalize_for_dedup(name: str) -> str:
    """Normalize for duplicate detection: Pharmacy vs Pharmacy Dept. -> pharmacy"""
    n = (name or "").strip().lower()
    # Remove common suffixes/prefixes that cause duplicates
    for suffix in (" dept.", " dept", " department", " unit", " services", " service"):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    # Special cases: keep core word
    # e.g., "pharmacy dept." -> "pharmacy", "family medicine (gopd/sopd)" -> "family medicine"
    n = n.split("(")[0].strip()
    return n

def public_departments(org_id: int, *, only_reception: bool = False) -> list[Department]:
    """Short list for patient pickers. Fast Track is always first. Deduplicated.
    
    If only_reception=True (queue), returns only Reception + Fast Track per founder:
    Link queue only to Reception and they should show as Patient on Queue with priority for today's date only.
    """
    ensure_fast_track(org_id)
    ensure_reception(org_id)
    rows = (db.session.query(Department)
            .filter_by(org_id=org_id, active=True)
            .order_by(Department.name)
            .all())
    if only_reception:
        # Queue links only to Reception + Fast Track — founder requirement
        places = [d for d in rows if d.name.strip().lower() in ("reception", "fast track")]
        # Ensure order: Fast Track first, then Reception
        gold = [d for d in places if is_fast_track_dept(d)]
        rest = [d for d in places if not is_fast_track_dept(d)]
        return gold + rest

    places = [d for d in rows if is_patient_place(d.name)]
    # Deduplicate: keep first occurrence of normalized name (e.g., Pharmacy vs Pharmacy Dept.)
    seen = {}
    deduped = []
    for d in places:
        key = _normalize_for_dedup(d.name)
        # For pharmacy, laboratory, etc, use core word
        # If key already seen, skip duplicate
        if key in seen:
            continue
        # Also check if any existing seen key is substring of new or vice versa for pharmacy case
        # e.g., "pharmacy" and "pharmacy dept" both normalize to "pharmacy" -> deduped
        # For safety, also check if key contains "pharmacy" and we already have pharmacy
        is_dup = False
        for existing_key in seen:
            if existing_key == key:
                is_dup = True
                break
            # If both contain pharmacy, treat as dup
            if "pharmacy" in existing_key and "pharmacy" in key:
                is_dup = True
                break
            if "laboratory" in existing_key and "laboratory" in key:
                is_dup = True
                break
            if "radiology" in existing_key and "radiology" in key:
                is_dup = True
                break
        if is_dup:
            continue
        seen[key] = d.id
        deduped.append(d)
    places = deduped
    gold = [d for d in places if is_fast_track_dept(d)]
    rest = [d for d in places if not is_fast_track_dept(d)]
    return gold + rest
