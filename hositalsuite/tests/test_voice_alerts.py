"""Spoken staff announcements.

Reported as "voice reminders not working". Investigation found FOUR separate
causes, each of which alone was enough to produce total silence:

  1. No patient event ever created an alert — only five admin events were
     registered as speakable, so there was nothing to announce.
  2. hmsVoice.speak() called this.inQuietHours(), which lives on hmsAlerts —
     a TypeError killed every announcement before it started.
  3. Quiet hours defaulted to 22:00–07:00, silencing night-shift staff.
  4. Browsers block audio until the user interacts, and the failure was
     invisible.

Every one of them is covered below.
"""
from app import announce
from app.models import AppNotification, Department, User, db
from conftest import csrf, login


# ================================================================ what staff hear
def test_the_founders_examples_are_spoken_correctly():
    assert announce.phrase("dispensary_waiting", name="Mr. Tunde Bakare", count=3,
                           place="the drug dispensary") == \
        "Mr Tunde, you have 3 patients waiting for attention at the drug dispensary."

    assert announce.phrase("triage_backlog", name="Nurse Mr. Adelowo", count=6) == \
        "Nurse Adelowo, 6 patients are on the queue waiting to be placed with a doctor."

    line = announce.phrase("queue_waiting", name="Mrs. Tayo Adeyemi", count=1,
                           place="Injection Room")
    assert line.startswith("Mrs Tayo,")
    assert "1 patient is waiting" in line, "must not say '1 patients'"


def test_counts_are_pluralised():
    one = announce.phrase("queue_waiting", name="Dr Ade", count=1, place="OPD")
    many = announce.phrase("queue_waiting", name="Dr Ade", count=4, place="OPD")
    assert "1 patient is" in one and "patients" not in one.split("is")[0]
    assert "4 patients are" in many


def test_names_are_shortened_for_speech():
    """A full name read by a synthesiser is slow and robotic on a busy ward."""
    assert announce.speech_name("MRS TAYO ADEYEMI") == "Mrs Tayo"
    assert announce.speech_name("DR ADENIYI") == "Doctor Adeniyi"
    assert announce.speech_name("PHARM UKPE AUGUSTINE") == "Pharmacist Ukpe"


def test_double_titles_are_collapsed():
    """Regression: 'Nurse Mr Adelowo' was announced as 'Nurse Mr' — a title
    twice and no name at all."""
    assert announce.speech_name("Nurse Mr. Adelowo") == "Nurse Adelowo"
    assert announce.speech_name("Dr Mrs Bola Ige") == "Doctor Bola"


def test_initialisms_are_spoken_as_letters():
    """'CNO Ogunleye' must not be read aloud as the word 'Sno'."""
    assert announce.speech_name("CNO OGUNLEYE") == "C N O Ogunleye"
    assert announce.speech_name("ADNS ABDUL AZEEZ") == "A D N S Abdul"


def test_announcements_never_contain_clinical_advice():
    """Announcements say who and where — never a diagnosis, drug or dose."""
    banned = ("mg", "dose", "diagnos", "prescrib", "tablet")
    for kind in announce.PATIENT_ALERTS:
        line = announce.phrase(kind, name="Dr Ade", count=2, place="OPD",
                               patient="Ticket A-001", room="Room 1").lower()
        for word in banned:
            assert word not in line, f"{kind} announcement contains {word!r}"


def test_unknown_name_does_not_produce_an_empty_greeting():
    assert announce.speech_name("") == "Colleague"
    assert announce.phrase("queue_waiting", name="", count=2).startswith("Team")


# ================================================================ events -> alerts
def test_patient_events_are_speakable(app):
    """Regression cause #1: only five ADMIN events could ever be spoken, so a
    nurse waiting on patient announcements heard nothing."""
    from app.views.api import _speakable
    speakable = _speakable()
    for kind in ("queue_waiting", "dispensary_waiting", "triage_backlog",
                 "consult_ready", "emergency_arrival"):
        assert kind in speakable, f"{kind} cannot be spoken"
    assert speakable["emergency_arrival"] == "emergency"


def test_joining_the_queue_raises_an_announcement(client, seeded):
    """The end-to-end reason nothing was ever heard: no event raised an alert."""
    before = db.session.query(AppNotification).filter_by(
        template_key="queue_waiting").count()
    r = client.post("/queue/join", data={
        "_csrf": csrf(client, "/queue/join"), "department_id": seeded["dept"],
        "patient_name": "Ada Patient", "phone": "08011112222"},
        follow_redirects=True)
    assert r.status_code == 200
    after = db.session.query(AppNotification).filter(
        AppNotification.template_key.in_(("queue_waiting", "dispensary_waiting"))).count()
    assert after > before, "joining the queue announced nothing"


