"""KB audience-sharing audit (report §15 item 4) — who can write the library
the PUBLIC patient assistant reads, and does the one audience-safety lever
actually work?

Surfaces traced: the public web chat (/api/chat, no login), the WhatsApp
webhook, and the admin KB console all read ONE shared KnowledgeArticle table
through engine.answer — there is no staff/patient audience split anywhere.
That makes the WRITE gates the only thing between a head-office role of one
hospital and the assistant every hospital's patients hear:

  * kb_edit / kb_delete used to let ANY SUPER_MD role (MD_CEO, DMD, DCST,
    APEX_NURSE, HEAD_ADMIN_HR) edit or delete a GLOBAL (org_id NULL) article,
    because the tenant check only fired when org_id was set. The keyword
    learning path explicitly forbids exactly this ("a tenant must not edit
    the shared global library in place").
  * the clinical_safe column ("False = refuse/redirect template") was stored
    by every writer but read by nothing — a dialogue marked unsafe answered
    verbatim.
"""
from __future__ import annotations

import pytest

from app.models import db, now_naive


def _mk(org_id, username, role, department_id=None):
    from app.models import User
    u = User(org_id=org_id, username=username, name=username.title(),
             role=role, department_id=department_id)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    return u


def _article(org_id, intent, keywords, en, clinical_safe=True):
    from app.models import KnowledgeArticle
    a = KnowledgeArticle(org_id=org_id, category="general", intent=intent,
                         keywords=keywords, en=en, scope="global" if org_id is None
                         else "tenant", status="approved",
                         clinical_safe=clinical_safe)
    db.session.add(a)
    db.session.flush()
    return a


# ---------------------------------------------------------------- write gates

def test_non_super_cannot_edit_a_global_article(app, seeded):
    from app.models import KnowledgeArticle
    from tests.conftest import csrf, login
    with app.app_context():
        _mk(seeded["org"], "mdceo1", "MD_CEO")
        art = _article(None, "cafeteria", "cafeteria\ncanteen",
                       "GLOBAL CAFETERIA WORDING")
        db.session.commit()
        kid = art.id
    client = app.test_client()
    assert login(client, "mdceo1")
    r = client.post(f"/admin/kb/{kid}/edit", data={
        "_csrf": csrf(client, "/admin/kb"),
        "intent": "cafeteria", "en": "TAMPERED WORDING",
    }, follow_redirects=True)
    assert r.status_code == 404
    with app.app_context():
        assert "GLOBAL CAFETERIA WORDING" == db.session.get(
            KnowledgeArticle, kid).en


def test_non_super_cannot_delete_a_global_article(app, seeded):
    from app.models import KnowledgeArticle
    from tests.conftest import csrf, login
    with app.app_context():
        _mk(seeded["org"], "mdceo2", "MD_CEO")
        art = _article(None, "visiting", "visiting hours",
                       "GLOBAL VISITING HOURS")
        db.session.commit()
        kid = art.id
    client = app.test_client()
    assert login(client, "mdceo2")
    r = client.post(f"/admin/kb/{kid}/delete",
                    data={"_csrf": csrf(client, "/admin/kb")},
                    follow_redirects=True)
    assert r.status_code == 404
    with app.app_context():
        assert db.session.get(KnowledgeArticle, kid) is not None


def test_head_office_still_edits_their_own_tenant_article(app, seeded):
    """Regression: the legitimate path — a hospital tuning its own voice."""
    from app.models import KnowledgeArticle
    from tests.conftest import csrf, login
    with app.app_context():
        _mk(seeded["org"], "mdceo3", "MD_CEO")
        art = _article(seeded["org"], "parking", "parking",
                       "TENANT PARKING WORDING")
        db.session.commit()
        kid = art.id
    client = app.test_client()
    assert login(client, "mdceo3")
    r = client.post(f"/admin/kb/{kid}/edit", data={
        "_csrf": csrf(client, "/admin/kb"),
        "intent": "parking", "en": "PARKING, IMPROVED",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert "PARKING, IMPROVED" == db.session.get(KnowledgeArticle, kid).en


def test_super_still_edits_global_articles(app, seeded):
    from app.models import KnowledgeArticle
    from tests.conftest import csrf, login
    with app.app_context():
        art = _article(None, "wifi", "wifi password", "GLOBAL WIFI WORDING")
        db.session.commit()
        kid = art.id
    client = app.test_client()
    assert login(client, "admin")
    r = client.post(f"/admin/kb/{kid}/edit", data={
        "_csrf": csrf(client, "/admin/kb"),
        "intent": "wifi", "en": "GLOBAL WIFI, UPDATED",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert "GLOBAL WIFI, UPDATED" == db.session.get(KnowledgeArticle, kid).en


# ---------------------------------------------------------------- read lever

def test_clinical_safe_false_article_answers_with_the_safe_redirect(app, seeded):
    """The flag's documented contract: refuse/redirect, never the body."""
    from app.chatbot import engine
    with app.app_context():
        _article(None, "staff_meals", "staff discount\nstaff meal",
                 "SECRET STAFF-ONLY BODY about meal discounts",
                 clinical_safe=False)
        db.session.commit()
        got = engine.answer("do you give staff discount", org_id=seeded["org"])
    assert got is not None
    assert got["action"] == "clinical"
    assert got["article"] is None
    assert "SECRET STAFF-ONLY BODY" not in got["text"]


def test_clinical_safe_true_article_still_answers_normally(app, seeded):
    """Regression: the default flag must not start refusing everything."""
    from app.chatbot import engine
    with app.app_context():
        _article(None, "cafeteria_hours", "cafeteria hours",
                 "The cafeteria is open 7am to 7pm daily.")
        db.session.commit()
        got = engine.answer("what are the cafeteria hours", org_id=seeded["org"])
    assert got is not None and got["article"] is not None
    assert "7am to 7pm" in got["text"]
