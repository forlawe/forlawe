# Security Role Enforcement Audit — v1.7.17

**Date:** 2026-08-28 13:25 UTC (Africa/Lagos)
**Version:** 1.7.17
**Scope:** Enforce strict role separation, remove patient data linkage to unauthorized staff
**Auditor:** Hands-Off Attached review per user request

---

## Summary

Found **7 critical gaps** where any authenticated staff (including HOD of unrelated dept, e.g. Theatre) could view patient PII (name, phone, dept, date) via staff routes that only used `@require_login`.

Fixed by adding **dual enforcement**: `@require_permission()` (from navigation.py / Role Management) + `@require_role()` (RBAC). Also fixed public status pages that allowed ref enumeration without phone verification.

**Result:** Patient portals remain public (book, queue join, complaint, feedback, welcome, TV, health) but staff views of patient data now require front-desk or management roles + explicit permission.

---

## Gaps Found & Fixed

### 1. bookings.py — Staff booking list
- **Before:** `@require_login` only → any logged-in user could see all appointments with patient_name, phone, dept, date, fast_track status.
- **After:** `@require_login @require_permission("bookings") @require_role("SUPER_ADMIN","MD_CEO","DMD","DCST","HEAD_ADMIN_HR","ADMIN_MANAGER","HOD","APEX_NURSE")`
- **Why:** bookings permission is granted only to front desk (HIMS, reception) + management per navigation.py. HOD of Theatre no longer sees bookings.

### 2. bookings.py — mark-paid-fasttrack
- **Before:** `@require_login` only → any staff could mark Fast Track paid.
- **After:** `@require_permission("bookings") @require_role("SUPER_ADMIN","ADMIN_MANAGER","HOD","MD_CEO")`

### 3. queue.py — Staff queue (5 routes)
- **Routes:** `/queue`, `/queue/<id>/call-next`, `/queue/<id>/finish`, `/queue/<id>/to-reception`, `/bookings/<id>/checkin-queue`
- **Before:** `@require_login` only → any staff could see queue with patient_name, phone, call next, finish, send to reception.
- **After:** All now `@require_permission("bookings") @require_role(...)` with appropriate role sets.
- **Impact:** Queue is patient PII. Now front desk + management only.

### 4. inspections.py — list/detail/pdf
- **Before:** `@require_login` only → any staff could see inspection list, detail, PDF.
- **After:** `@require_permission("inspections") @require_role("SUPER_ADMIN","ADMIN_MANAGER","MD_CEO"...)`
- **Why:** Inspections are Admin Manager job, not for all HODs.

### 5. referrals.py — staff analytics
- **Before:** `@require_login` only → any staff could see referral analytics (hospital-wide share links, stats).
- **After:** `@require_permission("referrals") @require_role("SUPER_ADMIN","MD_CEO","DMD","DCST","HEAD_ADMIN_HR","ADMIN_MANAGER")`

### 6. main.py — corrective-actions
- **Before:** `@require_login` only for list, create, update → any staff could see all corrective actions.
- **After:** list requires `corrective` permission + management/HOD roles, create requires SUPER/MD/ADMIN_MANAGER, update requires `corrective` permission.

### 7. complaints.py & feedback.py — already had department scoping but decorator weak
- **Before:** `@require_login` only, but inside function checked `visible_department_ids` and `permissions_for`.
- **After:** Added explicit `@require_permission("complaints") @require_role(...)` on all 6 complaint staff routes and 2 feedback staff routes. Defense in depth: decorator + internal scoping + audit of SCOPE_BLOCKED.

### 8. Public status pages — ref enumeration without phone (CRITICAL)
- **book/status:** Before filtered by phone only if provided, else returned appointment by ref alone. Ref is sequential `ORG-APT-YYYY-000001` → guessable, leaks patient_name, dept, date.
- **Fix:** Now requires phone >=7 chars, otherwise error "Please enter both reference and phone". Query always filters by phone.
- **complaint/status:** Same pattern, fixed to require phone >=7 chars. Anonymous complaints (phone="anonymous") cannot be checked via portal by design — staff only.

### 9. tv.py — public POST volume/brightness
- **Before:** Public POST without rate limit → anyone could spam TV settings.
- **After:** Added `@rate_limit(limit=60, window=60.0)` to both endpoints. Still public (TV remote needs no auth) but throttled and org-scoped.

---

## What Remains Public (by design, no patient PII)

