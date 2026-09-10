# ROADMAP — Upgrade to "AI-Powered African Patient Experience & Hospital Operations Platform"

> Gap review (2026-08-11) of v1.0 against the new Master Product Priority & Build Specification,
> followed by the prioritized upgrade plan. Reviewed against the spec's own Priority Order (§48).

---

## 1. SCORECARD — what exists today vs the specification

| Priority (spec §48) | Status | Built today | Missing |
|---|---|---|---|
| P0 Foundation | ~75% | Flask monolith, 20+ normalized tables (org_id on all), scrypt auth, RBAC server-side, CSRF, rate limiting, hash-chained audit, mobile-first CSS | PostgreSQL live (SQLite now), RLS tenant isolation, Branch layer (Hospital→Branch→Dept→Section→Unit), roles: Hospital Admin / Staff / Public, MFA, formal design-token system |
| P1 Patient Experience | ~45% | Public portal (no login), QR with location tagging, USSD intake, full complaint ticketing (§9–13 exact), SLA + auto-escalation | **Booking, queue management, queue status, patient feedback/rating, satisfaction dashboard, digital check-in** |
| P2 Retention & Referral | ~10% | Service-recovery via complaint resolution workflow | Repeat-visit prompts, referral links/QR, referral tracking, satisfaction analytics, AI feedback analysis |
| P3 Hospital Operations | ~95% | Daily inspection (exactly 5 criteria §15), mandatory explanation 1–2, voice-to-text, photo evidence, PDF + verification QR, WhatsApp delivery, roster Excel/CSV import + validation, day-before/duty-day reminders (§16–18 exact) | Reminder quiet hours/frequency setting |
| P4 Staff Control | ~40% | Staff login, role management | **Attendance register, geo-fencing, tamper-resistant events, late/absence detection, monthly attendance report, manual correction workflow** |
| P5 Automation | ~45% | WhatsApp Business API (cloud/sandbox, retry, delivery status), auto-escalation, notification templates + logs | **Notification Provider Interface + Termii SMS (Twilio fallback), Web Push, browser voice reminders, AI classification, true async job queue** |
| P6 Management Intelligence | ~60% | Executive dashboard, KPIs, heatmap, department performance, recurring-problem detection, Management Attention, 8 report types | Queue/satisfaction/repeat-visit/referral analytics, AI-written insight summaries with supporting data |
| P7 SaaS Scale | ~25% | Multi-tenant schema (org_id everywhere), per-hospital settings/logo/ref prefix | RLS, multi-branch, tenant branding (colours, branded portal), subscriptions (deferred per §29 — correct) |
| P8 Documentation | ~40% | README (deploy + WhatsApp go-live + security), HANDOFF.md | **Founder's Guide (10-year-old level)**, step-by-step Deployment Guide, API docs page, privacy policy/terms templates |

**Overall vs §50 MVP launch list: ~55–60% complete.** Complaints + inspections (two pillars) are production-grade;
the patient-journey half (book → queue → feedback → refer) is the main build target.

## 2. HARD CONSTRAINTS — honest status

| Constraint (§) | Status | Action |
|---|---|---|
| 2,000 requests/min (§39) | ✅ TESTED & PASSED at 4,000/min — see LOAD_TEST_REPORT.md (0% failures, concurrency bug found & fixed) | gunicorn, PostgreSQL tested; scaling path documented |
| Tenant isolation + RLS (§25) | ⚠️ app-layer only | Migrate to Supabase PostgreSQL, add RLS policies on tenant tables, keep app-layer scoping as defence-in-depth |
| Notification providers (§38) | ❌ no SMS | Provider interface: Termii primary, Twilio fallback, never hard-coded |
| Async resilience (§39) | ⚠️ WhatsApp send partially in-request | 100% of third-party calls → background job queue; submissions always succeed instantly |
| Failure fallback matrix (§40) | ⚠️ partial | Complete matrix: SMS failover, realtime→polling, push→SMS, AI→rule-based (rule engine already exists as fallback) |
| Idempotency (§41) | ⚠️ duplicate-guards exist | Add client-generated idempotency keys on complaint/inspection/booking submission |
| NDP Act 2023 alignment (§35) | ⚠️ data minimization/retention/audit done | Add consent notices, privacy policy + terms pages, data-subject rights process, breach-response runbook |
| Languages (§34) | ❌ | String-table architecture ready for EN → YO/HA/IG (translate after validation, per spec) |

## 3. UPGRADE PLAN — build order respects spec priority

