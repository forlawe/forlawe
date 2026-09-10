# SECURITY ROLE AUDIT — v1.7.19 Dashboard Scoping Fix
Date: 2026-08-28
Version: 1.7.19
Builds on v1.7.18 STRICT

## Issue Reported
Screenshot of Nursing Services user (olatunji, likely HOD Nursing / APEX_NURSE) shows:
- Dashboard with hospital-wide KPIs: 13 inspections, 21.9 avg, 11% compliance, 25% complaint resolution, 3 open complaints, 3 escalated, 3 SLA breaches, critical findings, bookings today, queue, satisfaction, referrals, repeat visits, lowest-scoring departments (Engineering, Laundry, Nutrition, Pharmacy, Surgery), performance heatmap (14 days) across all departments.
- My Department page says "You are seeing Nursing Services only — your own department." which is CORRECT per v1.7.18.
- Question: Is it right for department and staff to see dashboard and full details about the roster?

## Answer: No — Fixed in v1.7.19

### v1.7.18 Already Fixed:
- Roster: visible_departments() limited to own dept for HOD/APEX/STAFF, can_manage() blocks other dept
- Bookings/Queue: filtered by visible_department_ids
- Attendance: supervise_dept_ids() own dept only, STAFF cannot help
- ADMIN_MANAGER day-on-duty enforced

### v1.7.19 Additional Fix — Dashboard
- **Before**: _kpi(org_id) computed hospital-wide metrics for ALL roles, including Nursing Services. Any HOD could see 13 inspections, all complaints, all departments heatmap — violates least privilege.
- **After**: _kpi(org_id, viewer) scoped:
  - SUPER_ADMIN, HEAD_ADMIN_HR, MD_CEO, DMD, DCST, ADMIN_MANAGER on-duty: whole hospital (existing behavior)
  - HOD, APEX_NURSE: only own dept(s) via visible_department_ids — total_inspections, avg_score, critical_findings, bookings_today, queue_waiting filtered to own dept; complaints, compliance, satisfaction, referrals hidden (0) to avoid leaking hospital-wide PII; heatmap filtered or hidden; lowest_depts filtered to own dept(s)
  - STAFF: dashboard redirects to /my-department (My Department only + Roster view-only). No hospital-wide dashboard at all.

- **Dashboard route**:
  - STAFF role → redirect to deptdesk.my_department
  - HOD/APEX_NURSE → _kpi with viewer, attention hidden (management attention only for management), recent_complaints hidden, flow headline scoped to own dept if possible
  - Template: KPI grid shows limited version for is_limited (only own dept metrics + note about least privilege), full grid for management; lowest-scoring and heatmap hidden for limited, replaced with "Your department — last 30 days" card

- **Roster**:
  - STAFF: view/read-only roster of own department only (VIEWERS includes STAFF, EDITORS excludes STAFF, can_manage False)
  - HOD/APEX_NURSE: roster creation/edit/delete/upload only for own Department/Section/Unit (can_manage checks hod_user_id or department_id or UserRole grant)
  - ADMIN_MANAGER: roster edit only ORG scope when on duty today

### Is it right for department and staff to see dashboard and full roster details?
- **STAFF**: No dashboard, only My Department + Roster view-only own dept — CORRECT after v1.7.19
- **HOD / APEX_NURSE**: Dashboard scoped to own dept only, not full hospital — CORRECT after v1.7.19; full details about roster only for own dept, not other depts — CORRECT
- **Management (MD_CEO, DMD, DCST, HEAD_ADMIN_HR, SUPER_ADMIN, on-duty ADMIN_MANAGER)**: Full dashboard and full roster sight — CORRECT

### Verification Steps
1. Login as Nursing Services HOD/APEX (olatunji) → /dashboard should show only own dept KPIs (e.g., Inspections your dept, Avg score your dept, Bookings today your dept, In queue now your dept) + note about least privilege, no hospital-wide compliance/complaints/satisfaction/referrals, no heatmap of all departments, only your dept bar
2. Login as STAFF in Nursing → /dashboard redirects to /my-department, /roster shows only Nursing roster, no edit/delete/upload buttons, /attendance no help section
3. Login as MD_CEO / SUPER_ADMIN → full dashboard as before
4. Login as off-duty ADMIN_MANAGER → /dashboard shows own dept only, /admin-manager 403, /roster only own dept view, no edit

### Production Readiness
- [x] create_app boots 1.7.19
- [x] _kpi scoped
- [x] dashboard redirects STAFF
- [x] template hides hospital-wide cards for limited roles
- [ ] Need to push to Render and manual QA with screenshots

### Voice Bank Reminder
- Native voice bank: wait for their pick, phrase bank not clone

### Pending Menu
1. Push v1.7.19 to GitHub (needs new PAT)
2. Manual QA with Nursing Services account (olatunji)
3. Load test 5k rps advice
4. DB comparison (Render vs Neon vs Supabase)
