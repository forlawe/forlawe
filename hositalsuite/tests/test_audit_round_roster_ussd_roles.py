"""Audit round: roster engine, USSD call flow, and the privilege-escalation
trace through role management — the report's own "not yet audited" list.

Roster:
  * leave-over-duty — a person cannot be on duty AND on leave the same day;
    every write path (preview, manual add, commit) refuses or skips it.
  * ORG autofill — the Admin Manager roster lives in duty_roster; autofill
    must copy from and to that table (it used to read the wrong one and
    silently do nothing).

USSD:
  * ticket codes recycle every day; "check status" must resolve today's
    ticket first, and an older code only via the caller's own phone number.

Role management:
  * a delegated roles_admin holder (not Super Admin) can never grant
    permissions above their own clearance — not by editing a custom role's
    permissions, not by editing a built-in role, not by assigning a role
    that carries powers they lack.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.models import db, now_naive


# ================================================================ roster

def _mk_user(org_id, username, role="STAFF", department_id=None):
    from app.models import User
    u = User(org_id=org_id, username=username, name=username.title(),
             role=role, department_id=department_id)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    return u


def test_leave_over_duty_is_refused_in_manual_add(app, seeded):
    """End-to-end: POST /roster/add LEAVE for a day the nurse is on DUTY —
    the HOD-style manual add path must refuse it and save nothing."""
    from app.models import Department, RosterEntry
    from tests.conftest import csrf, login
    with app.app_context():
        org = seeded["org"]
        dept = Department(org_id=org, name="Ward A1")
        nurse = _mk_user(org, "nightnurse", role="STAFF")
        db.session.add_all([dept, nurse])
        db.session.commit()
        day = (now_naive() + timedelta(days=2)).date()
        db.session.add(RosterEntry(org_id=org, duty_date=day, user_id=nurse.id,
                                   kind="DUTY", shift="NIGHT", scope="DEPARTMENT",
                                   department_id=dept.id, source="manual",
                                   created_by=seeded["admin"]))
        db.session.commit()
        dept_id, nurse_id, org_id = dept.id, nurse.id, org
    client = app.test_client()
    assert login(client, "admin")          # SUPER_ADMIN may manage any roster
    page = client.get("/roster")
    token = page.get_data(as_text=True).split('name="_csrf" value="')[1].split('"')[0]
    r = client.post("/roster/add", data={
        "_csrf": token, "scope": "DEPARTMENT", "department_id": str(dept_id),
        "duty_date": day.isoformat(), "end_date": day.isoformat(),
        "user_id": str(nurse_id), "kind": "LEAVE", "leave_type": "ANNUAL",
    }, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "already on duty" in body or "remove that" in body.lower(), body[-600:]
    with app.app_context():
        assert db.session.query(RosterEntry).filter_by(
            org_id=org_id, user_id=nurse_id, duty_date=day,
            kind="LEAVE").count() == 0


def test_import_preview_refuses_leave_on_a_duty_day(app, seeded):
    from app.models import Department, RosterEntry
    from app import rosterdata as rd
    with app.app_context():
        org = seeded["org"]
        dept = Department(org_id=org, name="Ward Y")
        nurse = _mk_user(org, "wardnurse")
        db.session.add_all([dept, nurse])
        db.session.flush()
        day = now_naive().date() + timedelta(days=3)
        db.session.add(RosterEntry(org_id=org, duty_date=day, user_id=nurse.id,
                                   kind="DUTY", shift="DAY", scope="DEPARTMENT",
                                   department_id=dept.id, source="manual",
                                   created_by=seeded["admin"]))
        db.session.commit()
        place = {"scope": "DEPARTMENT", "department_id": dept.id,
                 "section_id": None, "unit_id": None}
        rows = rd.build_preview(org, [
            {"line": 2, "name": "Wardnurse", "date": day.isoformat(), "end": "",
             "shift": "", "leave": "ANNUAL", "department": "", "section": "",
             "unit": "", "note": ""},
        ], place=place, mode="two_12h")
        assert rows[0]["ok"] is False
        assert any("already rostered for duty" in e for e in rows[0]["errors"])


def test_commit_skips_leave_rows_that_clash_with_duty(app, seeded):
    from app.models import Department, RosterEntry
    from app import rosterdata as rd
    with app.app_context():
        org = seeded["org"]
        dept = Department(org_id=org, name="Ward Z")
        nurse = _mk_user(org, "commitnurse")
        db.session.add_all([dept, nurse])
        db.session.flush()
        day = now_naive().date() + timedelta(days=4)
        db.session.add(RosterEntry(org_id=org, duty_date=day, user_id=nurse.id,
                                   kind="DUTY", shift="NIGHT", scope="DEPARTMENT",
                                   department_id=dept.id, source="manual",
                                   created_by=seeded["admin"]))
        db.session.commit()
        place = {"scope": "DEPARTMENT", "department_id": dept.id,
                 "section_id": None, "unit_id": None}
        result = rd.commit_rows(org, [{
            "ok": True, "person_id": nurse.id, "date": day.isoformat(),
            "end": "", "kind": "LEAVE", "shift": "LEAVE", "leave_type": "SICK",
            "note": "",
        }], place=place, created_by_id=seeded["admin"])
        assert result["skipped"] == 1 and result["added"] == 0
        assert db.session.query(RosterEntry).filter_by(
            user_id=nurse.id, duty_date=day, kind="LEAVE").count() == 0


def test_org_autofill_copies_the_admin_manager_roster(app, seeded):
    """The hospital-wide roster lives in duty_roster — autofill must fill
    next week's Admin Manager days from this week's (used to do nothing)."""
    from app.models import DutyRoster
    from app import rosterdata as rd
    with app.app_context():
        org = seeded["org"]
        admin = _mk_user(org, "dutymanager", role="ADMIN_MANAGER")
        db.session.flush()
        source_start = now_naive().date() + timedelta(days=10)
        for i in range(3):
            db.session.add(DutyRoster(org_id=org, duty_date=source_start + timedelta(days=i),
                                      user_id=admin.id, source="manual",
                                      created_by=seeded["admin"]))
        db.session.commit()
        place = {"scope": "ORG", "department_id": None, "section_id": None, "unit_id": None}
        result = rd.autofill_next_week(org, place, source_start=source_start,
                                       target_start=source_start + timedelta(days=7),
                                       created_by_id=seeded["admin"])
        assert result["added"] == 3, result
        # running it again fills nothing new (idempotent)
        again = rd.autofill_next_week(org, place, source_start=source_start,
                                      target_start=source_start + timedelta(days=7),
                                      created_by_id=seeded["admin"])
        assert again["added"] == 0


# ================================================================ ussd

def _join_ticket(org_id, dept_id, code, phone, days_ago=0, name="Test Patient"):
    from app.models import QueueTicket
    created = now_naive() - timedelta(days=days_ago)
    t = QueueTicket(org_id=org_id, code=code, department_id=dept_id,
                    queue_date=created.date(), patient_name=name,
                    phone=phone, status="WAITING", source="ussd",
                    created_at=created)
    db.session.add(t)
    db.session.commit()          # the USSD request uses its own session
    return t


def test_ussd_status_resolves_todays_ticket_not_a_stale_one(app, seeded, client, monkeypatch):
    """G-001 exists today AND 40 days ago — the caller must get TODAY's."""
    from app.models import Organization
    monkeypatch.setitem(app.config, "USSD_SHARED_SECRET", "ussd-sec")
    with app.app_context():
        old = _join_ticket(seeded["org"], seeded["dept"], "G-001",
                           "08011110001", days_ago=40, name="Old Patient")
        fresh = _join_ticket(seeded["org"], seeded["dept"], "G-001",
                             "08011110002", days_ago=0, name="New Patient")
        code = Organization.query.get(seeded["org"]).code
    r = client.post("/api/v1/ussd/callback", data={
        "sessionId": "s1", "serviceCode": "*384*123#",
        "phoneNumber": "08011110002", "text": f"{code}*3*G-001",
    })
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "New Patient" not in body               # names never go to USSD
    assert "G-001" in body and "in line" in body


