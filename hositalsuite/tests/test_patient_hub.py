"""Patient & visitor service hub — the six things a patient can do.

Also re-covers the two bugs fixed alongside it:
  * the Create User form pointing at a URL that does not exist
  * migrations failing on PostgreSQL because "user" is a reserved word
"""
from app.models import Organization, QrLocation, Referral, db, new_code
from conftest import csrf, login


# ================================================================ the hub itself
def test_root_shows_the_patient_hub_to_visitors(client, seeded):
    """Regression: '/' demanded a login, so a patient scanning a QR code landed
    on a staff login screen."""
    r = client.get("/")
    assert r.status_code == 200
    assert b"hub-tile" in r.data


def test_root_still_shows_the_dashboard_to_staff(client, seeded):
    login(client, "admin")
    r = client.get("/")
    assert r.status_code == 200
    assert b"hub-tile" not in r.data, "staff must not be sent to the patient hub"


def test_hub_lists_all_six_services_in_order(client, seeded):
    html = client.get("/welcome").data.decode()
    for n, href in enumerate(["/book", "/queue/join", "/chat",
                              "/complaint", "/feedback"], start=1):
        assert f'href="{href}"' in html, f"service {n} ({href}) missing"
    # 6th is the share tile (JS-driven, not a plain link)
    assert 'id="share-tile"' in html
    # Order must be preserved — book, queue, chat, complaint, feedback, share
    # Premium tile design no longer uses numbered "1 ·" — check positional order instead
    positions = []
    for href in ["/book", "/queue/join", "/chat", "/complaint", "/feedback"]:
        pos = html.find(f'href="{href}"')
        assert pos != -1
        positions.append(pos)
    assert positions == sorted(positions), "services not in expected order"
    share_pos = html.find('id="share-tile"')
    assert share_pos > positions[-1], "share tile should be last"


def test_hub_works_in_every_language(client, seeded):
    for code, marker in [("en", "How can we help"), ("yo", "Báwo"),
                         ("ha", "Ta yaya"), ("ig", "Kedu")]:
        client.get(f"/lang/{code}?next=/welcome")
        html = client.get("/welcome").data.decode()
        assert marker in html, f"{code} translation missing from the hub"
    client.get("/lang/en?next=/welcome")


def test_hub_has_an_emergency_notice(client, seeded):
    html = client.get("/welcome").data.decode()
    assert "emerg" in html
    assert "Accident &amp; Emergency" in html or "Accident & Emergency" in html


def test_hub_offers_a_working_share_link(client, seeded):
    html = client.get("/welcome").data.decode()
    org = db.session.get(Organization, seeded["org"])
    row = db.session.query(Referral).filter_by(org_id=org.id, kind="hospital").first()
    assert row is not None, "hospital-wide referral code was not created"
    assert row.code in html
    assert "wa.me" in html or "whatsapp" in html.lower()

    # and the link actually resolves
    assert client.get(f"/r/{row.code}").status_code == 200


def test_share_link_is_reused_not_recreated(client, seeded):
    """Every hub view must not mint a new referral code."""
    client.get("/welcome")
    client.get("/welcome")
    client.get("/welcome")
    n = db.session.query(Referral).filter_by(org_id=seeded["org"], kind="hospital").count()
    assert n == 1


def test_hub_keeps_the_qr_location_tag_on_every_link(client, seeded):
    """A poster at Reception must still attribute to Reception after the patient
    picks a service from the hub."""
    loc = db.session.query(QrLocation).filter_by(org_id=seeded["org"]).first()
    html = client.get(f"/welcome?loc={loc.code}").data.decode()
    assert f"/book?loc={loc.code}" in html
    assert f"/complaint?loc={loc.code}" in html
    assert loc.name in html


def test_hub_keeps_a_referral_code_across_links(client, seeded):
    html = client.get("/welcome?ref=ABC123").data.decode()
    assert "/book?ref=ABC123" in html


def test_hub_survives_an_unknown_qr_location(client, seeded):
    r = client.get("/welcome?loc=NOSUCHCODE")
    assert r.status_code == 200
    assert b"hub-tile" in r.data


def test_every_hub_destination_actually_loads(client, seeded):
    """No dead ends: every tile must lead to a real, working page."""
    for path in ["/book", "/queue/join", "/chat", "/complaint", "/feedback",
                 "/complaint/status", "/book/status", "/privacy"]:
        assert client.get(path).status_code == 200, f"{path} is broken"


def test_hub_shows_the_hospital_phone_number(client, seeded):
    org = db.session.get(Organization, seeded["org"])
    org.phone = "08031234567"
    db.session.commit()
    html = client.get("/welcome").data.decode()
    assert "tel:08031234567" in html


# ================================================================ bug 1 regression
def test_create_user_form_targets_an_existing_route(client, seeded, app):
    """Regression: the form posted to /users/create, which does not exist, so
    pressing 'Create user' silently did nothing."""
    rules = {str(r) for r in app.url_map.iter_rules()}
    assert "/admin/users/create" in rules
    assert "/users/create" not in rules

    login(client, "admin")
    html = client.get("/admin/users").data.decode()
    assert 'action="/admin/users/create"' in html
    assert 'action="/users/create"' not in html


def test_create_user_actually_creates_a_user(client, seeded):
    from app.models import User
    login(client, "admin")
    client.post("/admin/users/create", data={
        "_csrf": csrf(client, "/admin/users"), "username": "formtest",
        "name": "Form Test", "role": "HOD", "phone": "08012223333",
        "email": "formtest@gmail.com",
        "password": "Passw0rd!x"}, follow_redirects=True)
    assert db.session.query(User).filter_by(username="formtest").first() is not None


# ================================================================ bug 2 regression
def test_migration_quotes_reserved_table_names():
    """Regression: 'user' is a RESERVED WORD in PostgreSQL. An unquoted
    ALTER TABLE user ... is a syntax error, so the new user columns would have
    been added locally on SQLite and silently skipped in production."""
    import inspect as _inspect

    from app import migrate
    src = _inspect.getsource(migrate.ensure_schema)
    assert 'ALTER TABLE "{table}"' in src, "table name must be quoted"
    assert "ALTER TABLE {table}" not in src


def test_new_user_columns_exist_after_migration(app):
    """The columns the Day 1 features depend on are really present."""
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(db.engine)
    user_cols = {c["name"] for c in insp.get_columns("user")}
    assert {"department_id", "approved"} <= user_cols
    dept_cols = {c["name"] for c in insp.get_columns("department")}
    assert {"hod_name", "hod_phone"} <= dept_cols
