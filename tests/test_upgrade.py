"""Upgrade batch tests: full CRUD for admin entities, plus the UNIFIED roster —
one page covering the Admin Manager duty roster, departments, sections, units,
shift patterns (12h / 24h / 8h / office Mon-Fri), unlimited staff per shift,
leave, bulk upload and export."""
import io
from datetime import timedelta

from app.models import (ComplaintCategory, Department, DeptRosterEntry,
                        QrLocation, User, db, now_naive)

from conftest import csrf, login


# ------------------------------------------------------------------ CRUD (#4)
def test_user_edit_name_role_phone(client, seeded):
    login(client, "admin")
    tok = csrf(client, "/admin/users")
    r = client.post(f"/admin/users/{seeded['hod']}/edit",
                    data={"_csrf": tok, "name": "Hannah HeadOfDept", "role": "HOD",
                          "phone": "2348099990000", "email": "hod@gmail.com"},
                    follow_redirects=True)
    assert b"updated" in r.data.lower()
    u = db.session.get(User, seeded["hod"])
    assert u.name == "Hannah HeadOfDept" and u.phone == "2348099990000"
    # keep verified so HOD can still sign in after email change
    u.email_verified = True
    u.profile_completed = True
    u.approved = True
    db.session.commit()
    # invalid role rejected
    client.post(f"/admin/users/{seeded['hod']}/edit",
                data={"_csrf": tok, "name": "x", "role": "HACKER"})
    assert db.session.get(User, seeded["hod"]).role == "HOD"
    # HOD cannot edit users
    login(client, "hod1")
    tok2 = csrf(client, "/admin/users")
    r2 = client.post(f"/admin/users/{seeded['hod']}/edit",
                     data={"_csrf": tok2, "name": "y", "role": "HOD"})
    assert r2.status_code == 403


def test_department_delete_guarded(client, app, seeded):
    login(client, "admin")
    tok = csrf(client, "/admin/structure")
    # Emergency has records? none yet in seeded — add a complaint to create a reference
    from app.models import Complaint
    db.session.add(Complaint(org_id=seeded["org"], ref="TEST-CMP-2026-000099",
                             department_id=seeded["dept"], category="Other",
                             description="x" * 20, phone="0801", status="NEW",
                             sla_hours=24, sla_deadline_at=now_naive()))
    db.session.commit()
    r = client.post(f"/admin/structure/department/{seeded['dept']}/delete",
                    data={"_csrf": tok}, follow_redirects=True)
    assert b"sections/units first" in r.data
    assert db.session.get(Department, seeded["dept"]) is not None
    # a department with children is blocked too
    # NOTE: HOD name + phone are now mandatory when creating a department.
    r = client.post("/admin/structure/department",
                    data={"_csrf": tok, "name": "Empty Dept",
                          "hod_name": "Dr. Empty", "hod_phone": "08010001000"})
    new_id = db.session.query(Department).filter_by(name="Empty Dept").first().id
    client.post(f"/admin/structure/department/{new_id}/delete", data={"_csrf": tok},
                follow_redirects=True)
    assert db.session.get(Department, new_id) is None


