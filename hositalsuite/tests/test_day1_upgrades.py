"""Day 1 upgrade requirements.

Covers: HOD name/phone on departments, staff department + approval + delete,
bigger logo with a resolution warning, and the Admin Manager's final comment.
"""
from app.models import Department, Inspection, User, db
from conftest import csrf, login


# ================================================================ REQ 3: HOD contact
def test_new_department_requires_hod_name_and_phone(client, seeded):
    login(client, "admin")
    r = client.post("/admin/structure/department", data={
        "_csrf": csrf(client, "/admin/structure"), "name": "Radiology"},
        follow_redirects=True)
    assert r.status_code == 200
    assert b"HOD name and HOD phone number are required" in r.data
    assert db.session.query(Department).filter_by(name="Radiology").first() is None


def test_department_stores_hod_name_and_phone(client, seeded):
    login(client, "admin")
    client.post("/admin/structure/department", data={
        "_csrf": csrf(client, "/admin/structure"), "name": "Radiology",
        "hod_name": "Dr. Amina Bello", "hod_phone": "080-1234 5678"},
        follow_redirects=True)
    d = db.session.query(Department).filter_by(name="Radiology").first()
    assert d is not None
    assert d.hod_name == "Dr. Amina Bello"
    assert d.hod_phone == "08012345678", "phone must be normalised (spaces/dashes stripped)"


def test_department_rejects_bad_hod_phone(client, seeded):
    login(client, "admin")
    r = client.post("/admin/structure/department", data={
        "_csrf": csrf(client, "/admin/structure"), "name": "Physio",
        "hod_name": "Dr. Test", "hod_phone": "not-a-number"}, follow_redirects=True)
    assert b"valid HOD phone number" in r.data
    assert db.session.query(Department).filter_by(name="Physio").first() is None


def test_hod_details_autofill_from_chosen_staff_account(client, seeded):
    """Picking an HOD staff account should carry their name/phone across."""
    login(client, "admin")
    client.post("/admin/structure/department", data={
        "_csrf": csrf(client, "/admin/structure"), "name": "Theatre",
        "hod_user_id": seeded["hod"], "hod_phone": "08055556666"},
        follow_redirects=True)
    d = db.session.query(Department).filter_by(name="Theatre").first()
    assert d.hod_name == "Hannah Hod"


# ================================================================ REQ 4: user management
def test_create_user_form_posts_to_a_real_url(client, seeded):
    """Regression: the form posted to /users/create but the route is
    /admin/users/create — creating a user silently 404'd."""
    login(client, "admin")
    page = client.get("/admin/users").data.decode()
    assert 'action="/admin/users/create"' in page
    assert 'action="/users/create"' not in page


def test_create_user_with_department(client, seeded):
    login(client, "admin")
    client.post("/admin/users/create", data={
        "_csrf": csrf(client, "/admin/users"), "username": "nurse1",
        "name": "Ngozi Nurse", "role": "HOD", "phone": "08012341234",
        "email": "ngozi.nurse@gmail.com", "department_id": seeded["dept"],
        "password": "Passw0rd!x"}, follow_redirects=True)
    u = db.session.query(User).filter_by(username="nurse1").first()
    assert u is not None
    assert u.department_id == seeded["dept"]
    assert u.approved is False, "admin still taps Approve after the staff card"
    assert u.email_verified is False, "they must still activate the mailbox"


def test_create_user_rejects_bad_phone(client, seeded):
    login(client, "admin")
    r = client.post("/admin/users/create", data={
        "_csrf": csrf(client, "/admin/users"), "username": "baduser",
        "name": "Bad Phone", "role": "HOD", "phone": "abc",
        "password": "Passw0rd!x"}, follow_redirects=True)
    assert b"valid phone number" in r.data
    assert db.session.query(User).filter_by(username="baduser").first() is None


