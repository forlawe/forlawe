"""AI fallback layer: safety, failover, metering and SaaS controls.

The AI must never be able to hurt a patient, cost the hospital money, or take
the chat down when it fails.
"""
import pytest

from app.chatbot import ai
from app.models import ChatMessage, Organization, db


@pytest.fixture()
def kb(app, seeded):
    from app.chatbot.seed_kb import seed_global_kb
    seed_global_kb(app, quiet=True)
    return seeded


# ================================================================ off by default
def test_disabled_when_no_provider_key(monkeypatch, app, seeded):
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert ai.is_enabled(seeded["org"]) is False
    assert ai.answer("something obscure", org=None) is None


def test_chat_still_works_with_no_ai_configured(client, kb, monkeypatch):
    """The whole point: no key, no crash, still a helpful reply."""
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = client.post("/api/chat", json={"text": "zzz qqq xxx nonsense", "lang": "en"})
    assert r.status_code == 200
    assert r.get_json()["reply"], "must always reply to a patient"


# ================================================================ KB priority
def test_knowledge_base_is_used_before_ai(client, kb, monkeypatch):
    """AI must NOT be called when the hospital has its own answer."""
    called = {"n": 0}

    def spy(*a, **kw):
        called["n"] += 1
        return {"text": "AI answer", "provider": "test", "ms": 1}

    monkeypatch.setattr(ai, "answer", spy)
    body = client.post("/api/chat",
                       json={"text": "what are your opening hours", "lang": "en"}).get_json()
    assert called["n"] == 0, "AI was called even though the KB had an answer"
    assert "open" in body["reply"].lower()


def test_a_miss_does_not_ask_the_language_model(client, kb, monkeypatch):
    """The founder: do not suggest anything that is not in the answer book."""
    called = {"n": 0}

    def spy(*a, **kw):
        called["n"] += 1
        return {"text": "Invented offer", "provider": "test", "ms": 1}

    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(ai, "answer", spy)
    body = client.post("/api/chat", json={
        "text": "zzqq wobble frobnicate xyzzy", "lang": "en"}).get_json()
    assert called["n"] == 0, "the language model was asked to invent an answer"
    assert body["answered"] is False
    assert "answer book" not in body["reply"].lower()
    assert any(w in body["reply"].lower() for w in ("person", "staff", "desk", "call"))
    assert "invented" not in body["reply"].lower()


def test_a_miss_is_saved_as_unanswered(client, kb):
    body = client.post("/api/chat", json={
        "text": "zzqq wobble frobnicate plover", "lang": "en"}).get_json()
    rows = db.session.query(ChatMessage).filter_by(session_id=body["session"]).all()
    assert any(m.role == "user" and m.unanswered for m in rows)
    assert any(m.role == "bot" and "answer book" not in (m.text or "").lower()
               and any(w in (m.text or "").lower()
                       for w in ("person", "staff", "desk", "call"))
               for m in rows)


# ================================================================ clinical safety
def test_clinical_questions_never_reach_the_model(monkeypatch, app, seeded):
    """The guardrail runs BEFORE the provider is called."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    called = {"n": 0}
    monkeypatch.setattr(ai, "_PROVIDERS",
                        {"groq": lambda *a, **kw: called.__setitem__("n", 1) or "unsafe"})

    org = db.session.get(Organization, seeded["org"])
    for q in ["what disease do i have", "which drug should i take",
              "please prescribe something for my fever"]:
        out = ai.answer(q, org=org, lang="en")
        assert out is not None
        assert out["provider"] == "guardrail"
        assert "diagnose" in out["text"].lower() or "clinician" in out["text"].lower()
    assert called["n"] == 0, "a clinical question was sent to the language model"


def test_clinical_output_from_the_model_is_blocked(monkeypatch, app, seeded):
    """Even if the model is jailbroken, the patient must not see clinical advice."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai, "_PROVIDERS", {"groq": lambda *a, **kw:
                        "You probably have malaria. Take paracetamol 500mg twice daily."})
    org = db.session.get(Organization, seeded["org"])
    out = ai.answer("my head hurts and I feel hot", org=org, lang="en")
    assert out is not None
    assert "paracetamol" not in out["text"].lower()
    assert "guardrail" in out["provider"]