def test_category_and_qr_lifecycle(client, seeded):
    login(client, "admin")
    tok = csrf(client, "/admin/settings")
    cat = db.session.query(ComplaintCategory).first()
    client.post(f"/admin/settings/categories/{cat.id}/toggle", data={"_csrf": tok})
    assert db.session.get(ComplaintCategory, cat.id).active is False
    # used categories cannot be deleted
    client.post("/complaint/submit", data={"consent": "1", "_csrf": csrf(client, "/complaint"),
                                           "department_id": seeded["dept"],
                                           "category": cat.name,
                                           "description": "A test complaint for deletion guard.",
                                           "phone": "08011112222", "idem": "crud-1"},
                follow_redirects=True)
    client.post(f"/admin/settings/categories/{cat.id}/delete", data={"_csrf": tok},
                follow_redirects=True)
    assert db.session.get(ComplaintCategory, cat.id) is not None
    # unused category deletes fine
    free = db.session.query(ComplaintCategory).filter_by(name="Billing / charges").first()
    client.post(f"/admin/settings/categories/{free.id}/delete", data={"_csrf": tok})
    assert db.session.get(ComplaintCategory, free.id) is None
    # QR location rename + delete
    loc = db.session.query(QrLocation).first()
    client.post(f"/admin/settings/locations/{loc.id}/edit", data={"_csrf": tok, "name": "Main Gate"})
    assert db.session.get(QrLocation, loc.id).name == "Main Gate"
    client.post(f"/admin/settings/locations/{loc.id}/delete", data={"_csrf": tok})
    assert db.session.get(QrLocation, loc.id) is None   # nothing references it yet


# ------------------------------------------------------------------ unified roster
def _add(client, dept, date, shift, user_id, end="", kind="DUTY", leave=""):
    return client.post("/roster/add", data={
        "_csrf": csrf(client, f"/roster?scope=DEPARTMENT&department_id={dept}"),
        "scope": "DEPARTMENT", "department_id": dept, "duty_date": date, "end_date": end,
        "shift": shift, "user_id": user_id, "kind": kind, "leave_type": leave},
        follow_redirects=True)


def test_hod_manages_own_dept_only(client, seeded):
    from app.models import RosterEntry
    login(client, "hod1")
    day = (now_naive().date() + timedelta(days=2)).isoformat()
    _add(client, seeded["dept"], day, "DAY", seeded["hod"])
    assert db.session.query(RosterEntry).count() == 1
    # another (non-HOD) department: create one, then try — 403
    db.session.add(Department(org_id=seeded["org"], name="Radiology"))
    db.session.commit()
    rad = db.session.query(Department).filter_by(name="Radiology").first()
    assert client.post("/roster/add", data={
        "_csrf": csrf(client, "/roster"), "scope": "DEPARTMENT", "department_id": rad.id,
        "duty_date": day, "shift": "DAY", "user_id": seeded["hod"]}).status_code == 403


def test_shift_system_rules(client, seeded):
    from app.models import RosterEntry
    login(client, "admin")
    dept = seeded["dept"]
    day = (now_naive().date() + timedelta(days=3)).isoformat()
    # default mode two_12h: 24H rejected
    r = _add(client, dept, day, "24H", seeded["am"])
    assert b"Choose a shift" in r.data and db.session.query(RosterEntry).count() == 0
    # valid entry; the SAME person on the SAME shift is a no-op, not a duplicate
    _add(client, dept, day, "DAY", seeded["am"])
    assert db.session.query(RosterEntry).count() == 1
    r = _add(client, dept, day, "DAY", seeded["am"])
    assert b"already exist" in r.data
    assert db.session.query(RosterEntry).count() == 1
    # a SECOND person on the same day+shift is allowed — the old design could not do this
    _add(client, dept, day, "DAY", seeded["am2"])
    assert db.session.query(RosterEntry).count() == 2
    # switch dept to 24h via department edit
    tok = csrf(client, "/admin/structure")
    client.post("/admin/structure/department", data={
        "_csrf": tok, "department_id": dept, "name": "Emergency",
        "roster_mode": "24h", "roster_staff_per_shift": "6"})
    d = db.session.get(Department, dept)
    assert d.roster_mode == "24h" and d.roster_staff_per_shift == 6
    day2 = (now_naive().date() + timedelta(days=4)).isoformat()
    _add(client, dept, day2, "24H", seeded["am"])
    assert db.session.query(RosterEntry).filter_by(shift="24H").count() == 1
    # now DAY is rejected for a 24h dept
    r = _add(client, dept, (now_naive().date() + timedelta(days=5)).isoformat(),
             "DAY", seeded["am"])
    assert b"Choose a shift" in r.data


