"""F-065 / F-069 — inspections are stamped with the criteria wording version.

The audit found NO criteria_version column anywhere: an inspection recorded
under the v1 wording (criterion #2 = cleanliness) could later be read, trended
or "recurring-problem"-counted as if it had been recorded under v2
(criterion #2 = equipment). These tests pin the structural fix:

  * every inspection created through the real write path is stamped with
    scoring.CRITERIA_VERSION at write time (single source of truth);
  * the detail page shows the wording the record was actually scored under;
  * recurring-problem / criterion-average logic never mixes versions.
"""
import sqlite3
import tempfile

from app import scoring
from app.models import (Department, Inspection, InspectionScore,
                        Organization, User, db, now_naive)
from app.services import recurring_flags_for_department
from tests.conftest import csrf, login

V1_CRITERION_2 = "Cleanliness & Infection Prevention"   # v1 meaning of #2
V2_CRITERION_2 = "Equipment / Tools & Consumables"      # v2 meaning of #2


def _mk_inspection(org_id, dept_id, inspector_id, day, version, scores):
    """Create a submitted inspection exactly as the write path would, but with
    a forced criteria_version (to simulate a v1-era record)."""
    insp = Inspection(
        org_id=org_id, ref=f"INS-{new_code_unique()}", verify_code=f"V{new_code_unique()}",
        inspector_id=inspector_id, duty_date=day, department_id=dept_id,
        status="SUBMITTED", started_at=now_naive(), submitted_at=now_naive(),
        total_score=sum(scores.values()), percent=scoring.calc_percent(sum(scores.values())),
        rating=scoring.rating_for(sum(scores.values())),
        criteria_version=version,
        critical_count=scoring.critical_count(scores),
        poor_count=scoring.poor_count(scores),
    )
    db.session.add(insp)
    db.session.flush()
    for no in range(1, 6):
        db.session.add(InspectionScore(inspection_id=insp.id, criterion_no=no,
                                       score=scores[no]))
    return insp


_counter = 0


def new_code_unique():
    global _counter
    _counter += 1
    return f"x{_counter:06d}"


# ------------------------------------------------------------------ write path
def test_new_inspection_is_stamped_with_current_version(app, client, seeded):
    login(client, "am1")
    tok = csrf(client, "/inspections/new")
    client.post("/inspections/submit", data={
        "_csrf": tok, "department_id": seeded["dept"],
        "score_1": "4", "score_2": "4", "score_3": "4", "score_4": "4", "score_5": "4"},
        follow_redirects=True)
    with app.app_context():
        insp = db.session.query(Inspection).first()
        assert insp is not None
        assert insp.criteria_version == scoring.CRITERIA_VERSION, \
            "a new inspection must be stamped with the CURRENT criteria version"


def test_model_default_reads_the_single_constant(app, seeded):
    """Even a bare Inspection(...) insert must not hardcode a magic number."""
    from datetime import timedelta
    from app.models import new_code
    day = now_naive().date()
    insp = Inspection(
        org_id=seeded["org"], ref=f"INS-{new_code(8)}", verify_code=new_code(10),
        inspector_id=seeded["am"], duty_date=day, department_id=seeded["dept"],
        status="SUBMITTED", submitted_at=now_naive())
    db.session.add(insp)
    db.session.flush()
    assert insp.criteria_version == scoring.CRITERIA_VERSION


# ------------------------------------------------------------------ read path
def test_detail_page_shows_the_wording_the_record_was_scored_under(app, client, seeded):
    from datetime import date, timedelta
    # write first, log in after — keeps the test database free of lock clashes
    with app.app_context():
        v1_insp = _mk_inspection(
            seeded["org"], seeded["dept"], seeded["am"],
            date.today() - timedelta(days=40), version=1,
            scores={1: 5, 2: 1, 3: 4, 4: 4, 5: 4})
        db.session.commit()
        v1_id = v1_insp.id
    login(client, "am1")
    r = client.get(f"/inspections/{v1_id}")
    assert r.status_code == 200
    import html as _html
    body = _html.unescape(r.data.decode())
    # criterion #2 under v1 was "Cleanliness & Infection Prevention"...
    assert V1_CRITERION_2 in body, "detail page must show the v1 wording for a v1 record"
    # ...and must NOT be labelled with the v2 meaning it never had.
    assert V2_CRITERION_2 not in body, \
        "a v1 record must not be re-labelled with v2 criterion wording"


