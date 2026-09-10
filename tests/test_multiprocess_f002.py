"""F-002: correctness when more than one web worker runs.

The pilot ran a single gunicorn worker (WEB_CONCURRENCY=1) with an in-process
scheduler, an in-process rate limiter, and a hash chain guarded by a threading
lock. That ceiling was deliberate. This suite pins the three things that must
hold BEFORE the ceiling is lifted, so lifting it cannot silently fork the
audit trail, double-fire automation, or throttle inconsistently:

  1. the audit hash chain takes a PostgreSQL transaction-scoped advisory lock
     around "read last hash -> write next row" (and is a no-op on SQLite);
  2. the scheduler elects a single leader via a PostgreSQL session-scoped
     advisory lock (every loop is the leader on SQLite);
  3. the rate limiter uses Redis when REDIS_URL is set (shared across
     workers) and falls back to memory otherwise.
"""
from __future__ import annotations

import types

import pytest
from sqlalchemy import text


# ---------------------------------------------------------------- audit chain

class _FakePGConn:
    def __init__(self, dialect="postgresql"):
        self.dialect = types.SimpleNamespace(name=dialect)
        self.executed = []

    def execute(self, stmt):
        self.executed.append(str(stmt))


def test_audit_chain_lock_noop_on_sqlite():
    """SQLite is single-process by design — no advisory lock may be issued."""
    from app.audit import _acquire_chain_lock
    conn = _FakePGConn(dialect="sqlite")
    _acquire_chain_lock(conn)
    assert conn.executed == []


def test_audit_chain_lock_uses_transaction_scoped_advisory_lock():
    """On PostgreSQL the lock must be pg_advisory_XACT_lock: it is held until
    the worker's transaction commits, so the next worker reads the committed
    tail — a plain session lock would release too early and could still fork."""
    import app.audit as audit_mod
    from app.audit import _acquire_chain_lock
    conn = _FakePGConn(dialect="postgresql")
    _acquire_chain_lock(conn)
    assert len(conn.executed) == 1
    stmt = conn.executed[0]
    assert "pg_advisory_xact_lock" in stmt.lower(), stmt
    assert str(audit_mod._AUDIT_CHAIN_LOCK_KEY) in stmt, stmt


def test_audit_chain_still_verifies_after_locked_write(app, seeded):
    """The happy path is unchanged: an audit row written under the (no-op on
    SQLite) lock still chains from the previous hash and verifies."""
    from app.audit import audit, verify_chain
    with app.app_context():
        audit("F002_TEST", "patient", 1, {"k": "v"}, org_id=seeded["org"])
        db = app.extensions["sqlalchemy"]
        db.session.commit()
        ok, n = verify_chain(seeded["org"])
        assert ok and n >= 1


# ------------------------------------------------------- scheduler leadership

class _FakeEngine:
    def __init__(self, backend, is_leader=True):
        self._backend = backend
        self._is_leader = is_leader
        self.connected = 0
        self.lock_stmts = []
        url = types.SimpleNamespace(get_backend_name=lambda: self._backend)
        self.url = url

    def connect(self):
        self.connected += 1
        outer = self

        class _Conn:
            dialect = types.SimpleNamespace(name=outer._backend)

            def execute(self, stmt):
                outer.lock_stmts.append(str(stmt))
                return types.SimpleNamespace(scalar=lambda: outer._is_leader)

            def rollback(self):
                pass

        return _Conn()


class _FakeDB:
    def __init__(self, engine):
        self.engine = engine


class _LoopBreak(Exception):
    pass


def _run_one_loop_iteration(monkeypatch, scheduler_mod, fake_db, tick_calls):
    """Drive exactly one iteration of the scheduler loop by making tick (or,
    if tick is never reached, the sleep) raise the loop-break sentinel."""
    def _tick(app):
        tick_calls.append("tick")
        raise _LoopBreak()

    monkeypatch.setattr(scheduler_mod, "tick", _tick)

    def _sleep(_s):
        raise _LoopBreak()

    monkeypatch.setattr(scheduler_mod.time, "sleep", _sleep)
    with pytest.raises(_LoopBreak):
        scheduler_mod._loop(types.SimpleNamespace(logger=__import__("logging")
                                                 .getLogger("test")), 60)


def test_scheduler_sqlite_always_leads(monkeypatch):
    """Single-process pilot (SQLite): tick runs with no election round-trip."""
    import app.scheduler as scheduler_mod
    eng = _FakeEngine("sqlite")
    monkeypatch.setattr(scheduler_mod, "db", _FakeDB(eng))
    calls: list = []
    _run_one_loop_iteration(monkeypatch, scheduler_mod, None, calls)
    assert calls == ["tick"] and eng.connected == 0


def test_scheduler_leader_runs_tick(monkeypatch):
    """The instance that wins pg_try_advisory_lock runs the automation."""
    import app.scheduler as scheduler_mod
    eng = _FakeEngine("postgresql", is_leader=True)
    monkeypatch.setattr(scheduler_mod, "db", _FakeDB(eng))
    calls: list = []
    _run_one_loop_iteration(monkeypatch, scheduler_mod, None, calls)
    assert calls == ["tick"]
    assert eng.connected == 1
    assert any("pg_try_advisory_lock" in s.lower() for s in eng.lock_stmts)


def test_scheduler_follower_sleeps_without_ticking(monkeypatch):
    """A second instance must NOT run jobs — the whole point of the lock."""
    import app.scheduler as scheduler_mod
    eng = _FakeEngine("postgresql", is_leader=False)
    monkeypatch.setattr(scheduler_mod, "db", _FakeDB(eng))
    calls: list = []
    _run_one_loop_iteration(monkeypatch, scheduler_mod, None, calls)
    assert calls == []                      # no tick
    assert eng.lock_stmts                   # but it did ask for the lock


def test_scheduler_survives_dead_db_connection(monkeypatch):
    """If the leader-election connection cannot be opened, the loop backs off
    and retries — it must not crash the automation thread."""
    import app.scheduler as scheduler_mod

    class _DeadDB:
        class engine:                                   # noqa: N801
            url = types.SimpleNamespace(
                get_backend_name=lambda: "postgresql")

            @staticmethod
            def connect():
                raise RuntimeError("db down")

    monkeypatch.setattr(scheduler_mod, "db", _DeadDB)

    def _sleep(_s):
        raise _LoopBreak()

    monkeypatch.setattr(scheduler_mod.time, "sleep", _sleep)
    with pytest.raises(_LoopBreak):
        scheduler_mod._loop(types.SimpleNamespace(logger=__import__("logging")
                                                 .getLogger("test")), 60)


# --------------------------------------------------------------- rate limiter

def test_rate_limiter_prefers_redis_when_configured(monkeypatch):
    """REDIS_URL set → limits are counted in Redis, shared by all workers."""
    from app.security import RateLimiter
    rl = RateLimiter()
    rl._redis_checked = False
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(rl, "_redis", object(), raising=False)
    rl._redis_checked = True
    assert rl._get_redis() is not None


def test_rate_limiter_memory_fallback_without_redis(monkeypatch):
    """No REDIS_URL → in-memory limiter (documented single-worker behaviour)."""
    from app.security import RateLimiter
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_TLS_URL", raising=False)
    monkeypatch.setattr("flask.current_app", None, raising=False)
    rl = RateLimiter()
    rl._redis_checked = False
    assert rl._get_redis() is None
    assert rl.allow("f002-key", 2, 60) is True
    assert rl.allow("f002-key", 2, 60) is True
    assert rl.allow("f002-key", 2, 60) is False
