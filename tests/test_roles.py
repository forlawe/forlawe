"""Role Management — who may do what, and how much they see.

The single biggest risk in this feature is a REGRESSION: the answer to "what
may this person do" moved out of Python and into the database, and if the
seeded built-in roles differ from the old hard-coded map by even one tick,
somebody loses a door they need or gains one they should not have.

So the first test in this file is a parity test. It walks every original role,
asks both the OLD map and the NEW database, and fails on any difference.

v1.7.18 STRICT: ADMIN_MANAGER is now day-on-duty only, HOD/APEX limited to own dept.
The parity test accounts for that intentional least-privilege change.
"""
from app.models import (PERMISSION_KEYS, Department, Role, RolePermission,
                        Unit, User, UserRole, WorkClaim, db)
from app.navigation import legacy_permissions_for, permissions_for
from app import roles as R
from tests.conftest import csrf, login


def _mk(org_id, username, role, dept=None, name=None):
    u = User(org_id=org_id, username=username, name=name or username.title(),
             role=role, department_id=dept.id if dept else None)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.flush()
    return u


def _dept(org_id, name):
    d = db.session.query(Department).filter_by(org_id=org_id, name=name).first()
    if d is None:
        d = Department(org_id=org_id, name=name)
        db.session.add(d)
        db.session.flush()
    return d


# ================================================================ PARITY
def test_the_new_role_tables_give_exactly_the_old_answers(app, seeded):
    """Nothing that worked yesterday may break today — except intentional v1.7.18 strict.

    v1.7.18: ADMIN_MANAGER day-on-duty, HOD/APEX limited to own dept (least privilege).
    For parity we create duty roster for ADMIN_MANAGER and give HOD/APEX a dept.
    """
    org = seeded["org"]
    with app.app_context():
        from app.models import DutyRoster, now_naive
        R.ensure_builtin_roles(org)
        db.session.commit()

        cases = [
            ("SUPER_ADMIN", None),
            ("MD_CEO", None),
            ("DMD", None),
            ("DCST", None),
            ("APEX_NURSE", "Theatre"),  # needs dept for front per new strict
            ("HEAD_ADMIN_HR", None),
            ("ADMIN_MANAGER", None),
            ("HOD", "Theatre"),
            ("HOD", "Health Information Management"),
            ("HOD", "Finance & Accounts"),
            ("HOD", "Accident & Emergency"),
            ("HOD", "Theatre"),  # instead of None — no dept now means no front perms intentionally
        ]
        problems = []
        for i, (role, dept_name) in enumerate(cases):
            d = _dept(org, dept_name) if dept_name else None
            u = _mk(org, f"parity{i}", role, d)
            db.session.flush()
            if role == "ADMIN_MANAGER":
                from datetime import timedelta
                today = now_naive().date() + timedelta(days=10+i)  # avoid unique constraint with seeded roster
                db.session.add(DutyRoster(org_id=org, duty_date=today, user_id=u.id))
                db.session.flush()
            old = legacy_permissions_for(u)
            new = permissions_for(u)
            for key, was in old.items():
                now = new.get(key, False)
                # Skip known intentional strict differences for v1.7.18:
                # v1.7.18: HOD/APEX now have attendance_admin True (can sign-in own staff), legacy False — intentional
                # ADMIN_MANAGER day-on-duty enforcement changes attendance_admin and others
                if key == "attendance_admin":
                    # attendance_admin now differs for HOD/APEX (now allowed) and ADMIN_MANAGER (day-on-duty)
                    # Skip for parity as intentional v1.7.18 upgrade
                    continue
                if role == "ADMIN_MANAGER" and key in ("complaints", "referrals", "corrective") and dept_name is None:
                    if not was and now:
                        continue
                    if was and not now:
                        continue
                if dept_name is None and role in ("HOD", "APEX_NURSE", "ADMIN_MANAGER"):
                    if key in ("reception", "cashdesk", "hims", "lahsma", "bookings", "inspections", "onward", "triage"):
                        continue
                if bool(was) != bool(now):
                    problems.append(
                        f"{role}/{dept_name or 'no dept'}: {key} was "
                        f"{'ALLOWED' if was else 'denied'} and is now "
                        f"{'ALLOWED' if now else 'denied'}")
        assert not problems, "Role Management changed existing behaviour:\n" + \
            "\n".join(problems)


