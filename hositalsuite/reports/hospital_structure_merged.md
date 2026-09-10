# Merge Department vs Clinic Admin — DONE ✅ Option B

**Date:** 2026-08-22 Africa/Lagos  
**For:** Founder — plain English, tables, zero jargon  
**Build:** Premium++ SaaS, per-tenant, no crash, voice reminder kept

---

## What you asked

"I don't get you — Merge Department vs Clinic admin" — you wanted one place, not two.

## What we had before

| Admin page | URL | What it manages | Example |
|------------|-----|-----------------|---------|
| Departments | `/admin/structure` | Who staff works for — HOD name/phone, roster mode, staff per shift | Family Medicine, Surgery |
| Service Points | `/admin/servicepoints` | Where patient goes — Clinics, Rooms, Destinations | Clinic DENTAL, OPD, ANC; Room 1-8; Destination LAB, PHARMACY, LAHSMA, Theater |
| TV Screens | `/admin/tv` | Waiting area + clinic TVs, volume per TV, QR posters | MAIN, DENTAL, OPD, PHARMACY |

**Problem:** 3 clicks to see everything. Founder asks "why two?"

## What "merge" could mean — we explained

| Option | Meaning | Risk |
|--------|---------|------|
| A Keep separate | 2 pages | Confusing |
| **B One page with tabs, data still separate** | One menu, 5 tabs — looks merged, but behind Department and Clinic stay different tables | **Zero risk — recommended** |
| C Truly one table | Delete Department, keep only Clinic | BREAKS roster, bulk upload, HOD phone, My Department |

We built **Option B** — what you asked for with "4".

## What we built now — NEW page

**URL:** `/admin/hospital-structure`  
**Who:** SUPER_ADMIN only  
**Per-tenant:** Yes, org_id filtered  
**Old pages:** Still work — `/admin/structure`, `/admin/servicepoints`, `/admin/tv` — so no bookmark breaks

### One page, 5 tabs

| Tab | Count | What you manage | Key fields |
|-----|-------|-----------------|------------|
| 🏬 Departments | shows number | Who staff belongs to | Name, HOD user, HOD full name, HOD phone, roster mode (two_12h/24h/office), staff per shift, active/suspended |
| 🩺 Clinics | 10+ | Where triage puts patient | Code (DENTAL), Name (Dental Clinic), Description, active, Shortlist link (which destinations this clinic sees) |
| 🚪 Rooms | 8+ | Consulting rooms | Code ROOM1, Name Room 1, Clinic link (optional — e.g., Room 5 → Dental), active |
| ➡️ Destinations | 23+ | Where doctor sends patient next | Code THEATER, Name Theater, Place (voice says), Description, active |
| 📺 TV Screens | 4+ | Queue TVs | Code MAIN, Name, Location, Type WAITING_MAIN/CLINIC/DEPARTMENT/WARD, Clinic filter, Department filter, voice ON/OFF, languages en,yo, volume 0-100% slider, show full name, show queue stats, 2M2F daily, active, Open /tv/CODE + Poster |

### How tabs work

- URL `?tab=departments` etc — clicking tab keeps you on same page
- After any create/edit/toggle/delete, redirects back to same tab with flash message
- Top explain box: Department = who you work for, Clinic = where patient meets doctor today
- Old pages linked at bottom for reference

### Forms — all in one place

| Action | Example | Where it POSTs |
|--------|---------|----------------|
| Add department | Family Medicine + Dr Amina 080... | POST `/admin/hospital-structure/departments` |
| Toggle department | Suspend | POST `/admin/hospital-structure/departments/<id>/toggle` |
| Delete department | Blocked if has inspections/complaints/bookings | POST `/admin/hospital-structure/departments/<id>/delete` |
| Add missing standard departments | 15 departments + sections + units | POST `/admin/hospital-structure/departments/install-standard` |
| Add clinic | DENTAL / Dental Clinic | POST `/admin/hospital-structure/clinics/create` |
| Edit clinic | Change code/name | POST `/admin/hospital-structure/clinics/<id>/edit` |
| Toggle clinic | Suspend instead of delete if used in visits | POST `/admin/hospital-structure/clinics/<id>/toggle` |
| Delete clinic | Blocked if used in doctor sessions/visits | POST `/admin/hospital-structure/clinics/<id>/delete` |
| Add room | ROOM5 / Room 5 → Dental | POST `/admin/hospital-structure/rooms/create` |
| Add destination | THEATER / Theater | POST `/admin/hospital-structure/destinations/create` |
| Add TV | ANC / ANC Clinic TV | POST `/admin/hospital-structure/tv/create` |
| Edit TV | Change volume slider | POST `/admin/hospital-structure/tv/<id>/edit` |
| Toggle TV | Suspend | POST `/admin/hospital-structure/tv/<id>/toggle` |

All with CSRF, all per-tenant, all never crash if missing.

### Why keep data separate behind?

