# Sub-Processors — Hospital Admin Manager Suite
**Date:** 27 Aug 2026 · **Version:** 1.7.15 · **Status:** Living document — update when you add a vendor

This is the consolidated sub-processor list required by NDPA Article 29 and for hospital contracts (Gap G2).

## What this is

When a hospital signs up, they are the Data Controller. You (Hcarepro) are the Data Processor. These companies are your Sub-Processors — they touch personal data on your behalf.

## List

| # | Vendor | What they do | Data they see | Where data lives | DPA / Terms |
|---|---|---|---|---|---|
| 1 | **Supabase** (or Render Postgres if you migrate) | Database hosting (PostgreSQL) | All patient/staff data stored in DB, including `stored_file` bytes if `STORAGE_BACKEND=db` | AWS EU-West (Frankfurt) for Supabase EU, or Render Frankfurt region. Confirm in Supabase dashboard → Settings → Region. **Data residency must be stated in privacy notice (G5)** | Supabase DPA: https://supabase.com/dpa — sign it |
| 2 | **Render** | App hosting (web + worker) | All data in transit, logs, env vars | Frankfurt (eu-central) — your `render.yaml` region. Ephemeral disk wiped on deploy | Render DPA: https://render.com/dpa |
| 3 | **Meta (WhatsApp Business Cloud API)** | Deliver reports/alerts to MD/CEO via WhatsApp | MD/CEO phone, report text, patient names in alerts (no clinical data) | Meta US + EU — cross-border transfer, needs consent | Meta Business Terms |
| 4 | **Twilio** | WhatsApp/SMS fallback when Meta fails | Phone numbers, message bodies | US (Twilio) — cross-border | Twilio DPA |
| 5 | **Termii** | Primary SMS for Nigeria (OTP, alerts) | Phone numbers, OTP codes, alert text | Nigeria + US — Termii is Nigerian aggregator | Termii DPA |
| 6 | **Brevo** (active), Resend, SendGrid (fallback) | Transactional email (activation codes, reset codes) | Email addresses, 6-digit codes, staff names | EU (Brevo), US (Resend/SendGrid) | Brevo DPA: https://www.brevo.com/legal/ |
| 7 | **Cloudflare** (if you add domain) | CDN, WAF, DNS | IP addresses, request metadata, static assets | Global edge, logs in US/EU | Cloudflare DPA |
| 8 | **Sentry** (if enabled) | Error tracking | Stack traces, request path, user ID (if logged in), no patient data by default | US/EU | Sentry DPA |
| 9 | **OpenStreetMap** | Map tiles for branch location | No personal data — only map imagery requests, no patient data sent | EU | OSM policy |
| 10 | **Supabase Storage / Cloudflare R2 / AWS S3** (when you move from `STORAGE_BACKEND=db`) | Object storage for photos, PDFs, backups | Complaint evidence photos, inspection photos, hospital logo, generated PDFs, backup zips | Same region as DB if Supabase Storage, or chosen R2/S3 region | Same as DB provider |
| 11 | **Groq / Google Gemini / OpenRouter** (AI fallback chain — only when AI_FALLBACK=1 and the hospital enables it) | Generates assistant-chat replies when the hospital's own prepared answers can't | The patient's typed chat message and recent conversation history (no hospital metadata beyond public info) | US (Groq, OpenRouter) / provider regions (Google) — cross-border | Each provider's API terms; disclose in privacy notice §3 (F-036) |

## What to do with this list

1. Put this table (or a summary) in your **Privacy Notice** `/privacy` under "Who else processes your data".
2. Attach as **Annex 1** to hospital contracts.
3. Update when you add/remove vendor — e.g., when you switch from Supabase to Render Postgres, update row 1.
4. Sign DPAs with each vendor that offers one (Supabase, Render, Brevo, Twilio, Termii).

## Cross-border transfers (NDPA Article 43)

NDPA allows transfers if:
- Data subject consents (your `consent_at` timestamp), OR
- Transfer is necessary for contract performance, OR
- Recipient is in country with adequate protection, OR
- You have Binding Corporate Rules / SCCs.

Your current transfer to Meta (US) relies on **consent** + **contract necessity** (MD/CEO needs report to do job). State this in privacy notice.

## Review cadence

Review this list quarterly, or when you add new integration (e.g., adding Paystack for payments would add new row).

---
**Owner:** Founder / DPO (see DPO_AND_LAWFUL_BASIS.md)  
**Next review:** 27 Nov 2026
