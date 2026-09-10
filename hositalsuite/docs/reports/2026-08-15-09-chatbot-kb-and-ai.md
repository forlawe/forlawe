# ✅ Chatbot upgraded — 458 intents, full department coverage, free AI fallback

**249 tests passing** on both databases · Live and verified on your site

---

## First: UptimeRobot is working 🎉

Your screenshot shows it monitoring, **98.48% uptime, site Up**. That's one more item off
your list — and it's now also keeping Supabase awake.

---

## 1. Did the chatbot cover the new departments? **No — 17 of 31 were missing**

I tested all 31 departments before changing anything. Only 14 had any coverage. A patient
asking about **Internal Medicine, Surgery, Obstetrics & Gynaecology, the Laboratory, Medical
Records, Billing, Admin, ICT, Engineering, Environmental Health, Security, Audit, Planning,
Public Affairs, Laundry, Orthopaedics or Public Health** was told *"I don't have an answer
for that."*

## 2. What I built: 20 dialogues per department

**21 departments × up to 20 real patient exchanges = 339 new dialogues, ~6,500 new triggers.**

Written as you asked — drama-style dialogue, the way patients actually speak, in **English and
Nigerian Pidgin**. Example:

> **Patient:** "How much is delivery?"
> **Assistant:** "Delivery costs vary depending on the type of birth and what's needed on the
> day, so I won't quote you a figure I can't stand behind. The billing desk gives written
> estimates — and it's a very good idea to ask for one during pregnancy, not on the day."

Every answer is held to house rules, **enforced by automated tests**:
- Never diagnoses, never prescribes, never quotes a dose
- Money answers give ranges or point to billing — never invented figures
- Urgent situations (bleeding, labour signs, chest pain, a lost child, an exposed wire) push
  straight to A&E or to staff
- Names the actual room, document or person to ask for
- A quality test caught 7 answers that were too thin; all were rewritten

**Result: 31/31 departments covered — verified live on your site**, on both the full name
("Radiology / Imaging") and the short name a patient would really type ("Radiology").

Library grew from **119 → 458 intents** and **1,078 → 7,559 triggers**.

---

## 3. The AI fallback — free forever, safest-first

```
Patient question
   ↓
1. Clinical? → safe refusal + offer a clinician.   AI is NEVER called.
2. Hospital's own library? → use the hospital's exact words.  Instant. Free.
3. Still nothing? → AI (Groq → Gemini → OpenRouter)
                    reply re-checked for clinical content before display
4. AI down or capped? → warm human handoff.  Patient NEVER sees an error.
```

**The hospital's own answers always win.** That's deliberate: curated wording is more accurate,
more defensible, and costs nothing.

### Which AI, and why

| Provider | Model | Speed | Free forever | Card |
|---|---|---|---|---|
| **Groq (primary)** | **Llama 3.3 70B** | 300–800 tok/s | ✅ | ❌ none |
| Gemini (second) | Gemini Flash | ~100 tok/s | ✅ | ❌ none |
| OpenRouter (third) | Various free | Varies | ✅ | ❌ none |

I chose Groq as primary for **accuracy per zero naira, plus speed**. Llama 3.3 70B is among
the strongest open models, and Groq's hardware answers in about a second. That matters: a
patient on a weak Lagos signal abandons a chat that takes ten seconds.

---

## 4. What you need to set up (3 minutes, ₦0)

**Only one variable is needed:**

1. Go to **console.groq.com** → sign up (Google login works) → **API Keys** → **Create**
2. Copy the key (starts with `gsk_`)
3. Render → `hospital-suite` → **Environment** → Add:

| Key | Value |
|---|---|
| `GROQ_API_KEY` | `gsk_...` |

Save. That's it.

**Optional extras** (all documented in `AI_SETUP.md` in your repo):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Second provider (aistudio.google.com) |
| `OPENROUTER_API_KEY` | — | Third provider |
| `AI_PROVIDER` | auto | Force one, e.g. `gemini` |
| `AI_FALLBACK` | `1` | `0` turns AI off everywhere |
| `AI_TIMEOUT` | `8` | Seconds before trying the next provider |

**Add nothing and everything still works** — you just get the 458 curated answers.

Check it at **Admin → System Health**, which now shows AI status, provider, model and usage.

---

## 5. Built MVP-SaaS, as you asked

| Capability | How |
|---|---|
| Per-hospital on/off | `ai_fallback_enabled` setting — one hospital can disable without affecting others |
| Per-hospital daily cap | `ai_daily_cap`, default 400/day — protects the free tier |
| Usage metering | Counted per hospital per day, shown in admin |
| Provider failover | Automatic; a dead provider never reaches the patient |
| Zero-config default | Works with no key at all |

The second hospital is a settings row, not a redeploy.

---

## 6. Two serious bugs found while testing live

**A. KB improvements could never reach production.** The loader only *inserted* intents it had
never seen and skipped everything else. So improved wording or new triggers on an existing
answer were **silently dead on arrival** — I deployed two trigger fixes and watched them not
work. Now global answers refresh on deploy, while anything a hospital wrote itself is never
overwritten (verified by test).

**B. Generic phrases hijacked answers.** "What does **surgery** do" was answered by the generic
terminology entry, because the trigger "what does" tied with "surgery". Question-*shape*
phrases now score below any subject word.

---

## Verification

| Check | Result |
|---|---|
| Department coverage, live | **31/31** |
| Test suite, SQLite | **249 passed** |
| Test suite, PostgreSQL 17 | **249 passed** |
| Clinical guardrail (before + after model) | enforced, tested |
| No AI configured | still fully working |
| Live site | `status: ok`, backup today ✅ |

---

## Still on your list

- ⬜ **Revoke the GitHub token** you pasted in chat — github.com/settings/tokens
- ⬜ **Add `GROQ_API_KEY`** to Render (3 minutes, above)
- ⬜ **Supabase backups** — Database → Backups
- ⬜ **Press "Add any missing standard departments"** in Admin → Structure
- ⬜ **Day 2: bulk user upload** — your nominal roll photo is exactly the use case
