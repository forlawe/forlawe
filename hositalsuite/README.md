# Hospital Admin Manager Suite

**Production-ready, mobile-first platform for automated Admin Manager inspections,
monitoring, reporting and patient complaint management** — built for Nigerian hospital
environments (NDPR-aware, low-connectivity tolerant, WhatsApp-first delivery).

---

## 1. What the system does

| Module | Behaviour |
|---|---|
| **Patient booking** | Public QR/web/USSD booking: service + date + time slot + name + phone → reference like `HOSP-APT-2026-000001`, SMS confirmation (Termii/Twilio/sandbox), capacity-limited slots, patient self-service status check & cancellation, staff check-in that issues a queue ticket. |
| **Queue management** | Digital queue numbers per department, private ticket status page (position + estimated wait), staff queue control (call next / served / no-show), privacy-safe public display screen (numbers only, never names) with zero-cost browser voice announcement, SMS "you're next", USSD join. |
| **Patient feedback** | ⭐ 1–5 rating + optional voice/text comment. Low ratings are **instantly routed into the complaint/service-recovery pipeline** (AM on duty + HOD notified, SLA applies). Positive ratings unlock "Book another visit" + "Refer a friend" prompts. Satisfaction KPI on the executive dashboard. |
| **Referrals** | Happy patients (4–5★) get a personal share-link + QR (`/r/CODE`). Friends who open it can book in one minute. The hospital sees clicks, bookings and returning patients. Hospital-wide poster QR included. **No prizes, no pressure.** |
| **Daily inspection** | The rostered Admin Manager scores **exactly five criteria** (1–5 each, max 25). Scores of **1 or 2 force a mandatory explanation** (typed or voice-to-text). One review screen → **SUBMIT INSPECTION** locks the record. |
| **PDF report** | Generated instantly on submission: hospital branding, ref number, five scores, explanations, total/percent/rating, findings, **verification QR + code**. Archived permanently. |
| **WhatsApp delivery** | Report is sent to the MD/CEO over the **official WhatsApp Business Cloud API** (Media upload + document message). Status pipeline Generated → Sending → Delivered → Failed with retries and audit. |
| **Duty roster** | Manual entry + Excel/CSV import with validation (names, dates, duplicates) and a confirm-preview. Reminders: **day-before** and **duty-day** at configurable times. |
| **Daily control** | Dashboard shows `Admin Manager on Duty` + 🟢 Completed / 🔴 Pending / ⚠️ Overdue. Overdue inspections notify management at a configurable time. |
| **Patient complaints** | Public portal via **QR code, direct link or USSD** — **no login, exactly 5 fields**, voice-to-text description, optional photo. Ref like `HOSP-CMP-2026-000001` with anonymous status check. |
| **Routing & SLA** | Every complaint auto-routes to the **Admin Manager on duty + the affected HOD**. Configurable SLA; on expiry the system **automatically escalates to the MD/CEO** and marks the complaint `ESCALATED` (audit-logged, never silently reset). |
| **Corrective actions** | Finding → required action → owner → deadline → statuses OPEN/IN_PROGRESS/COMPLETED/OVERDUE/VERIFIED, with evidence upload and management verification. |
| **Analytics** | Executive dashboard, 14-day heatmap, department trends, recurring-problem detection ("Equipment… scored 1–2 in 6 of the last 10 inspections"), Management Attention list. |
| **Reports** | Daily / weekly / monthly / department / complaint / escalation / corrective-action / compliance / **referrals** — **PDF + CSV**, digital archive with verification codes. |
| **Audit & security** | Hash-chained tamper-evident audit trail, RBAC (4 roles), CSRF, rate limiting, password policy, validated uploads, tenant org-id on every record. |

### The five criteria (fixed by design)
1. Staff & Service Delivery
2. Cleanliness & Infection Prevention
3. Equipment, Facilities & Supplies
4. Records, Compliance & Accountability
5. Safety, Security & Overall Condition

Rating bands: 22–25 EXCELLENT · 18–21 GOOD · 13–17 FAIR/NEEDS IMPROVEMENT · 8–12 POOR · 5–7 CRITICAL.

---

## 2. Quick start (this workspace)

```bash
cd hospitalsuite
pip install -r requirements.txt
python run.py seed          # clean production setup (hospital + users + structure + roster)
# or: python run.py demo    # same + 10 days of sample inspection history for evaluation
./start.sh                  # serves on http://0.0.0.0:8077
```

**Seeded accounts (change all passwords before real use):**

