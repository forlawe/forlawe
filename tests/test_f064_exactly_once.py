"""F-064 — every queued message is sent exactly once, even under concurrency.

The rebuild spec (Phase 4) acceptance test: "firing 20 simultaneous triggering
events for message dispatch results in exactly 20 messages sent, never more,
never fewer." The fix is the atomic claim (UPDATE ... WHERE status='QUEUED')
in whatsapp.process_queue / sms.process_sms_queue; these tests prove that N
concurrent workers dispatching the same N-message queue produce exactly N
sent messages with no duplicate provider ids.
"""
import threading

from app.models import SmsMessage, WhatsAppMessage, db, now_naive


def _queue_whatsapp(app, org_id, n):
    with app.app_context():
        for i in range(n):
            db.session.add(WhatsAppMessage(
                org_id=org_id, to_number="+2348012345678", body=f"WA msg {i}",
                kind="alert", status="QUEUED", attempts=0))
        db.session.commit()


def _queue_sms(app, org_id, n):
    with app.app_context():
        for i in range(n):
            db.session.add(SmsMessage(
                org_id=org_id, to_number="+2348012345678", body=f"SMS msg {i}",
                kind="alert", status="QUEUED", attempts=0))
        db.session.commit()


def _run_workers(app, fn, workers):
    """Run `workers` threads all calling fn(app) at the same time."""
    barrier = threading.Barrier(workers)
    results, errors = [], []

    def worker():
        try:
            barrier.wait(timeout=10)
            with app.app_context():
                results.append(fn())
        except Exception as exc:                            # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, f"workers raised: {errors}"
    return results


def test_twenty_events_send_exactly_twenty_whatsapp_messages(app, seeded):
    from app import whatsapp
    _queue_whatsapp(app, seeded["org"], 20)
    # 4 concurrent dispatchers race over the same 20-row queue
    results = _run_workers(app, lambda: whatsapp.process_queue(limit=20), workers=4)
    assert sum(results) == 20, f"total dispatched {sum(results)} != 20 ({results})"
    with app.app_context():
        rows = db.session.query(WhatsAppMessage).order_by(WhatsAppMessage.id).all()
        sent = [r for r in rows if r.status in ("SENT", "DELIVERED")]
        assert len(sent) == 20, \
            f"exactly 20 rows may be sent, got {len(sent)}"
        ids = [r.provider_id for r in sent]
        assert len(ids) == len(set(ids)), "duplicate provider ids = duplicate sends!"


def test_thirty_sms_events_send_exactly_thirty(app, seeded):
    from app import sms as sms_engine
    _queue_sms(app, seeded["org"], 30)
    results = _run_workers(app, lambda: sms_engine.process_sms_queue(limit=30), workers=3)
    assert sum(results) == 30, f"total dispatched {sum(results)} != 30 ({results})"
    with app.app_context():
        rows = db.session.query(SmsMessage).order_by(SmsMessage.id).all()
        sent = [r for r in rows if r.status == "SENT"]
        assert len(sent) == 30, f"exactly 30 rows may be sent, got {len(sent)}"
        # a double-send would mean a second worker reclaimed a row and sent it
        # again, pushing that row's attempts to 2+. Every row must be 1.
        assert all(r.attempts == 1 for r in rows), \
            "every row must be attempted exactly once (no double-sends)"
        assert all(r.claimed_at is not None for r in rows)


def test_second_dispatch_pass_sends_nothing(app, seeded):
    """After one full pass there is nothing left to claim — no re-sends."""
    from app import whatsapp
    _queue_whatsapp(app, seeded["org"], 5)
    with app.app_context():
        first = whatsapp.process_queue(limit=20)
        second = whatsapp.process_queue(limit=20)
    assert first == 5 and second == 0
    with app.app_context():
        assert db.session.query(WhatsAppMessage).filter(
            WhatsAppMessage.status == "QUEUED").count() == 0