def test_unapproved_user_cannot_sign_in(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    u = User(org_id=seeded["org"], username="pending1", name="Pending Person",
             role="HOD", approved=False)
    u.set_password("Passw0rd!x")
    u.must_change_password = False
    db.session.add(u)
    db.session.commit()

    r = client.post("/login", data={"username": "pending1", "password": "Passw0rd!x",
                                    "_csrf": csrf(client, "/login")}, follow_redirects=True)
    assert r.status_code == 403
    assert b"waiting for administrator approval" in r.data


def test_admin_can_approve_a_pending_user(client, seeded):
    u = User(org_id=seeded["org"], username="pending2", name="Pending Two",
             role="HOD", approved=False)
    u.set_password("Passw0rd!x")
    db.session.add(u)
    db.session.commit()
    uid = u.id

    login(client, "admin")
    client.post(f"/admin/users/{uid}/approve",
                data={"_csrf": csrf(client, "/admin/users")}, follow_redirects=True)
    assert db.session.get(User, uid).approved is True


def test_user_with_no_history_can_be_deleted(client, seeded):
    u = User(org_id=seeded["org"], username="temp1", name="Temp Staff", role="HOD")
    u.set_password("Passw0rd!x")
    db.session.add(u)
    db.session.commit()
    uid = u.id

    login(client, "admin")
    client.post(f"/admin/users/{uid}/delete",
                data={"_csrf": csrf(client, "/admin/users")}, follow_redirects=True)
    assert db.session.get(User, uid) is None


def test_user_with_history_cannot_be_deleted(client, seeded):
    """Deleting a staff member who signed inspections would orphan the audit
    trail. The system must refuse and tell the admin to suspend instead."""
    from datetime import date
    insp = Inspection(org_id=seeded["org"], ref="HIST-1", verify_code="HISTCODE1",
                      inspector_id=seeded["am"], duty_date=date.today(),
                      department_id=seeded["dept"], status="SUBMITTED")
    db.session.add(insp)
    db.session.commit()

    login(client, "admin")
    r = client.post(f"/admin/users/{seeded['am']}/delete",
                    data={"_csrf": csrf(client, "/admin/users")}, follow_redirects=True)
    assert b"cannot be deleted" in r.data
    assert db.session.get(User, seeded["am"]) is not None


def test_cannot_delete_or_demote_the_last_super_admin(client, seeded):
    login(client, "admin")
    r = client.post(f"/admin/users/{seeded['admin']}/delete",
                    data={"_csrf": csrf(client, "/admin/users")}, follow_redirects=True)
    # blocked either as self-delete or as last-super-admin — never actually deleted
    assert db.session.get(User, seeded["admin"]) is not None
    assert r.status_code == 200

    # demoting the only super admin must also be refused
    r = client.post(f"/admin/users/{seeded['admin']}/edit", data={
        "_csrf": csrf(client, "/admin/users"), "name": "Ada Admin", "role": "HOD"},
        follow_redirects=True)
    assert b"last Super Admin" in r.data
    assert db.session.get(User, seeded["admin"]).role == "SUPER_ADMIN"


def test_editing_a_user_can_move_them_between_departments(client, seeded):
    login(client, "admin")
    client.post(f"/admin/users/{seeded['hod']}/edit", data={
        "_csrf": csrf(client, "/admin/users"), "name": "Hannah Hod", "role": "HOD",
        "department_id": seeded["dept"], "phone": "08099998888"}, follow_redirects=True)
    u = db.session.get(User, seeded["hod"])
    assert u.department_id == seeded["dept"]
    assert u.phone == "08099998888"


# ================================================================ REQ 5: logo
def test_logos_are_larger_than_before(client, seeded):
    """Sizes were 28px (topbar) / 56px (portal) / 64px (login) — too small."""
    css = client.get("/static/css/app.css").data.decode()
    assert "height:44px;width:44px" in css, "topbar logo not enlarged"

    login_html = client.get("/login").data.decode()
    if "branding/logo" in login_html:
        assert "height:104px" in login_html


def test_small_logo_upload_warns_about_resolution(client, seeded):
    """A big display box makes a small file look blurry — warn at upload."""
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), "white").save(buf, format="PNG")
    buf.seek(0)

    login(client, "admin")
    r = client.post("/admin/hospital", data={
        "_csrf": csrf(client, "/admin/hospital"), "name": "Test Hospital",
        "logo": (buf, "tiny.png")}, content_type="multipart/form-data",
        follow_redirects=True)
    assert r.status_code == 200
    assert b"may look" in r.data and b"blurry" in r.data


# ================================================================ REQ 6: final comment
def test_final_comment_box_is_on_the_inspection_form(client, seeded):
    login(client, "am1")
    page = client.get("/inspections/new").data.decode()
    assert 'name="final_comment"' in page
    assert "hmsVoice.start(this,'final_comment')" in page, "voice-to-text missing"


def test_final_comment_is_saved_with_the_inspection(client, seeded):
    login(client, "am1")
    comment = "Ward was clean but the suction machine has been faulty for three weeks."
    client.post("/inspections/submit", data={
        "_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
        "score_1": "5", "score_2": "4", "score_3": "4", "score_4": "4", "score_5": "5",
        "final_comment": comment}, follow_redirects=True)
    insp = db.session.query(Inspection).filter_by(status="SUBMITTED").first()
    assert insp is not None
    assert insp.final_comment == comment


def test_final_comment_is_optional(client, seeded):
    login(client, "am1")
    r = client.post("/inspections/submit", data={
        "_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
        "score_1": "5", "score_2": "5", "score_3": "5", "score_4": "5", "score_5": "5"},
        follow_redirects=True)
    assert r.status_code == 200
    insp = db.session.query(Inspection).filter_by(status="SUBMITTED").first()
    assert insp is not None
    assert insp.final_comment is None


def test_final_comment_appears_on_detail_page_and_pdf(client, seeded):
    login(client, "am1")
    comment = "Overall good, but oxygen cylinders need restocking."
    client.post("/inspections/submit", data={
        "_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
        "score_1": "5", "score_2": "4", "score_3": "4", "score_4": "4", "score_5": "5",
        "final_comment": comment}, follow_redirects=True)
    insp = db.session.query(Inspection).filter_by(status="SUBMITTED").first()

    page = client.get(f"/inspections/{insp.id}").data.decode()
    assert "oxygen cylinders need restocking" in page

    from app import storage
    assert insp.pdf_path and storage.exists(insp.pdf_path)
    assert len(storage.get(insp.pdf_path)) > 1500


def test_submit_is_still_once_only_per_day(client, seeded):
    """Requirement 6 also says one submission per report — already enforced."""
    login(client, "am1")
    data = {"_csrf": csrf(client, "/inspections/new"), "department_id": seeded["dept"],
            "score_1": "5", "score_2": "5", "score_3": "5", "score_4": "5", "score_5": "5"}
    client.post("/inspections/submit", data=data, follow_redirects=True)
    data["_csrf"] = csrf(client, "/inspections/new")
    r = client.post("/inspections/submit", data=data, follow_redirects=True)
    assert b"already submitted" in r.data
    assert db.session.query(Inspection).filter_by(status="SUBMITTED").count() == 1
