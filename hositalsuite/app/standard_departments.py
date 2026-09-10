"""Standard department structure for a general hospital.

Modelled on how a Nigerian state/general hospital is actually organised (and
consistent with WHO service-delivery groupings): clinical services, diagnostics,
nursing, and the administrative functions that keep them running.

Used two ways:
  * fresh installs get the whole structure seeded automatically
  * existing hospitals can add any missing ones from Admin -> Structure,
    without touching departments they already created

Each entry: (department, [(section, [units...]), ...])
"""
from __future__ import annotations

STANDARD_DEPARTMENTS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    # Premium lane — a real department patients can pick, not a hidden flag.
    ("Fast Track", [
        ("Executive Lounge", ["Gold Lane", "Fast Track Desk"]),
    ]),
    # ---------------------------------------------------------------- clinical
    ("Accident & Emergency", [
        ("Emergency Room", ["Triage", "Resuscitation Room", "Observation Bay"]),
        ("Ambulance Services", ["Dispatch"]),
    ]),
    ("Internal Medicine", [
        ("Outpatient Clinic", ["General OPD", "Specialist Clinic"]),
        ("Medical Wards", ["Male Medical Ward", "Female Medical Ward"]),
    ]),
    ("Surgery", [
        ("Theatre Complex", ["Theatre 1", "Theatre 2", "Recovery Room"]),
        ("Surgical Wards", ["Male Surgical Ward", "Female Surgical Ward"]),
    ]),
    ("Obstetrics & Gynaecology", [
        ("Antenatal Care (ANC)", ["ANC Clinic", "ANC Ward"]),
        ("Labour & Delivery", ["Labour Room", "Postnatal Ward"]),
        ("Gynaecology", ["Gynae Clinic", "Gynae Ward"]),
    ]),
    ("Paediatrics", [
        ("Children's Outpatient", ["CHOP Clinic"]),
        ("Paediatric Ward", ["Children's Ward"]),
        ("Neonatal Unit", ["NICU", "SCBU"]),
    ]),
    ("Family Medicine / General Outpatient", [
        ("GOPD", ["Consulting Rooms", "Treatment Room", "Dressing Room"]),
    ]),
    ("Dental Services", [("Dental Clinic", ["Dental Surgery", "Oral Hygiene"])]),
    ("Ophthalmology (Eye Clinic)", [("Eye Clinic", ["Refraction", "Eye Theatre"])]),
    ("ENT (Ear, Nose & Throat)", [("ENT Clinic", ["Audiology"])]),
    ("Orthopaedics", [("Orthopaedic Clinic", ["Plaster Room", "Orthopaedic Ward"])]),
    ("Public Health", [
        ("Immunisation", ["Immunisation Post"]),
        ("Health Education", ["Community Outreach"]),
    ]),
    ("Physiotherapy", [("Physiotherapy Unit", ["Rehabilitation Gym"])]),
    ("Mental Health", [("Psychiatry Clinic", ["Counselling Room"])]),

    # ---------------------------------------------------------------- nursing
    ("Nursing Services", [
        ("Ward Nursing", ["Day Shift", "Night Shift"]),
        ("Infection Prevention & Control", ["IPC Unit"]),
    ]),

    # ---------------------------------------------------------------- diagnostics
    ("Laboratory", [
        ("Main Laboratory", ["Haematology", "Chemical Pathology", "Microbiology",
                             "Blood Bank"]),
        ("Sample Collection", ["Phlebotomy"]),
    ]),
    ("Radiology / Imaging", [
        ("Imaging", ["X-Ray", "Ultrasound Scan", "ECG"]),
    ]),
    ("Pharmacy", [
        ("Dispensary", ["Main Pharmacy", "Emergency Pharmacy"]),
        ("Drug Store", ["Central Store"]),
    ]),
    ("Nutrition & Dietetics", [("Dietetics Unit", ["Diet Counselling"])]),

    # ---------------------------------------------------------------- support / admin
    ("Health Information Management (HIMS)", [
        ("Medical Records", ["Records Office", "Filing Room"]),
    ]),
    ("Administration & Human Resources", [
        ("Admin Office", ["Registry", "Human Resources"]),
    ]),
    ("Finance & Accounts", [
        ("Accounts", ["Revenue / Billing", "Cash Office"]),
    ]),
    ("Internal Audit", [("Audit Unit", ["Audit Office"])]),
    ("Planning, Research & Statistics", [("Planning Unit", ["Statistics"])]),
    ("Public Affairs", [("Public Relations", ["Enquiries Desk"])]),
    ("ICT", [("ICT Unit", ["Systems Support"])]),
    ("Engineering & Maintenance", [
        ("Maintenance", ["Electrical", "Plumbing", "Biomedical Equipment"]),
    ]),
    ("Environmental Health", [
        ("Sanitation", ["Cleaning Services", "Waste Management"]),
    ]),
    ("Catering Services", [("Kitchen", ["Patient Meals"])]),
    ("Security", [("Security Post", ["Main Gate", "Patrol"])]),
    ("Laundry", [("Laundry Unit", ["Linen Store"])]),
    ("Mortuary", [("Mortuary Unit", ["Body Storage"])]),
]


def department_names() -> list[str]:
    return [d for d, _ in STANDARD_DEPARTMENTS]


def install(org_id: int, *, only_missing: bool = True) -> dict:
    """Create the standard departments (and their sections/units) for an org.

    Idempotent: existing departments are left completely alone, so this is safe
    to run on a hospital that has already customised its structure.
    Returns {"departments": n, "sections": n, "units": n} actually created.
    """
    from .models import Department, Section, Unit, db

    made = {"departments": 0, "sections": 0, "units": 0}
    existing = {d.name.strip().lower()
                for d in db.session.query(Department).filter_by(org_id=org_id).all()}

    for dept_name, sections in STANDARD_DEPARTMENTS:
        if only_missing and dept_name.strip().lower() in existing:
            continue
        dept = Department(org_id=org_id, name=dept_name)
        db.session.add(dept)
        db.session.flush()
        made["departments"] += 1
        for sec_name, units in sections:
            sec = Section(org_id=org_id, department_id=dept.id, name=sec_name)
            db.session.add(sec)
            db.session.flush()
            made["sections"] += 1
            for unit_name in units:
                db.session.add(Unit(org_id=org_id, department_id=dept.id,
                                    section_id=sec.id, name=unit_name))
                made["units"] += 1
    return made
