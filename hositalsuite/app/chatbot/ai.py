"""AI fallback for the patient assistant — zero-cost, multi-provider, safe.

DESIGN PRINCIPLES (read before changing anything)
=================================================

1. THE KNOWLEDGE BASE ALWAYS WINS.
   422 curated intents answer instantly, cost nothing, work offline, and say
   exactly what the hospital wants said. AI is only consulted when the KB has
   no confident match. This is not a cost compromise — a hand-written answer
   from the hospital beats a generated one every time.

2. AI NEVER SPEAKS CLINICALLY.
   The clinical guardrail runs BEFORE the model is called (so diagnosis-seeking
   questions never reach it) AND on the model's reply (so a jailbreak cannot
   leak clinical advice to a patient). Belt and braces, deliberately.

3. FOREVER-FREE PROVIDERS ONLY, WITH FAILOVER.
   Providers are tried in order of accuracy-per-zero-naira. If one is down,
   rate-limited or unconfigured, we fall through to the next, and finally to a
   safe human-handoff reply. The assistant NEVER shows an error to a patient.

4. SaaS-READY FROM DAY ONE.
   Per-tenant enable/disable, per-tenant daily caps, provider choice, usage
   metering and full audit — because the second hospital is a settings row,
   not a redeploy.

PROVIDER LADDER (all free, no credit card)
------------------------------------------
  1. groq     — Llama 3.3 70B on LPU hardware. Fastest quality option
                (300-800 tok/s), OpenAI-compatible, generous free tier.
  2. gemini   — Google AI Studio, Gemini Flash. Large free daily quota.
  3. openrouter — aggregator with free models; useful as a third line.
  4. (none)   — rule-based safe reply + offer of a human. Always works.

Set GROQ_API_KEY and it just works. Everything else is optional.
"""
from __future__ import annotations

import json
import os
import time

import requests

from ..models import db, now_naive

# Groq retired llama-3.3-70b-versatile on 16 Aug 2026. Keep this pinned to a
# CURRENT production model and re-check https://console.groq.com/docs/deprecations
# before every release. A dead model ID returns 400 model_decommissioned, which
# used to fail silently into "no answer".
# Groq labels every model PRODUCTION or PREVIEW. Preview models "may be
# discontinued at short notice" - never pin one for a hospital. Groq offered
# two replacements for llama-3.3-70b-versatile: openai/gpt-oss-120b
# (PRODUCTION) and qwen/qwen3.6-27b (PREVIEW). We take the production one.
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"          # PRODUCTION - the safe pin

# Failover ladder: PRODUCTION models only, best first. Deliberately excludes
# preview models - a short-notice shutdown is exactly what we are guarding
# against. Re-check https://console.groq.com/docs/deprecations each release.
GROQ_MODEL_FALLBACKS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")

# Models Groq lists as PREVIEW. Pinning one of these is a latent outage, so
# the test suite fails the build if GROQ_DEFAULT_MODEL ever names one.
GROQ_PREVIEW_MODELS = frozenset({
    "qwen/qwen3.6-27b", "openai/gpt-oss-safeguard-20b", "minimaxai/minimax-m2.7",
    "meta-llama/llama-prompt-guard-2-22m", "meta-llama/llama-prompt-guard-2-86m",
})