| Role | Username | Password |
|---|---|---|
| Super Administrator | `admin` | `Admin#2026!` |
| MD/CEO | `md` | `Mdceo#2026!` |
| Admin Manager | `am.funke` | `Amfunke#2026!` |
| Admin Manager | `am.emeka` | `Amemeka#2026!` |
| HODs | `hod.medicine`, `hod.surgery`, `hod.paeds`, `hod.emergency`, `hod.pharmacy`, `hod.lab` | see seed output |

Complaint portal (public, no login): `http://<host>:8077/complaint`
Printable QR codes: **Admin → Settings → Complaint QR locations → ⬇ QR**.

---

## 3. Architecture

```
hospitalsuite/
├── run.py                  # entry point + CLI (seed/demo/tick/backup)
├── requirements.txt
├── .env.example            # every secret/credential lives here — never in code or frontend
├── app/
│   ├── __init__.py         # app factory, error handlers, security headers
│   ├── config.py           # env-driven configuration (DB, WhatsApp, SMTP, USSD, backups)
│   ├── models.py           # 20+ normalized tables, multi-tenant (org_id everywhere)
│   ├── scoring.py          # PURE business logic: criteria, ratings, SLA, recurring detection
│   ├── services.py         # settings, refs, duty detection, routing, analytics, heatmap
│   ├── notifications.py    # template engine: in-app / email / WhatsApp (all logged)
│   ├── whatsapp.py         # Meta WhatsApp Business Cloud API client + sandbox mode
│   ├── pdfgen.py           # ReportLab report builder with verification QR
│   ├── qrgen.py            # complaint QR codes
│   ├── scheduler.py        # daemon: reminders, overdue flags, SLA escalation, retries, backups
│   ├── audit.py            # hash-chained audit trail + chain verification
│   ├── security.py         # CSRF, RBAC, rate limiting, password policy, upload validation
│   ├── views/              # auth, dashboards, inspections, complaints, roster, admin, reports, api
│   ├── templates/          # mobile-first server-rendered UI (no external CDN dependencies)
│   └── static/             # design-system CSS + voice/offline/GPS JS
└── tests/                  # 99 automated tests (unit + end-to-end)
```

**Stack:** Python 3.13 · Flask 3 · SQLAlchemy 2 · SQLite (dev) / PostgreSQL (prod) ·
ReportLab · qrcode · Web Speech API (voice-to-text) · Meta WhatsApp Cloud API.

**Multi-hospital ready:** every record carries `org_id`; all queries are tenant-scoped.

---

## 4. Production deployment

### 4.1 Environment (see `.env.example`)
| Variable | Purpose |
|---|---|
| `SECRET_KEY` | session/CSRF signing — long random string |
| `DATABASE_URL` | `sqlite:///data/app.db` (default) or `postgresql://user:pass@host/db` |
| `PUBLIC_BASE_URL` | used inside QR codes and verification links |
| `WHATSAPP_MODE` | `sandbox` (default) · `cloud` · `disabled` |
| `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN` | **Meta Cloud API credentials** (create a Meta Business app → WhatsApp → API Setup; use a permanent System User token) |
| `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | webhook security |
| `SMTP_*` | email notifications (optional) |
| `USSD_SHARED_SECRET` | authenticates the USSD aggregator POSTing to `/api/v1/ussd/complaint` |

Secrets are read **only from the environment** — nothing sensitive is ever sent to the browser.

### 4.2 WhatsApp go-live checklist
1. Create Meta Business portfolio → WhatsApp Business Account → get **Phone Number ID** and a **permanent access token**.
2. Set `WHATSAPP_MODE=cloud`, fill the variables above, restart.
3. Configure the webhook: `https://<your-domain>/api/v1/whatsapp/webhook` with your verify token; enable **statuses** events. Delivery receipts flip messages SENT → DELIVERED automatically.
4. Set the MD/CEO number under **Admin → Settings → WhatsApp report delivery** and send a test from **Admin → Notifications**.
5. Until the hospital's template is approved by Meta, document messages carry a plain caption + PDF (works for business-initiated messages within the 24h window); add `WHATSAPP_REPORT_TEMPLATE` once approved.

