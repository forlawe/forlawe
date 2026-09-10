"""The assistant learning from real conversations.

THE RULE THIS FILE DEFENDS
--------------------------
The assistant may LEARN continuously, but it must NEVER change what a patient
is told without a human approving it. An answer nobody approved is an answer
nobody is accountable for, and this app talks to sick people about where to go
and what to pay.
"""
from datetime import timedelta

from app.chatbot import engine, learning
from app.chatbot.seed_kb import seed_global_kb
from app.models import (ChatFeedback, ChatMessage, ChatSession,
                        KnowledgeArticle, Organization, db, now_naive)
from tests.conftest import csrf, login


def _session(org_id):
    s = ChatSession(org_id=org_id, lang="en", channel="web")
    db.session.add(s)
    db.session.flush()
    return s


def _asked(sess, text, *, answered=False, article=None, intent=None, days_ago=0):
    m = ChatMessage(session_id=sess.id, role="user", text=text,
                    unanswered=not answered,
                    article_id=article.id if article is not None else None,
                    intent=intent,
                    at=now_naive() - timedelta(days=days_ago))
    db.session.add(m)
    db.session.flush()
    return m


# ================================================================ the rule
def test_learning_never_changes_an_answer_by_itself(app, seeded):
    """The whole design in one test.

    Nothing in this module may write to the TEXT a patient reads. It may only
    propose. If this ever fails, the assistant has started teaching itself
    what to tell sick people.
    """
    import inspect

    from app.chatbot import learning as mod
    source = inspect.getsource(mod)
    # The only function permitted to write anything is add_keyword, and even
    # that touches triggers, never the answer body.
    for banned in (".en =", ".pidgin =", ".yo =", ".ha =", ".ig =", ".cta ="):
        assert banned not in source, (
            f"learning.py assigns to {banned.strip(' =')} — it is rewriting "
            f"what patients are told without anybody approving it")


def test_approving_a_word_does_not_alter_the_answer_text(app, seeded):
    _kb = seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria").first())
        before = art.en

        ok, _ = learning.add_keyword(org_id, art.id, "chop")
        db.session.commit()
        assert ok
        # The global answer is untouched...
        assert db.session.get(KnowledgeArticle, art.id).en == before
        # ...and the hospital's own copy says exactly the same thing.
        mine = (db.session.query(KnowledgeArticle)
                .filter_by(org_id=org_id, intent="cafeteria").first())
        assert mine is not None and mine.en == before


# ================================================================ missing words
def test_it_spots_words_that_should_reach_an_existing_answer(app, seeded):
    """The highest-value learning: the answer exists but cannot be found."""
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for q in ("abeg where I go chop", "where I fit chop for here",
                  "I dey find place to chop", "where person dey chop"):
            _asked(s, q)
        db.session.commit()

        found = learning.missing_words(org_id)
        chop = [f for f in found if f["word"] == "chop"]
        assert chop, f"did not learn 'chop': {[f['word'] for f in found]}"
        assert chop[0]["intent"] == "cafeteria", \
            f"attached 'chop' to the wrong answer: {chop[0]['intent']}"
        assert chop[0]["count"] >= 4
        assert chop[0]["examples"], "no evidence shown to the person approving"


def test_one_person_asking_once_is_not_a_pattern(app, seeded):
    """Three is a pattern. One is an accident and must not create noise."""
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        _asked(s, "abeg where I go chop")
        db.session.commit()
        assert learning.missing_words(org_id) == []


def test_approving_a_word_makes_the_question_answerable(app, seeded):
    """END TO END: failing question -> proposal -> one tap -> answered."""
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for q in ("abeg where I go chop", "where I fit chop",
                  "I dey find place to chop"):
            _asked(s, q)
        db.session.commit()

        assert engine.answer("abeg where I go chop", org_id=org_id) is None

        proposal = [p for p in learning.missing_words(org_id)
                    if p["word"] == "chop"][0]
        ok, msg = learning.add_keyword(org_id, proposal["article_id"], "chop")
        db.session.commit()
        assert ok, msg

        after = engine.answer("abeg where I go chop", org_id=org_id)
        assert after is not None, "the assistant did not actually learn"
        assert after["article"].intent == "cafeteria"


def test_the_shared_library_is_never_edited_for_one_hospital(app, seeded):
    """Multi-tenant safety: one hospital must not change every hospital."""
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria", org_id=None).first())
        before = art.keywords

        learning.add_keyword(org_id, art.id, "chop")
        db.session.commit()

        assert db.session.get(KnowledgeArticle, art.id).keywords == before, \
            "the global library was edited — every hospital just changed"
        mine = (db.session.query(KnowledgeArticle)
                .filter_by(org_id=org_id, intent="cafeteria").first())
        assert "chop" in mine.keywords


