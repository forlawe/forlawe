"""Roles, standard departments, patient navigation, help desk, and the 404 fix."""
from app.models import (MANAGEMENT_ROLES, ROLES, Department, Organization,
                        Section, Unit, User, db, role_label)
from conftest import csrf, login


# ================================================================ item 9: the 404
def test_section_and_unit_urls_point_at_real_routes(app):
    """Regression: the structure page posted to /admin/section/<id>/delete but
    the route is /admin/structure/section/<id>/delete — every section and unit
    edit/delete returned 404."""
    rules = {str(r) for r in app.url_map.iter_rules()}
    for path in ["/admin/structure/section/<int:sid>/edit",
                 "/admin/structure/section/<int:sid>/delete",
                 "/admin/structure/unit/<int:uid_>/edit",
                 "/admin/structure/unit/<int:uid_>/delete"]:
        assert path in rules
    for dead in ["/admin/section/<int:sid>/delete", "/admin/unit/<int:uid_>/delete"]:
        assert dead not in rules

    html = open("app/templates/admin/structure.html").read()
    assert 'action="/admin/section/' not in html
    assert 'action="/admin/unit/' not in html


def test_every_template_link_resolves(app):
    """Catch this whole class of bug automatically."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "tools/check_links.py"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_section_delete_actually_works(client, seeded):
    login(client, "admin")
    dept = db.session.get(Department, seeded["dept"])
    sec = Section(org_id=seeded["org"], department_id=dept.id, name="Temp Section")
    db.session.add(sec)
    db.session.commit()
    sid = sec.id
    r = client.post(f"/admin/structure/section/{sid}/delete",
                    data={"_csrf": csrf(client, "/admin/structure")}, follow_redirects=False)
    assert r.status_code == 302, "section delete 404'd again"
    assert db.session.get(Section, sid) is None


# ================================================================ item 7: roles
def test_all_four_new_roles_exist():
    for code in ("DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR"):
        assert code in ROLES, f"{code} missing"
        assert role_label(code) != code, f"{code} has no readable label"
    assert "Deputy Medical Director" in role_label("DMD")
    assert "Clinical Services" in role_label("DCST")
    assert "Nursing" in role_label("APEX_NURSE")
    assert "Admin" in role_label("HEAD_ADMIN_HR")


def test_new_roles_can_be_created_and_signed_in(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    login(client, "admin")
    for code in ("DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR"):
        client.post("/admin/users/create", data={
            "_csrf": csrf(client, "/admin/users"), "username": code.lower(),
            "name": f"Test {code}", "role": code, "password": "Passw0rd!x",
            "email": f"{code.lower()}@gmail.com"},
            follow_redirects=True)
        u = db.session.query(User).filter_by(username=code.lower()).first()
        assert u is not None, f"could not create a {code}"
        assert u.role == code
        assert u.is_management is True, f"{code} should have management sight"


def test_management_roles_see_the_dashboard(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    u = User(org_id=seeded["org"], username="dmd1", name="Deputy MD", role="DMD")
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.commit()

    login(client, "dmd1")
    assert client.get("/dashboard").status_code == 200
    assert client.get("/reports").status_code == 200


def test_role_dropdown_offers_every_role(client, seeded):
    login(client, "admin")
    html = client.get("/admin/users").data.decode()
    for code in ROLES:
        assert f'value="{code}"' in html, f"{code} missing from the role dropdown"


def test_escalation_reaches_the_deputy_md(app, seeded):
    """A breach must still reach a decision-maker when the MD is away."""
    from app import notifications
    dep = User(org_id=seeded["org"], username="dmd2", name="Deputy", role="DMD",
               phone="2348000000009")
    dep.set_password("Passw0rd!x")
    db.session.add(dep)
    db.session.commit()
    targets = {u.username for u in notifications.md_ceos(seeded["org"])}
    assert "dmd2" in targets, "the Deputy MD is not an escalation target"
    assert "md" in targets, "the MD/CEO must still be notified"


# ================================================================ item 6: departments
def test_standard_department_catalogue_is_sensible():
    from app.standard_departments import STANDARD_DEPARTMENTS, department_names
    names = department_names()
    assert len(names) >= 25, "a general hospital needs a fuller structure"
    assert len(names) == len(set(names)), "duplicate department in the catalogue"
    for expected in ["Accident & Emergency", "Internal Medicine", "Surgery",
                     "Obstetrics & Gynaecology", "Paediatrics", "Laboratory",
                     "Pharmacy", "Radiology / Imaging", "Nursing Services",
                     "Health Information Management (HIMS)", "Finance & Accounts",
                     "Administration & Human Resources", "Environmental Health"]:
        assert expected in names, f"missing standard department: {expected}"
    # every department must have at least one section, and every section a unit
    for dept, sections in STANDARD_DEPARTMENTS:
        assert sections, f"{dept} has no sections"
        for sec, units in sections:
            assert units, f"{dept} / {sec} has no units"


def test_installing_standard_departments_is_idempotent(app, seeded):
    from app.standard_departments import install
    first = install(seeded["org"], only_missing=True)
    db.session.commit()
    assert first["departments"] > 20

    second = install(seeded["org"], only_missing=True)
    db.session.commit()
    assert second["departments"] == 0, "re-running duplicated departments"

    names = [d.name for d in db.session.query(Department)
             .filter_by(org_id=seeded["org"]).all()]
    assert len(names) == len(set(names)), "duplicate departments created"


def test_install_button_never_touches_existing_departments(client, seeded):
    """The hospital's own customised departments must survive untouched."""
    existing = db.session.get(Department, seeded["dept"])
    existing.hod_name = "Dr. Original"
    db.session.commit()
    original_name = existing.name

    login(client, "admin")
    r = client.post("/admin/structure/install-standard",
                    data={"_csrf": csrf(client, "/admin/structure")}, follow_redirects=True)
    assert r.status_code == 200

    still = db.session.get(Department, seeded["dept"])
    assert still.name == original_name
    assert still.hod_name == "Dr. Original", "an existing department was overwritten"


# ================================================================ items 3 & 5
PATIENT_PAGES = ["/chat", "/complaint", "/book", "/queue/join", "/feedback",
                 "/privacy", "/privacy/request", "/complaint/status", "/book/status"]


def test_every_patient_page_has_a_back_link(client, seeded):
    missing = []
    for p in PATIENT_PAGES:
        html = client.get(p).data.decode()
        if "patient-back" not in html and 'class="back"' not in html:
            missing.append(p)
    assert not missing, f"no way back from: {missing}"


def test_every_patient_page_shows_the_help_desk_phone(client, seeded):
    org = db.session.get(Organization, seeded["org"])
    org.phone = "09154967034"
    db.session.commit()
    missing = []
    for p in PATIENT_PAGES + ["/welcome"]:
        if "tel:" not in client.get(p).data.decode():
            missing.append(p)
    assert not missing, f"no help desk number on: {missing}"


def test_help_desk_degrades_when_no_phone_is_set(client, seeded):
    org = db.session.get(Organization, seeded["org"])
    org.phone = None
    org.phone_alt = None
    db.session.commit()
    html = client.get("/complaint").data.decode()
    assert "reception" in html.lower(), "should tell the patient to ask at reception"


def test_back_and_help_text_translate(client, seeded):
    for code, back_word in [("yo", "Padà"), ("ha", "Koma"), ("ig", "Laghachi")]:
        client.get(f"/lang/{code}?next=/complaint")
        assert back_word in client.get("/complaint").data.decode()
    client.get("/lang/en?next=/complaint")