def test_ussd_status_of_someone_elses_old_code_is_refused(app, seeded, client, monkeypatch):
    """An old-day code may only be resolved by the number that owns it."""
    from app.models import Organization
    monkeypatch.setitem(app.config, "USSD_SHARED_SECRET", "ussd-sec")
    with app.app_context():
        _join_ticket(seeded["org"], seeded["dept"], "K-009",
                     "08022220001", days_ago=5, name="Someone")
        code = Organization.query.get(seeded["org"]).code
    r = client.post("/api/v1/ussd/callback", data={
        "sessionId": "s2", "serviceCode": "*384*123#",
        "phoneNumber": "08099990000",           # a stranger's phone
        "text": f"{code}*3*K-009",
    })
    body = r.get_data(as_text=True)
    assert "Ticket not found" in body


# ================================================================ role management

def _grant_roles_admin(org_id, username):
    """A custom role holding ONLY roles_admin, assigned to a fresh user."""
    from app.models import Role, RolePermission, User, UserRole
    user = _mk_user(org_id, username, role="HOD")
    role = Role(org_id=org_id, code="DELEGATED_MGR", name="Delegated Manager",
                scope="DEPARTMENT", builtin=False, active=True)
    db.session.add(role)
    db.session.flush()
    db.session.add(RolePermission(role_id=role.id, permission="roles_admin"))
    db.session.add(UserRole(org_id=org_id, user_id=user.id, role_id=role.id,
                            active=True))
    db.session.commit()
    return user


