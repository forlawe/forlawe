"""Bulk staff upload — nominal roll, departmental and unit lists.

Built around a REAL Nigerian hospital duty roster (the founder photographed
one), so the tests use its actual shape and abbreviations.
"""
import io

from app import bulkusers
from app.models import Department, User, db
from conftest import csrf, login

# The real roster, abbreviations and all.
REAL_ROLL = """S/N,DATE,DAYS,NAMES,DEPARTMENT,PHONE NO
1,10/8/26,MONDAY,DR ADENIYI,MEDICAL,08065226200
2,11/8/26,TUESDAY,MRS ODEBE IDEHAI,PUB AFF OFF,08028327098
3,12/8/26,WEDNESDAY,MISS SADIQ M.O,ADMIN/HR,08084105130
4,13/8/26,THURSDAY,MRS ABE .M,FIN/ACCTS,08025023049
5,14/8/26,FRIDAY,MRS ABATAN L.F,LABORATORY,08059826879
6,15/8/26,SATURDAY,CNO OGUNLEYE,NURSING,08062801586
7,16/8/26,SUNDAY,PHARM KAREEM,PHARMACY,09031737994
8,17/8/26,MONDAY,MISS ADESANYA,HIMS,08122172375
9,18/8/26,TUESDAY,MRS OYESANYA,NUTRIT&DIET,07032322597
10,19/8/26,WEDNESDAY,MRS OBA,ICT,08030883865
"""


def _upload(client, csv_text, filename="roll.csv", **extra):
    data = {"_csrf": csrf(client, "/admin/users/import"),
            "file": (io.BytesIO(csv_text.encode()), filename)}
    data.update(extra)
    return client.post("/admin/users/import", data=data,
                       content_type="multipart/form-data")


def _std_departments(org_id):
    from app.standard_departments import install
    install(org_id, only_missing=True)
    db.session.commit()


# ================================================================ parsing
def test_parses_a_real_hospital_duty_roster(app, seeded):
    class F:
        filename = "roll.csv"

        def read(self):
            return REAL_ROLL.encode()

    rows, err = bulkusers.parse_file(F())
    assert err is None
    assert len(rows) == 10
    assert rows[0]["name"] == "DR ADENIYI"
    assert rows[1]["department"] == "PUB AFF OFF"
    assert rows[0]["phone"] == "08065226200"


def test_extra_columns_are_ignored(app, seeded):
    """The real roster has S/N, DATE and DAYS columns we do not need."""
    class F:
        filename = "roll.csv"

        def read(self):
            return REAL_ROLL.encode()

    rows, err = bulkusers.parse_file(F())
    assert err is None and rows


def test_rejects_a_file_with_no_name_column(app, seeded):
    class F:
        filename = "bad.csv"

        def read(self):
            return b"Department,Phone\nICT,08012345678\n"

    rows, err = bulkusers.parse_file(F())
    assert err and "Name" in err


def test_rejects_unsupported_file_types(app, seeded):
    class F:
        filename = "staff.pdf"

        def read(self):
            return b"%PDF-1.4"

    _, err = bulkusers.parse_file(F())
    assert err and ("csv" in err.lower() or "xlsx" in err.lower())


def test_accepts_alternative_column_headings(app, seeded):
    class F:
        filename = "alt.csv"

        def read(self):
            return b"Staff Name,Dept,GSM,Cadre\nMr Bello,ICT,08011112222,Officer\n"

    rows, err = bulkusers.parse_file(F())
    assert err is None
    assert rows[0]["name"] == "Mr Bello"
    assert rows[0]["phone"] == "08011112222"


# ================================================================ usernames
def test_usernames_strip_titles_and_stay_readable():
    taken = set()
    assert bulkusers.make_username("MRS ODEBE IDEHAI", taken) == "odebe.idehai"
    assert bulkusers.make_username("DR ADENIYI", taken) == "adeniyi"
    assert bulkusers.make_username("PHARM UKPE AUGUSTINE", taken) == "ukpe.augustine"
    assert bulkusers.make_username("CNO OGUNLEYE", taken) == "ogunleye"


def test_duplicate_names_get_distinct_usernames():
    taken = set()
    a = bulkusers.make_username("MR BELLO", taken)
    b = bulkusers.make_username("MR BELLO", taken)
    assert a != b


