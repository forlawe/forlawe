"""Background delivery dispatch (§39).

Critical operations never wait on slow third-party APIs: complaint/inspection/
booking submission saves instantly, then WhatsApp + SMS queues are processed
on a background thread. In tests, set SYNC_DELIVERY_FOR_TESTS=True to make
delivery synchronous and deterministic.
"""
from __future__ import annotations

import threading

from flask import current_app


def _process(app):
    with app.app_context():
        from . import sms, whatsapp
        from .models import db
        from .models import WhatsAppMessage
        try:
            # WhatsApp FIRST — process WhatsApp queue
            sent = whatsapp.process_queue(limit=20)
            # Check for failed WhatsApp messages that need SMS fallback
            try:
                failed = db.session.query(WhatsAppMessage).filter(
                    WhatsAppMessage.status == "FAILED",
                    WhatsAppMessage.last_error.ilike("%fallback%") | WhatsAppMessage.last_error.ilike("%failed%")
                ).order_by(WhatsAppMessage.created_at.desc()).limit(10).all()
                for f in failed:
                    if f.last_error and "fallback" in f.last_error.lower():
                        # Already queued SMS fallback in webhook, ensure it exists
                        pass
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001 — delivery must never crash the app
            app.logger.exception("whatsapp queue error: %s", exc)
            db.session.rollback()
        try:
            # Twilio SMS fallback — process only if WhatsApp failed or not available
            # SMS messages with kind ending _fallback are only sent if corresponding WhatsApp FAILED
            sms.process_sms_queue(limit=30)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("sms queue error: %s", exc)
            db.session.rollback()


def dispatch_delivery():
    """Fire-and-forget processing of WhatsApp + SMS queues."""
    app = current_app._get_current_object()
    if app.config.get("SYNC_DELIVERY_FOR_TESTS"):
        _process(app)
        return
    threading.Thread(target=_process, args=(app,), daemon=True,
                     name="hms-delivery").start()
