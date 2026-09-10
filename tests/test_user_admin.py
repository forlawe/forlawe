"""Roles & Users: deleting staff, and resetting a password.

REPORTED FROM THE LIVE SITE with a screenshot:
  1. Deleting a staff member gave a bare "500 Something went wrong on our side"
  2. "Reset password" appeared to do nothing when tapped on a phone
"""
from app.models import (AppNotification, Department, Inspection, PatientVisit,
                        User, UserPref, db)
from app.views.admincp import _USER_REFERENCES, _user_has_history
from tests.conftest import csrf, login


def _admin(client, app, seeded):
    with app.app_context():
        u = db.session.query(User).filter_by(org_id=seeded["org"],
                                             role="SUPER_ADMIN").first()
        u.must_change_password = False
        db.session.commit()
        return login(client, u.username)


def _staff(org_id, username="adenira", name="Adenira Theatre"):
    u = User(org_id=org_id, username=username, name=name, role="HOD")
    u.set_password("Passw0rd!x")
    db.session.add(u)
    db.session.flush()
    return u


# ================================================================ the 500
def test_deleting_staff_with_history_explains_instead_of_crashing(app, client,
                                                                   seeded):
    """THE REPORTED CRASH.

    The guard checked FIVE tables. Thirty-two columns point at user.id, so
    almost anything the person had touched — a single alert in their inbox is
    enough — made the database refuse the delete and the founder got a bare
    500 with no explanation.
    """
    with app.app_context():
        org_id = seeded["org"]
        staff = _staff(org_id)
        db.session.add(AppNotification(
            org_id=org_id, user_id=staff.id, channel="inapp",
            template_key="queue_waiting", subject="s", body="b", status="SENT"))
        db.session.commit()
        uid = staff.id

    _admin(client, app, seeded)
    r = client.post(f"/admin/users/{uid}/delete",
                    data={"_csrf": csrf(client, "/admin/users")},
                    follow_redirects=True)

    assert r.status_code == 200, f"still crashing with {r.status_code}"
    body = r.get_data(as_text=True)
    assert "cannot be deleted" in body
    assert "alerts in their inbox" in body, \
        "the reason was not explained in plain English"
    with app.app_context():
        assert db.session.get(User, uid) is not None


def test_a_brand_new_user_can_still_be_deleted(app, client, seeded):
    """The guard must not become so cautious that nobody can be removed.

    A first version of this fix queried `model.id` — but UserPref has a
    composite primary key and no `id`, so the query raised, the guard returned
    "records we could not fully check", and EVERY delete was refused,
    including for accounts created seconds earlier.
    """
    with app.app_context():
        uid = _staff(seeded["org"], "neverused", "Never Used").id
        db.session.commit()

    _admin(client, app, seeded)
    r = client.post(f"/admin/users/{uid}/delete",
                    data={"_csrf": csrf(client, "/admin/users")},
                    follow_redirects=True)
    assert "permanently deleted" in r.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(User, uid) is None


def test_the_guard_survives_a_table_with_no_id_column(app, seeded):
    """UserPref is the reason the whole thing broke. Prove it is handled."""
    with app.app_context():
        staff = _staff(seeded["org"], "prefs", "Has Prefs")
        db.session.add(UserPref(user_id=staff.id, key="voice", value="1"))
        db.session.commit()
        # Their OWN settings must not block removing their account.
        assert _user_has_history(staff) is None


def test_every_reference_in_the_list_is_real(app, seeded):
    """A typo here would silently stop checking a table and bring the 500 back."""
    from app import models as M
    for model_name, column, label in _USER_REFERENCES:
        model = getattr(M, model_name, None)
        assert model is not None, f"{model_name} is not a real model"
        assert getattr(model, column, None) is not None, \
            f"{model_name}.{column} does not exist"
        # Must read naturally after "they have ..." — proper nouns like
        # WhatsApp are legitimately capitalised.
        assert label, f"{model_name}.{column} has no plain-English label"
        assert not label.endswith("."), f"{label!r} should not end with a stop"


def test_the_common_reasons_are_each_detected(app, seeded):
    """The five things a real staff member is most likely to have."""
    from datetime import date
    with app.app_context():
        org_id = seeded["org"]

        doctor = _staff(org_id, "doc9", "Dr Nine")
        db.session.flush()
        p = db.session.query(db.session.get(User, doctor.id).__class__).first()
        visit = PatientVisit(org_id=org_id, patient_id=None, visit_no="V-X",
                             visit_type="NEW", status="TRIAGED",
                             doctor_id=doctor.id)
        # patient_id is required; use any existing patient if the fixture has one
        from app.models import Patient
        pat = Patient(org_id=org_id, hospital_number="X/9", surname="A",
                      first_name="B", sex="F")
        db.session.add(pat)
        db.session.flush()
        visit.patient_id = pat.id
        db.session.add(visit)
        db.session.commit()
        assert "patient visits" in (_user_has_history(doctor) or "")

        hod = _staff(org_id, "hod9", "Head Nine")
        db.session.flush()
        db.session.add(Department(org_id=org_id, name="Ward Nine",
                                  hod_user_id=hod.id))
        db.session.commit()
        assert "HOD" in (_user_has_history(hod) or "")


