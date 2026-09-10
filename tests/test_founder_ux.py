"""Founder requests: single Admin Manager page, patient complaint messages,
hospital contact details, name+logo on every page."""
from app.models import (Complaint, Organization, SmsMessage, WhatsAppMessage,
                        db)

from conftest import csrf, login


def test_admin_manager_is_one_page_not_a_dropdown(client, seeded):
    login(client, "am1")
    home = client.get("/")
    assert home.status_code == 200
    assert b"Admin Manager" in home.data
    assert b"hmsToggleMenu" not in home.data
    assert b"Today's Inspection" not in home.data or b'href="/inspections"' in home.data
    # the nav points at the single page
    assert b'href="/inspections"' in home.data
    assert b'href="/inspections/new"' not in home.data

    page = client.get("/inspections")
    assert page.status_code == 200
    assert b"Today" in page.data
    assert b"Inspection history" in page.data
    assert b"Score each criterion" in page.data   # form lives on the same page

    same = client.get("/inspections/new")
    assert same.status_code == 200
    assert b"Inspection history" in same.data


def test_md_sees_admin_manager_history_not_the_form(client, seeded):
    login(client, "md")
    r = client.get("/inspections")
    assert r.status_code == 200
    assert b"Inspection history" in r.data
    assert b"SUBMIT INSPECTION" not in r.data


def test_patient_gets_inapp_ack_and_sms_whatsapp(client, seeded):
    token = csrf(client, "/complaint")
    r = client.post("/complaint/submit", data={"consent": "1", 
        "_csrf": token, "department_id": seeded["dept"], "category": "Long waiting time",
        "description": "We have been waiting for over four hours without any update.",
        "phone": "08012345678", "contact_method": "whatsapp"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"acknowledgment" in r.data or b"Acknowledgment" in r.data or b"Message to you" in r.data
    c = db.session.query(Complaint).first()
    assert c is not None
    # in-app (status page) shows the same words
    status = client.get(f"/complaint/status?ref={c.ref}&phone=08012345678")
    assert c.ref.encode() in status.data
    assert b"Messages from the hospital" in status.data
    assert b"received your complaint" in status.data
    # SMS + WhatsApp queued to the patient's phone — normalized to +234
    sms = db.session.query(SmsMessage).filter(SmsMessage.to_number.contains("8012345678")).first()
    assert sms is not None and c.ref in sms.body
    wa = db.session.query(WhatsAppMessage).filter(WhatsAppMessage.to_number.contains("8012345678")).first()
    assert wa is not None and c.ref in wa.body


def test_patient_gets_outcome_when_resolved(client, seeded):
    token = csrf(client, "/complaint")
    client.post("/complaint/submit", data={"consent": "1", 
        "_csrf": token, "department_id": seeded["dept"], "category": "Billing / charges",
        "description": "I was charged twice for the same laboratory test yesterday.",
        "phone": "08098765432"}, follow_redirects=True)
    c = db.session.query(Complaint).first()
    login(client, "hod1")
    client.post(f"/complaints/{c.id}/update",
                data={"_csrf": csrf(client, f"/complaints/{c.id}"),
                      "action_type": "resolve",
                      "resolution_notes": "Refund processed and confirmed with patient."},
                follow_redirects=True)
    sms = (db.session.query(SmsMessage)
           .filter(SmsMessage.to_number.contains("8098765432"),
                   SmsMessage.body.ilike("%resolved%")).first())
    assert sms is not None
    status = client.get(f"/complaint/status?ref={c.ref}&phone=08098765432")
    assert b"has been resolved" in status.data


def test_hospital_setup_saves_contact_and_name_shows_everywhere(client, seeded):
    login(client, "admin")
    tok = csrf(client, "/admin/hospital")
    r = client.post("/admin/hospital", data={
        "_csrf": tok, "name": "Hope City Hospital", "code": "HOPE",
        "email": "hello@hopecity.ng", "phone": "08030001111",
        "phone_alt": "014611000", "address": "12 Marina Road, Lagos Island",
    }, follow_redirects=True)
    assert r.status_code == 200
    org = db.session.get(Organization, seeded["org"])
    assert org.name == "Hope City Hospital"
    assert org.email == "hello@hopecity.ng"
    assert org.phone == "08030001111"
    assert org.address.startswith("12 Marina")
    # name on staff chrome
    dash = client.get("/")
    assert b"Hope City Hospital" in dash.data
    # name on login (after logout)
    client.post("/logout", data={"_csrf": csrf(client, "/")})
    login_page = client.get("/login")
    assert b"Hope City Hospital" in login_page.data
    # name on a public portal
    portal = client.get("/complaint")
    assert b"Hope City Hospital" in portal.data