def test_markdown_is_stripped_from_ai_replies(monkeypatch, app, seeded):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai, "_PROVIDERS",
                        {"groq": lambda *a, **kw: "**Bold** and ## heading\n* item"})
    org = db.session.get(Organization, seeded["org"])
    out = ai.answer("where can i wait", org=org, lang="en")
    assert "**" not in out["text"] and "##" not in out["text"]


# ================================================================ failover
def test_falls_through_to_the_next_provider(monkeypatch, app, seeded):
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k2")

    def boom(*a, **kw):
        raise RuntimeError("groq 429: rate limited")

    monkeypatch.setattr(ai, "_call_groq", boom)
    monkeypatch.setattr(ai, "_call_gemini", lambda *a, **kw: "Gemini to the rescue.")
    monkeypatch.setattr(ai, "_PROVIDERS", {"groq": boom, "gemini": ai._call_gemini})

    org = db.session.get(Organization, seeded["org"])
    out = ai.answer("is there parking", org=org, lang="en")
    assert out["provider"] == "gemini"
    assert out["text"] == "Gemini to the rescue."


def test_all_providers_failing_returns_none_not_an_error(monkeypatch, app, seeded):
    monkeypatch.setenv("GROQ_API_KEY", "k1")

    def boom(*a, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr(ai, "_PROVIDERS", {"groq": boom})
    org = db.session.get(Organization, seeded["org"])
    assert ai.answer("anything", org=org, lang="en") is None


def test_provider_order_is_quality_first(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    assert ai._provider_chain()[0] == "groq", "Groq (Llama 3.3 70B) should lead"


def test_provider_can_be_pinned(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    assert ai._provider_chain()[0] == "gemini"


# ================================================================ SaaS controls
def test_daily_cap_protects_the_free_tier(monkeypatch, app, seeded):
    from app import services
    monkeypatch.setenv("GROQ_API_KEY", "k")
    services.set_setting(seeded["org"], "ai_daily_cap", 2)
    db.session.commit()

    monkeypatch.setattr(ai, "_PROVIDERS", {"groq": lambda *a, **kw: "ok"})
    org = db.session.get(Organization, seeded["org"])
    assert ai.answer("q1", org=org) is not None
    assert ai.answer("q2", org=org) is not None
    assert ai.answer("q3", org=org) is None, "daily cap was not enforced"


def test_a_hospital_can_switch_ai_off(monkeypatch, app, seeded):
    from app import services
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert ai.is_enabled(seeded["org"]) is True
    services.set_setting(seeded["org"], "ai_fallback_enabled", False)
    db.session.commit()
    assert ai.is_enabled(seeded["org"]) is False


def test_status_reports_configuration(monkeypatch, app, seeded):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    st = ai.status(seeded["org"])
    assert st["enabled"] is True
    assert st["primary"] == "groq"
    assert st["daily_cap"] > 0


def test_context_never_invents_hospital_facts(app, seeded):
    org = db.session.get(Organization, seeded["org"])
    ctx = ai.build_context(org)
    assert org.name in ctx
    assert "Accident & Emergency" in ctx
    # departments are real rows, not invented
    assert "Emergency" in ctx


def test_system_prompt_forbids_diagnosis_and_invention():
    p = ai.SYSTEM_PROMPT
    assert "NEVER diagnose" in p
    assert "NEVER invent" in p
    assert "Accident & Emergency" in p


# ================================================================ department KB
def test_every_standard_department_is_covered(app, kb):
    """No patient should hit 'I don't know' for a department we run."""
    from app.chatbot import engine
    from app.standard_departments import department_names

    gaps = []
    for d in department_names():
        r = engine.answer(f"I need help with {d}", org_id=kb["org"])
        if not (r and r.get("article")):
            gaps.append(d)
    assert not gaps, f"departments with no dialogue coverage: {gaps}"


def test_department_library_is_well_formed():
    from app.chatbot.kb_departments_full import DEPT_DIALOGUES, KB

    assert len(DEPT_DIALOGUES) >= 15
    for dept, rows in DEPT_DIALOGUES.items():
        for suffix, triggers, en, pcm, cta in rows:
            assert triggers, f"{dept}/{suffix} has no triggers"
            assert len(en) > 40, f"{dept}/{suffix} english answer too thin"
            assert len(pcm) > 20, f"{dept}/{suffix} missing pidgin"
            assert cta, f"{dept}/{suffix} has no call to action"
    intents = [e["intent"] for e in KB]
    assert len(intents) == len(set(intents)), "duplicate intent id in the department KB"


def test_department_answers_never_diagnose():
    """Spot-check the new library against clinical language."""
    from app.chatbot.kb_departments_full import KB
    banned = ("you have malaria", "take paracetamol", "i diagnose", "your diagnosis",
              "mg twice daily", "you are suffering from")
    for entry in KB:
        low = entry["en"].lower()
        for b in banned:
            assert b not in low, f"{entry['intent']} contains clinical advice: {b}"


def test_emergency_answers_send_people_to_ae():
    from app.chatbot.kb_departments_full import KB
    urgent = [e for e in KB if any(w in e["intent"] for w in
                                   ("emergency", "labour_signs", "bleeding", "fracture",
                                    "appendix", "unsafe", "child"))]
    assert urgent, "expected some urgent intents"
    strong = [e for e in urgent
              if "a&e" in (e["en"] + e["cta"]).lower()
              or "accident & emergency" in (e["en"] + e["cta"]).lower()
              or "come in now" in (e["en"] + e["cta"]).lower()
              or "immediately" in (e["en"] + e["cta"]).lower()
              or "now" in e["cta"].lower()]
    assert len(strong) >= len(urgent) // 2, "urgent intents must direct patients to help"


# ================================================================ routing quality
def test_generic_question_shapes_do_not_hijack_answers(app, kb):
    """Regression: 'what does SURGERY do' matched the trigger 'what does'
    (generic terminology answer) and beat the Surgery answer on a tie.
    Question-shape phrases must never outrank subject matter."""
    from app.chatbot import engine
    cases = {
        "what does surgery do": "surgery",
        "what does internal medicine do": "internal_medicine",
        "what is the laboratory": "laboratory",
        "tell me about obstetrics": "obstetrics",
    }
    wrong = []
    for q, expect in cases.items():
        r = engine.answer(q, org_id=kb["org"])
        got = r["article"].intent if r and r.get("article") else "NONE"
        if expect not in got:
            wrong.append(f"{q!r} -> {got}")
    assert not wrong, "generic trigger hijacked: " + "; ".join(wrong)


def test_real_patient_phrasings_reach_the_right_department(app, kb):
    from app.chatbot import engine
    cases = {
        "the ward is dirty": "environmental_health",
        "i want to report a bribe": "audit",
        "how do i pay my bill": "bill",
        "how much is delivery": "obstetrics",
        "book antenatal": "anc",
        "i need my file number": "file_number",   # HIMS slug is truncated in the intent id
        "my cast is too tight": "orthopaedics",
        "when is immunisation": "public_health",
    }
    wrong = []
    for q, expect in cases.items():
        r = engine.answer(q, org_id=kb["org"])
        got = r["article"].intent if r and r.get("article") else "NONE"
        if expect not in got:
            wrong.append(f"{q!r} -> {got}")
    assert not wrong, "misrouted: " + "; ".join(wrong)


def test_department_intents_keep_their_action_buttons(app, kb):
    """A department complaint answer must still offer 'Make a complaint'."""
    from app.chatbot import engine
    r = engine.answer("the nurse was rude", org_id=kb["org"])
    assert r["action"] == "complaint"
    r = engine.answer("book antenatal", org_id=kb["org"])
    assert r["action"] == "book"


def test_kb_sync_refreshes_existing_intents(app, seeded):
    """Regression: the loader SKIPPED intents that already existed, so improved
    wording and new triggers never reached a deployed hospital. A fix could be
    written, tested, deployed — and still not work in production."""
    from app.chatbot.seed_kb import seed_global_kb
    from app.models import KnowledgeArticle

    seed_global_kb(app, quiet=True)
    row = (db.session.query(KnowledgeArticle)
           .filter_by(org_id=None, intent="hours_clinic").first())
    assert row is not None

    row.keywords = "stale trigger only"
    row.en = "Stale answer."
    db.session.commit()

    seed_global_kb(app, quiet=True)          # must repair it
    row = (db.session.query(KnowledgeArticle)
           .filter_by(org_id=None, intent="hours_clinic").first())
    assert row.en != "Stale answer.", "shipped library did not refresh the row"
    assert "opening hours" in row.keywords, "triggers were not refreshed"


def test_kb_sync_does_not_touch_tenant_authored_rows(app, seeded):
    """A hospital's own edits must survive a deploy."""
    from app.chatbot.seed_kb import seed_global_kb
    from app.models import KnowledgeArticle

    mine = KnowledgeArticle(org_id=seeded["org"], scope="tenant", status="approved",
                            category="local", intent="hours_clinic",
                            keywords="our own trigger", en="Our own local answer.")
    db.session.add(mine)
    db.session.commit()
    mid = mine.id

    seed_global_kb(app, quiet=True)
    still = db.session.get(KnowledgeArticle, mid)
    assert still.en == "Our own local answer.", "a tenant's own dialogue was overwritten"


# ---------------------------------------------------------------- model life
# Groq retired llama-3.3-70b-versatile on 16 Aug 2026. The app was still
# pinned to it, so every AI fallback returned 400 model_decommissioned and the
# patient silently got "I don't have an answer". These guard the recovery.

def test_default_groq_model_is_not_a_retired_one(monkeypatch):
    from app.chatbot import ai
    retired = {
        "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "moonshotai/kimi-k2-instruct-0905",
    }
    assert ai.GROQ_DEFAULT_MODEL not in retired, (
        f"{ai.GROQ_DEFAULT_MODEL} is decommissioned - see "
        "https://console.groq.com/docs/deprecations")
    assert not (retired & set(ai.GROQ_MODEL_FALLBACKS)), "retired model in the fallback ladder"


def test_decommissioned_model_self_heals_to_a_live_one(monkeypatch):
    """A retired model ID must not silently become 'no answer' to a patient."""
    from app.chatbot import ai

    calls = []

    class Resp:
        def __init__(self, code, payload=None, text=""):
            self.status_code, self._p, self.text = code, payload, text

        def json(self):
            return self._p

    def fake_post(url, **kw):
        model = kw["json"]["model"]
        calls.append(model)
        if model == "some-retired-model":
            return Resp(400, text='{"error":{"code":"model_decommissioned"}}')
        return Resp(200, {"choices": [{"message": {"content": "Live answer."}}]})

    monkeypatch.setattr(ai.requests, "post", fake_post)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GROQ_MODEL", "some-retired-model")

    out = ai._call_groq([{"role": "user", "content": "hi"}], 5)
    assert out == "Live answer.", "self-heal did not recover the answer"
    assert calls[0] == "some-retired-model" and len(calls) > 1, "no fallback attempted"


def test_never_pin_a_preview_model(monkeypatch):
    """Preview models 'may be discontinued at short notice' - Groq's own words.

    A hospital assistant must run on PRODUCTION models only. Groq recommended
    qwen/qwen3.6-27b as a replacement for llama-3.3-70b-versatile, but it is a
    PREVIEW model - taking that advice would have set up the next silent outage.
    """
    from app.chatbot import ai
    assert ai.GROQ_DEFAULT_MODEL not in ai.GROQ_PREVIEW_MODELS, (
        f"{ai.GROQ_DEFAULT_MODEL} is a PREVIEW model - not safe for a hospital")
    leaked = ai.GROQ_PREVIEW_MODELS & set(ai.GROQ_MODEL_FALLBACKS)
    assert not leaked, f"preview model(s) in the failover ladder: {leaked}"
