"""Build 6: phone-code sign-in, security self-check, hospital sites."""
from app import mfa as engine
from app.models import Branch, Patient, PatientVisit, User, db

from conftest import csrf, login


def test_totp_round_trip():
    secret = engine.new_secret()
    code = engine.totp(secret)
    assert engine.verify_totp(secret, code)
    assert not engine.verify_totp(secret, "000000")
    assert not engine.verify_totp(secret, "abc")


def test_backup_codes_are_one_use():
    codes = engine.new_backup_codes()
    stored = engine.hash_backup_codes(codes)
    ok, remaining = engine.consume_backup_code(stored, codes[0])
    assert ok
    ok2, _ = engine.consume_backup_code(remaining, codes[0])
    assert not ok2
    ok3, remaining2 = engine.consume_backup_code(remaining, codes[1])
    assert ok3
    import json
    assert len(json.loads(remaining2)) == len(codes) - 2


def test_login_without_mfa_still_works(client, seeded):
    r = login(client, "admin")
    assert r.status_code == 302
    assert client.get("/").status_code == 200


def test_mfa_is_paused_so_staff_are_not_locked_out(client, seeded):
    """Founder was trapped on the QR screen. Phone-code lock stays off."""
    admin = db.session.get(User, seeded["admin"])
    admin.mfa_secret = engine.new_secret()
    admin.mfa_enabled = True
    db.session.commit()
    from app import services
    services.set_setting(seeded["org"], "mfa_required_roles", ["SUPER_ADMIN"])
    db.session.commit()
    r = login(client, "admin")
    assert r.status_code == 302
    loc = r.headers.get("Location", "")
    assert "/mfa/" not in loc
    assert client.get("/admin").status_code == 200
    page = client.get("/mfa/setup")
    assert page.status_code == 200
    assert b"Skip" in page.data and b"take me to my work" in page.data


def test_security_page_and_policy(client, seeded):
    login(client, "admin")
    r = client.get("/admin/security")
    assert r.status_code == 200
    assert b"Security check" in r.data
    assert b"Phone code" in r.data or b"phone code" in r.data
    client.post("/admin/security/policy",
                data={"_csrf": csrf(client, "/admin/security"),
                      "mfa_required_roles": "SUPER_ADMIN"},
                follow_redirects=True)
    from app import services
    assert "SUPER_ADMIN" in (services.get_setting(seeded["org"], "mfa_required_roles") or [])


def test_main_branch_is_created_and_second_site_works(client, seeded):
    from app.branches import ensure_main_branch
    main = ensure_main_branch(seeded["org"])
    db.session.commit()
    assert main.code == "MAIN"
    login(client, "admin")
    r = client.get("/admin/branches")
    assert r.status_code == 200
    assert b"Main" in r.data
    client.post("/admin/branches", data={
        "_csrf": csrf(client, "/admin/branches"),
        "name": "Annex", "code": "ANNEX", "address": "Other road",
    }, follow_redirects=True)
    annex = db.session.query(Branch).filter_by(org_id=seeded["org"], code="ANNEX").first()
    assert annex is not None and annex.active
    assert db.session.query(Branch).filter_by(org_id=seeded["org"]).count() == 2


def test_staff_can_be_assigned_to_a_site(client, seeded):
    from app.branches import ensure_main_branch
    main = ensure_main_branch(seeded["org"])
    db.session.commit()
    login(client, "admin")
    hod = db.session.get(User, seeded["hod"])
    client.post(f"/admin/users/{hod.id}/edit", data={
        "_csrf": csrf(client, "/admin/users"),
        "name": hod.name, "role": hod.role,
        "branch_id": main.id, "department_id": seeded["dept"],
    }, follow_redirects=True)
    hod = db.session.get(User, seeded["hod"])
    assert hod.branch_id == main.id


def test_hospital_colours_save(client, seeded):
    from app import services
    login(client, "admin")
    client.post("/admin/hospital", data={
        "_csrf": csrf(client, "/admin/hospital"),
        "name": "Test Hospital", "code": "TEST",
        "brand_primary": "#112233", "brand_accent": "#445566",
        "brand_gold": "#FFCC00",
    }, follow_redirects=True)
    assert services.get_setting(seeded["org"], "brand_primary") == "#112233"
    page = client.get("/")
    assert b"#112233" in page.data


def test_branch_filter_hides_other_site(app, seeded):
    from app.branches import apply_branch_filter, ensure_main_branch
    main = ensure_main_branch(seeded["org"])
    annex = Branch(org_id=seeded["org"], code="ANNEX", name="Annex", active=True)
    db.session.add(annex)
    db.session.flush()
    hod = db.session.get(User, seeded["hod"])
    hod.branch_id = annex.id
    db.session.add(Patient(org_id=seeded["org"], hospital_number="TES/2026/00001",
                           surname="MAIN", first_name="Site", sex="F", age_years=20,
                           payer_type="SELF", category="GENERAL", branch_id=main.id))
    db.session.add(Patient(org_id=seeded["org"], hospital_number="TES/2026/00002",
                           surname="ANNEX", first_name="Site", sex="M", age_years=20,
                           payer_type="SELF", category="GENERAL", branch_id=annex.id))
    db.session.commit()
    q = apply_branch_filter(db.session.query(Patient), Patient.branch_id, user=hod)
    names = {p.surname for p in q.all()}
    assert names == {"ANNEX"}


def test_pentest_self_check_has_no_fails_on_headers(client, seeded, app):
    from app import pentest
    probe = client.get("/login")
    checks = pentest.run(app, seeded["org"], sample_headers=dict(probe.headers))
    header_ids = {"csp", "xfo", "nosniff", "referrer", "coop"}
    for c in checks:
        if c.id in header_ids:
            assert c.level == "pass", c
    # default SECRET_KEY in tests is test-secret → warn, never a crash
    assert any(c.id == "secret" for c in checks)
