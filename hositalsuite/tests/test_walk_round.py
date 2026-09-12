"""The Admin Manager hospital walk-round: 24 areas, five criteria, one page."""
from app import scoring
from app.inspection_areas import (AREA_KEYS, INSPECTION_AREAS,
                                  match_department)
from app.models import Department, Inspection, InspectionScore, db, now_naive
from tests.conftest import csrf, login


# ------------------------------------------------------------------ criteria
def test_the_five_criteria_are_the_ones_the_founder_asked_for(app, seeded):
    titles = [scoring.CRITERIA[n]["title"] for n in range(1, 6)]
    assert "Staff / Personnel" == titles[0]
    assert "Equipment" in titles[1] and "Consumable" in titles[1]
    assert "Cleanliness" in titles[2]
    assert "Power" in titles[3] and "Engineering" in titles[3]
    assert titles[4], "a fifth criterion must exist"
    assert len(scoring.CRITERIA) == 5, "exactly five criteria — never a sixth"


def test_old_inspections_keep_their_original_criteria_wording(app, seeded):
    """An inspection is a signed record; its criteria must not silently change."""
    v1 = scoring.criteria_for(1)
    assert v1[4]["title"] == "Records, Compliance & Accountability"
    v2 = scoring.criteria_for(2)
    assert v2[4]["title"] == "Power & Engineering Service"
    assert scoring.criteria_for(None) is scoring.CRITERIA


# ------------------------------------------------------------------ the areas
def test_every_area_the_founder_listed_is_present(app, seeded):
    labels = {label for _, label, _ in INSPECTION_AREAS}
    for wanted in ("Engineering", "Laboratory", "Female Ward", "Laundry",
                   "Male Ward", "Pharmacy / Dispensary", "ICU / HDU", "Theatre",
                   "Kitchen / Canteen", "Child Welfare", "Billing Point",
                   "HIMS", "Dental Services", "Megalex / Paying Point",
                   "Triage / Reception", "Accident & Emergency", "Transport",
                   "Driver", "Fast-Track Centre", "Isolation Ward"):
        assert wanted in labels, f"{wanted} is missing from the walk-round"
    assert len(INSPECTION_AREAS) == 24
    assert len(set(AREA_KEYS)) == 24, "area keys must be unique"


def test_areas_match_real_departments_even_when_named_differently(app, seeded):
    with app.app_context():
        org_id = seeded["org"]
        for name in ("Laboratory", "Pharmacy", "Accident & Emergency"):
            db.session.add(Department(org_id=org_id, name=name))
        db.session.commit()
        depts = db.session.query(Department).filter_by(org_id=org_id).all()

        assert match_department("laboratory", depts).name == "Laboratory"
        assert match_department("pharmacy", depts).name == "Pharmacy"
        assert match_department("a_and_e", depts).name == "Accident & Emergency"
        # An area with no matching department is not a crash — it is a card
        # that tells the manager to add the department first.
        assert match_department("isolation", depts) is None


# ------------------------------------------------------------------ the page
def _login_am(client, app, seeded):
    """Sign in as the Admin Manager (conftest.login handles CSRF)."""
    with app.app_context():
        from app.models import User
        u = db.session.query(User).filter_by(org_id=seeded["org"],
                                             role="ADMIN_MANAGER").first()
        u.must_change_password = False
        db.session.commit()
        username = u.username
    return login(client, username)


def test_walk_page_shows_every_area_and_the_overall_report_box(app, client, seeded):
    _login_am(client, app, seeded)
    r = client.get("/admin-manager/walk")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    for label in ("Engineering", "Laundry", "ICU / HDU", "Isolation Ward",
                  "Megalex / Paying Point"):
        assert label in body, f"{label} card missing from the page"
    # the Admin Manager's own overall situation report, with voice-to-text
    assert 'name="overall_report"' in body
    assert "hmsVoice.start(this,'overall_report')" in body
    # cards must be collapsible and self-contained
    assert "hmsWalk.toggle(" in body
    assert 'name="laundry_score_1"' in body
    assert 'name="laundry_explanation_1"' in body


def test_each_card_names_the_staff_on_duty_from_the_roster(app, client, seeded):
    from datetime import date

    from app.models import RosterEntry, User
    with app.app_context():
        org_id = seeded["org"]
        dept = Department(org_id=org_id, name="Laundry")
        db.session.add(dept)
        db.session.flush()
        nurse = User(org_id=org_id, username="wash1", name="Bisi Laundry",
                     role="HOD", department_id=dept.id)
        nurse.set_password("Passw0rd!x")
        db.session.add(nurse)
        db.session.flush()
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=nurse.id, kind="DUTY", shift="DAY",
                                   scope="DEPARTMENT", department_id=dept.id))
        db.session.commit()

    _login_am(client, app, seeded)
    body = client.get("/admin-manager/walk").get_data(as_text=True)
    assert "Bisi Laundry" in body, "the roster name is not shown on the card"


