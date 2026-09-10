# Data Protection Officer & Lawful Basis Register — NDPA 2023
**Date:** 27 Aug 2026 · **Version:** 1.7.15 · **Status:** DRAFT — needs lawyer sign-off before enterprise contracts
**Gaps closed:** G3 (named DPO), G1 (separate consent for disability data), G5 (data residency), G6 (retention check)

---

## 1. Data Protection Officer (G3)

| Field | Value |
|---|---|
| **DPO Name** | Hospital Admin / Founder (replace with real person when you have one) |
| **DPO Email** | Set `DPO_EMAIL` env var — e.g., `dpo@hcarepro.com` — and show on `/privacy` page |
| **DPO Phone** | Optional — same as hospital help desk for pilot |
| **Responsibility** | Respond to data-subject requests (access, erasure, rectification), maintain this register, review sub-processors quarterly |

**Code change:** `app/config.py` now reads `DPO_NAME`, `DPO_EMAIL` from env. Set them in Render → Environment → `DPO_NAME`, `DPO_EMAIL`.

**Privacy page:** Update `templates/privacy.html` to show:
```
Data Protection Officer: {{ config.DPO_NAME }} — {{ config.DPO_EMAIL }}
Contact us for data requests: /privacy/request
```

---

## 2. Lawful Basis Register (NDPA Article 25)

| Data | Purpose | Lawful Basis | Evidence in Code | Retention |
|---|---|---|---|---|
| Patient surname, first_name, phone, address, NOK name/phone/relationship | Open folder, contact patient, emergency contact | **Consent** (patient provides at Reception/HIMS) + **Contract** (hospital needs it to provide care) | `Patient.consent_at` timestamp, `ReceptionIntake` creation, `hims.validate()` | 6 years (2190 days) then anonymize via `job_retention_purge` — floor 30 days enforced |
| **Assistance needs (WHEELCHAIR, HEARING, SIGHT, etc.)** — disability-adjacent | Look after patient well (offer seat, wheelchair, interpreter) — NOT clinical | **Explicit separate consent** (G1 fix) — more sensitive than name/phone | `Patient.assistance`, `Patient.assistance_consent_at`, `ReceptionIntake.assistance_consent_at`, separate checkbox `assistance_consent` required if assistance provided | Same as above, but consent timestamp separate |
| Preferred language (en, yo, ha, ig) | Greet patient in own language | **Consent** | `Patient.preferred_lang` | Same |
| Complaint description, category, phone (if not anonymous) | Resolve complaint, SLA, escalation | **Consent** (patient chooses to submit) + **Legitimate Interest** (hospital must handle complaints) | `Complaint.consent_at`, `is_anonymous` flag, anonymous path stores no phone | Anonymize after retention period |
| Appointment patient_name, phone | Book visit, track no-shows | **Consent** | `Appointment.consent_at` | Anonymize after retention |
| Patient feedback rating, comment, phone | Measure satisfaction, service recovery | **Consent** | `PatientFeedback.consent_at` | Anonymize after retention |
| Queue ticket patient_name, phone | Join queue, track turn | **Consent** | `QueueTicket.anonymized_at` | Anonymize after retention |
| Staff roster, attendance, scores | Duty management, payroll, performance | **Employment contract / Legitimate Interest** | `DutyRoster`, `StaffAttendance` | 6 years for audit, then anonymize |
| User account (username, email, phone, role) | Sign in, RBAC | **Contract / Legitimate Interest** | `User` table | Until account deleted + audit retained |

**What we explicitly DO NOT collect (strongest compliance asset):**
- Diagnoses, vital signs, prescriptions, lab results, blood group, genotype, allergies.
- Enforced by test `test_the_folder_holds_no_medical_record` — if anyone adds clinical column, test fails.

---

## 3. Consent Handling (G1 fix details)

**Before fix:** One checkbox for all patient data, including wheelchair/hearing needs (disability data is more sensitive under NDPA).