# ------------------------------------------------------------------ prompt
SYSTEM_PROMPT = """You are the patient care assistant for {hospital}, a hospital in Nigeria.

YOUR JOB
Answer practical questions about visiting the hospital: booking, opening hours,
departments, bills and payment, directions, what to bring, and how to complain
or give feedback.

ABSOLUTE RULES — THESE OVERRIDE EVERYTHING ELSE
1. NEVER diagnose a condition, suggest what an illness might be, recommend or
   adjust any medicine, dose or treatment, or interpret test results. If asked,
   warmly explain that you cannot, and offer to book them with a clinician.
2. For anything urgent — chest pain, severe bleeding, difficulty breathing,
   a collapsed or unresponsive person, a baby not moving in pregnancy — tell
   them to go straight to Accident & Emergency now. Do not discuss anything else.
3. NEVER invent facts about this hospital. This is the rule you will be most
   tempted to break, so it is spelled out:
   - NO directions or locations. Never say a place is "beside", "opposite",
     "on the ground floor", "near the entrance" or "in the main building".
     You have not seen this hospital. Say "ask at the reception desk and they
     will point you to it".
   - NO prices, fees or amounts.
   - NO phone numbers except one written in CONTEXT below, copied exactly.
   - NO doctor names, no opening times, no waiting times, no room numbers,
     no department names that are not listed in CONTEXT.
   If you do not know, say so plainly and point them to reception. A patient
   sent to the wrong place by a confident answer is worse off than one who was
   told honestly that we did not know.

4. WHEN THE PATIENT IS AGREEING TO SOMETHING
   If their message is just "yes", "ok", "please do" or similar, they are
   accepting the offer in YOUR previous message. Re-read your last message in
   the conversation above and do exactly what you offered. Do not change the
   offer. If you offered the online booking page, give them the booking page —
   not a phone number. If you truly cannot tell what they agreed to, ask them
   to say a little more.

5. ONE INSTRUCTION, NOT THREE
   Give the patient the single best next step. Offering the website, the phone
   and the front desk all at once is how people end up doing nothing.
6. Never ask for a password, bank details or payment.

STYLE
Warm, calm and human — like a kind receptionist who has time for them. Short
paragraphs. Contractions. No bullet lists, no headings, no markdown. Two or
three sentences is usually plenty. End with a gentle next step.
Reply in the SAME language the patient used (English, Nigerian Pidgin, Yoruba,
Hausa or Igbo).

CONTEXT YOU MAY USE
{context}"""

SAFE_FALLBACK = (
    "I want to get this right for you, and I don't have a confident answer to that "
    "one yet. Our front desk will know — shall I let them know you'd like a hand? "
    "You can also call the help desk number at the bottom of this page."
)

# Refuse-and-redirect if the MODEL somehow produces clinical content.
# English first, then the same dangers in the four other supported languages
# (F-033). Phrases are NORMALIZED form (diacritics folded) — _looks_clinical
# runs the reply through the same normalizer as the pre-model gate, so
# "O ní ìbà" and "o ni iba" are caught alike.
_CLINICAL_LEAK = (
    "you may have", "you might have", "you probably have", "this is likely",
    "take paracetamol", "take ibuprofen", "mg twice", "mg daily", "prescribe",
    "your diagnosis", "i diagnose", "you are suffering from", "sounds like malaria",
    "sounds like typhoid", "dosage", "stop taking your",
    # Nigerian Pidgin — a diagnosis handed down as fact
    "you get malaria", "you get typhoid", "na malaria you get", "na typhoid you get",
    "you dey suffer from", "i don diagnose", "wetin dey worry you na",
    # Yoruba — "you have X" (iba=fever/malaria, arun=disease), take-medicine orders
    "o ni iba", "o ni arun", "o nijetta", "o ni je", "mu oogun", "oogun meji",
    # Hausa — "you have (fever|illness)", take-pill orders, pill counts
    "kana da zazzabi", "kina da zazzabi", "kana da ciwon", "kina da ciwon",
    "sha kwayoyi", "kwayoyi biyu", "sau biyu a rana",
    # Igbo — "you have (an) illness", take-medicine orders
    "nwere oria", "were ogwu", "ogwu abuo",
)


# ------------------------------------------------------------------ settings
def _setting(org_id, key, default=None):
    from .. import services
    try:
        return services.get_setting(org_id, key, default)
    except Exception:                                    # noqa: BLE001
        return default


def is_enabled(org_id) -> bool:
    """AI fallback is opt-in per hospital and needs at least one provider key."""
    if os.environ.get("AI_FALLBACK", "1") != "1":
        return False
    if org_id is not None and not _setting(org_id, "ai_fallback_enabled", True):
        return False
    return bool(_provider_chain())


def _provider_chain() -> list[str]:
    """Configured providers, best-first. Order is deliberate."""
    chain = []
    if os.environ.get("GROQ_API_KEY"):
        chain.append("groq")
    if os.environ.get("GEMINI_API_KEY"):
        chain.append("gemini")
    if os.environ.get("OPENROUTER_API_KEY"):
        chain.append("openrouter")
    preferred = os.environ.get("AI_PROVIDER", "").strip().lower()
    if preferred and preferred in chain:                 # pin one if asked
        chain.remove(preferred)
        chain.insert(0, preferred)
    return chain


# ------------------------------------------------------------------ usage cap
def _today_key() -> str:
    return now_naive().strftime("%Y-%m-%d")


