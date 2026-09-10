import os
import tempfile
import pathlib

# The suite must pass on BOTH engines: SQLite (developer laptop) and PostgreSQL
# (what production actually runs on Supabase). Set TEST_DATABASE_URL to run the
# whole suite against a real PostgreSQL server, e.g.
#   TEST_DATABASE_URL=postgresql://hms:pw@127.0.0.1:5432/hms_test pytest -q
# Without it we fall back to a temporary SQLite file with unique name per process
# to avoid WAL locking issues with new v2 tables.
#
# This used to be hard-coded to single file, causing flaky failures.
_test_db_path = os.path.join(tempfile.gettempdir(), f"hms_test_{os.getpid()}.db")
# Clean any leftover
try:
    for suf in ("", "-wal", "-shm"):
        p = pathlib.Path(_test_db_path + suf) if suf else pathlib.Path(_test_db_path)
        if p.exists():
            p.unlink()
except Exception:
    pass

os.environ["DATABASE_URL"] = (
    os.environ.get("TEST_DATABASE_URL")
    or f"sqlite:///{_test_db_path}"
)
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["WHATSAPP_MODE"] = "sandbox"
os.environ["WHATSAPP_SIMULATE_FAILURE"] = "0"
os.environ["USSD_SHARED_SECRET"] = "ussd-test-secret"

import pytest

from app import create_app
from app.models import (ComplaintCategory, Department, DutyRoster, Organization,
                        QrLocation, Section, Unit, User, db, new_code)


@pytest.fixture()
def app():
    application = create_app(scheduler=False)
    application.config["TESTING"] = True
    application.config["SYNC_DELIVERY_FOR_TESTS"] = True   # deterministic WhatsApp/SMS delivery
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app, seeded):
    from app.security import _limiter
    _limiter.hits.clear()
    return app.test_client()


@pytest.fixture()
def seeded(app):
    """Minimal hospital: org, 4 users, 1 department tree, roster, categories."""
    with app.app_context():
        org = Organization(code="TEST", name="Test Hospital", phone="08030001111")
        db.session.add(org)
        db.session.flush()

        # Seed builtin roles for this org — otherwise ADMIN_MANAGER has no Role row and scope falls back to DEPARTMENT with empty visible
        try:
            from app.roles import ensure_builtin_roles
            ensure_builtin_roles(org.id)
            db.session.flush()
        except Exception:
            db.session.rollback()
            # retry after adding org
            org = db.session.query(Organization).filter_by(code="TEST").first()
            if org:
                from app.roles import ensure_builtin_roles
                ensure_builtin_roles(org.id)
                db.session.flush()

        def mk(username, name, role, phone=None):
            u = User(org_id=org.id, username=username, name=name, role=role, phone=phone)
            u.set_password("Passw0rd!x")
            db.session.add(u)
            db.session.flush()
            return u

        admin = mk("admin", "Ada Admin", "SUPER_ADMIN")
        md = mk("md", "Mark Director", "MD_CEO", phone="2348000000001")
        am = mk("am1", "Alice Manager", "ADMIN_MANAGER", phone="2348000000002")
        am2 = mk("am2", "Bob Manager", "ADMIN_MANAGER")
        hod = mk("hod1", "Hannah Hod", "HOD", phone="2348000000003")

        dept = Department(org_id=org.id, name="Emergency", hod_user_id=hod.id)
        db.session.add(dept)
        db.session.flush()
        sec = Section(org_id=org.id, department_id=dept.id, name="A&E")
        db.session.add(sec)
        db.session.flush()
        db.session.add(Unit(org_id=org.id, department_id=dept.id, section_id=sec.id, name="Triage"))

        for cat in ("Long waiting time", "Staff attitude / conduct", "Billing / charges"):
            db.session.add(ComplaintCategory(org_id=org.id, name=cat))
        db.session.add(QrLocation(org_id=org.id, name="Reception", code=new_code(6)))

        from datetime import timedelta
        from app.models import now_naive
        today = now_naive().date()
        db.session.add(DutyRoster(org_id=org.id, duty_date=today, user_id=am.id))
        db.session.add(DutyRoster(org_id=org.id, duty_date=today + timedelta(days=1), user_id=am2.id))

        # test users keep their strong test passwords (no forced change)
        for u in (admin, md, am, am2, hod):
            u.must_change_password = False

        db.session.commit()
        return {"org": org.id, "admin": admin.id, "md": md.id, "am": am.id, "am2": am2.id,
                "hod": hod.id, "dept": dept.id}


def login(client, username, password="Passw0rd!x"):
    # ensure a clean session even if another user is already logged in
    page = client.get("/login", follow_redirects=False)
    if page.status_code == 302:
        tok = csrf(client, "/")
        client.post("/logout", data={"_csrf": tok})
        page = client.get("/login")
    token = page.data.decode().split('name="_csrf" value="')[1].split('"')[0]
    r = client.post("/login", data={"username": username, "password": password,
                                    "_csrf": token}, follow_redirects=False)
    assert r.status_code in (302, 200), f"login failed for {username}: {r.status_code}"
    return r


def csrf(client, path="/"):
    page = client.get(path)
    html = page.data.decode()
    return html.split('name="_csrf" value="')[1].split('"')[0]
