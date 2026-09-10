"""Reception — the first desk in the patient flow.

THE WALK, IN THE FOUNDER'S OWN WORDS
------------------------------------
    Reception (take details, special needs, insurance)
      -> Billing Unit (bill for folder + blood sugar test)
      -> Megalex / Pay-Point (pay)
      -> HIMS (open the folder)
      -> Triage (blood sugar test, then a ready doctor's consulting room)

This module owns the first four steps. HIMS already knows how to open a folder,
so the handover at step four REUSES `app.hims.create_patient` rather than
duplicating folder logic — one place decides what a valid folder is.

NOT A MEDICAL RECORD
--------------------
Nothing here records a symptom, an observation or a result. "Blood sugar test"
is a BILLING LINE and a Triage instruction, not a reading: this module never
stores a value for it. The test that guards the folder against EMR creep applies
here just as strongly.
"""
from __future__ import annotations

from datetime import date

from . import announce
from .models import (ASSISTANCE_CODES, INTAKE_STAGE_CODES, MARITAL_STATUSES,
                     PATIENT_LANGS, PAYER_CODES, ReceptionIntake, db,
                     new_code, now_naive)
from .security import clean_phone, valid_phone

LANG_CODES = tuple(c for c, _ in PATIENT_LANGS)

# Insurance routes that are meaningless without a policy number. Billing cannot
# claim against "LAHSMA, number unknown", so Reception must capture it.
SCHEME_REQUIRED = ("LAHSMA", "NHIS", "HMO")