# ------------------------------------------------------------------ analytics
def test_recurring_findings_never_mix_versions():
    """Pure-function guard: v1 bad scores must not count as v2 problems."""
    bad_2 = {1: 5, 2: 1, 3: 5, 4: 5, 5: 5}
    good_2 = {1: 5, 2: 5, 3: 5, 4: 5, 5: 5}
    history = [{"criterion_scores": bad_2, "criteria_version": 1} for _ in range(10)]
    assert scoring.recurring_findings(history) == [], \
        "ten v1 'bad #2' records must not be reported as a current recurring problem"
    history = [{"criterion_scores": bad_2, "criteria_version": 2} for _ in range(6)]
    history += [{"criterion_scores": good_2, "criteria_version": 2} for _ in range(4)]
    msgs = scoring.recurring_findings(history)
    assert any("scored 1–2 in 6 of the last 10" in m for m in msgs), \
        "six current-version bad records SHOULD be reported"


def test_recurring_flags_for_department_ignores_older_wording(app, seeded):
    """End-to-end service guard over real rows in one department."""
    from datetime import date, timedelta
    with app.app_context():
        day = date.today() - timedelta(days=1)
        # 8 records under v1 with criterion #2 always failing...
        for i in range(8):
            _mk_inspection(seeded["org"], seeded["dept"], seeded["am"], day,
                           version=1, scores={1: 5, 2: 1, 3: 5, 4: 5, 5: 5})
        # ...and 2 under the current version where #2 is fine.
        for i in range(2):
            _mk_inspection(seeded["org"], seeded["dept"], seeded["am"], day,
                           version=scoring.CRITERIA_VERSION,
                           scores={1: 5, 2: 5, 3: 5, 4: 5, 5: 5})
        db.session.commit()
        flags = recurring_flags_for_department(seeded["org"], seeded["dept"])
        assert flags == [], \
            f"v1 failures must not surface as current recurring problems: {flags}"


def test_criterion_averages_use_only_the_current_wording(app, client, seeded):
    """department_report criterion averages exclude older-wording records."""
    from datetime import date, timedelta
    # write first, log in after — keeps the test database free of lock clashes
    with app.app_context():
        day = date.today() - timedelta(days=1)
        _mk_inspection(seeded["org"], seeded["dept"], seeded["am"], day,
                       version=1, scores={1: 1, 2: 1, 3: 1, 4: 1, 5: 1})
        _mk_inspection(seeded["org"], seeded["dept"], seeded["am"], day,
                       version=scoring.CRITERIA_VERSION,
                       scores={1: 5, 2: 5, 3: 5, 4: 5, 5: 5})
        db.session.commit()
    login(client, "admin")
    # render the HTML department report through the test client
    r = client.get(f"/reports/departments/{seeded['dept']}")
    assert r.status_code == 200
    body = r.data.decode()
    # the v1 record (all 1s) must be EXCLUDED from the criterion averages, so
    # every average is 5.0. If versions were mixed the average would be 3.0.
    assert body.count("5.0") >= 5, \
        "criterion averages must exclude older-wording records (got no 5.0s)"
    assert "3.0" not in body, "a v1 all-1s record leaked into current-version averages"


# ------------------------------------------------------------------ migration
def test_upgrade_backfills_old_inspections_with_version_1():
    """A real alembic upgrade (k28 -> l29) must stamp pre-2026-08-18 rows v1."""
    from alembic import command
    from alembic.config import Config

    root = "."
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp.name}")
    # build the full pre-l29 schema
    command.upgrade(cfg, "k28_tenant_usernames")
    con = sqlite3.connect(tmp.name)
    con.execute(
        "INSERT INTO inspection (id, org_id, ref, verify_code, inspector_id, "
        "duty_date, department_id, status, started_at, submitted_at) VALUES "
        "(1, 1, 'INS-OLD-1', 'VERIFYOLD1', 1, '2026-08-01', 1, 'SUBMITTED', "
        "'2026-08-01 09:00:00', '2026-08-01 10:00:00')")
    con.execute(
        "INSERT INTO inspection (id, org_id, ref, verify_code, inspector_id, "
        "duty_date, department_id, status, started_at, submitted_at) VALUES "
        "(2, 1, 'INS-NEW-1', 'VERIFYNEW1', 1, '2026-08-20', 1, 'SUBMITTED', "
        "'2026-08-20 09:00:00', '2026-08-20 10:00:00')")
    con.commit()
    con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(tmp.name)
    rows = dict(con.execute("SELECT id, criteria_version FROM inspection"))
    con.close()
    try:
        os_unlink = __import__("os").unlink
        os_unlink(tmp.name)
    except Exception:
        pass
    assert rows == {1: 1, 2: 2}, \
        f"backfill must stamp pre-v2 records v1: got {rows}"
