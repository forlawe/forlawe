"""Headless-browser proof that the merged Roster page really works.

Runs a real server, signs in as the administrator, and drives the page the way
the founder would: pick a department, place staff on shifts, record leave, try
to double-book somebody who is on leave, upload a file, approve the preview,
and download the export. Anything that only "looks" fixed fails here.
"""
import os
import re
import sys
import tempfile
import threading
import time
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(),
                                                                  "roster_ui_check.db"))
os.environ["SECRET_KEY"] = "browser-check"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["COOKIE_SECURE"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                                    # noqa: E402
from app.models import (Department, Organization, RosterEntry, Section, Unit,  # noqa: E402
                        User, db)

PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"
PW = "Passw0rd!x"
FAILURES = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def build():
    app = create_app(scheduler=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        org = Organization(code="IJEDE", name="General Hospital Ijede")
        db.session.add(org)
        db.session.flush()

        def mk(username, name, role):
            u = User(org_id=org.id, username=username, name=name, role=role, active=True,
                     approved=True, must_change_password=False)
            u.set_password(PW)
            db.session.add(u)
            db.session.flush()
            return u

        mk("admin", "System Administrator", "SUPER_ADMIN")
        # real names from the founder's nominal roll
        for n in ("DR ADENIYI", "MRS ABATAN L.F", "CNO OGUNLEYE", "PHARM KAREEM",
                  "MISS ADESANYA", "MRS OBA", "MR AFOLABI", "CNO AJIBOYE",
                  "ADNS ABDUL AZEEZ", "MISS TAIWO"):
            mk(n.split()[-1].lower().replace(".", ""), n, "HOD")

        nursing = Department(org_id=org.id, name="Nursing", roster_mode="two_12h",
                             roster_staff_per_shift=4, hod_name="CNO Ogunleye",
                             hod_phone="08062801586")
        audit = Department(org_id=org.id, name="Internal Audit", roster_mode="office",
                           roster_staff_per_shift=2, hod_name="Miss Taiwo",
                           hod_phone="08027301447")
        db.session.add_all([nursing, audit])
        db.session.flush()
        sec = Section(org_id=org.id, department_id=nursing.id, name="Female Ward")
        db.session.add(sec)
        db.session.flush()
        db.session.add(Unit(org_id=org.id, department_id=nursing.id, section_id=sec.id,
                            name="Side Ward"))
        db.session.commit()
        return app, nursing.id, audit.id, sec.id


def main():
    from playwright.sync_api import sync_playwright
    app, nursing_id, audit_id, section_id = build()
    threading.Thread(target=lambda: app.run(port=PORT, threaded=True, use_reloader=False),
                     daemon=True).start()
    time.sleep(2.5)

    today = date.today()
    d1 = today + timedelta(days=3)
    d2 = today + timedelta(days=4)

    # a Saturday, for the office-hours department
    sat = today + timedelta(days=1)
    while sat.weekday() != 5:
        sat += timedelta(days=1)

    upload = os.path.join(tempfile.gettempdir(), "ward_roster.csv")
    with open(upload, "w") as fh:
        fh.write("Name,Date,End Date,Shift,Leave Type,Note\n")
        fh.write(f"CNO OGUNLEYE,{d1},,DAY,,\n")
        fh.write(f"ADNS ABDUL AZEEZ,{d1},,DAY,,second nurse same shift\n")
        fh.write(f"CNO AJIBOYE,{d1},,NIGHT,,\n")
        fh.write(f"MRS OBA,{d1},,NIGHT,,fourth person - old design could not do this\n")
        fh.write(f"PHARM KAREEM,{d2},{d2 + timedelta(days=4)},,ANNUAL,5 days annual leave\n")
        fh.write(f"SOMEBODY WHO LEFT,{d1},,DAY,,\n")

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 390, "height": 844})   # a real phone size

        pg.goto(f"{BASE}/login")
        pg.fill('input[name="username"]', "admin")
        pg.fill('input[name="password"]', PW)
        pg.click('button[type="submit"]')
        pg.wait_for_load_state("networkidle")

        # ---- 1. one nav link, not two
        nav = pg.inner_text("nav.nav")
        check("navigation shows a single 'Roster' link",
              nav.count("Roster") == 1 and "Dept Roster" not in nav, repr(nav[:120]))

        # ---- 2. old bookmark still works
        pg.goto(f"{BASE}/dept-roster?dept={nursing_id}")
        pg.wait_for_load_state("networkidle")
        check("old /dept-roster bookmark lands on the merged page",
              "/roster" in pg.url and pg.locator("h1").first.inner_text().strip().endswith("Roster"),
              pg.url)

        # ---- 3. date range presets
        for preset, expect in (("today", 1), ("7", 7), ("14", 14), ("21", 21), ("30", 30)):
            pg.goto(f"{BASE}/roster?range={preset}&scope=DEPARTMENT&department_id={nursing_id}")
            rows = pg.locator("table tr").count() - 1
            check(f"date range '{preset}' shows {expect} day(s)", rows == expect, f"got {rows}")

        pg.goto(f"{BASE}/roster?range=custom&from={today}&to={today + timedelta(days=9)}"
                f"&scope=DEPARTMENT&department_id={nursing_id}")
        check("custom date range shows 10 days",
              pg.locator("table tr").count() - 1 == 10)

        # ---- 4. upload with preview
        pg.goto(f"{BASE}/roster?range=30&scope=DEPARTMENT&department_id={nursing_id}")
        pg.set_input_files('input[type="file"]', upload)
        pg.click('button:has-text("Check the file")')
        pg.wait_for_load_state("networkidle")
        body = pg.inner_text("body")
        check("upload shows a preview instead of saving", "Nothing has been saved yet" in body)
        check("unknown staff is rejected with a reason",
              "No active staff account matches" in body)
        check("five good lines are ready to save", re.search(r"\b5\b", body) is not None)

        pg.click('button:has-text("Save")')
        pg.wait_for_load_state("networkidle")

        with app.app_context():
            duty = db.session.query(RosterEntry).filter_by(kind="DUTY").count()
            leave = db.session.query(RosterEntry).filter_by(kind="LEAVE").count()
        check("four people on one day across two shifts saved", duty == 4, f"got {duty}")
        check("a 5-day leave block became 5 leave days", leave == 5, f"got {leave}")

        # ---- 5. the page actually shows them
        pg.goto(f"{BASE}/roster?range=30&scope=DEPARTMENT&department_id={nursing_id}")
        body = pg.inner_text("body")
        check("both night nurses appear on the same day",
              "CNO AJIBOYE" in body and "MRS OBA" in body)
        check("leave is shown on the roster", "Annual leave" in body)

        # ---- 6. leave blocks duty
        pg.select_option('select[name="user_id"]', label="PHARM KAREEM")
        pg.fill('input[name="duty_date"]', (d2 + timedelta(days=1)).isoformat())
        pg.select_option('select[name="shift"]', "DAY")
        pg.click('button:has-text("Save to roster")')
        pg.wait_for_load_state("networkidle")
        check("system refuses to place a staff member on duty during their leave",
              "annual leave" in pg.inner_text("body").lower() and
              "cannot be placed on duty" in pg.inner_text("body"))

        # ---- 7. office department: no weekend duty
        pg.goto(f"{BASE}/roster?range=30&scope=DEPARTMENT&department_id={audit_id}")
        check("office department offers OFFICE hours, not day/night shifts",
              "OFFICE" in pg.inner_text("body") and
              pg.locator('select[name="shift"] option').count() == 1)
        pg.select_option('select[name="user_id"]', label="MISS TAIWO")
        pg.fill('input[name="duty_date"]', sat.isoformat())
        pg.click('button:has-text("Save to roster")')
        pg.wait_for_load_state("networkidle")
        check("office department refuses a weekend duty",
              "weekend" in pg.inner_text("body"))

        # ---- 8. section roster
        pg.goto(f"{BASE}/roster?range=30&scope=SECTION&department_id={nursing_id}"
                f"&section_id={section_id}")
        pg.select_option('select[name="user_id"]', label="MRS ABATAN L.F")
        pg.fill('input[name="duty_date"]', d1.isoformat())
        pg.click('button:has-text("Save to roster")')
        pg.wait_for_load_state("networkidle")
        with app.app_context():
            n = db.session.query(RosterEntry).filter_by(scope="SECTION").count()
        check("a SECTION can own its own roster", n == 1, f"got {n}")

        # ---- 9. export
        pg.goto(f"{BASE}/roster?range=30&scope=DEPARTMENT&department_id={nursing_id}")
        with pg.expect_download() as dl:
            pg.click('a:has-text("Download")')
        path = dl.value.path()
        text = open(path).read()
        check("export downloads a real CSV of what is on screen",
              text.startswith("Date,Day,Type") and "CNO OGUNLEYE" in text)

        # ---- 10. nothing off-screen on a phone
        box = pg.locator('button:has-text("Save to roster")').bounding_box()
        check("the Save button is reachable on a 390x844 phone screen",
              box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 391,
              str(box))
        pg.screenshot(path="/home/user/roster_phone.png", full_page=True)
        b.close()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("ALL BROWSER CHECKS PASSED")


if __name__ == "__main__":
    main()