def test_office_departments_have_no_shifts_and_no_weekends(client, seeded):
    """Procurement / Audit / ICT style departments: Mon-Fri office hours."""
    from app.models import RosterEntry
    login(client, "admin")
    dept = seeded["dept"]
    client.post("/admin/structure/department", data={
        "_csrf": csrf(client, "/admin/structure"), "department_id": dept,
        "name": "Emergency", "roster_mode": "office", "roster_staff_per_shift": "3"})
    # find the next Saturday
    d = now_naive().date() + timedelta(days=1)
    while d.weekday() != 5:
        d += timedelta(days=1)
    r = _add(client, dept, d.isoformat(), "OFFICE", seeded["am"])
    assert b"weekend" in r.data and db.session.query(RosterEntry).count() == 0
    monday = d + timedelta(days=2)
    _add(client, dept, monday.isoformat(), "OFFICE", seeded["am"])
    assert db.session.query(RosterEntry).filter_by(shift="OFFICE").count() == 1


def test_leave_blocks_duty(client, seeded):
    from app.models import RosterEntry
    login(client, "admin")
    dept = seeded["dept"]
    start = now_naive().date() + timedelta(days=10)
    end = start + timedelta(days=6)
    _add(client, dept, start.isoformat(), "", seeded["am"], end=end.isoformat(),
         kind="LEAVE", leave="ANNUAL")
    # 7 days of leave, one row per day, so any single-date lookup just works
    assert db.session.query(RosterEntry).filter_by(kind="LEAVE").count() == 7
    r = _add(client, dept, (start + timedelta(days=2)).isoformat(), "DAY", seeded["am"])
    assert b"annual leave" in r.data
    assert db.session.query(RosterEntry).filter_by(kind="DUTY").count() == 0
    # somebody else is fine on the same day
    _add(client, dept, (start + timedelta(days=2)).isoformat(), "DAY", seeded["am2"])
    assert db.session.query(RosterEntry).filter_by(kind="DUTY").count() == 1


def test_section_and_unit_rosters(client, seeded):
    """A section or a unit can own a roster — the old design could not."""
    from app.models import RosterEntry, Section, Unit
    login(client, "admin")
    sec = db.session.query(Section).filter_by(org_id=seeded["org"]).first()
    unit = db.session.query(Unit).filter_by(org_id=seeded["org"]).first()
    day = (now_naive().date() + timedelta(days=20)).isoformat()
    tok = csrf(client, "/roster")
    client.post("/roster/add", data={
        "_csrf": tok, "scope": "SECTION", "department_id": seeded["dept"],
        "section_id": sec.id, "duty_date": day, "shift": "DAY",
        "user_id": seeded["am"]}, follow_redirects=True)
    client.post("/roster/add", data={
        "_csrf": tok, "scope": "UNIT", "department_id": seeded["dept"],
        "section_id": sec.id, "unit_id": unit.id, "duty_date": day, "shift": "NIGHT",
        "user_id": seeded["am2"]}, follow_redirects=True)
    assert db.session.query(RosterEntry).filter_by(scope="SECTION").count() == 1
    assert db.session.query(RosterEntry).filter_by(scope="UNIT").count() == 1
    # a section belonging to a DIFFERENT department must be refused
    db.session.add(Department(org_id=seeded["org"], name="Pharmacy Dept"))
    db.session.commit()
    other = db.session.query(Department).filter_by(name="Pharmacy Dept").first()
    r = client.post("/roster/add", data={
        "_csrf": csrf(client, "/roster"), "scope": "SECTION", "department_id": other.id,
        "section_id": sec.id, "duty_date": day, "shift": "DAY",
        "user_id": seeded["am"]}, follow_redirects=True)
    assert b"is not a section of" in r.data
    assert db.session.query(RosterEntry).filter_by(scope="SECTION").count() == 1