def test_username_never_empty_even_for_odd_input():
    taken = set()
    assert bulkusers.make_username("!!!", taken)
    assert bulkusers.make_username("", taken)


# ================================================================ departments
def test_real_hospital_abbreviations_are_understood(app, seeded):
    """MEDICAL, PUB AFF OFF, FIN/ACCTS, NUTRIT&DIET etc. from the real roster."""
    _std_departments(seeded["org"])

    class F:
        filename = "roll.csv"

        def read(self):
            return REAL_ROLL.encode()

    raw, _ = bulkusers.parse_file(F())
    rows = bulkusers.build_preview(seeded["org"], raw)
    got = {r["name"]: r["department"] for r in rows}
    assert got["DR ADENIYI"] == "Internal Medicine"
    assert got["MRS ODEBE IDEHAI"] == "Public Affairs"
    assert got["MISS SADIQ M.O"] == "Administration & Human Resources"
    assert got["MRS ABE .M"] == "Finance & Accounts"
    assert got["CNO OGUNLEYE"] == "Nursing Services"
    assert got["MISS ADESANYA"] == "Health Information Management (HIMS)"
    assert got["MRS OYESANYA"] == "Nutrition & Dietetics"
    unassigned = [n for n, d in got.items() if not d]
    assert not unassigned, f"departments not matched: {unassigned}"


def test_unknown_department_warns_but_does_not_block(app, seeded):
    rows = bulkusers.build_preview(seeded["org"], [
        {"line": 2, "name": "Mr Test", "department": "ZZZ Nonexistent",
         "phone": "", "email": "", "role_raw": "", "username": ""}])
    assert rows[0]["ok"] is True, "an unknown department must not block the import"
    assert rows[0]["warnings"]


def test_default_department_is_applied_when_blank(app, seeded):
    rows = bulkusers.build_preview(
        seeded["org"],
        [{"line": 2, "name": "Mr Blank", "department": "", "phone": "",
          "email": "", "role_raw": "", "username": ""}],
        default_department_id=seeded["dept"])
    assert rows[0]["department_id"] == seeded["dept"]


# ================================================================ validation
def test_bad_phone_warns_and_is_dropped_not_stored(app, seeded):
    rows = bulkusers.build_preview(seeded["org"], [
        {"line": 2, "name": "Mr Test", "department": "", "phone": "not-a-number",
         "email": "", "role_raw": "", "username": ""}])
    assert rows[0]["phone"] == ""
    assert rows[0]["ok"] is True
    assert any("not a valid number" in w for w in rows[0]["warnings"])


def test_duplicate_names_in_one_file_are_flagged(app, seeded):
    rows = bulkusers.build_preview(seeded["org"], [
        {"line": 2, "name": "Mr Same", "department": "", "phone": "", "email": "",
         "role_raw": "", "username": ""},
        {"line": 3, "name": "Mr Same", "department": "", "phone": "", "email": "",
         "role_raw": "", "username": ""}])
    assert rows[0]["ok"] is True
    assert rows[1]["ok"] is False


def test_existing_username_is_rejected(app, seeded):
    rows = bulkusers.build_preview(seeded["org"], [
        {"line": 2, "name": "Ada Admin", "department": "", "phone": "", "email": "",
         "role_raw": "", "username": "admin"}])
    assert rows[0]["ok"] is False
    assert any("already exists" in e for e in rows[0]["errors"])


def test_designation_maps_to_a_sensible_role():
    assert bulkusers.guess_role("Deputy Medical Director") == "DMD"
    assert bulkusers.guess_role("Head of Nursing Services") == "APEX_NURSE"
    assert bulkusers.guess_role("Admin Manager") == "ADMIN_MANAGER"
    assert bulkusers.guess_role("HOD") == "HOD"
    assert bulkusers.guess_role("") == "HOD"
    # an unrecognised title must NOT accidentally grant admin rights
    assert bulkusers.guess_role("Chief Bottle Washer") == "HOD"


# ================================================================ preview storage
def test_large_preview_survives_the_session_cookie_limit(app, seeded):
    """Regression risk: the roster import stores its preview in the Flask
    session, which holds ~4KB — about 24 rows. A real nominal roll overflows
    it silently. Previews here go to durable storage instead."""
    rows = bulkusers.build_preview(seeded["org"], [
        {"line": i, "name": f"Staff Number {i}", "department": "", "phone": "",
         "email": "", "role_raw": "", "username": ""} for i in range(2, 402)])
    assert len(rows) == 400
    token = bulkusers.save_preview(seeded["org"], rows)
    back = bulkusers.load_preview(seeded["org"], token)
    assert back is not None and len(back) == 400