### WAVE A — Patient Experience completion + foundation hardening ✅ COMPLETE (2026-08-11)
1. **PostgreSQL migration**: connect to Supabase free project (founder creates project), extend schema
   (appointments, queues, queue_events, feedback, referrals, attendance, geofences, branches), verify, keep SQLite for dev.
2. **Booking** (§5): QR/Web/USSD-ready, service + date + contact, reference number, confirmation via available channel,
   phone-instructions fallback. Max 4 fields.
3. **Queue management** (§6): digital queue numbers, public-safe status page (no sensitive data), staff controls,
   progression + completion, estimated wait where reliable, polling-based updates (Realtime-ready).
4. **Patient feedback** (§7): "How was your experience?" rating → optional voice/text improvement note;
   low ratings instantly route into the existing service-recovery/complaint pipeline.
5. **Notification Provider Interface + Termii/Twilio SMS** (§38) with automatic fallback + delivery logs.
6. **Resilience**: idempotency keys, all third-party calls → background queue, gunicorn entrypoint, Dockerfile.

> ✅ All six items shipped & tested (50 automated tests, green on SQLite + PostgreSQL 17):
> booking (HOSP-APT refs, capacity, cancel, USSD), queue (tickets, staff control,
> privacy-safe screen, voice announcement), feedback → service recovery (auto complaint),
> SMS provider interface (Termii/Twilio/sandbox), idempotency on booking+complaint,
> Dockerfile + render.yaml + dbcheck. Supabase compatibility proven; live connection
> happens on the deployed host (workspace egress is web-only).

### WAVE B — Retention, referral & AI (Priority 2)
7. **Referral engine** (§14): ✅ COMPLETE (2026-08-13) — personal link/QR after 4–5★ feedback,
   hospital-wide + staff-named codes, `/r/<code>` landing, click/book/repeat analytics,
   own-link ≠ conversion, PDF/CSV report, poster pack. No prizes.
8. **AI service-recovery engine** (§8): classify urgency/category/department/sentiment/repeats from complaints & feedback;
   free-tier AI provider with **rule-based fallback** (our existing rules become the fallback); advisory only (§44).
9. **AI management insights** (§24): narrative summaries that always show the underlying data.
10. **Satisfaction dashboard** for MD/CEO (P1 item 20 + P6 item 55).

### WAVE C — Staff operations (Priority 4)
11. **Tamper-resistant attendance** (§20): server-side timestamps, signed events, geo-fence validation,
    duplicate prevention, suspicious-event flags, controlled manual corrections with mandatory reason + audit,
    monthly report PDF/CSV.

### WAVE D — Scale, docs & production gate (Priority 7–8 + §47)
12. **Load campaign**: ✅ DONE — locust at 2,000 & 4,000 req/min on SQLite + PostgreSQL 17,
    0% failures, graceful degradation at 2× overload; found & fixed a ref-number race.
    Re-run against real Supabase after deploy (same scripts).
13. **SaaS readiness**: branch layer, tenant branding, onboarding — after pilot validation (§25 "only after core stable").
14. **Documentation**: Founder's Guide (zero-jargon), Deployment Guide, API docs, privacy policy/terms templates,
    backup/recovery runbook.

### Deliberately deferred (per §49 — agreed)
Billing/SSO/native apps/EMR/complex AI agents/loyalty points — untouched until paying customers exist.

## 4. ARCHITECTURE DECISIONS (kept deliberately)

- **Keep the Flask monolith** (semi-enterprise monolith): server-rendered pages are the *best* fit for
  low-bandwidth Nigerian networks; no heavy JS framework rewrite. Harden with gunicorn + workers.
- **Free-first infra path (§2)**: Supabase Free (DB/MVP) → paid Postgres on revenue; Render free (staging only,
  it says so itself) → paid host or portable Docker for production; Termii for SMS; Web Speech API for voice;
  every provider behind an interface with a fallback.
- **AI guardrails**: administrative use only, human decision authority, no clinical output (§44).

## 5. DEFINITION OF DONE for pilot (§50 MVP)

Patient: QR/Web access ✅ · Booking (A) · Queue (A) · Complaint ✅ · Feedback (A) · Referral (B) ✅
Hospital: Dashboard ✅ · Complaint mgmt ✅ · HOD assignment ✅ · SLA ✅ · Escalation ✅
Admin Manager: Inspection ✅ · 5 criteria ✅ · Voice/text explanation ✅ · PDF ✅ · Roster ✅ · Reminders ✅
Management: Dashboard ✅ · Reports ✅ · Alerts ✅
Foundation: Auth ✅ · Tenant isolation (RLS in A) · Security ✅ · Audit ✅ · Backup ✅