def _usage(org_id) -> tuple[str, int]:
    raw = _setting(org_id, "ai_usage_today", "") or ""
    if isinstance(raw, str) and "|" in raw:
        day, _, n = raw.partition("|")
        if day == _today_key():
            try:
                return day, int(n)
            except ValueError:
                pass
    return _today_key(), 0


def _bump_usage(org_id) -> None:
    from .. import services
    day, n = _usage(org_id)
    try:
        services.set_setting(org_id, "ai_usage_today", f"{day}|{n + 1}")
    except Exception:                                    # noqa: BLE001
        db.session.rollback()


def daily_cap(org_id) -> int:
    """Per-hospital daily ceiling. Protects the free tier AND the hospital."""
    try:
        return int(_setting(org_id, "ai_daily_cap", 400) or 400)
    except (TypeError, ValueError):
        return 400


def cap_reached(org_id) -> bool:
    if org_id is None:
        return False
    return _usage(org_id)[1] >= daily_cap(org_id)


# ------------------------------------------------------------------ providers
def _call_groq(messages: list[dict], timeout: float) -> str | None:
    """Groq — Llama 3.3 70B. Fastest quality-per-zero-cost option available."""
    key = os.environ.get("GROQ_API_KEY")
    model = os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.3,
              "max_tokens": 320, "top_p": 0.9},
        timeout=timeout)
    if r.status_code == 400 and "decommissioned" in r.text.lower():
        # Self-heal: the pinned model was retired. Try the known-good ladder
        # rather than silently degrading the assistant to "no answer".
        for alt in GROQ_MODEL_FALLBACKS:
            if alt == model:
                continue
            r2 = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": alt, "messages": messages, "temperature": 0.3,
                      "max_tokens": 320, "top_p": 0.9},
                timeout=timeout)
            if r2.status_code == 200:
                _log(None, "groq", "model_migrated",
                     f"{model} is decommissioned; served with {alt}")
                return (r2.json()["choices"][0]["message"]["content"] or "").strip()
        raise RuntimeError(f"groq model {model} decommissioned and no fallback worked")
    if r.status_code != 200:
        raise RuntimeError(f"groq {r.status_code}: {r.text[:160]}")
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def _call_gemini(messages: list[dict], timeout: float) -> str | None:
    """Google AI Studio — Gemini Flash. Large free daily quota."""
    key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    convo = [m for m in messages if m["role"] != "system"]
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user" if m["role"] == "user" else "model",
                          "parts": [{"text": m["content"]}]} for m in convo],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 320},
        },
        timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"gemini {r.status_code}: {r.text[:160]}")
    data = r.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def _call_openrouter(messages: list[dict], timeout: float) -> str | None:
    """OpenRouter — aggregator with free models. Third line of defence."""
    key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "X-Title": "Hospital Admin Manager Suite"},
        json={"model": model, "messages": messages, "temperature": 0.3,
              "max_tokens": 320},
        timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"openrouter {r.status_code}: {r.text[:160]}")
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


_PROVIDERS = {"groq": _call_groq, "gemini": _call_gemini, "openrouter": _call_openrouter}


# Phrases that mean the model has INVENTED a place. It has never seen this
# hospital, so any of these is a guess dressed up as a fact — and a patient
# sent to the wrong corridor by a confident answer is worse off than one who
# was told honestly that we did not know.
_INVENTED_LOCATION = (
    "beside the", "next to the", "opposite the", "ground floor", "first floor",
    "second floor", "upstairs", "downstairs", "to the left", "to the right",
    "behind the", "in front of the", "main building", "block a", "block b",
    "near the entrance", "near the gate", "at the back of",
)

_ASK_AT_RECEPTION = (
    "I don't want to send you the wrong way — I'm not able to give directions "
    "inside the hospital. Please ask at the reception desk and they will point "
    "you straight to it."
)


def _invents_a_location(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in _INVENTED_LOCATION)


# ------------------------------------------------------------------ safety
def _looks_clinical(text: str) -> bool:
    from .engine import _norm
    low = _norm(text)
    return any(p in low for p in _CLINICAL_LEAK)


def _clean(text: str) -> str:
    """Strip markdown the model may add — our bubbles render plain text."""
    out = (text or "").replace("**", "").replace("##", "").replace("* ", "")
    out = out.replace("\n\n\n", "\n\n").strip()
    return out[:1200]