# ------------------------------------------------------------------ validation
def clean_form(form) -> tuple[dict, list[str]]:
    """Turn a submitted Reception form into clean values + plain-English errors."""
    v: dict = {}
    errors: list[str] = []

    v["surname"] = (form.get("surname") or "").strip()[:80]
    v["first_name"] = (form.get("first_name") or "").strip()[:80]
    v["other_names"] = (form.get("other_names") or "").strip()[:80]
    if not v["surname"]:
        errors.append("Surname is required.")
    if not v["first_name"]:
        errors.append("First name is required.")

    sex = (form.get("sex") or "").strip().upper()[:1]
    v["sex"] = sex if sex in ("F", "M") else None

    # Age is REQUIRED here, even though it feels like a detail.
    #
    # HIMS cannot open a folder without it, and Triage needs it to place a
    # child in the right clinic and to offer an elderly patient a seat. When
    # Reception treated it as optional, the receptionist could walk a patient
    # all the way through Billing and the Paying Point, and only be blocked at
    # the folder — after the patient had already paid. Asking at the front
    # door, where the patient is standing in front of you, is the kind thing.
    raw_age = (form.get("age_years") or "").strip()
    if raw_age:
        try:
            age = int(raw_age)
            if not (0 <= age <= 120):
                errors.append("Age must be between 0 and 120.")
            else:
                v["age_years"] = age
        except ValueError:
            errors.append("Age must be a number.")
    else:
        v["age_years"] = None

    v["occupation"] = (form.get("occupation") or "").strip()[:80]
    v["address"] = (form.get("address") or "").strip()[:300]

    # --- the rest of the hospital's paper admission form.
    # A real date of birth is BETTER than a stated age, so accept it when the
    # patient knows it — but never invent one, and never demand it.
    raw_dob = (form.get("date_of_birth") or "").strip()
    v["date_of_birth"] = None
    if raw_dob:
        from datetime import date as _date
        try:
            dob = _date.fromisoformat(raw_dob)
            if dob > _date.today():
                errors.append("The date of birth is in the future.")
            elif (_date.today().year - dob.year) > 130:
                errors.append("That date of birth would make the patient "
                              "over 130 years old.")
            else:
                v["date_of_birth"] = dob
                # A known birthday beats a guessed age, so derive the age.
                age = _date.today().year - dob.year - (
                    (_date.today().month, _date.today().day)
                    < (dob.month, dob.day))
                v["age_years"] = age
        except ValueError:
            errors.append("The date of birth is not a valid date.")

    # ONE of the two is required. HIMS cannot open a folder without an age,
    # and Triage needs it to place a child or an elderly patient correctly —
    # but a patient who knows their birthday should not be asked twice.
    if not v.get("age_years") and not v.get("date_of_birth"):
        errors.append("Enter the date of birth, or the age if they do not "
                      "know their birthday. HIMS cannot open a folder "
                      "without it.")

    marital = (form.get("marital_status") or "").strip()[:16]
    v["marital_status"] = marital if marital in MARITAL_STATUSES else None
    # Religion, tribe and ethnic group are FREE TEXT on purpose. They are on
    # the paper form for dietary needs, burial rites and finding a real
    # interpreter — a hospital must never turn somebody away because their
    # faith or language is not on a dropdown.
    v["religion"] = (form.get("religion") or "").strip()[:40]
    v["state_of_origin"] = (form.get("state_of_origin") or "").strip()[:60]
    v["town"] = (form.get("town") or "").strip()[:80]
    v["tribe"] = (form.get("tribe") or "").strip()[:60]
    v["ethnic_group"] = (form.get("ethnic_group") or "").strip()[:60]

    phone = clean_phone(form.get("phone") or "")
    if phone and not valid_phone(phone):
        errors.append("The patient's phone number does not look like a Nigerian number.")
    v["phone"] = phone or None

    # Next of kin: all three parts, because a name with no number helps nobody
    # in an emergency and a number with no relationship tells you nothing.
    v["nok_name"] = (form.get("nok_name") or "").strip()[:120]
    v["nok_relationship"] = (form.get("nok_relationship") or "").strip()[:40]
    nok_phone = clean_phone(form.get("nok_phone") or "")
    if nok_phone and not valid_phone(nok_phone):
        errors.append("The next of kin phone number does not look like a Nigerian number.")
    v["nok_phone"] = nok_phone or None
    if not v["nok_name"]:
        errors.append("Next of kin name is required — somebody must be reachable in an emergency.")
    if not v["nok_phone"]:
        errors.append("Next of kin phone number is required.")
    if not v["nok_relationship"]:
        errors.append("Next of kin relationship to the patient is required.")

    payer = (form.get("payer_type") or "SELF").strip().upper()
    v["payer_type"] = payer if payer in PAYER_CODES else "SELF"
    v["payer_number"] = (form.get("payer_number") or "").strip()[:60]
    v["payer_name"] = (form.get("payer_name") or "").strip()[:120]
    if v["payer_type"] in SCHEME_REQUIRED and not v["payer_number"]:
        errors.append(
            f"A {v['payer_type']} number is required — Billing cannot claim without it.")

    lang = (form.get("preferred_lang") or "en").strip()
    v["preferred_lang"] = lang if lang in LANG_CODES else "en"
    picked = form.getlist("assistance") if hasattr(form, "getlist") else []
    assistance_str = ",".join(a for a in picked if a in ASSISTANCE_CODES)[:200]
    v["assistance"] = assistance_str
    # G1 FIX: separate explicit consent for disability/assistance data (NDPA)
    assistance_consent = form.get("assistance_consent")
    if assistance_str and not assistance_consent:
        errors.append("Assistance needs (wheelchair, hearing, etc.) are sensitive — please tick the separate consent box for disability assistance data.")
    v["assistance_consent_at"] = now_naive() if assistance_consent else None
    v["care_note"] = (form.get("care_note") or "").strip()[:200]

    v["needs_blood_sugar"] = bool(form.get("needs_blood_sugar"))

    # --- Fast-track: elderly / pregnant / child / wheelchair — premium patient care
    # Auto-detect from age + assistance + care_note, plus manual override tick
    is_fast = bool(form.get("is_fast_track"))
    fast_reason = (form.get("fast_track_reason") or "").strip().upper()[:40]

    # Auto-detect if not manually ticked
    if not is_fast:
        age_val = v.get("age_years")
        assistance_str = v.get("assistance") or ""
        care_lower = (v.get("care_note") or "").lower()
        if age_val is not None:
            if age_val >= 60:
                is_fast = True
                fast_reason = fast_reason or "ELDERLY"
            elif age_val <= 5:
                is_fast = True
                fast_reason = fast_reason or "CHILD"
        if "WHEELCHAIR" in assistance_str:
            is_fast = True
            fast_reason = fast_reason or "WHEELCHAIR"
        if "PREGNANT" in assistance_str or "pregnant" in care_lower or "antenatal" in care_lower:
            is_fast = True
            fast_reason = fast_reason or "PREGNANT"
        if "ELDERLY" in assistance_str and not fast_reason:
            fast_reason = "ELDERLY"

    # If manual tick but no reason, default to GENERAL priority
    if is_fast and not fast_reason:
        fast_reason = "PRIORITY"

    v["is_fast_track"] = bool(is_fast)
    v["fast_track_reason"] = fast_reason if is_fast else None
    return v, errors


