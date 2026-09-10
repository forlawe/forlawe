"""Headless-browser proof of Stage A — the HIMS Register desk.

Drives the real page the way a clerk at General Hospital Ijede would: search
for a patient who is not there, open a folder, try to open the SAME folder
twice, find the returning patient by phone number, and start a second visit.
"""
import os
import sys
import tempfile
import threading
import time

os.environ.setdefault("DATABASE_URL",
                      "sqlite:///" + os.path.join(tempfile.gettempdir(), "hims_ui.db"))
os.environ["SECRET_KEY"] = "browser-check"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["COOKIE_SECURE"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                                       # noqa: E402
from app.models import (Department, Organization, Patient, PatientVisit,  # noqa: E402
                        User, db)

PORT = 8901
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
        u = User(org_id=org.id, username="admin", name="MISS ADESANYA",
                 role="SUPER_ADMIN", active=True, approved=True,
                 must_change_password=False)
        u.set_password(PW)
        db.session.add(u)
        db.session.add(Department(org_id=org.id, name="General Outpatient",
                                  hod_name="Dr Adeniyi", hod_phone="08065226200"))
        db.session.commit()
        return app


def fill(pg, name, value):
    pg.fill(f'[name="{name}"]', value)


def main():
    from playwright.sync_api import sync_playwright
    app = build()
    threading.Thread(target=lambda: app.run(port=PORT, threaded=True, use_reloader=False),
                     daemon=True).start()
    time.sleep(2.5)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 390, "height": 844})    # a real phone

        pg.goto(f"{BASE}/login")
        fill(pg, "username", "admin")
        fill(pg, "password", PW)
        pg.click('button[type="submit"]')
        pg.wait_for_load_state("networkidle")

        check("HIMS appears in the menu", "HIMS" in pg.inner_text("nav.nav"))

        # ---- 1. search for somebody who is not registered
        pg.goto(f"{BASE}/hims/")
        fill(pg, "q", "Abatan")
        pg.click('button:has-text("Search")')
        pg.wait_for_load_state("networkidle")
        body = pg.inner_text("body")
        check("searching an unknown patient says so, and offers a new folder",
              "No folder found" in body and "Open a new folder" in body)

        # ---- 2. open the folder, carrying the search term across
        pg.click('a:has-text("Open a new folder")')
        pg.wait_for_load_state("networkidle")
        check("the name typed into search is carried into the form",
              pg.input_value('[name="surname"]').lower() == "abatan",
              pg.input_value('[name="surname"]'))

        # ---- 3. the form refuses an incomplete folder
        fill(pg, "first_name", "Lekan")
        pg.select_option('[name="sex"]', "F")
        pg.click('button:has-text("Open the folder")')
        pg.wait_for_load_state("networkidle")
        # The browser's own required-field check should stop this before it is
        # ever sent. (The server rejects it too - see tests/test_hims.py - but a
        # clerk should never have to wait for a round trip to learn that.)
        still_on_form = pg.locator('[name="nok_name"]').count() == 1
        invalid = pg.eval_on_selector('[name="nok_name"]',
                                      "el => !el.validity.valid")
        check("an incomplete folder never even leaves the phone",
              still_on_form and invalid, f"on form={still_on_form} flagged={invalid}")

        # ---- 4. complete it properly
        fill(pg, "age_years", "34")
        fill(pg, "phone", "08059826879")
        fill(pg, "nok_name", "Mr Abatan")
        fill(pg, "nok_relationship", "husband")
        fill(pg, "nok_phone", "08033901140")
        pg.select_option('[name="payer_type"]', "LAHSMA")
        fill(pg, "payer_number", "LAH/2026/99881")
        pg.select_option('[name="preferred_lang"]', "yo")
        pg.check('input[name="assistance"][value="WHEELCHAIR"]')
        fill(pg, "care_note", "travels from Ikorodu")
        fill(pg, "reason", "fever and headache for 3 days")
        pg.click('button:has-text("Open the folder")')
        pg.wait_for_load_state("networkidle")
        body = pg.inner_text("body")
        check("the folder is created and given a hospital number",
              "IJE/" in body and "Folder opened" in body,
              [l for l in body.splitlines() if "IJE/" in l][:1])
        check("the folder says how to look after the person, not their diagnosis",
              "Looking after" in body and "wheelchair" in body.lower()
              and "travels from Ikorodu" in body)
        check("the visit was started and is waiting for Triage",
              "REGISTERED" in body.upper())

        with app.app_context():
            from app.models import AppNotification
            spoken = [r.body for r in db.session.query(AppNotification)
                      .filter_by(channel="station").all()]
            check("arrival is ANNOUNCED OUT LOUD to the desk",
                  any("registered" in x.lower() for x in spoken), str(spoken[:1]))
            check("the wheelchair request is announced as its own urgent call",
                  any("needs help" in x and "wheelchair" in x.lower() for x in spoken),
                  str([x for x in spoken if "needs help" in x][:1]))
            pt = db.session.query(Patient).first()
            check("payment route was saved for Billing",
                  pt.payer_type == "LAHSMA" and pt.payer_number == "LAH/2026/99881")
            check("age was stored without inventing a birthday",
                  pt.age == 34 and pt.date_of_birth is None)

        # ---- 5. try to open the SAME patient again
        pg.goto(f"{BASE}/hims/register")
        fill(pg, "surname", "Abatan")
        fill(pg, "first_name", "Lekan")
        pg.select_option('[name="sex"]', "F")
        fill(pg, "age_years", "34")
        fill(pg, "phone", "08059826879")
        fill(pg, "nok_name", "Mr Abatan")
        fill(pg, "nok_phone", "08033901140")
        pg.click('button:has-text("Open the folder")')
        pg.wait_for_load_state("networkidle")
        body = pg.inner_text("body")
        check("a duplicate folder is stopped before it is created",
              "may already have a folder" in body)
        with app.app_context():
            n = db.session.query(Patient).count()
        check("still only one folder exists", n == 1, f"got {n}")

        # ---- 6. find the returning patient by phone number
        pg.goto(f"{BASE}/hims/?q=08059826879")
        body = pg.inner_text("body")
        check("a returning patient is found by phone number",
              "ABATAN Lekan" in body and "1 folder found" in body)

        pg.click('a:has-text("Open folder")')
        pg.wait_for_load_state("networkidle")
        check("the folder page shows the returning-patient badge",
              "Returning patient" in pg.inner_text("body"))

        # ---- 7. a second visit on the same day is blocked
        pg.click('button:has-text("Start visit")')
        pg.wait_for_load_state("networkidle")
        check("a second visit on the same day is refused",
              "already has an open visit today" in pg.inner_text("body"))
        with app.app_context():
            v = db.session.query(PatientVisit).count()
        check("still only one visit today", v == 1, f"got {v}")

        # ---- 8. export
        pg.goto(f"{BASE}/hims/")
        with pg.expect_download() as dl:
            pg.click('a:has-text("Download register")')
        text = open(dl.value.path()).read()
        check("the register downloads as a CSV with the real folder in it",
              "Hospital Number,Surname" in text and "ABATAN" in text
              and "LAH/2026/99881" in text)
        check("the downloaded register carries no medical data",
              "Genotype" not in text and "Blood Group" not in text
              and "Allergies" not in text)

        # ---- 9. usable on a phone
        pg.goto(f"{BASE}/hims/register")
        box = pg.locator('button:has-text("Open the folder")').bounding_box()
        check("the save button is on-screen on a 390x844 phone",
              box and box["x"] >= 0 and box["x"] + box["width"] <= 391, str(box))
        pg.screenshot(path="/home/user/hims_phone.png", full_page=True)
        b.close()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED: " + ", ".join(FAILURES))
        sys.exit(1)
    print("ALL BROWSER CHECKS PASSED")


if __name__ == "__main__":
    main()
