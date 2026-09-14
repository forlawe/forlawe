"""Boot-step isolation (Issue #4, 2026-09-14).

Every start-up step (create_all, migrations, auto-seed, KB, RLS, roles,
branches) runs through run_boot_step(), which guarantees the property Issue
#4 asked for: a step that dies mid-transaction rolls its OWN work back
before the next step touches the session.

WHY THIS MATTERS (learned from the live logs, not from theory)
--------------------------------------------------------------
A SQLAlchemy session that hits a flush error is left in a pending-rollback
state. If the failure is swallowed ("continuing") WITHOUT the rollback,
every later step on that session silently misbehaves: inserts vanish,
objects read back as deleted (ObjectDeletedError on /book), and the hospital
record itself never persists — so the next restart re-seeds from scratch
and prints a brand-new random admin password. One un-rolled-back flush
looked like five unrelated bugs.

Living in its own module (not a closure inside create_app) so a test can
pin the behaviour directly: tests/test_issue4_issue6_foundations.py.
"""
from __future__ import annotations


def run_boot_step(app, name: str, fn) -> None:
    """Run one start-up step; on ANY failure roll back and carry on serving."""
    from .models import db
    try:
        fn()
    except Exception:                                    # noqa: BLE001
        db.session.rollback()
        app.logger.exception("boot step %r failed — continuing", name)
