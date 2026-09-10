"""F-041: every chatbot trigger phrase has exactly ONE owner intent.

Exact duplicate triggers used to be silently resolved by file order —
"audit log" could land on the security-headers answer, "data protection"
on the privacy policy. learning.py's coin-flip detector existed to catch
this class of bug; now the library itself cannot contain the condition.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def kb_entries():
    from app.chatbot.seed_kb import _all_kb
    return _all_kb()


def _owners(entries):
    owner = {}
    collisions = []
    for entry in entries:
        for kw in entry.get("kw", []):
            key = " ".join(kw.lower().split())
            if key in owner and owner[key] != entry["intent"]:
                collisions.append((key, owner[key], entry["intent"]))
            else:
                owner.setdefault(key, entry["intent"])
    return collisions


def test_no_exact_trigger_collisions_anywhere(kb_entries):
    collisions = _owners(kb_entries)
    assert not collisions, collisions[:10]


def test_audited_collisions_now_have_their_reviewed_winner(kb_entries):
    by_intent = {e["intent"]: {" ".join(k.lower().split()) for k in e["kw"]}
                 for e in kb_entries}
    expectations = {
        "audit log": "reports_archive",
        "data protection": "ndpa_rights",
        "how to assign role": "how_to_manage_users",
        "where is lab": "lab_how",
        "how long will i wait": "queue_wait_time",
        "baby not moving": "obstetrics_gynaecology_baby_movement",
        "billing": "finance_accounts_what",
        "hims": "health_information_managemen_what",
        "security": "security_what",
        "visiting hours": "visiting",
    }
    for trigger, winner in expectations.items():
        assert trigger in by_intent[winner], (trigger, winner)
        for intent, kws in by_intent.items():
            if intent != winner:
                assert trigger not in kws, (trigger, intent)


def test_specific_triggers_survive_dedupe(kb_entries):
    """De-duplication must not gut the specific triggers that make the KB
    precise — the fasting question still reaches the laboratory answer."""
    kws = {e["intent"]: kws for e in kb_entries if (kws := {" ".join(k.lower().split()) for k in e["kw"]})}
    assert any("fasting" in k for k in kws["laboratory_fasting"])
    assert any("file number" in k for k in kws["health_information_managemen_file_number"])


def test_exact_ambiguous_query_goes_to_the_reviewed_winner(app, seeded):
    from app.chatbot import engine
    from app.chatbot.seed_kb import seed_global_kb
    seed_global_kb(app, quiet=True)
    with app.app_context():
        res = engine.answer("audit log")
        assert res is not None and res["article"].intent == "reports_archive"