**After fix (v1.7.15):**
- General patient data: `consent_at` set when folder created (HIMS or Reception → HIMS flow).
- Assistance needs: **separate checkbox** `assistance_consent` required if any `assistance` code selected.
  - In `app/hims.py` `validate()`: if `assistance` non-empty and no `assistance_consent`, error: "Assistance needs are sensitive — please tick separate consent box".
  - In `app/reception.py` `clean_form()`: same check.
  - Stored as `assistance_consent_at` timestamp (DateTime) on `Patient` and `ReceptionIntake`.
  - Migration adds columns via `app/migrate.py` COLUMNS (idempotent).

**UI change needed:** In `templates/hims/register.html` and `templates/reception/new.html`, add:
```html
{% if assistance_needs %}
  <label><input type="checkbox" name="assistance_consent" value="1"> I consent to the hospital recording my assistance needs (wheelchair, hearing, etc.) to look after me well. This is separate from general consent.</label>
{% endif %}
```

---

## 4. Data Residency (G5)

| Component | Current | Residency Statement for Privacy Notice |
|---|---|---|
| Web app | Render Frankfurt (eu-central) | Data processed in Frankfurt, EU |
| Database (Supabase) | AWS EU-West (check dashboard → Settings → Region) | Data stored in [your Supabase region] — e.g., EU-West-1 (Ireland) or EU-Central-1 (Frankfurt) — confirm and state |
| Database (Render Postgres if migrated) | Render Frankfurt | Data stored in Frankfurt, EU |
| Backups (CSV zip in stored_file) | Same as DB (in DB) | Same residency as DB |
| Object storage (future S3) | Supabase Storage same region, or R2 EU | State chosen region |

**Set env:** `DATA_RESIDENCY="Frankfurt, EU (Render) + EU-West-1 (Supabase)"` — shown in health? No, but used in privacy notice.

**Privacy notice text:**
> Your data is stored in Frankfurt, EU (Render hosting) and [Supabase region]. Backups are stored in the same region. If you use WhatsApp/SMS/email, your phone/email and message content is transmitted to Meta/Twilio/Termii/Brevo which may process data outside Nigeria — we rely on your consent for this.

---

## 5. Retention (G6)

**Code:** `app/scheduler.py::job_retention_purge`:
- Reads `retention_days` setting per org (default 2190 = 6 years)
- Floor `max(30, days)` — never purge more aggressively than 30 days, even if misconfigured
- Anonymizes (not hard-deletes) Complaints, Appointments, Feedback, QueueTickets past cutoff — keeps stats, destroys PII
- Audit-logged, idempotent

**Is 6 years correct under NDPA vs old NDPR?**
- NDPR (old) said 6 years for health-related? Actually NDPR didn't specify, but many Nigerian hospitals keep 6 years for medical records.
- NDPA 2023 + GAID: retention must be "no longer than necessary" for purpose. For hospital admin data (not clinical), 6 years is defensible for audit/compliance, but you should confirm with lawyer.
- **Action:** Keep 2190 default, but add setting in Admin → Settings → Retention Days so hospital can lower to 1-2 years if they want. Floor 30 days prevents accidental purge.

**Set env:** `RETENTION_DAYS=2190` (default) — already in render.yaml.

---

## 6. DPO Tasks (for founder)

- [ ] Set `DPO_EMAIL` in Render env to real email you check daily
- [ ] Update `/privacy` page with DPO name/email and data residency statement
- [ ] Add assistance_consent checkbox to HIMS and Reception forms (UI)
- [ ] Review sub-processors list (SUB_PROCESSORS.md) quarterly
- [ ] Test data-subject request flow: `/privacy/request` → access → erasure
- [ ] Schedule backup restore drill quarterly (see OPERATIONS.md)

---
**Next:** DPIA.md (G4) and DATA_RESIDENCY.md (G5 detailed)