def test_you_cannot_delete_yourself_or_the_last_super_admin(app, client, seeded):
    _admin(client, app, seeded)
    with app.app_context():
        me = db.session.query(User).filter_by(org_id=seeded["org"],
                                              role="SUPER_ADMIN").first().id
    r = client.post(f"/admin/users/{me}/delete",
                    data={"_csrf": csrf(client, "/admin/users")},
                    follow_redirects=True)
    assert "cannot delete your own account" in r.get_data(as_text=True).lower()
    with app.app_context():
        assert db.session.get(User, me) is not None


# ================================================================ the reset
def test_reset_password_opens_a_real_page(app, client, seeded):
    """It was a <details> popover inside a horizontally scrolling table.

    On a phone the panel was clipped by the table, so tapping "Reset password"
    appeared to do nothing at all.
    """
    with app.app_context():
        uid = _staff(seeded["org"], "resetme", "Reset Me").id
        db.session.commit()

    _admin(client, app, seeded)
    r = client.get(f"/admin/users/{uid}/password")
    assert r.status_code == 200, "the reset password page does not exist"
    body = r.get_data(as_text=True)
    assert "Reset Me" in body, "the page does not say whose password it is"
    assert 'name="password"' in body
    assert 'name="confirm"' in body, "no confirmation box"
    assert "10 characters" in body, "the rules are not shown"

    # ...and the list must LINK to it rather than hide a popover.
    listing = client.get("/admin/users").get_data(as_text=True)
    assert f"/admin/users/{uid}/password" in listing


def test_resetting_a_password_works_and_forces_a_change(app, client, seeded):
    with app.app_context():
        uid = _staff(seeded["org"], "resetme2", "Reset Two").id
        db.session.commit()

    _admin(client, app, seeded)
    r = client.post(f"/admin/users/{uid}/reset-password",
                    data={"_csrf": csrf(client, f"/admin/users/{uid}/password"),
                          "password": "Str0ngPassw0rd!",
                          "confirm": "Str0ngPassw0rd!"},
                    follow_redirects=True)
    assert "password reset" in r.get_data(as_text=True).lower()
    with app.app_context():
        u = db.session.get(User, uid)
        assert u.check_password("Str0ngPassw0rd!")
        assert u.must_change_password is True, \
            "the staff member was not asked to choose their own password"


def test_mismatched_passwords_are_refused(app, client, seeded):
    with app.app_context():
        uid = _staff(seeded["org"], "resetme3", "Reset Three").id
        db.session.commit()

    _admin(client, app, seeded)
    r = client.post(f"/admin/users/{uid}/reset-password",
                    data={"_csrf": csrf(client, f"/admin/users/{uid}/password"),
                          "password": "Str0ngPassw0rd!",
                          "confirm": "Different0ne"},
                    follow_redirects=True)
    assert "do not match" in r.get_data(as_text=True).lower()
    with app.app_context():
        assert not db.session.get(User, uid).check_password("Str0ngPassw0rd!")


def test_a_weak_password_is_refused_on_the_reset_page(app, client, seeded):
    with app.app_context():
        uid = _staff(seeded["org"], "resetme4", "Reset Four").id
        db.session.commit()

    _admin(client, app, seeded)
    r = client.post(f"/admin/users/{uid}/reset-password",
                    data={"_csrf": csrf(client, f"/admin/users/{uid}/password"),
                          "password": "abc", "confirm": "abc"},
                    follow_redirects=True)
    # ...and it must land back on the reset page, where the rules are visible.
    assert 'name="confirm"' in r.get_data(as_text=True), \
        "the error sent the administrator away from the rules"


def test_another_hospitals_user_cannot_be_touched(app, client, seeded):
    from app.models import Organization
    with app.app_context():
        other = Organization(code="OTHER9", name="Other")
        db.session.add(other)
        db.session.flush()
        uid = _staff(other.id, "notyours", "Not Yours").id
        db.session.commit()

    _admin(client, app, seeded)
    assert client.get(f"/admin/users/{uid}/password").status_code == 404
    assert client.post(f"/admin/users/{uid}/delete",
                       data={"_csrf": csrf(client, "/admin/users")}
                       ).status_code == 404