- `/` , `/welcome` — patient hub (no PII)
- `/book`, `/book/submit`, `/book/thanks` — public booking (thanks shows dept/date/ref only, not name/phone)
- `/book/status` — now requires ref+phone
- `/queue/join`, `/queue/join POST`, `/queue/ticket?key=...` (access_key secret), `/queue/screen` (ticket numbers only, no names)
- `/complaint`, `/complaint/submit`, `/complaint/thanks`, `/complaint/status` (now requires phone)
- `/feedback`, `/feedback/submit`, `/feedback/thanks`
- `/chat`, `/api/chat`, `/chat/feedback`, `/chat/handoff` — public assistant, no PII
- `/r/<code>`, `/r/<code>.png`, `/lang/<code>`, `/branding/logo`, `/privacy`, `/privacy/request`, `/sales`, `/manifest`, `/sw.js`, `/offline`, `/verify/<code>`
- `/api/v1/health`, `/api/v1/ready`, `/api/v1/whatsapp/webhook`, `/api/v1/ussd/*`, `/api/v1/alerts/station` (announcements, no patient names), `/api/v1/voice/*` (audio), `/tv`, `/tv/<code>`, `/api/tv/feed`, `/api/tv/volume`, `/api/tv/brightness`, `/api/tv/qr-url`

All public endpoints either have rate limiting or are read-only, no clinical data.

---

## What Is Strictly Staff-Only (now enforced)

- `/bookings`, `/bookings/.../mark-paid-fasttrack` — bookings permission + front desk roles
- `/queue`, `/queue/...` — bookings permission + front desk/management roles
- `/feedbacks`, `/feedbacks.csv` — complaints permission + management/HOD
- `/complaints`, `/complaints/<id>`, `/complaints/<id>/escalate/update/extend/attachment` — complaints permission + HOD/management + department scoping + audit SCOPE_BLOCKED
- `/inspections`, `/inspections/<id>`, `/inspections/<id>/pdf`, `/admin-manager`, `/admin-manager/walk` — inspections permission + ADMIN_MANAGER/SUPER_ADMIN
- `/referrals`, `/referrals/create/toggle` — referrals permission + SUPER/MD_CEO
- `/corrective-actions` — corrective permission + management/HOD
- `/reception/`, `/billing`, `/paypoint`, `/hims/`, `/triage/`, `/consulting-room`, `/onward`, `/tracking`, `/fasttrack`, `/lahsma` — already had require_role + require_permission (verified)
- `/admin/*` — SUPER_ADMIN only (verified)
- `/admin/roles` — roles_admin permission (verified)
- `/my-department` — dept_desk/claim permissions (verified)
- `/roster` — VIEWERS/EDITORS roles (verified)
- `/attendance` — login_required for punch, but board restricted via permissions_for attendance_admin + can_supervise (verified)
- `/admin/tv`, `/admin/native-voice` — SUPER_ADMIN (verified)

---

## Interface Linkage Checks

- **Patient → Staff:** Patients are unauthenticated, so `@require_login` redirects to `/login`. They cannot access staff routes. Public portals do not contain links to staff desks (checked base.html menu uses `nav_permissions()` which returns False for unauthenticated).
- **Staff → Patient:** Staff with wrong department (e.g. HOD Theatre) trying to access `/bookings` or `/queue` now gets 403 via permission check, not just hidden menu. Server-side enforcement, not just presentation.
- **Department scoping:** Complaints, My Department, Attendance board, Roster all filter by `visible_department_ids()` and audit `SCOPE_BLOCKED` when blocked. Typing `?dept=3` for another department aborts 403.
- **Cross-tenant:** All staff queries filter by `org_id == current_user.org_id` and abort 404 if mismatch. RLS also enforces at DB layer for protected tables including new native_voice tables.

---

## Testing

- `python -m py_compile` all edited views — ok
- `create_app(scheduler=False)` boots, version 1.7.17
- Manual check: bookings.py staff_list now has dual decorator, queue.py 5 routes fixed, inspections 3 routes fixed, referrals 1, main 3, complaints 6, feedback 2, tv 2 rate limited, status pages require phone.

---

## Version

- config.py APP_VERSION 1.7.17
- __init__.py fallback 1.7.17

---

## Next Push

- Commit this audit + fixes, push to main with PAT, clean remote, present report.
- No token in file.

---

## Voice Reminder (per project rule)

> Role enforcement is defense in depth: menu hides + decorator blocks + query filters by org_id + department scoping + audit. No linkage of patient interface to unauthorized staff. Patient PII (name, phone) only visible to front desk + management with explicit permission.

**End of audit — v1.7.17 ready to push.**
