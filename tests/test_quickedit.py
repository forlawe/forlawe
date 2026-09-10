"""Correcting a bad answer from inside the chat.

The founder asked for a secret one-word code. I built that, and added a second
lock, because `/api/chat` is PUBLIC and CSRF-exempt — the whole internet can
post to it. A code alone would put the hospital's answers about medicines,
fees and emergencies one lucky guess away from a stranger.

Both locks must be open: signed in as Super Admin, AND the code.
"""
from app.chatbot import engine, quickedit
from app.chatbot.seed_kb import seed_global_kb
from app.models import AuditLog, KnowledgeArticle, Organization, User, db
from tests.conftest import csrf, login

CODE = "ijede2026"


def _setup(app, seeded):
    """A hospital with a code set, a Super Admin and an HOD."""
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        admin = db.session.query(User).filter_by(
            org_id=org_id, role="SUPER_ADMIN").first()
        admin.must_change_password = False
        hod = User(org_id=org_id, username="justahod", name="Just A HOD",
                   role="HOD")
        hod.set_password("Passw0rd!x")
        hod.must_change_password = False
        db.session.add(hod)
        quickedit.set_code(org_id, CODE)
        db.session.commit()
        return admin.username


def _ask(client, text):
    return client.post("/api/chat", json={"text": text}).get_json()


def _cafeteria(org_id):
    r = engine.answer("where is the cafeteria", org_id=org_id)
    return (r or {}).get("text", "")


# ================================================================ SECURITY
def test_a_stranger_with_the_right_code_changes_nothing(app, client, seeded):
    """THE TEST THAT JUSTIFIES THE SECOND LOCK.

    Anyone on the internet can post to /api/chat. If the code were the only
    lock, guessing it would let them rewrite what a hospital tells sick people.
    """
    _setup(app, seeded)
    before = None
    with app.app_context():
        before = _cafeteria(seeded["org"])

    # Not signed in at all.
    _ask(client, f"{CODE} cafeteria :: HACKED. Go elsewhere and pay cash.")

    with app.app_context():
        assert _cafeteria(seeded["org"]) == before, \
            "an anonymous stranger rewrote a hospital answer"
        assert "HACKED" not in _cafeteria(seeded["org"])


def test_a_stranger_is_not_told_the_format_was_right(app, client, seeded):
    """A wrong guess must not confirm it was close.

    Replying "wrong code" to an outsider tells them the format works and only
    the word is missing — which is exactly the hint a guesser needs.
    """
    _setup(app, seeded)
    reply = _ask(client, f"{CODE} cafeteria :: rewritten")["reply"].lower()
    assert "code" not in reply, \
        f"the reply hinted that a code exists: {reply[:120]}"


def test_an_ordinary_member_of_staff_cannot_correct_answers(app, client, seeded):
    """Signed in, correct code — but not the Super Admin."""
    _setup(app, seeded)
    with app.app_context():
        before = _cafeteria(seeded["org"])

    login(client, "justahod")
    _ask(client, f"{CODE} cafeteria :: An HOD changed this.")

    with app.app_context():
        assert _cafeteria(seeded["org"]) == before, \
            "an HOD rewrote a hospital answer"


def test_the_super_admin_with_the_wrong_code_is_refused(app, client, seeded):
    username = _setup(app, seeded)
    with app.app_context():
        before = _cafeteria(seeded["org"])

    login(client, username)
    reply = _ask(client, "wrongword cafeteria :: nope, changed")["reply"]
    assert "not right" in reply.lower()

    with app.app_context():
        assert _cafeteria(seeded["org"]) == before


def test_the_code_is_never_stored_in_plain_text(app, seeded):
    """Anyone reading the settings table must not find the code."""
    from app import services
    _setup(app, seeded)
    with app.app_context():
        stored = services.get_setting(seeded["org"], quickedit.SETTING_KEY, "")
        assert stored, "no code was stored at all"
        assert CODE not in stored, "the code is sitting in the database in plain text"


def test_the_code_is_never_written_to_the_audit_log(app, client, seeded):
    username = _setup(app, seeded)
    login(client, username)
    _ask(client, f"{CODE} cafeteria :: Our cafeteria is open all day for meals.")
    with app.app_context():
        for row in db.session.query(AuditLog).all():
            assert CODE not in (row.detail or ""), \
                "the secret code was written into the audit trail"


# ================================================================ IT WORKS
def test_the_super_admin_can_correct_an_answer_from_the_chat(app, client, seeded):
    username = _setup(app, seeded)
    login(client, username)

    new_text = "Our cafeteria is open all day for hot meals. Ask at reception."
    reply = _ask(client, f"{CODE} cafeteria :: {new_text}")["reply"]
    assert "updated" in reply.lower()
    assert "this hospital" in reply.lower()

    with app.app_context():
        assert new_text in _cafeteria(seeded["org"]), \
            "it said Updated but the assistant still gives the old answer"