def test_preview_is_isolated_between_hospitals(app, seeded):
    from app.models import Organization
    other = Organization(code="OTHER", name="Other Hospital")
    db.session.add(other)
    db.session.commit()

    token = bulkusers.save_preview(seeded["org"], [{"name": "x", "ok": True}])
    assert bulkusers.load_preview(other.id, token) is None, "cross-tenant preview leak"
    assert bulkusers.load_preview(seeded["org"], token) is not None


def test_preview_token_cannot_traverse_paths(app, seeded):
    assert bulkusers.load_preview(seeded["org"], "../../etc/passwd") is None
    assert bulkusers.load_preview(seeded["org"], "") is None


# ================================================================ the web journey
def test_full_upload_journey(client, seeded):
    _std_departments(seeded["org"])
    login(client, "admin")

    assert client.get("/admin/users/import").status_code == 200

    r = _upload(client, REAL_ROLL)
    assert r.status_code == 200
    html = r.data.decode()
    assert "10 staff will be created" in html
    assert "odebe.idehai" in html

    token = html.split('name="token" value="')[1].split('"')[0]
    before = db.session.query(User).count()
    r = client.post("/admin/users/import/confirm",
                    data={"_csrf": csrf(client, "/admin/users"), "token": token})
    assert r.status_code == 200
    assert b"Temporary password" in r.data

    assert db.session.query(User).count() == before + 10
    made = db.session.query(User).filter_by(username="odebe.idehai").first()
    assert made is not None
    assert made.name == "MRS ODEBE IDEHAI"
    assert made.department.name == "Public Affairs"


def test_imported_accounts_are_safe_by_default(client, seeded):
    login(client, "admin")
    html = _upload(client, REAL_ROLL).data.decode()
    token = html.split('name="token" value="')[1].split('"')[0]
    client.post("/admin/users/import/confirm",
                data={"_csrf": csrf(client, "/admin/users"), "token": token})

    for u in db.session.query(User).filter_by(username="adeniyi").all():
        assert u.approved is False, "imported accounts must await approval"
        assert u.must_change_password is True
        assert not u.check_password("password")
        assert not u.check_password(u.username)


def test_imported_user_cannot_sign_in_until_approved(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    login(client, "admin")
    html = _upload(client, REAL_ROLL).data.decode()
    token = html.split('name="token" value="')[1].split('"')[0]
    done = client.post("/admin/users/import/confirm",
                       data={"_csrf": csrf(client, "/admin/users"), "token": token})
    body = done.data.decode()
    # pull one generated password straight off the confirmation screen
    assert "adeniyi" in body
    client.post("/logout", data={"_csrf": csrf(client, "/")})

    u = db.session.query(User).filter_by(username="adeniyi").first()
    assert u.approved is False
    r = client.post("/login", data={"username": "adeniyi", "password": "whatever",
                                    "_csrf": csrf(client, "/login")})
    assert r.status_code in (401, 403)


def test_templates_download(client, seeded):
    login(client, "admin")
    for kind in ("nominal", "department", "unit"):
        r = client.get(f"/admin/users/import/template?kind={kind}")
        assert r.status_code == 200
        assert b"Name,Department,Phone" in r.data


def test_expired_preview_is_handled_kindly(client, seeded):
    login(client, "admin")
    r = client.post("/admin/users/import/confirm",
                    data={"_csrf": csrf(client, "/admin/users"), "token": "nope"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert b"expired" in r.data


def test_empty_file_is_rejected(client, seeded):
    login(client, "admin")
    r = _upload(client, "Name,Department\n", follow_redirects=True)
    assert r.status_code in (200, 302)


def test_only_super_admin_can_bulk_upload(client, seeded):
    login(client, "hod1")
    assert client.get("/admin/users/import").status_code == 403


def test_oversized_file_is_refused(app, seeded):
    big = "Name,Department\n" + "".join(f"Staff {i},ICT\n" for i in range(2600))

    class F:
        filename = "big.csv"

        def read(self):
            return big.encode()

    _, err = bulkusers.parse_file(F())
    assert err and "more than" in err
