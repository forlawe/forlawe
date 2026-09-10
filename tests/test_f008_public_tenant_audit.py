"""F-008: the public surfaces' manual tenant filtering, pinned.

Public requests run under all_orgs(), so every org_id filter in those views
is manual. The full audit lives in docs/PUBLIC_ROUTE_TENANT_AUDIT_F008.md;
these tests pin the two checks the whole patient flow leans on:

  1. queue join cannot be pointed at another hospital's department by a
     forged form field — the server re-validates dept.org_id;
  2. the complaint portal hands over nothing without BOTH the reference
     and the matching phone (the ref alone is sequential and guessable).
"""
from __future__ import annotations

import pytest

from app.models import db, now_naive


def test_forged_department_cannot_cross_tenants(client, app, seeded):
    """A patient in hospital A's page posting hospital B's department id must
    get an error, and no ticket may be created in either hospital."""
    from app.models import Department, Organization, QueueTicket
    with app.app_context():
        b = Organization(code="TENB", name="Other Hospital")
        db.session.add(b)
        db.session.flush()
        foreign = Department(org_id=b.id, name="Reception")
        db.session.add(foreign)
        db.session.commit()
        foreign_id = foreign.id
        org_a = seeded["org"]

    page = client.get(f"/queue/join?h=TEST")
    token = page.get_data(as_text=True).split('name="_csrf" value="')[1].split('"')[0]
    r = client.post(f"/queue/join?h=TEST", data={
        "_csrf": token, "department_id": str(foreign_id),
        "patient_name": "Cross Tenant", "phone": "08011112222",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        # nothing was written anywhere: the foreign dept id is refused outright
        assert db.session.query(QueueTicket).filter_by(
            department_id=foreign_id).count() == 0
        assert db.session.query(QueueTicket).filter_by(
            org_id=org_a, patient_name="Cross Tenant").count() == 0


def test_complaint_status_needs_ref_and_matching_phone(client, app, seeded):
    """Sequential refs are guessable — the phone is the second credential."""
    from app.models import Complaint, now_naive
    with app.app_context():
        c = Complaint(org_id=seeded["org"], ref="TEST-CMP-2026-000042",
                      department_id=seeded["dept"],
                      phone="08099998877", category="SERVICE",
                      description="status probe", status="NEW", sla_hours=24,
                      sla_deadline_at=now_naive())
        db.session.add(c)
        db.session.commit()

    html = client.get("/complaint/status?ref=TEST-CMP-2026-000042").get_data(as_text=True)
    assert "both reference number and phone" in html          # ref alone refused

    html = client.get("/complaint/status?ref=TEST-CMP-2026-000042&phone=08000000001")
    assert "No complaint found" in html.get_data(as_text=True)   # wrong phone refused

    html = client.get("/complaint/status?ref=TEST-CMP-2026-000042&phone=08099998877")
    assert "TEST-CMP-2026-000042" in html.get_data(as_text=True)  # correct pair shows it
