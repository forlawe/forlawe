"""Service points — clinics, consulting rooms, destinations — all admin editable.

WHY ROWS NOT TUPLES
-------------------
Clinics, rooms and destinations were hard-coded Python tuples. Adding
\"Dental Clinic\" needed a developer and a deploy — the same trap Role
Management was built to escape. They are now rows in service_clinic,
consulting_room, service_destination, seeded from original tuples so nothing
that worked yesterday changes.

CLINIC DETERMINES ITS OWN LOAD
------------------------------
A dentist sees 8 relevant destinations, not 25. Empty shortlist means show
EVERYTHING, not nothing — empty-means-nothing would have given every doctor
an empty dropdown and stopped patients moving.

BUG FOUND IN PREVIOUS BUILD: doctor's room page 500'd because template still
unpacked destinations as (code, label) after they became dicts. Caught by tests.

EDGE CASE FROM REVIEW: shortlist non-empty but all items suspended.
If suspended items filtered silently, clinic could end up with dropdown showing
everything — exact failure mode feature was built to prevent. Fixed: after
filtering suspended, if original shortlist was non-empty and filtered result
is empty, show warning, not everything.

UPGRADE 2026-08-21
------------------
- Clinics: OPD, SOPD, MOPD, EMERGENCY + Dental, ANC, O&G, Ophthalmology/Eye,
  Pediatrics, Physiotherapy, etc.
- Destinations: HIMS, MOPD, SOPD, OPD, O&G, MSSD/Welfare, Pediatrics,
  Physiotherapy, Radiology/Imaging, Dental, Nutrition & Dietetics,
  Ophthalmology, Maternity, Casualty, Dressing Room, Theater, Male Ward,
  Female Ward, etc. Admin add/edit/suspend/delete.
- Consulting Rooms: up to 8, admin editable.
"""

from __future__ import annotations

from .models import (
    ClinicDestination,
    ConsultingRoom,
    ServiceClinic,
    ServiceDestination,
    db,
    now_naive,
)

# ------------------------------------------------------------------ defaults
# Seeded clinics — original 4 + new ones founder requested
DEFAULT_CLINICS = (
    ("OPD", "General Outpatient", "General OPD"),
    ("SOPD", "Surgical Outpatient", "SOPD"),
    ("MOPD", "Medical Outpatient", "MOPD"),
    ("EMERGENCY", "Accident & Emergency", "A&E / Casualty"),
    ("DENTAL", "Dental Clinic", "Dental / Oral Health"),
    ("ANC", "ANC Clinic", "Antenatal Care"),
    ("O&G", "O&G Clinic", "Obstetrics & Gynaecology"),
    ("EYE", "Ophthalmology / Eye Clinic", "Eye Clinic"),
    ("PAEDS", "Pediatrics", "Children's Clinic"),
    ("PHYSIO", "Physiotherapy", "Physiotherapy / Rehab"),
    ("MSSD", "MSSD / Welfare", "Medical Social Services"),
)

# 8 consulting rooms — founder asked up to 8
DEFAULT_ROOMS = (
    ("ROOM1", "Room 1"),
    ("ROOM2", "Room 2"),
    ("ROOM3", "Room 3"),
    ("ROOM4", "Room 4"),
    ("ROOM5", "Room 5"),
    ("ROOM6", "Room 6"),
    ("ROOM7", "Room 7"),
    ("ROOM8", "Room 8"),
    ("ER", "Emergency Room"),
)

# Destinations where doctors can send patients after consultation
# Original 6 + many more founder listed
DEFAULT_DESTINATIONS = (
    ("LABORATORY", "Laboratory", "the Laboratory", "tests"),
    ("PHARMACY", "Pharmacy / Dispensary", "the Pharmacy", "collect medicines"),
    ("BILLING", "Billing Point", "the Billing Point", "settle the bill"),
    ("MEGALEX", "Megalex / Paying Point", "the Megalex Paying Point", "make payment"),
    ("LAHSMA", "LAHSMA", "the LAHSMA desk", "insurance clearance"),
    ("EMERGENCY", "Accident & Emergency", "Accident and Emergency", "urgent"),
    ("HIMS", "HIMS", "HIMS", "folder / records"),
    ("OPD", "OPD", "OPD", "General Outpatient"),
    ("SOPD", "SOPD", "SOPD", "Surgical Outpatient"),
    ("MOPD", "MOPD", "MOPD", "Medical Outpatient"),
    ("O&G", "O&G", "O&G Clinic", "Obstetrics & Gynaecology"),
    ("MSSD", "MSSD / Welfare", "MSSD / Welfare", "social services"),
    ("PAEDS", "Pediatrics", "Pediatrics", "children"),
    ("PHYSIO", "Physiotherapy", "Physiotherapy", "rehab"),
    ("RADIOLOGY", "Radiology / Imaging", "Radiology", "X-ray, scan"),
    ("DENTAL", "Dental Clinic", "Dental Clinic", "dental"),
    ("NUTRITION", "Nutrition & Dietetics", "Nutrition & Dietetics", "diet"),
    ("EYE", "Ophthalmology", "Ophthalmology", "eye"),
    ("MATERNITY", "Maternity", "Maternity", "maternity"),
    ("CASUALTY", "Casualty", "Casualty", "casualty"),
    ("DRESSING", "Dressing Room", "Dressing Room", "dressing"),
    ("THEATER", "Theater", "Theater", "theater / surgery"),
    ("MALE_WARD", "Male Ward", "Male Ward", "male ward"),
    ("FEMALE_WARD", "Female Ward", "Female Ward", "female ward"),
)