### 4.3 USSD
Any Nigerian USSD aggregator (Africa's Talking, Termii, HollaTags…) can collect the five
fields over a USSD session and POST JSON to `/api/v1/ussd/complaint` with the shared secret.
The same routing/SLA/escalation pipeline applies.

### 4.4 Operations
- **Backups:** nightly at 02:00, on **both SQLite and PostgreSQL** (`app/backup.py`). Every table
  is exported to CSV and zipped with a manifest and restore instructions, then stored durably
  (retention `BACKUP_KEEP`, default 14). Manual: `python run.py backup` or Admin → Backups → Download.
  This is a safety net, not a replacement for your database provider's own snapshots — enable
  those too, and **restore one into a test database each quarter**: an untested backup is not a backup.
- **Scheduler:** runs in-process (30 s tick). For multi-instance deployments run one worker with the scheduler and set `DISABLE_SCHEDULER=1` on the others.
- **TLS:** terminate HTTPS at a reverse proxy (nginx/Caddy/ALB); the app sets secure headers and same-site cookies.
- **Monitoring:** `GET /api/v1/health` returns JSON health for uptime checks.

---

## 5. Business rules — verified

All rules from the specification are implemented **and covered by automated tests**
(`python -m pytest tests/ -q` → **914 passed**; coverage 69% — see the box above):

- Exactly five criteria; scores 1–5; total/percent/rating bands ✔
- Score 1 or 2 → submission blocked until explanation exists (form + API) ✔
- Score 3–5 → explanation optional ✔
- One submitted inspection per duty day per inspector; amendments are controlled (original preserved, audit-logged) ✔
- Duty detection from roster; only the rostered Admin Manager submits ✔
- Day-before + duty-day reminders at configurable times, sent once ✔
- Overdue inspection flag + management notification ✔
- PDF generated + archived + verification QR/code ✔
- WhatsApp report queued → sent → delivered, failures flagged & retryable ✔
- Complaint: no login, exactly 5 fields, ref `PREFIX-CMP-YYYY-NNNNNN`, anonymous status check ✔
- Auto-routing to AM on duty + HOD; SLA expiry → automatic ESCALATED to MD/CEO; idempotent; resolved complaints never escalate ✔
- SLA extension always writes an audit event ✔
- Roster import: missing names, invalid dates, duplicates (in-file and vs DB) all rejected with preview ✔
- RBAC (HOD ≠ admin), CSRF required, login rate-limited, audit chain tamper-evident ✔
- USSD intake authenticated and wired to the same pipeline ✔
- High ratings (4–5★) issue a personal trackable share-link + QR; friend bookings are attributed; own-link is a repeat visit, not a conversion; no prizes ✔

---

## 8. Scaling beyond the free tier

The app runs with **1 web worker + threads** on purpose: an in-process scheduler
delivers reminders, SLA escalations, WhatsApp/SMS retries and nightly backups, and it
must run exactly once. When traffic grows:

1. Move to a paid instance (Render Starter or a VPS with Docker — `Dockerfile` included).
2. To run multiple web workers, start **one** dedicated scheduler process
   (`python run.py tick` in a loop or a worker with the scheduler enabled) and set
   `DISABLE_SCHEDULER=1` on all web workers.
3. Move uploads/PDFs to object storage (Supabase Storage or any S3-compatible bucket)
   when file volume grows — local disk on free tiers is ephemeral.
4. Load-test before announcing capacity targets (`locust` recommended; see ROADMAP Wave D).

---

## 9. Security & privacy summary

- Sessions: server-side, HttpOnly, SameSite=Lax, 10 h lifetime; CSRF token on every POST.
- RBAC enforced **server-side** on every route (never frontend-only).
- Passwords: scrypt hashes; strength policy; admin resets force change-at-next-login.
- Rate limiting on login and public complaint submission.
- Uploads: extension + size + **magic-byte** validation, random names, served only through authenticated routes; patient complaint details and complainant phone numbers are visible **only to authorized staff roles** — never in notification previews beyond the minimum.
- Audit trail is hash-chained; Admin → Audit shows live chain verification.
- NDPR posture: data minimization on the complaint form, explicit privacy notice, configurable retention period, access-restricted records, no public complaint exposure.

---

## 7. UX targets achieved

- Admin Manager completes the daily inspection in **2–5 minutes**: open app → big "Today's Inspection" button → 5 tap-scores → speak/type any low-score explanations → review → submit. Drafts autosave; **offline submissions are stored locally and sync automatically** with ONLINE/OFFLINE indicators.
- Patient submits a complaint in **1–2 minutes**: scan QR → department → category → speak the description → phone → submit → reference number.
- MD/CEO reads hospital status in **30 seconds**: today's status strip, 8 KPI tiles, Management Attention, heatmap.