# ------------------------------------------------------------------ create
def next_ref(org_id: int) -> str:
    """Human-sayable reception reference: RCP-20260818-0001.

    Sequential per day so the desk can read it out loud over a noisy waiting
    area, with a random tail as the collision fallback.
    """
    stem = f"RCP-{now_naive():%Y%m%d}-"
    n = (db.session.query(db.func.count(ReceptionIntake.id))
         .filter(ReceptionIntake.org_id == org_id,
                 ReceptionIntake.ref.like(f"{stem}%")).scalar() or 0)
    for bump in range(1, 500):
        candidate = f"{stem}{n + bump:04d}"
        if not db.session.query(ReceptionIntake.id).filter_by(ref=candidate).first():
            return candidate
    return f"{stem}{new_code(4)}"


def create_intake(org_id: int, values: dict, user_id: int | None = None) -> ReceptionIntake:
    row = ReceptionIntake(org_id=org_id, ref=next_ref(org_id), created_by=user_id,
                          stage="RECEPTION", **values)
    db.session.add(row)
    db.session.flush()
    from . import branches as br
    br.stamp_branch(row)
    return row


def waiting(org_id: int, stages: tuple[str, ...] | None = None) -> list[ReceptionIntake]:
    """Everyone currently mid-walk, fast-track first, then oldest first."""
    stages = stages or ("RECEPTION", "BILLING", "PAYMENT", "PAID")
    from . import branches as br
    q = (db.session.query(ReceptionIntake)
         .filter(ReceptionIntake.org_id == org_id,
                 ReceptionIntake.stage.in_(stages)))
    q = br.apply_branch_filter(q, ReceptionIntake.branch_id)
    return (q.order_by(ReceptionIntake.is_fast_track.desc(),
                       ReceptionIntake.created_at.asc())
            .limit(200).all())


def counts_by_stage(org_id: int) -> dict[str, int]:
    out = {code: 0 for code in INTAKE_STAGE_CODES}
    for row in waiting(org_id):
        out[row.stage] = out.get(row.stage, 0) + 1
    return out


def today_registered(org_id: int) -> int:
    return (db.session.query(ReceptionIntake)
            .filter(ReceptionIntake.org_id == org_id,
                    ReceptionIntake.stage == "REGISTERED",
                    db.func.date(ReceptionIntake.registered_at) == date.today())
            .count())