# ------------------------------------------------------------------ context
def build_context(org, lang: str = "en") -> str:
    """Real facts the model may use. Everything else it must not invent."""
    bits = []
    if org is not None:
        bits.append(f"Hospital name: {org.name}")
        if getattr(org, "phone", None):
            bits.append(f"Help desk phone: {org.phone}")
        if getattr(org, "address", None):
            bits.append(f"Address: {org.address}")
        try:
            from ..models import Department
            names = [d.name for d in db.session.query(Department)
                     .filter_by(org_id=org.id, active=True)
                     .order_by(Department.name).limit(40).all()]
            if names:
                bits.append("Departments available: " + ", ".join(names))
        except Exception:                                # noqa: BLE001
            db.session.rollback()
    bits.append("Patients can book, join the queue, complain, give feedback and "
                "check status from the website with no account.")
    bits.append("Accident & Emergency is open at all hours.")
    return "\n".join(bits)


# ------------------------------------------------------------------ entry point
def answer(text: str, *, org=None, lang: str = "en", history=None) -> dict | None:
    """Ask the AI ladder. Returns {text, provider, ms} or None.

    None means "no AI available or it declined" — the caller then uses its own
    safe reply. This function NEVER raises and NEVER returns clinical content.
    """
    from .engine import SAFE_CLINICAL, SAFE_CLINICAL_PCM, is_clinical_seek

    org_id = getattr(org, "id", None)
    if not is_enabled(org_id):
        return None

    # Guardrail BEFORE the model: clinical questions never reach a language model.
    if is_clinical_seek(text):
        return {"text": SAFE_CLINICAL_PCM if lang == "pcm" else SAFE_CLINICAL,
                "provider": "guardrail", "ms": 0}

    if cap_reached(org_id):
        return None                                      # protect the free tier

    hospital = getattr(org, "name", None) or "this hospital"
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.format(hospital=hospital,
                                                 context=build_context(org, lang))}]
    for turn in (history or [])[-4:]:                    # short memory, low tokens
        role = "assistant" if turn.get("role") == "bot" else "user"
        content = (turn.get("text") or "").strip()
        if content:
            messages.append({"role": role, "content": content[:500]})
    messages.append({"role": "user", "content": text[:1000]})

    timeout = float(os.environ.get("AI_TIMEOUT", "8"))
    for provider in _provider_chain():
        started = time.time()
        try:
            reply = _PROVIDERS[provider](messages, timeout)
        except Exception as exc:                         # noqa: BLE001 - try the next one
            _log(org_id, provider, "error", str(exc)[:200])
            continue
        if not reply:
            continue
        # Guardrail AFTER the model: an invented location must not reach the
        # patient either. Cheaper to refuse than to send somebody wandering.
        if _invents_a_location(reply):
            _log(org_id, provider, "invented_location", reply[:160])
            _bump_usage(org_id)
            return {"text": _ASK_AT_RECEPTION, "provider": f"{provider}+guardrail",
                    "ms": int((time.time() - started) * 1000)}
        # Guardrail AFTER the model: a jailbreak must not reach the patient.
        if _looks_clinical(reply):
            _log(org_id, provider, "blocked", reply[:120])
            return {"text": SAFE_CLINICAL_PCM if lang == "pcm" else SAFE_CLINICAL,
                    "provider": f"{provider}+guardrail", "ms": int((time.time() - started) * 1000)}
        _bump_usage(org_id)
        return {"text": _clean(reply), "provider": provider,
                "ms": int((time.time() - started) * 1000)}
    return None


def _log(org_id, provider: str, kind: str, detail: str) -> None:
    try:
        from flask import current_app
        current_app.logger.warning("ai[%s] %s: %s", provider, kind, detail)
    except Exception:                                    # noqa: BLE001
        pass


# ------------------------------------------------------------------ diagnostics
def status(org_id=None) -> dict:
    """What the admin health page shows."""
    chain = _provider_chain()
    day, used = _usage(org_id) if org_id else (_today_key(), 0)
    return {
        "enabled": is_enabled(org_id),
        "providers": chain or ["(none configured)"],
        "primary": chain[0] if chain else None,
        "used_today": used,
        "daily_cap": daily_cap(org_id) if org_id else None,
        "model": os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL),
    }