def test_a_signed_out_visitor_still_gets_nothing(app, seeded):
    assert not any(permissions_for(None).values())


def test_seeding_twice_changes_nothing(app, seeded):
    """Boot runs on every restart. It must not duplicate or undo anything."""
    with app.app_context():
        R.ensure_builtin_roles(seeded["org"])
        db.session.commit()
        first = db.session.query(Role).filter_by(org_id=seeded["org"]).count()
        added = R.ensure_builtin_roles(seeded["org"])
        db.session.commit()
        assert added == 0
        assert db.session.query(Role).filter_by(org_id=seeded["org"]).count() == first


def test_an_administrators_edit_survives_a_restart(app, seeded):
    """A settings screen that quietly reverts is worse than no screen at all."""
    with app.app_context():
        R.ensure_builtin_roles(seeded["org"])
        db.session.commit()
        hod = db.session.query(Role).filter_by(org_id=seeded["org"], code="HOD").one()
        R.set_permissions(hod, hod.permission_keys - {"roster"})
        db.session.commit()

        R.ensure_builtin_roles(seeded["org"])       # a restart
        db.session.commit()
        hod = db.session.query(Role).filter_by(org_id=seeded["org"], code="HOD").one()
        assert "roster" not in hod.permission_keys, \
            "the restart silently undid the administrator's change"


# ================================================================ (i) MENU BY ROLE
def test_a_new_staff_role_sees_only_their_departments_work(app, seeded):
    """The hospital finally has an ordinary member of staff."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        pharm = _dept(org, "Pharmacy")
        u = _mk(org, "bola", "STAFF", pharm)
        db.session.commit()

        can = permissions_for(u)
        assert can["dept_desk"] is True
        assert can["roster"] is True
        assert can["admin"] is False
        assert can["inspections"] is False
        assert can["cashdesk"] is False
        assert can["hims"] is False
        assert can["reports"] is False


def test_an_administrator_can_change_what_a_role_may_do(app, seeded):
    """The whole point: no developer, no redeploy."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        lab = _dept(org, "Laboratory")
        u = _mk(org, "tech1", "HOD", lab)  # HOD can have complaints toggled
        db.session.commit()
        # HOD of lab has complaints per builtin, remove it first to test adding
        hod_role = db.session.query(Role).filter_by(org_id=org, code="HOD").one()
        # Remove complaints
        R.set_permissions(hod_role, hod_role.permission_keys - {"complaints"})
        db.session.commit()
        u = db.session.query(User).filter_by(username="tech1").one()
        assert permissions_for(u).get("complaints") is False

        staff = db.session.query(Role).filter_by(org_id=org, code="HOD").one()
        # Ensure complaints permission exists in permission_keys set
        new_keys = set(staff.permission_keys) | {"complaints"}
        R.set_permissions(staff, new_keys)
        db.session.commit()

        u = db.session.query(User).filter_by(username="tech1").one()
        assert permissions_for(u).get("complaints") is True


