"""First-boot bootstrap tests (AUTO_SEED): free-plan hosts have no shell."""
import os

from app import create_app
from app.models import Organization, User, db


def test_auto_seed_bootstraps_empty_db_once(app, monkeypatch):
    # the `app` fixture's DB was dropped/recreated by conftest without seeding:
    assert db.session.query(Organization).count() == 0

    monkeypatch.setenv("AUTO_SEED", "1")
    app2 = create_app(scheduler=False)
    with app2.app_context():
        assert db.session.query(Organization).count() == 1
        admin = db.session.query(User).filter_by(username="admin").first()
        assert admin is not None and admin.must_change_password is True
        assert db.session.query(User).count() == 10

    # second boot must NOT reseed or duplicate anything
    app3 = create_app(scheduler=False)
    with app3.app_context():
        assert db.session.query(Organization).count() == 1
        assert db.session.query(User).count() == 10


def test_no_auto_seed_without_flag(app, monkeypatch):
    monkeypatch.delenv("AUTO_SEED", raising=False)
    app2 = create_app(scheduler=False)
    with app2.app_context():
        assert db.session.query(Organization).count() == 0