def test_personal_feed_carries_a_spoken_sentence(client, seeded, app):
    app.config["RATE_LIMIT_SCALE"] = 10000
    u = db.session.get(User, seeded["hod"])
    announce.to_user(seeded["org"], u, "dispensary_waiting", count=3,
                     place="the drug dispensary")
    db.session.commit()

    login(client, "hod1")
    data = client.get("/api/v1/alerts/poll?after=0").get_json()
    spoken = [a["speech"] for a in data["alerts"]]
    assert any("3 patients" in s and "dispensary" in s for s in spoken), spoken


def test_station_screen_feed_works_without_login(client, seeded):
    """A dispensary tablet is not signed in as any individual."""
    dept = db.session.get(Department, seeded["dept"])
    announce.to_station(seeded["org"], "triage_backlog",
                        department_id=dept.id, name="Triage", count=6)
    db.session.commit()

    r = client.get(f"/api/v1/alerts/station?dept={dept.id}")
    assert r.status_code == 200
    spoken = [a["speech"] for a in r.get_json()["alerts"]]
    assert any("6 patients" in s for s in spoken), spoken


def test_station_feed_is_scoped_to_one_department(client, seeded):
    other = Department(org_id=seeded["org"], name="Other Dept")
    db.session.add(other)
    db.session.commit()
    announce.to_station(seeded["org"], "queue_waiting", department_id=other.id,
                        name="Other Dept", count=9)
    db.session.commit()

    r = client.get(f"/api/v1/alerts/station?dept={seeded['dept']}")
    spoken = " ".join(a["speech"] for a in r.get_json()["alerts"])
    assert "9 patients" not in spoken, "another department's announcement leaked"


def test_station_feed_never_exposes_other_tenants(client, seeded):
    from app.models import Organization
    other = Organization(code="OTH", name="Other Hospital")
    db.session.add(other)
    db.session.commit()
    announce.to_station(other.id, "queue_waiting", name="Theirs", count=77)
    db.session.commit()

    r = client.get("/api/v1/alerts/station")
    spoken = " ".join(a["speech"] for a in r.get_json()["alerts"])
    assert "77" not in spoken, "cross-tenant announcement leak"


# ================================================================ quiet hours
def test_quiet_hours_are_off_by_default():
    """Regression cause #3: the 22:00-07:00 default silenced night staff —
    exactly the people who most need to hear a patient is waiting."""
    from app.models import UserPref
    assert UserPref.DEFAULTS["quiet_start"] == ""
    assert UserPref.DEFAULTS["quiet_end"] == ""


# ================================================================ browser layer
def _js():
    return open("app/static/js/app.js", encoding="utf-8").read()


def test_speak_does_not_call_a_missing_function():
    """Regression cause #2: hmsVoice.speak called this.inQuietHours(), which
    only exists on hmsAlerts — a TypeError killed every announcement."""
    js = _js()
    assert "if (this.inQuietHours()) return;" not in js
    assert "alerts.inQuietHours()" in js


def test_audio_unlock_exists_and_is_visible():
    """Regression cause #4: browsers block audio until the user interacts, and
    the failure was completely invisible."""
    js = _js()
    assert "unlockAudio" in js
    assert "showUnlockBanner" in js
    assert "voice-unlock" in js
    assert "pointerdown" in js, "must unlock on first interaction"


def test_unlock_marks_ready_before_optional_apis():
    """One unsupported API must not leave voice switched off entirely."""
    js = _js()
    i_ready = js.index("this.audioReady = true;")
    i_ctx = js.index("window.AudioContext || window.webkitAudioContext", i_ready - 2000)
    assert i_ready < i_ctx, "audioReady must be set before the AudioContext attempt"


def test_speech_is_not_blocked_by_an_empty_voice_list():
    """On many Android builds onvoiceschanged never fires, which left the
    announcement queued forever and silent."""
    js = _js()
    assert "setTimeout(once, 250)" in js


def test_alert_text_is_never_injected_as_html():
    js = _js()
    assert "el.innerHTML = \"<div class='t-title'>\"" not in js
    assert "t.textContent = a.subject" in js


def test_a_test_button_exists_for_staff():
    js = _js()
    assert "testVoice" in js
    page = open("app/templates/alert_settings.html", encoding="utf-8").read()
    assert "hmsAlerts.testVoice()" in page