def test_someone_on_leave_is_not_shown_as_on_duty(app, seeded):
    """Listing a person on annual leave as 'on duty' sends the manager hunting."""
    from datetime import date

    from app import rosterdata
    from app.models import RosterEntry, User
    with app.app_context():
        org_id = seeded["org"]
        dept = Department(org_id=org_id, name="Kitchen")
        db.session.add(dept)
        db.session.flush()
        cook = User(org_id=org_id, username="cook1", name="Ade Cook",
                    role="HOD", department_id=dept.id)
        cook.set_password("Passw0rd!x")
        db.session.add(cook)
        db.session.flush()
        db.session.add(RosterEntry(org_id=org_id, duty_date=now_naive().date(),
                                   user_id=cook.id, kind="LEAVE", shift="LEAVE",
                                   leave_type="ANNUAL", scope="DEPARTMENT",
                                   department_id=dept.id))
        db.session.commit()

        on_duty = rosterdata.on_duty_in(org_id, date.today(), dept.id)
        assert on_duty == [], "somebody on leave was listed as on duty"


def test_submitting_the_walk_saves_only_the_areas_actually_scored(app, client, seeded):
    with app.app_context():
        org_id = seeded["org"]
        db.session.add(Department(org_id=org_id, name="Laundry"))
        db.session.add(Department(org_id=org_id, name="Laboratory"))
        db.session.commit()

    _login_am(client, app, seeded)
    data = {f"laundry_score_{n}": "4" for n in range(1, 6)}
    data["overall_report"] = "Calm morning. Power held overnight."
    data["_csrf"] = csrf(client, "/admin-manager/walk")
    r = client.post("/admin-manager/walk", data=data, follow_redirects=True)
    assert r.status_code == 200

    with app.app_context():
        saved = db.session.query(Inspection).filter_by(org_id=seeded["org"]).all()
        assert len(saved) == 1, "a blank area should not create an inspection"
        assert saved[0].total_score == 20
        assert saved[0].final_comment.startswith("Calm morning")

    # An area he simply did not visit must be SILENT — not an error message.
    # Nagging him about 23 untouched areas every time he saves would train him
    # to ignore the errors that matter.
    body = r.get_data(as_text=True)
    assert "Laboratory: please score" not in body
    assert body.lower().count("please score all five criteria") == 0, \
        "untouched areas produced complaints"


def test_a_low_score_cannot_be_saved_without_a_reason(app, client, seeded):
    """Score 1 or 2 demands a justification — enforced on the SERVER."""
    with app.app_context():
        db.session.add(Department(org_id=seeded["org"], name="Laundry"))
        db.session.commit()

    _login_am(client, app, seeded)
    data = {f"laundry_score_{n}": "4" for n in range(2, 6)}
    data["laundry_score_1"] = "1"          # critical, with no explanation
    data["_csrf"] = csrf(client, "/admin-manager/walk")
    r = client.post("/admin-manager/walk", data=data, follow_redirects=True)
    assert r.status_code == 200
    assert "reason is required" in r.get_data(as_text=True).lower()

    with app.app_context():
        assert db.session.query(Inspection).count() == 0, \
            "a critical score was saved with no justification"


def test_a_low_score_with_a_reason_saves_and_keeps_the_reason(app, client, seeded):
    with app.app_context():
        db.session.add(Department(org_id=seeded["org"], name="Laundry"))
        db.session.commit()

    _login_am(client, app, seeded)
    data = {f"laundry_score_{n}": "4" for n in range(2, 6)}
    data["laundry_score_1"] = "2"
    data["laundry_explanation_1"] = "Two staff absent, linen not turned round."
    data["_csrf"] = csrf(client, "/admin-manager/walk")
    client.post("/admin-manager/walk", data=data, follow_redirects=True)

    with app.app_context():
        insp = db.session.query(Inspection).one()
        row = (db.session.query(InspectionScore)
               .filter_by(inspection_id=insp.id, criterion_no=1).one())
        assert row.score == 2
        assert "Two staff absent" in row.explanation


def test_partial_scoring_of_one_area_is_refused(app, client, seeded):
    """Three scores out of five is not an inspection — say so, do not guess."""
    with app.app_context():
        db.session.add(Department(org_id=seeded["org"], name="Laundry"))
        db.session.commit()

    _login_am(client, app, seeded)
    data = {"laundry_score_1": "4", "laundry_score_2": "4", "laundry_score_3": "4",
            "_csrf": csrf(client, "/admin-manager/walk")}
    r = client.post("/admin-manager/walk", data=data, follow_redirects=True)
    assert "all five criteria" in r.get_data(as_text=True).lower()
    with app.app_context():
        assert db.session.query(Inspection).count() == 0