def test_a_useless_word_is_refused(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria").first())
        for junk in ("", "  ", "at"):
            ok, msg = learning.add_keyword(seeded["org"], art.id, junk)
            assert not ok, f"{junk!r} was accepted as a trigger"


def test_the_same_word_is_not_learned_twice(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria").first())
        assert learning.add_keyword(org_id, art.id, "chop")[0] is True
        db.session.commit()
        mine = (db.session.query(KnowledgeArticle)
                .filter_by(org_id=org_id, intent="cafeteria").first())
        ok, msg = learning.add_keyword(org_id, mine.id, "chop")
        assert not ok and "already" in msg.lower()


def test_another_hospitals_answer_cannot_be_edited(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        other = Organization(code="OTH9", name="Other")
        db.session.add(other)
        db.session.flush()
        theirs = KnowledgeArticle(org_id=other.id, category="x", intent="theirs",
                                  keywords="a", en="Their answer", scope="tenant")
        db.session.add(theirs)
        db.session.commit()
        ok, msg = learning.add_keyword(seeded["org"], theirs.id, "hello")
        assert not ok and "another hospital" in msg.lower()


# ================================================================ missing answers
def test_it_reports_questions_with_no_answer_at_all(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for q in ("where can I park my car", "is there parking space",
                  "car park available", "do you have parking for visitors"):
            _asked(s, q)
        db.session.commit()

        gaps = learning.missing_answers(org_id)
        assert gaps, "four people asked about parking and nothing was reported"
        assert any("park" in g["topic"] for g in gaps)
        assert gaps[0]["suggested_keywords"], "no starting words offered"


def test_a_missing_word_is_not_also_reported_as_a_missing_answer(app, seeded):
    """Otherwise the founder writes a duplicate answer for a one-tap fix."""
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for q in ("abeg where I go chop", "where I fit chop",
                  "I dey find place to chop", "where person dey chop"):
            _asked(s, q)
        db.session.commit()

        words = learning.missing_words(org_id)
        gaps = learning.missing_answers(
            org_id, exclude_words={w["word"] for w in words})
        assert not any("chop" in g["topic"] for g in gaps), \
            "'chop' is listed as both a missing word AND a missing answer"


# ================================================================ failing answers
def test_answers_collecting_thumbs_down_are_reported(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria").first())
        s = _session(org_id)
        msg = _asked(s, "food?", answered=True, article=art)
        for _ in range(4):
            db.session.add(ChatFeedback(message_id=msg.id, article_id=art.id,
                                        rating="down"))
        db.session.commit()

        bad = learning.failing_answers(org_id)
        assert any(b["article_id"] == art.id for b in bad)


def test_a_well_liked_answer_is_not_reported(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria").first())
        s = _session(org_id)
        msg = _asked(s, "food?", answered=True, article=art)
        for _ in range(9):
            db.session.add(ChatFeedback(message_id=msg.id, article_id=art.id,
                                        rating="up"))
        for _ in range(3):
            db.session.add(ChatFeedback(message_id=msg.id, article_id=art.id,
                                        rating="down"))
        db.session.commit()
        assert not any(b["article_id"] == art.id
                       for b in learning.failing_answers(org_id))


# ================================================================ accuracy
def test_accuracy_is_measured_honestly(app, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for _ in range(15):
            _asked(s, "what are your opening hours", answered=True)
        for _ in range(5):
            _asked(s, "where can I park")
        db.session.commit()

        acc = learning.accuracy(org_id)
        assert acc["asked"] == 20
        assert acc["percent"] == 75
        assert acc["reliable"] is True


def test_too_few_questions_is_admitted_not_dressed_up(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        _asked(s, "hello", answered=True)
        db.session.commit()
        assert learning.accuracy(org_id)["reliable"] is False


def test_a_brand_new_hospital_sees_no_crash(app, seeded):
    """Day one: no conversations at all."""
    with app.app_context():
        org_id = seeded["org"]
        assert learning.missing_words(org_id) == []
        assert learning.missing_answers(org_id) == []
        assert learning.failing_answers(org_id) == []
        assert learning.coin_flip_matches(org_id) == []
        assert learning.corrections(org_id) == []
        assert learning.accuracy(org_id)["asked"] == 0
        assert learning.summary(org_id)["missing_words"] == 0


# ================================================================ the page
def _login_admin(client, app, seeded):
    from app.models import User
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"],
                                             role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


def test_the_learning_page_opens_and_shows_proposals(app, client, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for q in ("abeg where I go chop", "where I fit chop",
                  "I dey find place to chop"):
            _asked(s, q)
        db.session.commit()

    _login_admin(client, app, seeded)
    r = client.get("/admin/kb/learning")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "chop" in body
    assert "cafeteria" in body
    assert "Teach it this word" in body


def test_approving_from_the_page_works(app, client, seeded):
    seed_global_kb(app)
    with app.app_context():
        org_id = seeded["org"]
        s = _session(org_id)
        for q in ("abeg where I go chop", "where I fit chop",
                  "I dey find place to chop"):
            _asked(s, q)
        db.session.commit()
        art = (db.session.query(KnowledgeArticle)
               .filter_by(intent="cafeteria").first())
        aid = art.id

    _login_admin(client, app, seeded)
    r = client.post("/admin/kb/learn-word",
                    data={"_csrf": csrf(client, "/admin/kb/learning"),
                          "article_id": aid, "word": "chop"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "learned" in r.get_data(as_text=True).lower()

    with app.app_context():
        assert engine.answer("abeg where I go chop",
                             org_id=seeded["org"]) is not None


def test_the_page_opens_on_a_brand_new_hospital(app, client, seeded):
    _login_admin(client, app, seeded)
    assert client.get("/admin/kb/learning").status_code == 200


def test_only_management_may_see_what_was_asked(app, client, seeded):
    """Patients' questions are not for everybody to read."""
    from app.models import Department, User
    with app.app_context():
        dept = Department(org_id=seeded["org"], name="Theatre")
        db.session.add(dept)
        db.session.flush()
        u = User(org_id=seeded["org"], username="theatrehod2",
                 name="Theatre HOD", role="HOD", department_id=dept.id)
        u.set_password("Passw0rd!x")
        u.must_change_password = False
        db.session.add(u)
        db.session.commit()

    login(client, "theatrehod2")
    assert client.get("/admin/kb/learning").status_code == 403