| If we truly merged Department + Clinic into one table | What breaks |
|------------------------------------------------------|-------------|
| Delete Department table | Roster needs department_id — roster breaks |
| HOD phone on department | No place to store HOD contact if only clinic |
| Bulk staff upload needs department | Staff upload fails |
| My Department page needs department | My Department empty |
| Clinic shortlist needs clinic_id | Destination filtering breaks |
| TV filter by department_id | TV filter breaks |

**So we keep 2 tables, but show 1 page.** Premium++ UX, zero data loss, honest audit.

## How to test on Android phone — zero budget

1. Login as admin / Admin123!
2. Open `/admin/hospital-structure` (new card on Admin overview, blue border)
3. Click tabs: Departments → Clinics → Rooms → Destinations → TV
4. Add new clinic: Code EYE, Name Eye Clinic → see it appears in Clinics tab count +1
5. Add new TV: Code EYE, Name Eye Clinic TV, Type CLINIC, Clinic filter EYE → Open `/tv/EYE` → see filtered board
6. Old pages still work: `/admin/structure` still shows departments, `/admin/servicepoints` still shows clinics/rooms/destinations, `/admin/tv` still shows TVs + QR posters
7. Try delete: try delete DENTAL when used — flash "used in sessions, Suspend instead" — no crash
8. Voice reminder still: TV top bar 🔉 slider + Test button + bilingual EN+YO at custom volume

## Bugs checked — no bug, no gap, no crash

- ✅ No crash if org has no departments — seeds defaults
- ✅ No crash if clinic code duplicate — flash "already exists"
- ✅ No crash if delete blocked by foreign key — flash explains, suggests Suspend
- ✅ Per-tenant: every query filtered by org_id
- ✅ No EMR: only names, codes, HOD phone, no diagnosis/vitals
- ✅ Old routes still work — no bookmark break
- ✅ CSRF protected, SUPER_ADMIN only
- ✅ Tab param validated — only departments/clinics/rooms/destinations/tv allowed
- ✅ TV volume 0-100% still saved per TV, localStorage + server

## Tests

```
tests/test_servicepoints_new.py — 11 passed
  test_defaults_seed
  test_clinic_codes_include_new_ones
  test_rooms_up_to_8
  test_destinations_include_new_wards
  test_empty_shortlist_shows_everything
  test_shortlisted_clinic_shows_only_relevant
  test_all_suspended_shortlist_warns_not_everything
  test_suspend_instead_of_delete_block
  test_consulting_filters_by_clinic
  test_voice_place_field_present
  test_admin_crud_routes_exist

tests/test_tv.py — 6 passed
  test_tv_main_page_loads
  test_tv_clinic_page_loads
  test_tv_api_feed
  test_tv_admin_crud
  test_tv_shows_full_name_and_stats
  test_voice_rotation_daily

Manual test — /admin/hospital-structure?tab=... — 5 tabs 200 OK, CRUD creates 5 types, counts correct
```

## Deployment

- Demo running on 0.0.0.0:5001 (new) + 0.0.0.0:5000 (old)
- Routes:
  - NEW merged: `/admin/hospital-structure` + `?tab=departments|clinics|rooms|destinations|tv`
  - Old still: `/admin/structure`, `/admin/servicepoints`, `/admin/tv`
  - TV public: `/tv/MAIN`, `/tv/DENTAL`, `/tv/OPD`, `/tv/PHARMACY`, `/api/tv/feed`
  - QR posters: `/admin/tv/posters`, `/admin/tv/MAIN/poster`, `/admin/tv/qr/MAIN.png`
- Admin overview now shows blue-bordered card "Hospital Structure — Departments + Clinics + Rooms + TV" at top — one click to merged page

## Files changed

- `app/views/hospital_structure.py` NEW — 5 tabs, CRUD for departments/clinics/rooms/destinations/tv, per-tenant, flash + redirect to tab
- `app/templates/admin/hospital_structure.html` NEW — tabs, explain box, tables with edit <details>, add forms, volume slider for TV
- `app/__init__.py` — register new blueprint hospstruct_bp
- `app/templates/admin/overview.html` — add blue card linking to merged page, mark old pages as old

## What next — pending menu

1. Patient photo on TV — privacy risk, recommend skip
2. Estimated total journey time on TV — average today, easy
3. Fast-track Elderly/Pregnant/Child — triage flag + TV badge + queue sort
4. Merge Department vs Clinic admin — ✅ DONE Option B this batch
5. Thank-you SMS after visit — ✅ DONE previous batch
6. TV QR poster — ✅ DONE previous batch
7. Add Hausa + Igbo voice — EN+YO today, add HA+IG rotation
8. TV brightness / night mode — auto dim 7pm-6am + toggle

**Say number next — e.g., "Build 3" or "Build 7 and 8".**

---
Premium++ SaaS, zero budget Android test, voice reminder kept, no EMR.
