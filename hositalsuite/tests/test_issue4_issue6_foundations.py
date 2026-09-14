"""One isolated transaction per boot step; a login race must never 500.

Pins the two foundation fixes the consultant asked to see closed before any
UX work starts (issues #4 and #6):

* #4 asked that every boot step run in its own isolated transaction — a
  failure (e.g. the RLS refusal in #3) must rollback before the next step
  touches the session, and the seeded hospital must SURVIVE a restart
  without re-seeding (which used to mint a new random admin password each
  time and leave departments half-missing).
* #6 bug 1: two near-simultaneous sign-ins for the same username collided
  on the login-attempt unique index and 500'd. _lock_row now rolls the
  collision back and takes the row the other request created.

(#6 bug 2, the scheduler app-context loop, was already fixed in this
codebase — tick() pushes app context and background_all_orgs(); the live
test site's /api/v1/health showed scheduler:true and a backup run at
02:00 on 2026-09-14.)
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Department, LoginAttempt, Organization, User, db


# ----------------------------------------------- #4: isolated boot transactions
def test_run_boot_step_rolls_back_and_keeps_the_session_usable(app, seeded):
    """A boot step that dies mid-flush must not poison the next step."""
    from app.boot import run_boot_step

    with app.app_context():
        def broken_step():
            db.session.add(Department(org_id=seeded["org"], name="Ghost Dept",
                                      active=True))
            db.session.flush()
            raise RuntimeError("pretend RLS refusal mid-step")

        run_boot_step(app, "broken_step", broken_step)

        # the failed step's row is gone...
        assert db.session.query(Department).filter_by(name="Ghost Dept").first() is None
        # ...and the session still works for the NEXT boot step
        def good_step():
            db.session.add(Department(org_id=seeded["org"], name="Real Dept",
                                      active=True))
            db.session.commit()

        run_boot_step(app, "good_step", good_step)
        assert db.session.query(Department).filter_by(name="Real Dept").first() is not None


def test_restart_does_not_reseed_or_mint_new_passwords(tmp_path, monkeypatch):
    """The #4 symptom: every restart re-seeded from scratch and printed a NEW
    random admin password because the org 'didn't reliably exist'. Two boots
    against the same database must agree on org, departments and passwords."""
    from app import create_app

    dbfile = tmp_path / "restart.db"
    monkeypatch.setenv("AUTO_SEED", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")

    apps = []
    try:
        first = create_app(scheduler=False)
        apps.append(first)
        with first.app_context():
            org_id = db.session.query(Organization).first().id
            admin_hash = (db.session.query(User)
                          .filter_by(username="admin").first().password_hash)
            dept_count = db.session.query(Department).count()
            assert org_id and admin_hash and dept_count > 0
            db.session.remove()

        second = create_app(scheduler=False)   # = a Render restart
        apps.append(second)
        with second.app_context():
            org2 = db.session.query(Organization).first()
            admin2 = db.session.query(User).filter_by(username="admin").first()
            assert org2.id == org_id, "restart must reuse the seeded hospital"
            assert admin2.password_hash == admin_hash, (
                "restart must not mint a new random admin password")
            assert db.session.query(Department).count() == dept_count
            db.session.remove()
    finally:
        for a in apps:
            with a.app_context():
                db.session.remove()
                db.engine.dispose()


# ------------------------------------------------- #6: the login double-submit
def test_lock_row_survives_a_double_submit_race(app, seeded, monkeypatch):
    """Two sign-ins land at once: both SELECT (no row), both INSERT, the
    second trips ix_login_attempt_username. The login must continue with
    the row the first request created — never a 500."""
    from app.views import auth as authmod

    with app.app_context():
        real_flush = db.session.flush
        state = {"calls": 0}

        def flaky_flush(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                # the racing request wins: it commits its own row for the
                # same username while our SELECT has already come back empty
                with db.engine.begin() as conn:
                    conn.execute(LoginAttempt.__table__.insert().values(
                        org_id=None, username="racer", failures=0,
                        locked_until=None, last_failure_at=None, last_ip=None,
                    ))
                raise IntegrityError(
                    "INSERT INTO login_attempt", {},
                    Exception('duplicate key value violates unique constraint '
                              '"ix_login_attempt_username"'))
            return real_flush(*args, **kwargs)

        monkeypatch.setattr(db.session, "flush", flaky_flush)
        row = authmod._lock_row("racer", None)

    assert row is not None and row.username == "racer"
    assert row.failures == 0
    assert state["calls"] == 1, "the retry must re-SELECT, never flush blindly"


def test_lock_row_still_creates_a_fresh_row_when_there_is_no_race(app, seeded):
    from app.views import auth as authmod
    with app.app_context():
        row = authmod._lock_row("newperson", None)
        db.session.commit()
        assert row.username == "newperson" and row.failures == 0
        assert db.session.query(LoginAttempt).filter_by(username="newperson").count() == 1
