"""The places the Admin Manager walks round and scores, in the founder's order.

WHY THIS FILE EXISTS
--------------------
The Admin Manager does not inspect the org chart. He inspects PLACES: the
laundry, the male ward, the theatre, the paying point. Some of those are whole
departments, some are sections and some are units, and a few (Driver,
Fast-Track Centre) do not appear in the standard department tree at all.

Forcing that walk-round into the department/section/unit hierarchy is what made
the old page a three-dropdown puzzle. This is the flat list, exactly as the
founder wrote it, and each entry is matched to a real Department row when one
exists so reports and corrective actions still join up properly.

Each entry: (key, display name, [names to match against the department tree])
"""
from __future__ import annotations

INSPECTION_AREAS: list[tuple[str, str, list[str]]] = [
    ("engineering",   "Engineering",                  ["Engineering", "Maintenance", "Works"]),
    ("laboratory",    "Laboratory",                   ["Laboratory", "Medical Laboratory"]),
    ("female_ward",   "Female Ward",                  ["Female Ward", "Female Medical Ward"]),
    ("laundry",       "Laundry",                      ["Laundry", "Linen"]),
    ("male_ward",     "Male Ward",                    ["Male Ward", "Male Medical Ward"]),
    ("paed_neonatal", "Paediatric / Neonatal",        ["Paediatrics", "Neonatal Unit", "Paediatric Ward"]),
    ("pharmacy",      "Pharmacy / Dispensary",        ["Pharmacy", "Dispensary"]),
    ("surgical_ward", "Surgical Ward",                ["Surgical Wards", "Surgery", "Male Surgical Ward"]),
    ("icu_hdu",       "ICU / HDU",                    ["ICU", "HDU", "Intensive Care"]),
    ("theatre",       "Theatre",                      ["Theatre Complex", "Theatre", "Surgery"]),
    ("maternity",     "Maternity / Labour Ward",      ["Labour & Delivery", "Labour Room", "Obstetrics & Gynaecology"]),
    ("kitchen",       "Kitchen / Canteen",            ["Kitchen", "Canteen", "Nutrition & Dietetics"]),
    ("child_welfare", "Child Welfare",                ["Child Welfare", "Immunisation", "Public Health"]),
    ("billing",       "Billing Point",                ["Billing", "Finance & Accounts", "Revenue"]),
    ("eye",           "Ophthalmology / Eye Service",  ["Ophthalmology (Eye Clinic)", "Eye Clinic", "Ophthalmology"]),
    ("hims",          "HIMS",                         ["HIMS", "Health Information Management", "Medical Records"]),
    ("dental",        "Dental Services",              ["Dental Services", "Dental Clinic"]),
    ("megalex",       "Megalex / Paying Point",       ["Megalex", "Paying Point", "Cash Office", "Revenue"]),
    ("triage_recept", "Triage / Reception",           ["Triage", "Reception", "Front Desk"]),
    ("a_and_e",       "Accident & Emergency",         ["Accident & Emergency", "Emergency Room"]),
    ("transport",     "Transport",                    ["Transport", "Ambulance Services"]),
    ("driver",        "Driver",                       ["Driver", "Drivers", "Transport"]),
    ("fast_track",    "Fast-Track Centre",            ["Fast-Track Centre", "Fast Track", "GOPD"]),
    ("isolation",     "Isolation Ward",               ["Isolation Ward", "Isolation"]),
]

AREA_KEYS = tuple(k for k, _, _ in INSPECTION_AREAS)
AREA_LABELS = {k: label for k, label, _ in INSPECTION_AREAS}


def match_department(area_key: str, departments) -> object | None:
    """Best-effort link from a walk-round area to a real Department row.

    Matching is deliberately forgiving (case-insensitive, substring both ways)
    because hospitals name things slightly differently. A None result is fine:
    the area is still inspectable, it simply is not tied to a department, and
    the page says so rather than hiding the card.
    """
    aliases = None
    for key, _, names in INSPECTION_AREAS:
        if key == area_key:
            aliases = names
            break
    if not aliases:
        return None
    lowered = [(d, (d.name or "").strip().lower()) for d in departments]
    for alias in aliases:                      # exact name first
        a = alias.strip().lower()
        for dept, name in lowered:
            if name == a:
                return dept
    for alias in aliases:                      # then a contains-either match
        a = alias.strip().lower()
        for dept, name in lowered:
            if a and (a in name or name in a):
                return dept
    return None