# Clinic-specific shortlists — dentist sees 8 relevant, not 25
# Empty shortlist = show everything (not configured yet)
CLINIC_SHORTLISTS = {
    "DENTAL": ["LABORATORY", "PHARMACY", "RADIOLOGY", "BILLING", "MEGALEX", "THEATER", "MALE_WARD", "FEMALE_WARD"],
    "EYE": ["LABORATORY", "PHARMACY", "RADIOLOGY", "BILLING", "MEGALEX", "THEATER", "OPD"],
    "ANC": ["LABORATORY", "PHARMACY", "RADIOLOGY", "O&G", "MATERNITY", "BILLING", "MEGALEX", "MSSD"],
    "O&G": ["LABORATORY", "PHARMACY", "RADIOLOGY", "MATERNITY", "THEATER", "BILLING", "MEGALEX", "MSSD", "FEMALE_WARD"],
    "PAEDS": ["LABORATORY", "PHARMACY", "RADIOLOGY", "NUTRITION", "BILLING", "MEGALEX", "MALE_WARD", "FEMALE_WARD"],
}


# ------------------------------------------------------------------ seeding
def ensure_defaults(org_id: int) -> dict:
    """Seed clinics, rooms, destinations if tables empty. Idempotent."""
    created = {"clinics": 0, "rooms": 0, "destinations": 0, "shortlists": 0}

    # Clinics
    existing_clinics = {c.code: c for c in db.session.query(ServiceClinic).filter_by(org_id=org_id).all()}
    for idx, (code, name, desc) in enumerate(DEFAULT_CLINICS):
        if code not in existing_clinics:
            c = ServiceClinic(
                org_id=org_id,
                code=code,
                name=name,
                description=desc,
                active=True,
                sort_order=idx,
            )
            db.session.add(c)
            db.session.flush()
            existing_clinics[code] = c
            created["clinics"] += 1

    # Rooms
    existing_rooms = {r.code: r for r in db.session.query(ConsultingRoom).filter_by(org_id=org_id).all()}
    for idx, (code, name) in enumerate(DEFAULT_ROOMS):
        if code not in existing_rooms:
            r = ConsultingRoom(org_id=org_id, code=code, name=name, active=True, sort_order=idx)
            db.session.add(r)
            db.session.flush()
            created["rooms"] += 1

    # Destinations
    existing_dests = {d.code: d for d in db.session.query(ServiceDestination).filter_by(org_id=org_id).all()}
    for idx, (code, name, place, desc) in enumerate(DEFAULT_DESTINATIONS):
        if code not in existing_dests:
            d = ServiceDestination(
                org_id=org_id,
                code=code,
                name=name,
                place=place,
                description=desc,
                active=True,
                sort_order=idx,
            )
            db.session.add(d)
            db.session.flush()
            existing_dests[code] = d
            created["destinations"] += 1

    # Shortlists per clinic
    for clinic_code, dest_codes in CLINIC_SHORTLISTS.items():
        clinic = existing_clinics.get(clinic_code)
        if not clinic:
            continue
        # Check if shortlist already set for this clinic
        existing_links = db.session.query(ClinicDestination).filter_by(clinic_id=clinic.id).count()
        if existing_links > 0:
            continue
        for dest_code in dest_codes:
            dest = existing_dests.get(dest_code)
            if dest:
                link = ClinicDestination(org_id=org_id, clinic_id=clinic.id, destination_id=dest.id)
                db.session.add(link)
                created["shortlists"] += 1

    if any(created.values()):
        db.session.commit()
    return created


# ------------------------------------------------------------------ reading
def active_clinics(org_id: int) -> list[ServiceClinic]:
    return (
        db.session.query(ServiceClinic)
        .filter_by(org_id=org_id, active=True)
        .order_by(ServiceClinic.sort_order, ServiceClinic.name)
        .all()
    )


def all_clinics(org_id: int) -> list[ServiceClinic]:
    return (
        db.session.query(ServiceClinic)
        .filter_by(org_id=org_id)
        .order_by(ServiceClinic.sort_order, ServiceClinic.name)
        .all()
    )


def active_rooms(org_id: int, clinic_id: int | None = None) -> list[ConsultingRoom]:
    q = db.session.query(ConsultingRoom).filter_by(org_id=org_id, active=True)
    if clinic_id:
        q = q.filter((ConsultingRoom.clinic_id == clinic_id) | (ConsultingRoom.clinic_id.is_(None)))
    return q.order_by(ConsultingRoom.sort_order, ConsultingRoom.name).all()


