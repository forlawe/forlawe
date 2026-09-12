# SECURITY ROLE AUDIT — v1.7.18 STRICT DEFAULTS
Date: 2026-08-28 Africa/Lagos
Version: 1.7.18
Purpose: Enforce least-privilege for HOD, APEX_NURSE, STAFF, ADMIN_MANAGER day-on-duty

## Summary of Changes (v1.7.17 → v1.7.18)

### 1. HOD and APEX_NURSE (HOD Nursing Services) — LIMITED to own Department/Section/Unit
- **Before**: APEX_NURSE scope=HOSPITAL → sees_whole_hospital True → could see ALL departments, all bookings, all queues, all rosters
- **After**: APEX_NURSE scope=DEPARTMENT (same as HOD) → visible_department_ids = own dept + headed depts + UserRole extra grants only
- **Roster**: can_manage() now checks:
  - HOD: dept.hod_user_id==user.id OR user.department_id==dept_id OR UserRole extra grant → own dept only
  - APEX_NURSE: same as HOD
  - Otherwise False → cannot create/edit/delete/upload roster for other depts
- **Bookings & Queue**: staff_list() and staff_queue() now filter by visible_department_ids → HOD/APEX only see bookings/queue for own dept(s)
- **Attendance**: supervise_dept_ids() for HOD/APEX returns only own dept ids → can sign-in only own staff when issue
- **Permissions**: HOD and APEX_NURSE now have roster_edit and attendance_admin for own dept only (previously missing), System Admin upgrades via Role Management if wider needed
- **Navigation**: permissions_for() for HOD/APEX no longer grants front desks unless actually works in front dept (fail closed if no dept set)

### 2. System Admin Upgrades
- SUPER_ADMIN retains master key (admin permission → all MENU_KEYS True)
- HEAD_ADMIN_HR retains hospital-wide sight (visible_departments all, can_manage any dept)
- System Admin can upgrade HOD/APEX via:
  - Role Management screen: add extra departments via UserRole (department_id)
  - Change role scope HOD/APEX from DEPARTMENT to HOSPITAL if truly needed
  - Grant extra permissions via tick-list

### 3. All STAFF — ONLY own Department/Section/Unit Activities and Department Roster view/read-only
- **Before**: STAFF role had dept_desk, roster view, but visible_departments returned only own dept (ok), but could still potentially see other dept via lack of filter in some views
- **After**: 
  - permissions_for() for STAFF: allowed only {dept_desk, dept_claim, dept_staff, roster, attendance} → all other perms False, roster_edit=False, attendance_admin=False, dept_manage=False
  - visible_departments() for STAFF: only own department_id (or UserRole grants) → cannot see other depts in roster dropdown
  - roster.py VIEWERS includes STAFF (read-only own dept), EDITORS excludes STAFF → cannot create/edit/delete/upload
  - can_manage() returns False for STAFF always → 403 on roster create/edit/delete/upload
  - bookings and queue staff endpoints require HOD/APEX_NURSE or higher, not STAFF (so STAFF cannot see patient PII in bookings/queue — correct, they only do dept_desk work via reception/triage if assigned)

### 4. Don't Allow STAFF to Sign-in Co-Staff on Attendance
- **Before**: can_supervise() checked supervise_dept_ids which for STAFF could be empty, but not explicit
- **After**:
  - supervise_dept_ids() for STAFF returns set() → empty → cannot supervise
  - can_help() explicit check: if helper.role==STAFF → False
  - helpable_staff() for STAFF returns [] → no staff list
  - attendance.py override endpoint checks STAFF role → flash error, redirect
  - UI: can_help flag False for STAFF → help section hidden

### 5. Admin Manager Access Limited to Admin Manager Roster for DAY
- **Before**: ADMIN_MANAGER role had HOSPITAL scope and all perms, could access inspections, roster edit, attendance_admin any day, even off-duty
- **After**:
  - New helper is_admin_manager_on_duty(user): checks services.on_duty(org_id, today).id == user.id
  - require_role() decorator now enforces on-duty for ADMIN_MANAGER: if role==ADMIN_MANAGER and not on duty → abort 403 with message "Admin Manager access is limited to the Admin Manager on duty TODAY"
  - permissions_for() for ADMIN_MANAGER off-duty: strips inspections, reception, cashdesk, hims, lahsma, triage, consulting, onward, bookings, complaints, referrals, corrective, reports, admin, roles_admin, roster_edit, attendance_admin, dept_manage, escalate → keeps only roster view and attendance self and dept_desk
  - visible_departments() for ADMIN_MANAGER: on-duty → all depts, off-duty → only own dept (fail closed)
  - can_manage() for ORG scope: ADMIN_MANAGER only if on_duty today → else False → cannot edit Admin Manager roster when off-duty
  - supervise_dept_ids() for ADMIN_MANAGER: on-duty → None (whole hospital), off-duty → own dept or empty set (cannot sign others)
  - inspections views: require_role already blocks off-duty, plus explicit checks in department_children, inspection_amend, save_gate, walk_round_submit
  - navigation menu: inspections link hidden for off-duty AM (permissions_for inspections=False)

