"""Guards against CONFIDENTLY WRONG answers to patients.

The assistant answering "can I bring a cooking pot" with the WEAPONS policy,
or "is there parking on Sunday" with the BILLING desk, is worse than saying
"I don't know" — it destroys trust and it never reaches the AI fallback,
because a wrong answer counts as an answer.

Two defects are guarded here:
  1. Question-shape triggers ("can i bring", "do you have") scored as if they
     were subject matter and outranked real topic words.
  2. There was no confidence floor at all: score >= 1 was allowed to answer.
"""
from app.chatbot import engine
from app.chatbot.seed_kb import seed_global_kb


def test_question_shape_triggers_score_nothing(app, seeded):
    """'can i bring' / 'do you have' name no subject - they must not win."""
    for shape in ("can i bring", "do you have", "is it possible to",
                  "i would like to know", "please tell me"):
        assert engine._is_generic(shape), f"{shape!r} must be treated as generic"


def test_real_subject_words_are_not_generic(app, seeded):
    for real in ("parking", "opening hours", "blood test", "pharmacy",
                 "make a complaint"):
        assert not engine._is_generic(real), f"{real!r} is real subject matter"


def test_cooking_pot_is_not_answered_with_the_weapons_policy(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        res = engine.answer("Can I bring a cooking pot and wrapper to stay overnight")
        intent = res["article"].intent if res and res["article"] else None
        assert intent != "security_weapon", (
            "A visitor asking about a cooking pot was told about WEAPONS - "
            "the 'can i bring' trigger outscored the real subject.")


def test_parking_question_is_not_answered_by_billing(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        res = engine.answer("Is there parking for visitors and is it free on Sunday")
        intent = res["article"].intent if res and res["article"] else None
        assert intent != "bill_estimate", "Parking question routed to the billing desk"


def test_a_genuine_miss_returns_none_so_we_stop(app, seeded):
    """If the book has nothing, we stop. We do not invent."""
    seed_global_kb(app)
    with app.app_context():
        assert engine.answer("Which bus from Ikorodu garage drops at your gate") is None


def test_the_everyday_questions_still_work(app, seeded):
    """The floor must not silence the questions patients actually ask."""
    expected = {
        "What are your opening hours": "hours_clinic",
        "How do I make a complaint": "complaint_start",
        "I want to book an appointment": "book_appointment",
        "Where is the pharmacy": "pharmacy",
    }
    seed_global_kb(app)
    with app.app_context():
        for q, intent in expected.items():
            res = engine.answer(q)
            assert res is not None, f"{q!r} must still be answered"
            got = res["article"].intent if res["article"] else None
            assert got == intent, f"{q!r} -> {got}, expected {intent}"


def test_emergency_is_never_silenced_by_the_confidence_floor(app, seeded):
    """A confidence floor must never swallow a life-threatening message."""
    seed_global_kb(app)
    with app.app_context():
        for q in ("chest pain and cannot breathe",
                  "severe bleeding that will not stop"):
            assert engine.answer(q) is not None, f"EMERGENCY silenced: {q!r}"
