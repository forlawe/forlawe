# Data Protection Impact Assessment (DPIA) — Hospital Admin Manager Suite
**Date:** 27 Aug 2026 · **Version:** 1.7.15 · **Status:** DRAFT — informal DPIA for single-hospital pilot, needs lawyer review for multi-hospital SaaS
**Gap:** G4 — required before enterprise deals

> NDPA Article 27: DPIA required when processing is likely to result in high risk to data subjects, especially sensitive data, large scale, or new tech.

Your system processes assistance needs (wheelchair, hearing, sight — disability-adjacent) which is sensitive-adjacent, plus phone numbers, NOK data. For single hospital pilot risk is low, but for multi-hospital SaaS (5,000 users) you need DPIA.

---

## 1. Description of Processing

**System:** Hospital Admin Manager Suite — Flask + PostgreSQL patient-experience platform (NOT EMR). Booking, queue, complaint, feedback, HIMS folder, reception intake, triage, consulting, onward routing, TV display, roster, inspections.

**Data subjects:** Patients (including children, elderly, pregnant), next-of-kin, staff.

**Personal data:**
- Identity: surname, first_name, other_names, sex, age/DOB, occupation
- Contact: phone, address, LGA, state
- NOK: name, relationship, phone, address
- Demographic: marital_status, religion, state_of_origin, town, tribe, ethnic_group
- Assistance needs: WHEELCHAIR, ELDERLY, PREGNANT, HEARING, SIGHT, MOBILITY, CARER, INTERPRETER — **sensitive-adjacent, separate consent (G1 fix)**
- Payer: payer_type (SELF, LAHSMA, NHIS, HMO), payer_number, payer_name
- Complaint/feedback/appointment/queue: description, category, rating, phone

**What we DO NOT process (deliberate boundary):** Diagnoses, vitals, prescriptions, lab results, blood group, genotype, allergies — enforced by failing test.

**Recipients:** Hospital staff per RBAC (SUPER_ADMIN, MD_CEO, DMD, DCST, APEX_NURSE, HEAD_ADMIN_HR, ADMIN_MANAGER, HOD, STAFF) + sub-processors (see SUB_PROCESSORS.md).

**Retention:** 2190 days (6 years) default, floor 30 days, anonymization not hard-delete, enforced by `job_retention_purge` nightly.

**Cross-border:** Meta (US), Twilio (US), Brevo (EU), Termii (NG/US) — consent basis.

---

## 2. Necessity & Proportionality

| Question | Answer |
|---|---|
| Is processing necessary for purpose? | Yes — hospital cannot open folder, contact patient, or handle complaint without name/phone/NOK. Assistance needs necessary to look after patient well (offer seat, wheelchair). |
| Is data minimization respected? | Yes — 5 fields for complaint (not 20), no clinical data, assistance codes limited to 8, not free-text disability diagnosis. |
| Is purpose limitation respected? | Yes — data collected for hospital admin, not reused for marketing. Referral engine uses anonymized counts, not personal data for prizes. |
| Is storage limitation respected? | Yes — retention purge job anonymizes after period, not forever. |
| Is accuracy ensured? | Yes — HIMS search before create prevents duplicates, edit screens allow rectification. |

---

## 3. Risks

