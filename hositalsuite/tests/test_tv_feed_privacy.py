"""F-028: the public TV JSON feed must obey the privacy rule the TV screen obeys.

The rendered screen shows first names + ticket codes only (NDPA). For a long
time the JSON feed behind it shipped the FULL name (full_name_private /
ticket patient_name) and the FULL hospital number to anyone who asked — no
login, no rate limit. These tests pin the fix: first names only, masked
codes, and a rate limit on the public endpoint.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.models import db, now_naive


@pytest.fixture()
def tv_world(app, seeded):
    """Two patients in consultation (one with a ticket, one without) + one
    called queue ticket, so both code paths are exercised."""
    from app.models import Patient, PatientVisit, QueueTicket

    with app.app_context():
        org_id = seeded["org"]
        p1 = Patient(org_id=org_id, hospital_number="IJ/2026/00312",
                     surname="OSEWA", first_name="Adekunle", sex="M",
                     age_years=40, payer_type="SELF", category="GENERAL")
        p2 = Patient(org_id=org_id, hospital_number="IJ/2026/00777",
                     surname="BALOGUN", first_name="Simisola", sex="F",
                     age_years=33, payer_type="SELF", category="GENERAL")
        db.session.add_all([p1, p2])
        db.session.flush()
        now = now_naive()
        v1 = PatientVisit(org_id=org_id, patient_id=p1.id, visit_no="V1",
                          status="IN_CONSULTATION", clinic="GENERAL",
                          is_fast_track=False, started_at=now - timedelta(minutes=30),
                          seen_at=now - timedelta(minutes=5))
        v2 = PatientVisit(org_id=org_id, patient_id=p2.id, visit_no="V2",
                          status="IN_CONSULTATION", clinic="DENTAL",
                          is_fast_track=False, started_at=now - timedelta(minutes=40),
                          seen_at=now - timedelta(minutes=8))
        db.session.add_all([v1, v2])
        t = QueueTicket(org_id=org_id, code="E-014",
                        department_id=seeded["dept"],
                        patient_name="Chiderah Nwosu-Ikenga",
                        patient_id=p1.id, status="CALLED",
                        queue_date=now.date(),
                        called_at=now - timedelta(minutes=2))
        db.session.add(t)
        db.session.commit()
        yield {"org": org_id, "visit_id": v1.id, "ticket_id": t.id,
               "patient_id": p1.id}


def _feed_json(client):
    r = client.get("/api/tv/feed")
    assert r.status_code == 200, r.status_code
    return r.get_json()


def test_feed_never_ships_full_names(client, tv_world):
    data = _feed_json(client)
    blob = str(data)
    assert "full_name_private" not in blob
    for surname in ("OSEWA", "BALOGUN", "Nwosu-Ikenga"):
        assert surname not in blob              # no surnames on the public wire
    for entry in data["now_serving"] + data["next_up"]:
        if entry.get("name"):
            assert " " not in entry["name"], entry   # first names only
            assert entry["name"] != "Patient" or entry.get("code")
    names = {e["name"] for e in data["now_serving"]}
    assert "Adekunle" in names and "Simisola" in names  # CALLED name, not folder surname


def test_feed_never_ships_full_hospital_number(client, tv_world):
    data = _feed_json(client)
    blob = str(data)
    assert "IJ/2026/00312" not in blob and "IJ/2026/00777" not in blob
    codes = [e.get("code", "") for e in data["now_serving"] + data["next_up"]]
    assert any("E-014" in c for c in codes)          # ticket code survives…
    assert any(c.startswith("••") for c in codes)    # …rest masked to last 3


def test_voice_still_has_a_name_to_announce(client, tv_world):
    """The TV page announces entry.name — it must still be a real first name,
    not an empty string, or the waiting room goes silent."""
    data = _feed_json(client)
    serving = data["now_serving"]
    assert serving and serving[0]["name"]


def test_feed_is_rate_limited(app, client, monkeypatch, tv_world):
    """The feed used to be the only unthrottled public TV endpoint."""
    from app.views import tv as tv_views
    monkeypatch.setattr(app, "config", dict(app.config), raising=False) if False else None
    app.config["RATE_LIMIT_SCALE"] = 1
    # 60/min is the production limit — the 61st hit from one IP must 429
    for _ in range(60):
        assert client.get("/api/tv/feed").status_code == 200
    assert client.get("/api/tv/feed").status_code == 429
    # sanity: the decorator is present on the view
    assert getattr(tv_views.api_feed, "__wrapped__", None) is not None
