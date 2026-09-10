"""F-042/F-043: the named departments the audit found with no real dialogue
coverage now have full, well-formed libraries — and Mental Health ships only
after clinical tone review.

F-042: Paediatrics, Dental Services, Ophthalmology (Eye Clinic) and
ENT (Ear, Nose & Throat) were stubs (one generic intent each); the audit
called out Paediatrics especially, "one of the largest patient populations".
They now use the proven 21-department template (real exchanges, Pidgin,
CTAs) and own their domain words.

F-043: Mental Health is drafted but deliberately NOT seeded until a
clinical staff member reviews the tone — the audit's explicit condition.
"""
from __future__ import annotations

import pytest


def test_new_departments_have_full_libraries():
    from app.chatbot.kb_departments_full import DEPT_DIALOGUES
    for dept, minimum in (("Paediatrics", 12), ("Dental Services", 10),
                          ("Ophthalmology (Eye Clinic)", 10),
                          ("ENT (Ear, Nose & Throat)", 10)):
        rows = DEPT_DIALOGUES.get(dept)
        assert rows, f"{dept} missing from the department library"
        assert len(rows) >= minimum, (dept, len(rows))
        for suffix, triggers, en, pcm, cta in rows:
            assert triggers, f"{dept}/{suffix} has no triggers"
            assert len(en) > 40 and len(pcm) > 20 and cta, f"{dept}/{suffix} malformed"


def test_new_departments_own_their_domain_words():
    from app.chatbot.seed_kb import _all_kb
    owner = {}
    for e in _all_kb():
        for kw in e["kw"]:
            owner.setdefault(kw, e["intent"])
    expected = {
        "dental": "dental_services_what",
        "dentist": "dental_services_what",
        "eye": "ophthalmology_eye_clinic_what",
        "ent": "ent_ear_nose_throat_what",
        "paediatrics": "paediatrics_what",
        "children clinic": "paediatrics_what",
    }
    for word, winner in expected.items():
        assert owner.get(word) == winner, (word, owner.get(word))


def test_every_standard_department_is_answered(app, seeded):
    """The audit's own coverage check, kept as a permanent regression test."""
    from app.chatbot import engine
    from app.chatbot.seed_kb import seed_global_kb
    from app.standard_departments import department_names
    seed_global_kb(app, quiet=True)
    with app.app_context():
        gaps = [d for d in department_names()
                if not (engine.answer(f"I need help with {d}") or {}).get("article")]
    assert not gaps, f"departments with no dialogue coverage: {gaps}"


def test_answers_never_diagnose_or_prescribe():
    from app.chatbot.kb_departments_full import KB
    banned = ("you have malaria", "take paracetamol", "take ibuprofen", "i diagnose",
              "your diagnosis", "mg twice daily", "you are suffering from", "dosage of")
    for entry in KB:
        blob = (entry["en"] + " " + (entry.get("pcm") or "")).lower()
        for phrase in banned:
            assert phrase not in blob, (entry["intent"], phrase)


# ---------------------------------------------------------------- F-043 gate

def test_mental_health_not_seeded_until_clinical_review():
    """The gate: no Mental Health intent may reach the live library while the
    draft is unreviewed."""
    from app.chatbot import kb_mental_health_draft
    from app.chatbot.seed_kb import _all_kb
    if not kb_mental_health_draft._REVIEWED:
        intents = {e["intent"] for e in _all_kb()}
        assert not any(i.startswith("mental_health_") for i in intents)


def test_mental_health_draft_is_well_formed_for_review():
    """When reviewers open the draft, it must already be complete and safe —
    every row has Pidgin + CTA, the crisis row points to a human, and no
    answer diagnoses."""
    from app.chatbot import kb_mental_health_draft as mod
    assert mod.KB, "draft is empty"
    banned = ("it could be worse", "snap out of", "just pray about it", "i diagnose",
              "you are suffering from")
    crisis = [e for e in mod.KB if e["intent"] == "mental_health_crisis"]
    assert crisis and "Accident & Emergency" in crisis[0]["en"]
    for entry in mod.KB:
        assert entry.get("pcm") and len(entry["pcm"]) > 20, entry["intent"]
        assert entry.get("cta"), entry["intent"]
        blob = (entry["en"] + " " + entry["pcm"]).lower()
        for phrase in banned:
            assert phrase not in blob, (entry["intent"], phrase)
