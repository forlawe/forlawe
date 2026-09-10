"""Assistant accuracy: follow-ups, invented facts, and being taught.

REPORTED FROM THE LIVE SITE with screenshots. The first answer was usually
right; the trouble started on the SECOND message:

  * "yes" to "shall I book you a morning slot?" came back with a phone number
    instead of the booking page
  * the cafeteria answer claimed it was "beside the main waiting hall", which
    is not true
  * "Ai please lean this ... store it in your memory permanently" produced a
    lecture about what OPD stands for
"""
from app.chatbot import engine
from app.chatbot.seed_kb import seed_global_kb
from app.models import ChatMessage, Organization, db


def _kb(app):
    seed_global_kb(app)


def _org(app):
    with app.app_context():
        org = db.session.query(Organization).first()
        if org is None:
            org = Organization(code="GHI", name="General Hospital Ijede",
                               phone="09154967034")
            db.session.add(org)
            db.session.commit()


def _ask(client, text, session=None):
    return client.post("/api/chat", json={"text": text, "session": session}).get_json()


# ================================================================ follow-ups
def test_a_bare_yes_is_recognised_as_agreement(app, seeded):
    for word in ("yes", "Yes", "yes please", "ok", "sure", "go ahead",
                 "please do", "abeg", "yeah"):
        assert engine.is_agreement(word), f"{word!r} was not read as a yes"


def test_a_real_question_is_never_mistaken_for_a_yes(app, seeded):
    """"Yes" is short. A question is not — never swallow a real question."""
    for q in ("yes but where is the pharmacy",
              "what are your opening hours",
              "can I book an appointment for my mother tomorrow"):
        assert not engine.is_agreement(q), f"{q!r} was swallowed as a yes"


def test_saying_yes_to_a_booking_offer_gives_the_booking_page(app, client, seeded):
    """THE REPORTED BUG. 'Yes' used to reach the AI, which invented a reply."""
    _kb(app)
    _org(app)
    first = _ask(client, "What are your opening hours?")
    assert first["answered"]
    second = _ask(client, "Yes", first["session"])

    reply = second["reply"].lower()
    assert second["answered"], "saying yes produced nothing at all"
    assert "book" in reply, f"'yes' did not lead to booking: {reply[:120]}"
    # It must be the hospital's own written answer, not something generated.
    assert second.get("source") is None, \
        "the follow-up went to the AI instead of the hospital's own words"


def test_saying_no_is_handled_kindly_and_stops_there(app, client, seeded):
    _kb(app)
    _org(app)
    first = _ask(client, "What are your opening hours?")
    second = _ask(client, "no thanks", first["session"])
    assert "no problem" in second["reply"].lower()


def test_yes_with_nothing_to_agree_to_asks_rather_than_guesses(app, client, seeded):
    """If we cannot tell what was agreed, ASK. Guessing is how this broke."""
    _kb(app)
    _org(app)
    d = _ask(client, "yes")
    reply = d["reply"].lower()
    assert "could you tell me" in reply or "what you'd like" in reply, \
        f"a stray 'yes' was answered with a guess: {reply[:120]}"


# ================================================================ invented facts
def test_the_cafeteria_answer_no_longer_invents_a_location(app, client, seeded):
    """It claimed to be "beside the main waiting hall". Nobody checked."""
    _kb(app)
    _org(app)
    d = _ask(client, "where is the cafeteria")
    reply = d["reply"].lower()
    assert "cafeteria" in reply
    for invented in ("beside", "opposite", "ground floor", "next to the"):
        assert invented not in reply, \
            f"the cafeteria answer still claims it is {invented!r}"
    assert "reception" in reply, "no honest alternative was offered"


def test_no_kb_answer_states_a_physical_location(app, seeded):
    """A hospital's layout is not in this app, so no answer may describe it.

    Every one of these is a guess dressed as a fact, and a patient sent to the
    wrong corridor is worse off than one told honestly that we do not know.
    """
    import glob
    import re
    banned = re.compile(
        r"(beside the|next to the|opposite the|ground floor|first floor|"
        r"second floor|upstairs|downstairs|behind the|in front of the|"
        r"near the gate|main building)", re.I)
    offenders = []
    for path in glob.glob("app/chatbot/kb_*.py"):
        for lineno, line in enumerate(open(path).read().splitlines(), 1):
            if re.search(r'\b(en|pcm|yo|ha|ig)\s*=\s*"', line) and banned.search(line):
                offenders.append(f"{path}:{lineno} claims "
                                 f"{banned.search(line).group(0)!r}")
    assert not offenders, "answers that invent a location:\n  " + \
        "\n  ".join(offenders)


def test_the_ai_guardrail_blocks_an_invented_location(app, seeded, monkeypatch):
    """Even if the model ignores its instructions, the patient must not be
    sent to a corridor that may not exist."""
    from app.chatbot import ai
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(
        ai, "_PROVIDERS",
        {"groq": lambda *a, **kw: "The pharmacy is on the ground floor, "
                                  "beside the main waiting hall."})
    with app.app_context():
        out = ai.answer("where is the pharmacy", org=None)
        assert out is not None
        assert "ground floor" not in out["text"].lower()
        assert "reception" in out["text"].lower()
        assert "guardrail" in out["provider"]


def test_the_guardrail_lets_an_honest_answer_through(app, seeded, monkeypatch):
    """The guard must not be so blunt that nothing useful gets said."""
    from app.chatbot import ai
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(
        ai, "_PROVIDERS",
        {"groq": lambda *a, **kw: "Yes, we have a pharmacy on site. Ask at "
                                  "reception and they will point you to it."})
    with app.app_context():
        out = ai.answer("do you have a pharmacy", org=None)
        assert "pharmacy on site" in out["text"]
        assert out["provider"] == "groq"


# ================================================================ being taught
def test_being_taught_is_recognised(app, seeded):
    for note in ("Ai please lean this and store it in your memory permanently",
                 "remember this: always use the booking page",
                 "that is wrong, stop saying that",
                 "from now on tell patients to book online"):
        assert engine.is_teaching(note), f"not recognised as teaching: {note!r}"


def test_ordinary_questions_are_not_mistaken_for_teaching(app, seeded):
    for q in ("what are your opening hours",
              "where is the pharmacy",
              "can I book an appointment"):
        assert not engine.is_teaching(q), f"{q!r} was treated as a correction"


def test_being_taught_gets_an_honest_answer_not_a_lecture(app, client, seeded):
    """THE REPORTED BUG: this produced an explanation of what OPD stands for.

    The assistant cannot learn from a chat message. Pretending it can is a
    promise it will silently break.
    """
    _kb(app)
    _org(app)
    d = _ask(client, "Ai please lean this. I think it's better to tell the "
                     "patient to use the booking page to book for morning OPD. "
                     "Can you always remember this and store it in your memory "
                     "permanently")
    reply = d["reply"].lower()
    assert "opd is our outpatient department" not in reply, \
        "still lecturing instead of answering the actual request"
    assert "cannot change" in reply, "it did not admit it cannot self-learn"
    assert "saved it" in reply or "review" in reply, \
        "the correction was not promised to a human"


def test_a_correction_is_recorded_for_a_human_to_action(app, client, seeded):
    """A promise to pass it on must actually be kept."""
    _kb(app)
    _org(app)
    _ask(client, "remember this: the cafeteria is near the car park")
    with app.app_context():
        notes = (db.session.query(ChatMessage)
                 .filter_by(intent="teaching_note").all())
        assert notes, "the correction was never recorded"
        assert notes[0].unanswered is True, \
            "it will not appear in the list of things needing attention"