def test_roster_upload_multi_person_and_leave(client, seeded):
    from app.models import RosterEntry
    login(client, "admin")
    dept = seeded["dept"]
    d1 = now_naive().date() + timedelta(days=30)
    body = ("Name,Date,End Date,Shift,Leave Type,Note\n"
            f"Alice Manager,{d1},,DAY,,\n"
            f"Bob Manager,{d1},,DAY,,second person same shift\n"
            f"Hannah Hod,{d1},,NIGHT,,\n"
            f"MRS Alice Manager,{d1 + timedelta(days=1)},,DAY,,title is ignored\n"
            f"Alice Manager,{d1 + timedelta(days=3)},{d1 + timedelta(days=5)},,SICK,\n"
            f"Ghost Staff,{d1},,DAY,,\n"
            f"Bob Manager,not-a-date,,DAY,,\n"
            f"Bob Manager,{d1},,TEATIME,,\n")
    r = client.post("/roster/upload", data={
        "_csrf": csrf(client, "/roster"), "scope": "DEPARTMENT", "department_id": dept,
        "file": (io.BytesIO(body.encode()), "ward.csv")},
        content_type="multipart/form-data", follow_redirects=True)
    page = r.data.decode()
    assert "No active staff account matches" in page          # Ghost Staff
    assert "Cannot read the date" in page                      # not-a-date
    assert "is not a shift or a leave type" in page            # TEATIME
    token = page.split('name="token" value="')[1].split('"')[0]

    client.post("/roster/upload/confirm", data={
        "_csrf": csrf(client, "/roster"), "token": token}, follow_redirects=True)
    assert db.session.query(RosterEntry).filter_by(kind="DUTY").count() == 4
    assert db.session.query(RosterEntry).filter_by(kind="LEAVE").count() == 3   # 3-day sick block


def test_date_range_presets(client, seeded):
    login(client, "admin")
    for preset in ("today", "7", "14", "21", "30", "month"):
        r = client.get(f"/roster?range={preset}")
        assert r.status_code == 200, preset
    r = client.get("/roster?range=custom&from=2026-09-01&to=2026-09-30")
    assert r.status_code == 200 and b"30 Sep 2026" in r.data
    # nonsense input must not crash the page
    assert client.get("/roster?range=custom&from=zzz&to=yyy").status_code == 200
    assert client.get("/roster?range=nonsense").status_code == 200


def test_old_dept_roster_url_still_works(client, seeded):
    login(client, "admin")
    r = client.get(f"/dept-roster?dept={seeded['dept']}", follow_redirects=False)
    assert r.status_code == 302 and "/roster" in r.headers["Location"]


def test_roster_export_csv(client, seeded):
    login(client, "admin")
    _add(client, seeded["dept"], (now_naive().date() + timedelta(days=2)).isoformat(),
         "DAY", seeded["am"])
    r = client.get("/roster/export?range=30&scope=DEPARTMENT&department_id=%s" % seeded["dept"])
    assert r.status_code == 200 and b"Date,Day,Type" in r.data and b"Alice Manager" in r.data


def test_legacy_dept_roster_rows_are_migrated(app, seeded):
    """Old two-staff rows must not be lost when the rosters merge."""
    from app.models import DeptRosterEntry, RosterEntry
    from app.rosterdata import migrate_legacy_entries
    with app.app_context():
        day = now_naive().date() + timedelta(days=40)
        db.session.add(DeptRosterEntry(org_id=seeded["org"], department_id=seeded["dept"],
                                       duty_date=day, shift="DAY",
                                       staff1_user_id=seeded["am"],
                                       staff2_user_id=seeded["am2"]))
        db.session.commit()
        assert migrate_legacy_entries(app) == 2
        assert db.session.query(RosterEntry).filter_by(source="legacy").count() == 2
        # idempotent: running it again must not duplicate anything
        assert migrate_legacy_entries(app) == 0
        assert db.session.query(RosterEntry).filter_by(source="legacy").count() == 2
        # the original rows are still there, untouched
        assert db.session.query(DeptRosterEntry).count() == 1