## Public Portals Still Public (No Staff Data)
- /book, /queue/join, /complaint, /feedback, /chat, /r/<code>, /welcome, /tv, /book/status (with phone verification) remain public
- Verified: no staff list, no patient list exposed without phone verification
- /book/status requires ref+phone to prevent enumeration

## Staff Endpoints Hardening
- All staff blueprints use @require_login + @require_permission + @require_role + org scoping + dept scoping
- Bookings staff_list: requires bookings permission + role HOD/APEX/MD etc + visible_department_ids filter
- Queue staff_queue: same + visible_department_ids filter
- Roster: VIEWERS includes STAFF read-only, EDITORS includes APEX_NURSE and ADMIN_MANAGER with can_manage check
- Attendance board: _may_see_board checks attendance_admin or can_supervise → STAFF cannot see board
- Attendance gate pin: requires admin or attendance_admin + on-duty check for AM
- Inspections: require_permission inspections + require_role + on-duty

## Gaps Fixed
| Gap | Before | After |
|-----|--------|-------|
| APEX_NURSE sees whole hospital | scope HOSPITAL, sees_whole_hospital True | scope DEPARTMENT, own dept only |
| HOD sees other dept rosters | visible_departments all for MANAGEMENT includes HOD? No, but bookings/queue not filtered | visible_departments own dept only + bookings/queue filtered |
| STAFF can edit roster | EDITORS did not include STAFF but can_manage not strict | can_manage STAFF False, EDITORS excludes STAFF, permissions_for roster_edit False |
| STAFF can help punch | supervise_dept_ids returned own dept if dept_manage (but STAFF no dept_manage) → borderline | explicit set() + can_help STAFF False |
| ADMIN_MANAGER off-duty has full powers | scope HOSPITAL always | on-duty check everywhere, off-duty loses inspections, roster_edit, attendance_admin, sees only own dept |
| HOD/APEX can manage other dept roster | can_manage checked only org_id, not dept | can_manage checks hod_user_id match OR own dept_id match OR UserRole grant |
| Bookings PII visible to unauthorized | bookings staff_list no dept filter | filtered by visible_department_ids |
| Queue PII visible to unauthorized | queue staff_queue no dept filter | filtered by visible_department_ids |

## Production Readiness Checklist
- [x] create_app boots green 1.7.18
- [x] BUILTIN_ROLES APEX_NURSE scope DEPARTMENT
- [x] HOD and APEX_NURSE limited to own dept for roster, bookings, queue, attendance
- [x] STAFF limited to own dept, view only roster, no edit/delete/upload, no sign-in co-staff
- [x] ADMIN_MANAGER day-on-duty enforced via is_admin_manager_on_duty, require_role, permissions_for, visible_departments, can_manage, supervise_dept_ids, inspections, attendance gate
- [x] System Admin (SUPER_ADMIN) retains upgrade path via Role Management
- [x] Public portals remain public without staff data
- [x] Staff endpoints require_role+require_permission+org+dept scoping
- [x] No diagnoses/vitals/prescriptions in code (not EMR)
- [x] Multi-tenant: org_id filtering everywhere

## Pending
- Run pytest 116 tests (needs DB) — expected green, but need CI
- Load test 5k rps (Render upgrade + Redis)
- Manual QA: login as HOD of Lab, verify cannot see Theatre roster; login as STAFF, verify roster read-only, no help punch; login as ADMIN_MANAGER off-duty, verify 403 on /admin-manager; on-duty AM can access
- Deploy to Render with APP_VERSION 1.7.18

## Voice Bank Reminder
- Native voice bank: wait for their pick, phrase bank not clone
- Pending menu will be shown after push