def test_delegated_manager_cannot_grant_powers_they_lack(app, seeded):
    """The escalation path: edit a custom role to hold everything, then wear it.
    The clamp must strip powers above the editor's own clearance."""
    from app import roles as R
    from app.models import PERMISSION_KEYS, Role
    from tests.conftest import login
    with app.app_context():
        mgr = _grant_roles_admin(seeded["org"], "delegated1")
        custom = Role(org_id=seeded["org"], code="RUNNERS", name="Runners",
                      scope="DEPARTMENT", builtin=False, active=True)
        db.session.add(custom)
        db.session.commit()
        rid, mgr_id = custom.id, mgr.id
    client = app.test_client()
    assert login(client, "delegated1")
    page = client.get(f"/admin/roles/{rid}")
    assert page.status_code == 200
    token = page.get_data(as_text=True).split('name="_csrf" value="')[1].split('"')[0]
    # try to tick EVERY permission, including admin
    data = {"_csrf": token, "perm": list(PERMISSION_KEYS)}
    r = client.post(f"/admin/roles/{rid}", data=data, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        keys = db.session.get(Role, rid).permission_keys
        assert "admin" not in keys and "user_admin" not in keys   # never above clearance
        assert keys <= R.permissions_of(db.session.get(
            __import__("app.models", fromlist=["User"]).User, mgr_id))


def test_delegated_manager_cannot_edit_builtin_roles(app, seeded):
    from app.models import Role
    from tests.conftest import login
    with app.app_context():
        _grant_roles_admin(seeded["org"], "delegated2")
        md = db.session.query(Role).filter_by(org_id=seeded["org"],
                                              code="MD_CEO").first()
        assert md is not None
        rid = md.id
    client = app.test_client()
    assert login(client, "delegated2")
    page = client.get(f"/admin/roles/{rid}")
    token = page.get_data(as_text=True).split('name="_csrf" value="')[1].split('"')[0]
    r = client.post(f"/admin/roles/{rid}", data={"_csrf": token, "perm": "roster"}, follow_redirects=True)
    assert "Only a Super Administrator" in r.get_data(as_text=True)


def test_delegated_manager_cannot_assign_a_role_above_their_clearance(app, seeded):
    from app.models import Role, User, UserRole
    from tests.conftest import login
    with app.app_context():
        mgr = _grant_roles_admin(seeded["org"], "delegated3")
        victim = _mk_user(seeded["org"], "victim", role="STAFF")
        db.session.commit()
        # a builtin hospital-wide role the manager does NOT hold
        target = db.session.query(Role).filter_by(org_id=seeded["org"],
                                                  code="MD_CEO").first()
        victim_id, target_id = victim.id, target.id
    client = app.test_client()
    assert login(client, "delegated3")
    page = client.get("/admin/roles/assign")
    token = page.get_data(as_text=True).split('name="_csrf" value="')[1].split('"')[0]
    r = client.post("/admin/roles/assign", data={
        "_csrf": token, "user_id": str(victim_id), "role_id": str(target_id),
    }, follow_redirects=True)
    assert "powers you do not hold yourself" in r.get_data(as_text=True)
    with app.app_context():
        assert db.session.query(UserRole).filter_by(
            user_id=victim_id, role_id=target_id).count() == 0


def test_super_admin_still_manages_roles_normally(app, seeded):
    """Regression: the ceiling is unchanged for the Super Admin."""
    from app.models import Role, UserRole
    from tests.conftest import login
    with app.app_context():
        victim = _mk_user(seeded["org"], "promoted1", role="STAFF")
        db.session.commit()
        target = db.session.query(Role).filter_by(org_id=seeded["org"],
                                                  code="HOD").first()
        victim_id, target_id = victim.id, target.id
    client = app.test_client()
    assert login(client, "admin")               # seeded SUPER_ADMIN
    page = client.get("/admin/roles/assign")
    token = page.get_data(as_text=True).split('name="_csrf" value="')[1].split('"')[0]
    r = client.post("/admin/roles/assign", data={
        "_csrf": token, "user_id": str(victim_id), "role_id": str(target_id),
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert db.session.query(UserRole).filter_by(
            user_id=victim_id, role_id=target_id).count() == 1
