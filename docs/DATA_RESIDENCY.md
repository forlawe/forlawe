# Data Residency & Cross-Border Transfers — NDPA Article 43
**Date:** 27 Aug 2026 · **Version:** 1.7.15 · **Gap:** G5

## Current Deployment (as of 27 Aug 2026)

| Layer | Provider | Region | How to verify |
|---|---|---|---|
| Web app | Render | Frankfurt (eu-central) — `render.yaml` `region: frankfurt` | Render dashboard → Service → Settings → Region |
| Database | Supabase | Check Supabase dashboard → Project Settings → Database → Region — likely `eu-west-1` (Ireland) or `eu-central-1` (Frankfurt) or `ap-southeast-1` — **you must confirm** | Supabase dashboard |
| Backups (CSV zip) | Stored in DB via `stored_file` table (`STORAGE_BACKEND=db`) | Same as DB | Same as DB |
| File uploads (photos, logos, PDFs) | Same as DB (if `STORAGE_BACKEND=db`) | Same as DB | Same as DB |
| Future object storage | Supabase Storage or Cloudflare R2 or S3 | You choose — recommend same as DB region | Set `S3_REGION` env |
| WhatsApp | Meta (US + EU) | US/EU | Meta docs |
| SMS | Termii (Nigeria + US), Twilio (US) | NG/US | Termii/Twilio docs |
| Email | Brevo (EU), Resend/SendGrid (US) | EU/US | Brevo dashboard |

## Why this matters for NDPA

NDPA Article 43: Transfer of personal data outside Nigeria is allowed if:
1. Data subject consents, OR
2. Transfer is necessary for contract performance, OR
3. Recipient country has adequate protection, OR
4. You have SCCs/BCRs.

Your transfers to Meta (US), Twilio (US), Brevo (EU) rely on **consent** (`consent_at` timestamp) + **contract necessity** (hospital needs to send report to MD/CEO).

You must **state residency plainly** in privacy notice — hospitals' legal teams ask this first.

## Privacy Notice Text (copy-paste)

> **Where your data lives**
> 
> Your hospital folder, bookings, complaints, and feedback are stored in a PostgreSQL database hosted in [YOUR_SUPABASE_REGION, e.g., EU-West-1 (Ireland)] by Supabase, and our application runs in Frankfurt, EU (Render). Backups are stored in the same database region.
> 
> When you provide a phone number for WhatsApp/SMS or email for codes, that phone/email and the message content is sent to:
> - Meta (WhatsApp) — US/EU
> - Termii / Twilio (SMS) — Nigeria/US
> - Brevo (email) — EU
> 
> We rely on your consent for these transfers, which you give when you provide your phone/email and tick the consent box. Assistance needs (wheelchair, hearing, etc.) have a separate consent box because they are more sensitive.
> 
> If you want your data to stay only in Nigeria, we can deploy a private instance on Render Nigeria (when available) or your own server — contact our DPO.

## How to set data residency explicitly

**Env var:** `DATA_RESIDENCY="Frankfurt, EU (Render Web) + eu-west-1 (Supabase DB, Ireland)"`

Set in Render → Environment → `DATA_RESIDENCY`.

Then in `templates/privacy.html`:
```html
<p>Data residency: {{ config.DATA_RESIDENCY }}</p>
```

## Render Postgres Alternative (your question)

If you move DB to Render Postgres:

- Region: Frankfurt (same as web) — **lower latency (5-10ms vs 20-80ms cross-provider)**, private networking (no public internet for DB traffic), single bill, no Supabase 7-day pause bug.
- Cost: Basic $7/mo (1 GB), Standard $20/mo (4 GB + HA $7). Supabase Pro $25/mo (8 GB + pooler + dashboard).
- Caveat: Render Postgres does NOT ship PgBouncer — you must add pooler yourself before >1 web instance, or use Supabase pooler.
- Migration steps: See `docs/RENDER_DB_MIGRATION.md`

## Checklist

- [ ] Confirm Supabase region in dashboard, update `DATA_RESIDENCY` env
- [ ] Update `/privacy` page with residency statement
- [ ] Add residency to hospital contracts
- [ ] If using WhatsApp/SMS/email, ensure consent covers cross-border transfer (it does via `consent_at`)
- [ ] For enterprise customers who require Nigeria-only residency, plan private deployment (Render private network or on-prem)

---
**Owner:** DPO  
**Next review:** When you change hosting provider or region