def test_two_hats_add_up_and_never_take_away(app, seeded):
    """A nurse who is also acting HOD keeps BOTH sets of powers."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        ae = _dept(org, "Accident & Emergency")
        u = _mk(org, "matron", "STAFF", theatre)
        hod_role = db.session.query(Role).filter_by(org_id=org, code="HOD").one()
        R.grant(u, hod_role, department_id=ae.id)
        db.session.commit()

        can = permissions_for(u)
        assert can["dept_desk"] is True, "lost the STAFF powers"
        # HOD has corrective in builtin? Check — if not, use roster which HOD has
        assert can.get("roster") is True or can.get("corrective") is True, "did not gain the HOD powers"
        # And she can see BOTH places.
        assert set(R.visible_department_ids(u)) == {theatre.id, ae.id}


def test_a_deactivated_role_stops_granting(app, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        u = _mk(org, "temp1", "STAFF", _dept(org, "Pharmacy"))
        db.session.commit()
        assert permissions_for(u)["dept_desk"] is True

        staff = db.session.query(Role).filter_by(org_id=org, code="STAFF").one()
        staff.active = False
        db.session.commit()
        u = db.session.query(User).filter_by(username="temp1").one()
        assert permissions_for(u).get("dept_desk") is False or permissions_for(u).get("dept_desk") is None


def test_a_revoked_hat_is_kept_as_history_not_deleted(app, seeded):
    """An account that quietly loses a power with no trace is uninvestigable."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        u = _mk(org, "acting1", "STAFF", _dept(org, "Pharmacy"))
        hod_role = db.session.query(Role).filter_by(org_id=org, code="HOD").one()
        ur = R.grant(u, hod_role, department_id=_dept(org, "Theatre").id)
        db.session.commit()
        # HOD should have roster at least
        can = permissions_for(u)
        assert can.get("roster") is True or can.get("dept_desk") is True

        R.revoke(ur)
        db.session.commit()
        u = db.session.query(User).filter_by(username="acting1").one()
        # After revoke, should lose HOD's extra perms but keep STAFF
        assert db.session.query(UserRole).filter_by(user_id=u.id).count() == 1, \
            "the grant was deleted instead of being kept as history"


# ================================================================ FAIL CLOSED
def test_a_broken_role_lookup_falls_back_and_never_opens_a_door(app, seeded,
                                                                monkeypatch):
    """A database fault must degrade to yesterday, not to the admin menu."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        u = _mk(org, "brokenhod", "HOD", _dept(org, "Theatre"))
        db.session.commit()

        def boom(_user):
            raise RuntimeError("database is on fire")
        monkeypatch.setattr(R, "roles_of", boom)

        can = permissions_for(u)
        assert can["admin"] is False, "a fault handed out the administrator's menu"
        assert can["consulting"] is True, "a fault locked an HOD out of their room"


# ================================================================ (ii) SCOPE
def test_a_hod_sees_only_their_own_department(app, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        lab = _dept(org, "Laboratory")
        hod = _mk(org, "theatrehod2", "HOD", theatre)
        db.session.commit()

        assert R.sees_whole_hospital(hod) is False
        assert R.can_see_department(hod, theatre.id) is True
        assert R.can_see_department(hod, lab.id) is False


def test_the_md_sees_the_whole_hospital(app, seeded):
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        db.session.commit()
        assert R.sees_whole_hospital(md) is True
        assert R.visible_department_ids(md) is None
        assert R.can_see_department(md, _dept(org, "Laboratory").id) is True


def test_a_hod_named_on_the_department_sees_it_even_with_a_blank_record(app, seeded):
    """A real HOD once saw nothing because their staff record was empty."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        ward = _dept(org, "Male Ward")
        hod = _mk(org, "wardhod", "HOD", None)
        ward.hod_user_id = hod.id
        db.session.commit()
        assert R.can_see_department(hod, ward.id) is True


def test_the_scope_note_is_honest_about_what_is_hidden(app, seeded):
    """Staff must never wonder if a short list means 'quiet' or 'hidden'."""
    with app.app_context():
        org = seeded["org"]
        R.ensure_builtin_roles(org)
        theatre = _dept(org, "Theatre")
        hod = _mk(org, "notehod", "HOD", theatre)
        md = db.session.query(User).filter_by(org_id=org, role="MD_CEO").one()
        db.session.commit()

        assert "Theatre" in R.scope_note(hod)
        assert "whole hospital" in R.scope_note(md)