# ------------------------------------------------------------------ the walk
def advance(intake: ReceptionIntake, to_stage: str, *, ref: str = "") -> None:
    """Move an intake one step along the walk and stamp the time."""
    now = now_naive()
    intake.stage = to_stage
    if to_stage == "BILLING":
        # Sent to Billing. The bill itself is raised AT the billing desk, so a
        # reference given here is unusual but accepted.
        if ref:
            intake.bill_ref = ref[:40]
    elif to_stage == "PAYMENT":
        # The bill has now actually been raised — this is the moment worth
        # stamping. Previously a bill number entered by the billing clerk was
        # silently discarded, and billed_at recorded when the patient was SENT
        # to Billing rather than when the bill existed, so "how long does
        # Billing take?" measured the wrong thing.
        intake.billed_at = now
        if ref:
            intake.bill_ref = ref[:40]
    elif to_stage == "PAID":
        intake.paid_at = now
        if ref:
            intake.payment_ref = ref[:40]
    elif to_stage == "REGISTERED":
        intake.registered_at = now


# ------------------------------------------------------------------ voice
def announce_arrival(intake: ReceptionIntake) -> None:
    """Say it out loud, at zero cost — the browser does the speaking.

    Two separate calls on purpose. "A patient has arrived" is routine and goes
    to the station screen. "This patient needs a wheelchair" is URGENT and must
    not be buried inside the routine one, or it becomes noise nobody acts on.
    """
    spoken = announce.speech_name(intake.full_name)
    announce.to_station(intake.org_id, "reception_arrival", patient=spoken,
                        place="reception")
    if intake.care_flags:
        announce.to_station(intake.org_id, "assistance_needed", patient=spoken,
                            place="the reception desk",
                            detail="; ".join(intake.care_flags))


def announce_stage(intake: ReceptionIntake) -> None:
    """Call the patient onward to the next desk, by name."""
    spoken = announce.speech_name(intake.full_name)
    if intake.stage == "BILLING":
        announce.to_station(intake.org_id, "go_to_billing", patient=spoken,
                            place="the Billing Unit")
    elif intake.stage == "PAYMENT":
        announce.to_station(intake.org_id, "go_to_payment", patient=spoken,
                            place="the Megalex Paying Point")
    elif intake.stage == "PAID":
        # HIMS is the audience here, not the patient: there is a folder to open.
        announce.to_station(intake.org_id, "ready_for_folder", patient=spoken,
                            place="HIMS")
    elif intake.stage == "REGISTERED":
        detail = "for a blood sugar test" if intake.needs_blood_sugar else ""
        announce.to_station(intake.org_id, "go_to_triage", patient=spoken,
                            place="Triage", detail=detail)


def folder_values(intake: ReceptionIntake) -> dict:
    """Everything HIMS needs to open the folder, already collected once.

    The whole point of Reception is that the patient answers these questions
    ONE time. HIMS must not ask again.

    Every value is a STRING because this dict is fed to `hims.validate`, which
    is written for raw form input and calls .strip() on what it is given. An
    int age used to crash it with "'int' object has no attribute 'strip'".
    """
    return {
        "surname": intake.surname,
        "first_name": intake.first_name,
        "other_names": intake.other_names or "",
        "sex": intake.sex or "F",
        "age_years": str(intake.age_years) if intake.age_years is not None else "",
        "occupation": intake.occupation or "",
        "date_of_birth": intake.date_of_birth.isoformat() if intake.date_of_birth else "",
        "marital_status": intake.marital_status or "",
        "religion": intake.religion or "",
        "state_of_origin": intake.state_of_origin or "",
        "town": intake.town or "",
        "tribe": intake.tribe or "",
        "ethnic_group": intake.ethnic_group or "",
        "phone": intake.phone or "",
        "address": intake.address or "",
        "nok_name": intake.nok_name or "",
        "nok_phone": intake.nok_phone or "",
        "nok_relationship": intake.nok_relationship or "",
        "payer_type": intake.payer_type or "SELF",
        "payer_number": intake.payer_number or "",
        "payer_name": intake.payer_name or "",
        "preferred_lang": intake.preferred_lang or "en",
        "assistance": intake.assistance or "",
        "assistance_consent": "1" if intake.assistance_consent_at else "",
        "care_note": intake.care_note or "",
    }