def all_rooms(org_id: int) -> list[ConsultingRoom]:
    return (
        db.session.query(ConsultingRoom)
        .filter_by(org_id=org_id)
        .order_by(ConsultingRoom.sort_order, ConsultingRoom.name)
        .all()
    )


def active_destinations(org_id: int) -> list[ServiceDestination]:
    return (
        db.session.query(ServiceDestination)
        .filter_by(org_id=org_id, active=True)
        .order_by(ServiceDestination.sort_order, ServiceDestination.name)
        .all()
    )


def all_destinations(org_id: int) -> list[ServiceDestination]:
    return (
        db.session.query(ServiceDestination)
        .filter_by(org_id=org_id)
        .order_by(ServiceDestination.sort_order, ServiceDestination.name)
        .all()
    )


def destinations_for_clinic(org_id: int, clinic_code: str | None) -> tuple[list[ServiceDestination], bool, bool]:
    """Get destinations a clinic's doctor may send patients to.

    Returns (destinations, is_shortlisted, all_suspended_warning)

    - If clinic has no shortlist (empty), show everything.
    - If shortlist exists but all suspended, return [] + warning flag (do NOT fallback to everything).
    """
    if not clinic_code:
        return active_destinations(org_id), False, False

    clinic = (
        db.session.query(ServiceClinic)
        .filter_by(org_id=org_id, code=clinic_code.upper())
        .first()
    )
    if not clinic:
        # Fallback to old constants if clinic not in DB yet
        return active_destinations(org_id), False, False

    # Get shortlist links for this clinic
    links = db.session.query(ClinicDestination).filter_by(clinic_id=clinic.id).all()
    if not links:
        # Empty shortlist = show everything (not configured yet)
        return active_destinations(org_id), False, False

    # Shortlist exists — filter to active destinations
    dest_ids = [link.destination_id for link in links]
    all_in_shortlist = (
        db.session.query(ServiceDestination)
        .filter(ServiceDestination.id.in_(dest_ids), ServiceDestination.org_id == org_id)
        .all()
    )
    active_in_shortlist = [d for d in all_in_shortlist if d.active]

    if not all_in_shortlist:
        # Shortlist points to nothing (deleted?) — treat as empty
        return active_destinations(org_id), False, False

    if not active_in_shortlist:
        # All suspended — warning, do NOT fallback to everything (reviewer edge case)
        return [], True, True

    return sorted(active_in_shortlist, key=lambda d: (d.sort_order, d.name)), True, False


# ------------------------------------------------------------------ admin helpers
def create_clinic(org_id: int, code: str, name: str, description: str = "") -> ServiceClinic:
    code = code.strip().upper()[:20]
    name = name.strip()[:120]
    if not code or not name:
        raise ValueError("Code and name required")
    existing = db.session.query(ServiceClinic).filter_by(org_id=org_id, code=code).first()
    if existing:
        raise ValueError(f"Clinic code {code} already exists")
    c = ServiceClinic(org_id=org_id, code=code, name=name, description=description[:300], active=True)
    db.session.add(c)
    db.session.flush()
    return c


def update_clinic(clinic: ServiceClinic, **fields):
    if "code" in fields:
        fields["code"] = fields["code"].strip().upper()[:20]
    if "name" in fields:
        fields["name"] = fields["name"].strip()[:120]
    for k, v in fields.items():
        if hasattr(clinic, k):
            setattr(clinic, k, v)
    clinic.updated_at = now_naive()


def suspend_clinic(clinic: ServiceClinic):
    clinic.active = False


def delete_clinic(clinic: ServiceClinic):
    # Check if used in DoctorSession or PatientVisit
    from .models import DoctorSession, PatientVisit

    used = (
        db.session.query(DoctorSession)
        .filter_by(org_id=clinic.org_id, clinic=clinic.code)
        .first()
    )
    if used:
        raise ValueError(f"Cannot delete {clinic.code} — used in doctor sessions. Suspend instead.")
    used_visit = (
        db.session.query(PatientVisit)
        .filter_by(org_id=clinic.org_id, clinic=clinic.code)
        .first()
    )
    if used_visit:
        raise ValueError(f"Cannot delete {clinic.code} — used in patient visits. Suspend instead.")
    db.session.delete(clinic)


def set_clinic_shortlist(org_id: int, clinic_id: int, dest_ids: list[int]):
    """Replace shortlist for a clinic. Empty list = show everything."""
    clinic = db.session.get(ServiceClinic, clinic_id)
    if not clinic or clinic.org_id != org_id:
        raise ValueError("Clinic not found")
    # Delete existing
    db.session.query(ClinicDestination).filter_by(clinic_id=clinic_id).delete()
    # Add new
    for dest_id in dest_ids:
        dest = db.session.get(ServiceDestination, dest_id)
        if dest and dest.org_id == org_id:
            link = ClinicDestination(org_id=org_id, clinic_id=clinic_id, destination_id=dest_id)
            db.session.add(link)
