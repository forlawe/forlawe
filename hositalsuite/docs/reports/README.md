# Work reports — August 2026

Plain-English records of what was found, what was changed, and what was verified.
Written for the founder (non-technical), kept here so the history survives.

Read them in order; each one names the bugs it fixed and how they were proven fixed.

| # | Report | What it covers |
|---|---|---|
| — | [2026-08-14-independent-audit.md](2026-08-14-independent-audit.md) | **Start here.** Independent audit of the whole system: honest scores, 4 P0 and 8 P1 defects, ordered plan |
| 01 | [hardening-complete.md](2026-08-15-01-hardening-complete.md) | All P0 + P1 fixed: durable storage, real backups, HTTPS/CSP, account lockout, NDPA consent, Alembic |
| 02 | [site-down-first-diagnosis.md](2026-08-15-02-site-down-first-diagnosis.md) | Production outage — first diagnosis (⚠️ partly wrong; superseded by 03) |
| 03 | [outage-resolved.md](2026-08-15-03-outage-resolved.md) | The real cause: our own health check returned 503 and the host kept killing the container |
| 04 | [upgrade-requirements-audit.md](2026-08-15-04-upgrade-requirements-audit.md) | Honest status of the founder's 6 upgrade requirements (1 of 6 done at the time) |
| 05 | [day1-upgrades.md](2026-08-15-05-day1-upgrades.md) | HOD contact, staff departments/approval/delete, bigger logo, Admin Manager final comment |
| 06 | [patient-hub.md](2026-08-15-06-patient-hub.md) | New patient home page with the six services; `/` no longer demands a staff login |
| 07 | [chatbot-fixed.md](2026-08-15-07-chatbot-fixed.md) | The chat typing box was rendered off-screen; wrong answers; a 500 crash; an open redirect |
| 08 | [batch3-voice-roles-departments.md](2026-08-15-08-batch3-voice-roles-departments.md) | Voice/mic rebuilt, 4 new roles, 31 standard departments, back arrows, help-desk phone, the 404 |
| 09 | [chatbot-kb-and-ai.md](2026-08-15-09-chatbot-kb-and-ai.md) | Department dialogue library (458 intents) + free AI fallback (Groq → Gemini → OpenRouter) |
| 10 | [bulk-staff-upload.md](2026-08-15-10-bulk-staff-upload.md) | Bulk staff upload, tested against the hospital's real duty roster |

## Setup guides (in the repo root)

- **[AI_SETUP.md](../../AI_SETUP.md)** — every AI environment variable, free-tier limits, 3-minute setup
- **[OPERATIONS.md](../../OPERATIONS.md)** — plain-English runbook: backups, health checks, data requests
- **[DEPLOYMENT_GUIDE.md](../../DEPLOYMENT_GUIDE.md)** — deploying to Render + Supabase
- **[ci/README.md](../../ci/README.md)** — turning on automated testing (5-minute copy-paste)

## Outstanding actions for the founder

- Revoke any GitHub token that has appeared in a chat window
- Add `GROQ_API_KEY` in Render to enable the AI assistant (free, no card)
- Turn on Supabase backups: Database → Backups
- Admin → Structure → "Add any missing standard departments"