| Risk | Likelihood | Impact | Mitigation | Residual |
|---|---|---|---|---|
| Unauthorized access — staff sees other hospital's data | Low (RLS + org_id) | High (breach) | RLS `FORCE ROW LEVEL SECURITY`, `PROTECTED_TABLES` explicit, `same_org_or_super` checks, audit chain | Low |
| Data loss — Render ephemeral disk wipes files | Medium (if STORAGE_BACKEND=disk) | High (evidence lost) | `STORAGE_BACKEND=db` default, `migrate_disk_to_db()` at boot, move to S3 for scale | Low (with db backend) |
| No backup / backup never restored | Medium (old backup was no-op on Postgres) | High (hospital loses all data) | `backup.py` CSV+zip works on Postgres, nightly job, `BACKUP_KEEP=7`, plus Supabase daily backups. **Gap D3: restore never tested — must test quarterly** | Medium until restore drill done |
| WhatsApp message stuck in SENDING (bug fixed) | Low (race) | Medium (MD/CEO never gets report) | **Fixed v1.7.15**: `process_queue` now re-queues SENDING >2 min old | Low |
| Rate limiting bypass with >1 worker (S5) | Medium when scaling | Medium (abuse) | **Fixed v1.7.15**: Redis backend if `REDIS_URL` set, fallback to memory | Low with Redis |
| GitHub token leak (S6) | High (pasted repeatedly) | High (repo takeover) | **Urgent:** Revoke token, generate short-lived, never paste in chat | High until revoked |
| Disability data without explicit consent (G1) | Medium | High (NDPA sensitive) | **Fixed v1.7.15**: separate checkbox `assistance_consent`, `assistance_consent_at` timestamp, validation requires it | Low |
| No DPO / no sub-processor list (G2,G3) | High | Medium (enterprise deal blocked) | **Fixed v1.7.15**: docs/SUB_PROCESSORS.md, DPO_AND_LAWFUL_BASIS.md, env vars `DPO_NAME`, `DPO_EMAIL` | Low |
| Data residency not stated (G5) | High | Medium (legal question) | **Fixed**: DATA_RESIDENCY.md + env var + privacy notice text | Low |
| Retention 6 years vs NDPA (G6) | Low | Medium (wrong legal claim) | Default 2190, floor 30, configurable per org via Setting, lawyer to confirm | Low |
| 5,000/sec claim vs reality (10-40 req/sec) | High | High (oversell) | Clarify: 5,000 concurrent users ≠ 5,000 req/sec. Provide real load test numbers, not architectural estimate | Medium until load test rerun |

---

## 4. Measures to Address Risks

**Technical:**
- RLS, RBAC (8 roles), CSRF, secure cookies, HSTS, CSP, X-Frame-Options, rate limiting (Redis-ready), scrypt hashing, magic-byte upload validation, 5 MB cap, audit chain, anonymization retention purge, degraded boot if DB down, pool_pre_ping, backup CSV+zip, SENTRY_DSN.

**Organizational:**
- DPO named, lawful basis register, sub-processor list, data residency statement, retention setting, backup restore drill quarterly, incident docs (INCIDENT_2026-08-15.md), test discipline (190+ tests).

**For multi-hospital scale (Phase 3):**
- Move scheduler out of web process to background worker, Redis for rate limiting/session, PgBouncer for connection pooling, object storage for files, CDN, 2-4 web instances, load balancer.

---

## 5. Consultation

- Hospital legal/compliance officer — share this DPIA + SUB_PROCESSORS + DPO_AND_LAWFUL_BASIS + DATA_RESIDENCY
- Data subjects — via privacy notice `/privacy` + consent checkboxes (general + assistance separate)
- NDPC — if high risk remains, consult per NDPA Article 27(4)

---

## 6. Decision

**For single-hospital pilot (Ijede):** Risk is **low** with mitigations in v1.7.15, provided you:
- Upgrade Render Free→Starter, Supabase Free→Pro
- Revoke GitHub token
- Do backup restore drill
- Add assistance_consent checkbox to UI
- Set DPO_EMAIL, DATA_RESIDENCY env
- Test real email + WhatsApp delivery

**For multi-hospital SaaS (5,000 concurrent users):** Risk is **medium** until Phase 3 architecture (Redis, separate scheduler, pooler, S3, CDN) + load test with real numbers + lawyer sign-off on NDPA note.

**For 5,000 requests/second sustained:** Not this architecture — would need different system. Don't claim this.

---

## 7. Review

- Review this DPIA when you add new data type (e.g., patient photo), new sub-processor, or new region.
- Next review: 27 Nov 2026 or before second hospital onboarded.

---
**Author:** Founder + Arena.ai audit  
**Approver:** [Lawyer name] — pending