def test_correcting_one_hospital_does_not_change_the_others(app, client, seeded):
    """The safe default. A wrong edit must affect one hospital, not all."""
    username = _setup(app, seeded)
    with app.app_context():
        shared = (db.session.query(KnowledgeArticle)
                  .filter(KnowledgeArticle.org_id.is_(None),
                          KnowledgeArticle.intent == "cafeteria").first())
        original = shared.en

    login(client, username)
    _ask(client, f"{CODE} cafeteria :: Only this hospital sees this wording.")

    with app.app_context():
        shared = (db.session.query(KnowledgeArticle)
                  .filter(KnowledgeArticle.org_id.is_(None),
                          KnowledgeArticle.intent == "cafeteria").first())
        assert shared.en == original, \
            "editing one hospital changed the shared library for everybody"


def test_the_hospitals_own_answer_beats_the_shared_one(app, client, seeded):
    """THE BUG THIS CAUGHT.

    The correction is saved as the hospital's own copy and the shared original
    is deliberately left alone — but that left two copies in play, and the
    shared (wrong) one could still out-score the corrected one. The founder
    would be told "Updated", ask again, and hear the old wording.
    """
    username = _setup(app, seeded)
    login(client, username)
    _ask(client, f"{CODE} cafeteria :: CORRECTED WORDING for this hospital only.")

    with app.app_context():
        answer = _cafeteria(seeded["org"])
        assert "CORRECTED WORDING" in answer, \
            f"the shared answer is still winning: {answer[:100]}"


def test_a_global_correction_changes_the_shared_library(app, client, seeded):
    username = _setup(app, seeded)
    login(client, username)
    reply = _ask(client, f"{CODE} global hours_clinic :: "
                         f"We open 8am to 6pm Monday to Friday.")["reply"]
    assert "every hospital" in reply.lower()

    with app.app_context():
        shared = (db.session.query(KnowledgeArticle)
                  .filter(KnowledgeArticle.org_id.is_(None),
                          KnowledgeArticle.intent == "hours_clinic").first())
        assert "8am to 6pm Monday to Friday" in shared.en


def test_a_correction_is_recorded_with_the_old_wording(app, client, seeded):
    """So a bad edit can always be traced and undone."""
    username = _setup(app, seeded)
    login(client, username)
    _ask(client, f"{CODE} cafeteria :: Replaced wording for the cafeteria.")

    with app.app_context():
        rows = (db.session.query(AuditLog)
                .filter_by(action="KB_QUICK_EDIT").all())
        assert rows, "the correction was not recorded at all"
        detail = rows[0].detail or ""
        assert "cafeteria" in detail
        assert "replaced" in detail, "the previous wording was not kept"


# ================================================================ SAFETY RAILS
def test_an_unknown_answer_name_is_reported_clearly(app, client, seeded):
    username = _setup(app, seeded)
    login(client, username)
    reply = _ask(client, f"{CODE} not_a_real_answer :: some replacement text")["reply"]
    assert "could not find" in reply.lower()


def test_a_suspiciously_short_replacement_is_refused(app, client, seeded):
    """A slip of the finger must not wipe an answer to two words."""
    username = _setup(app, seeded)
    with app.app_context():
        before = _cafeteria(seeded["org"])
    login(client, username)
    reply = _ask(client, f"{CODE} cafeteria :: oops")["reply"]
    assert "too short" in reply.lower()
    with app.app_context():
        assert _cafeteria(seeded["org"]) == before


def test_an_ordinary_question_containing_a_colon_is_still_answered(app, client,
                                                                    seeded):
    """"Note: what are your hours" must not be mistaken for an edit."""
    username = _setup(app, seeded)
    login(client, username)
    reply = _ask(client, "Note: what are your opening hours")["reply"].lower()
    assert "8am" in reply or "open" in reply
    assert "updated" not in reply


def test_a_patient_typing_the_double_colon_is_answered_normally(app, client,
                                                                 seeded):
    _setup(app, seeded)
    d = _ask(client, "my problem :: I need to see a doctor about my leg")
    assert d["answered"] in (True, False)
    assert "updated" not in d["reply"].lower()


def test_nothing_happens_before_a_code_is_set(app, client, seeded):
    seed_global_kb(app)
    with app.app_context():
        u = db.session.query(User).filter_by(
            org_id=seeded["org"], role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
        assert quickedit.has_code(seeded["org"]) is False

    login(client, username)
    reply = _ask(client, "anything cafeteria :: a replacement answer here")["reply"]
    assert "no correction code" in reply.lower()


# ================================================================ the code page
def test_only_the_super_admin_can_set_the_code(app, client, seeded):
    _setup(app, seeded)
    login(client, "justahod")
    assert client.get("/admin/kb/code").status_code == 403


def test_the_code_page_opens_for_the_super_admin(app, client, seeded):
    username = _setup(app, seeded)
    login(client, username)
    r = client.get("/admin/kb/code")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "::" in body, "the format is not explained"
    assert "global" in body.lower()
    assert "signed in" in body.lower(), "the two-lock rule is not explained"


def test_a_weak_code_is_refused(app, seeded):
    with app.app_context():
        for bad in ("", "ab", "two words"):
            ok, _ = quickedit.set_code(seeded["org"], bad)
            assert not ok, f"{bad!r} was accepted as a code"


def test_changing_the_code_replaces_the_old_one(app, client, seeded):
    username = _setup(app, seeded)
    with app.app_context():
        quickedit.set_code(seeded["org"], "brandnewcode")
        db.session.commit()
    login(client, username)
    assert "not right" in _ask(client, f"{CODE} cafeteria :: x y z")["reply"].lower()
