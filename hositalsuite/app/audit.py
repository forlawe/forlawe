"""Tamper-evident audit trail (hash-chained)."""
from __future__ import annotations

import json
import threading

from flask import has_request_context, request

from .models import AuditLog, db, now_naive

# serialize chain construction within this process so concurrent requests
# cannot read the same "last hash" and fork the chain
_chain_lock = threading.Lock()

# F-002: the threading lock only guards ONE process. With WEB_CONCURRENCY>1
# (or >1 dyno) two workers could read the same "last hash" and fork the
# chain, silently destroying its tamper-evidence. On PostgreSQL a
# TRANSACTION-scoped advisory lock closes this: it is held until the worker's
# transaction COMMITS, so the next worker reads the committed tail (including
# the winner's row) and chains from it. On SQLite the app is single-process
# and the threading lock is sufficient.
_AUDIT_CHAIN_LOCK_KEY = 736559102      # sibling of the migration lock in env.py


def _acquire_chain_lock(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    conn.execute(db.text(f"SELECT pg_advisory_xact_lock({_AUDIT_CHAIN_LOCK_KEY})"))


def last_hash(org_id: int) -> str:
    row = db.session.query(AuditLog).filter_by(org_id=org_id).order_by(AuditLog.id.desc()).first()
    return row.hash if row else "GENESIS"


def audit(action: str, entity_type: str = None, entity_id: int = None,
          detail: dict | None = None, user=None, org_id: int = None):
    from flask_login import current_user
    u = user or (current_user if current_user and current_user.is_authenticated else None)
    uid = u.id if u else None
    oid = org_id if org_id is not None else (u.org_id if u else None)
    detail_json = json.dumps(detail or {}, default=str, sort_keys=True)
    at = now_naive()
    with _chain_lock:
        db.session.flush()   # include rows added in this transaction
        _acquire_chain_lock(db.session.connection())
        prev = last_hash(oid) if oid else "GENESIS"
        h = AuditLog.chain_hash(prev, oid, uid, action, entity_type, entity_id, detail_json, at)
        # Real client IP, not the proxy's — otherwise every audit row records
        # the same address and the trail is useless for investigating an incident.
        ip = None
        if has_request_context():
            try:
                from .security import client_ip
                ip = client_ip()
            except Exception:                            # noqa: BLE001
                ip = request.remote_addr
        db.session.add(AuditLog(
            org_id=oid, user_id=uid, action=action, entity_type=entity_type, entity_id=entity_id,
            detail=detail_json, ip=ip,
            user_agent=(request.user_agent.string[:250] if has_request_context() else None),
            at=at, prev_hash=prev, hash=h,
        ))
        db.session.flush()


def verify_chain(org_id: int) -> tuple[bool, int]:
    """Re-verify the audit hash chain. Returns (ok, rows_checked)."""
    rows = db.session.query(AuditLog).filter_by(org_id=org_id).order_by(AuditLog.id).all()
    prev = "GENESIS"
    for r in rows:
        expected = AuditLog.chain_hash(prev, r.org_id, r.user_id, r.action, r.entity_type,
                                       r.entity_id, r.detail, r.at)
        if r.hash != expected or r.prev_hash != prev:
            return False, len(rows)
        prev = r.hash
    return True, len(rows)
