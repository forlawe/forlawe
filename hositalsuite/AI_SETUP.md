# Patient Assistant AI — setup guide

**Cost: ₦0. No credit card. Takes about 3 minutes.**

The assistant already answers **422 curated questions** without any AI at all. The AI layer is a
*fallback* for the long tail — the questions nobody could write down in advance.

---

## How it decides what to say

```
Patient asks a question
        │
        ├─ 1. Is it clinical? ("what disease do I have")
        │      → safe refusal + offer to book a clinician.  AI is NEVER called.
        │
        ├─ 2. Does the hospital's own library answer it?  (422 intents, 6,704 triggers)
        │      → use the hospital's exact wording.  Instant, free, works offline.
        │
        ├─ 3. Still nothing?  → ask the AI (Groq → Gemini → OpenRouter)
        │      → reply is re-checked for clinical content before the patient sees it
        │
        └─ 4. AI unavailable, capped, or failed?
               → warm human-handoff reply.  The patient NEVER sees an error.
```

**The hospital's own words always win.** That is deliberate: a curated answer is more accurate,
more legally defensible and cheaper than a generated one.

---

## Step 1 — Get a free Groq key (recommended)

Groq is the primary provider: **Llama 3.3 70B**, one of the strongest open models, running on
special hardware at 300–800 words per second. Free forever, no card.

1. Go to **console.groq.com** and sign up (Google sign-in works).
2. Open **API Keys** → **Create API Key**.
3. Copy the key — it starts with `gsk_...`.

## Step 2 — Add it to Render

Render dashboard → `hospital-suite` → **Environment** → **Add Environment Variable**:

| Key | Value |
|---|---|
| `GROQ_API_KEY` | `gsk_...` (the key you copied) |

Save. Render restarts automatically. **That's it — the AI is live.**

## Step 3 — Confirm it's working

Sign in as Super Admin → **Admin → System Health**. You'll see:

```
🤖 Patient Assistant AI
Status: on
Providers: groq
Model: openai/gpt-oss-120b  (PRODUCTION tier. llama-3.3-70b-versatile was retired by Groq on 16 Aug 2026.)
Used today: 0 of 400
```

---

## All environment variables (every one is optional)

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | — | **Recommended.** Primary provider. console.groq.com |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Change model if you want |
| `GEMINI_API_KEY` | — | Second line. Free at aistudio.google.com |
| `GEMINI_MODEL` | `gemini-2.0-flash` | |
| `OPENROUTER_API_KEY` | — | Third line. openrouter.ai |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | |
| `AI_PROVIDER` | (auto) | Force one provider, e.g. `gemini` |
| `AI_FALLBACK` | `1` | Set `0` to switch AI off entirely, everywhere |
| `AI_TIMEOUT` | `8` | Seconds to wait before trying the next provider |

**Add nothing and the assistant still works** — it just uses the 422 curated answers only.

### Per-hospital settings (in the app, not env vars — this is the SaaS layer)

| Setting | Default | Meaning |
|---|---|---|
| `ai_fallback_enabled` | `true` | One hospital can switch AI off without affecting others |
| `ai_daily_cap` | `400` | Max AI answers per hospital per day |

---

## Free-tier limits (as of 2026)

| Provider | Requests/min | Requests/day | Card needed |
|---|---|---|---|
| **Groq** | 30 | 1,000–14,400 (by model) | No |
| Google Gemini | 15 | 1,500 | No |
| OpenRouter | 20 | 50 (1,000 with a $10 top-up) | No |

The 400/day cap keeps you comfortably inside the free tier. Because the KB answers most questions
first, real AI usage is typically a small fraction of total chats.

---

## The safety design (please don't weaken this)

1. **Clinical questions never reach the model.** The guardrail runs *before* the API call.
2. **The model's reply is re-checked.** If a jailbreak produces clinical content, it is replaced
   with the safe refusal. Belt and braces.
3. **The model is told it may not invent facts** — no made-up prices, phone numbers or doctor names.
4. **Emergencies short-circuit everything** — straight to A&E, no discussion.
5. **Failures are invisible to patients.** Provider down → next provider → safe human handoff.

---

## Testing it yourself

Ask the assistant something deliberately obscure that no hospital would script:

> *"Is there somewhere quiet I can sit with my mother while she waits?"*

- **Without a key:** a warm "let me get the front desk" reply.
- **With a key:** a natural, specific answer in your hospital's voice.

Then test the guardrail:

> *"What medicine should I take for malaria?"*

It must **refuse and offer a clinician** — with or without AI configured. If it ever does anything
else, tell me immediately.

---

## Why Groq first

| Provider | Model quality | Speed | Free forever | Card |
|---|---|---|---|---|
| **Groq** | Llama 3.3 70B — top open model | 300–800 tok/s | Yes | No |
| Gemini | Gemini Flash — very good | ~100 tok/s | Yes | No |
| OpenRouter | Varies | Varies | Limited | No |

Speed matters here: a patient on a weak Lagos mobile signal will abandon a chat that takes ten
seconds to reply. Groq answers in about one.
