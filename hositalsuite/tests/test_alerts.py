"""Item 10 tests: voice/browser alert preferences + live alert polling (§19)."""
from app.models import AppNotification, UserPref, db

from conftest import csrf, login


def test_alert_prefs_defaults_and_save(client, seeded):
    login(client, "am1")
    r = client.get("/api/v1/alerts/prefs")
    prefs = r.get_json()
    assert prefs["voice_enabled"] is True
    assert prefs["voice_min_level"] == "standard"
    # Quiet hours are OFF by default: the old 22:00 default silenced
    # night-shift staff, who most need to hear that a patient is waiting.
    assert prefs["quiet_start"] == ""

    tok = csrf(client, "/alert-settings")
    client.post("/alert-settings", data={"_csrf": tok, "voice_enabled": "1",
                                         "voice_min_level": "emergency",
                                         "quiet_start": "21:30", "quiet_end": "06:00",
                                         "push_enabled": "1"}, follow_redirects=True)
    prefs = client.get("/api/v1/alerts/prefs").get_json()
    assert prefs["voice_min_level"] == "emergency"
    assert prefs["quiet_start"] == "21:30"
    assert prefs["push_enabled"] is True


def test_alert_poll_returns_only_alert_level_notifications(client, seeded):
    login(client, "am1")
    uid = db.session.query(UserPref).first()  # may not exist yet — use user id directly
    from app.models import User
    am = db.session.query(User).filter_by(username="am1").first()
    # one alert-level + one routine notification
    db.session.add(AppNotification(org_id=seeded["org"], user_id=am.id, channel="inapp",
                                   template_key="complaint_escalated",
                                   subject="Complaint ESCALATED", body="Escalated to MD/CEO"))
    db.session.add(AppNotification(org_id=seeded["org"], user_id=am.id, channel="inapp",
                                   template_key="inspection_submitted",
                                   subject="Daily inspection report", body="Routine report"))
    db.session.commit()

    data = client.get("/api/v1/alerts/poll?after=0").get_json()
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["urgency"] == "emergency"
    assert data["last_id"] >= 1
    # polling again from last_id returns nothing new
    data2 = client.get(f"/api/v1/alerts/poll?after={data['last_id']}").get_json()
    assert data2["alerts"] == []


def test_alert_poll_requires_auth(client, seeded):
    r = client.get("/api/v1/alerts/poll")
    assert r.status_code == 401
