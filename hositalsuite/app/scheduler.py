"""Background scheduler — one daemon thread driving all time-based automation:

* duty reminders (day-before + duty-day, configurable times)
* overdue inspection detection + management notification
* complaint SLA breach -> automatic escalation to MD/CEO
* complaint SLA warnings
* overdue corrective actions
* WhatsApp queue processing + retry
* nightly database backup

All jobs are idempotent (guarded by 'already-sent' markers / audit rows) so
restarting the app never double-sends.
"""
from __future__ import annotations

import threading
import time
from datetime import timedelta

from . import notifications, scoring, services, whatsapp
from .audit import audit
from .models import (AppNotification, Complaint, CorrectiveAction, DutyRoster,
                     Organization, db, now_naive)

_started = False
_thread_ref = None          # for health reporting
_lock = threading.Lock()
_last_backup_monotonic = 0.0   # in-memory min-interval guard for the nightly backup


# ------------------------------------------------------------------ helpers
def _sent_marker(org_id: int, template_key: str, entity_type: str, entity_id: int) -> bool:
    return db.session.query(AppNotification).filter_by(
        org_id=org_id, template_key=template_key, entity_type=entity_type,
        entity_id=entity_id).first() is not None


def _mark(template_key: str, user, body: str, org_id: int, entity_type: str, entity_id: int):
    db.session.add(AppNotification(org_id=org_id, user_id=user.id if user else None,
                                   channel="inapp", template_key=template_key,
                                   subject=template_key, body=body,
                                   entity_type=entity_type, entity_id=entity_id, status="SENT"))


# ------------------------------------------------------------------ jobs
def job_duty_reminders(app):
    """Day-before reminder and duty-day reminder at configured times."""
    now = now_naive()
    today = now.date()
    for org in db.session.query(Organization).all():
        db_hh, db_mm = services.parse_hhmm(services.get_setting(org.id, "reminder_day_before_time"))
        dy_hh, dy_mm = services.parse_hhmm(services.get_setting(org.id, "reminder_duty_day_time"))
        channels = services.get_setting(org.id, "reminder_channels") or ["inapp"]

        # day-before (tomorrow's duty)
        tomorrow = today + timedelta(days=1)
        roster = db.session.query(DutyRoster).filter_by(org_id=org.id, duty_date=tomorrow).first()
        if roster and now.replace(second=0, microsecond=0) >= now.replace(hour=db_hh, minute=db_mm, second=0, microsecond=0):
            if not _sent_marker(org.id, "duty_reminder_day_before", "roster", roster.id):
                notifications.notify(org.id, roster.user, "duty_reminder_day_before",
                                     {"name": roster.user.name, "date": tomorrow.strftime("%A, %d %B %Y"),
                                      "hospital": org.name},
                                     channels=channels, entity_type="roster", entity_id=roster.id)
                _mark("duty_reminder_day_before", roster.user,
                      f"Reminder sent for duty on {tomorrow}", org.id, "roster", roster.id)
                audit("REMINDER_SENT", "roster", roster.id, {"type": "day_before"},
                      org_id=org.id)

        # duty-day
        roster = db.session.query(DutyRoster).filter_by(org_id=org.id, duty_date=today).first()
        if roster and now.replace(second=0, microsecond=0) >= now.replace(hour=dy_hh, minute=dy_mm, second=0, microsecond=0):
            if not _sent_marker(org.id, "duty_reminder_day_of", "roster", roster.id):
                notifications.notify(org.id, roster.user, "duty_reminder_day_of",
                                     {"name": roster.user.name, "date": today.strftime("%A, %d %B %Y"),
                                      "hospital": org.name},
                                     channels=channels, entity_type="roster", entity_id=roster.id)
                _mark("duty_reminder_day_of", roster.user,
                      f"Reminder sent for duty on {today}", org.id, "roster", roster.id)
                audit("REMINDER_SENT", "roster", roster.id, {"type": "day_of"}, org_id=org.id)


def job_overdue_inspection(app):
    now = now_naive()
    today = now.date()
    for org in db.session.query(Organization).all():
        st = services.inspection_state(org.id, today, now=now)
        if st["state"] != "overdue":
            continue
        roster = db.session.query(DutyRoster).filter_by(org_id=org.id, duty_date=today).first()
        if not roster:
            continue
        if not _sent_marker(org.id, "inspection_overdue", "roster", roster.id):
            hh, mm = services.parse_hhmm(services.get_setting(org.id, "overdue_notify_time"))
            if now.hour * 60 + now.minute >= hh * 60 + mm:
                ctx = {"name": roster.user.name, "time":
                       services.get_setting(org.id, "inspection_deadline_time"), "hospital": org.name}
                # nudge the Admin Manager
                notifications.notify(org.id, roster.user, "inspection_overdue", ctx,
                                     channels=["inapp", "whatsapp"], entity_type="roster", entity_id=roster.id)
                # inform MD/CEO + super admins
                for md in notifications.md_ceos(org.id) + notifications.super_admins(org.id):
                    notifications.notify(org.id, md, "inspection_overdue", ctx,
                                         channels=["inapp"], entity_type="roster", entity_id=roster.id)
                _mark("inspection_overdue", roster.user, "Overdue inspection notification",
                      org.id, "roster", roster.id)
                audit("INSPECTION_OVERDUE_FLAG", "roster", roster.id, {"date": str(today)}, org_id=org.id)


def job_complaint_sla(app):
    """Warn before SLA expiry; escalate to MD/CEO when it expires — WhatsApp voice (feature 6)."""
    now = now_naive()
    for org in db.session.query(Organization).all():
        open_complaints = (db.session.query(Complaint)
                           .filter(Complaint.org_id == org.id,
                                   Complaint.status.in_(("NEW", "ACKNOWLEDGED", "IN_PROGRESS")),
                                   Complaint.escalated.is_(False)).all())
        for c in open_complaints:
            if scoring.should_escalate(c.status, c.escalated, c.sla_deadline_at, now):
                old_status = c.status                     # capture BEFORE mutation
                c.escalated = True
                c.status = "ESCALATED"
                c.escalated_at = now
                from .models import ComplaintStatusHistory
                pmsg = notifications.patient_update_text("escalated", org.name, c.ref)
                db.session.add(ComplaintStatusHistory(complaint_id=c.id, from_status=old_status,
                                                      to_status="ESCALATED",
                                                      note="Automatic escalation — HOD SLA expired",
                                                      patient_message=pmsg))
                audit("COMPLAINT_ESCALATED", "complaint", c.id,
                      {"reason": "SLA expired", "deadline": str(c.sla_deadline_at)}, org_id=org.id)
                ctx = {"ref": c.ref, "dept": c.department.name, "hospital": org.name}
                # WhatsApp-first escalation to MD/CEO + HOD + voice announcement
                for md in notifications.md_ceos(org.id):
                    notifications.notify(org.id, md, "complaint_escalated", ctx,
                                         channels=["inapp", "email", "whatsapp"],
                                         entity_type="complaint", entity_id=c.id)
                    # Voice reminder — standing requirement
                    try:
                        from . import announce as _ann
                        _ann.to_user(org.id, md, "complaint_escalated_voice",
                                     place=c.department.name,
                                     detail=f"Complaint {c.ref} for {c.department.name} breached SLA. Immediate action needed. Voice alert.",
                                     entity_type="complaint", entity_id=c.id)
                    except Exception:
                        pass
                hod = services.route_hod(c.department)
                if hod:
                    notifications.notify(org.id, hod, "complaint_escalated", ctx,
                                         channels=["inapp", "whatsapp"],
                                         entity_type="complaint", entity_id=c.id)
                    try:
                        from . import announce as _ann2
                        _ann2.to_user(org.id, hod, "complaint_escalated_voice",
                                      place=c.department.name,
                                      detail=f"Complaint {c.ref} breached SLA — escalated to MD/CEO. Please check now. Voice alert.",
                                      entity_type="complaint", entity_id=c.id)
                    except Exception:
                        pass
                duty = services.on_duty(org.id, now.date())
                if duty:
                    notifications.notify(org.id, duty, "complaint_escalated", ctx,
                                         channels=["inapp"], entity_type="complaint", entity_id=c.id)
                notifications.notify_complaint_patient(org, c, "escalated")
            else:
                # 4-hour warning, once — with voice
                remaining = (c.sla_deadline_at - now).total_seconds() / 3600
                if 0 < remaining <= 4 and not _sent_marker(org.id, "complaint_sla_warning", "complaint", c.id):
                    hod = services.route_hod(c.department)
                    if hod:
                        notifications.notify(org.id, hod, "complaint_sla_warning",
                                             {"ref": c.ref, "dept": c.department.name,
                                              "hours": f"{remaining:.0f}", "hospital": org.name},
                                             channels=["inapp", "whatsapp"],
                                             entity_type="complaint", entity_id=c.id)
                        try:
                            from . import announce as _ann3
                            _ann3.to_user(org.id, hod, "complaint_sla_warning_voice",
                                          place=c.department.name,
                                          detail=f"{c.ref} — {remaining:.0f} hours left. Voice reminder.",
                                          entity_type="complaint", entity_id=c.id)
                        except Exception:
                            pass
                        _mark("complaint_sla_warning", hod, "SLA warning", org.id, "complaint", c.id)


def job_corrective_actions(app):
    today = now_naive().date()
    cas = (db.session.query(CorrectiveAction)
           .filter(CorrectiveAction.status.in_(("OPEN", "IN_PROGRESS")),
                   CorrectiveAction.deadline < today).all())
    for ca in cas:
        ca.status = "OVERDUE"
        if not _sent_marker(ca.org_id, "ca_overdue", "ca", ca.id):
            notifications.notify(ca.org_id, ca.owner, "ca_overdue",
                                 {"details": ca.finding[:100], "date": ca.deadline.strftime("%d %b %Y")},
                                 channels=["inapp"], entity_type="ca", entity_id=ca.id)
            for md in notifications.md_ceos(ca.org_id):
                notifications.notify(ca.org_id, md, "ca_overdue",
                                     {"details": ca.finding[:100], "date": ca.deadline.strftime("%d %b %Y")},
                                     channels=["inapp"], entity_type="ca", entity_id=ca.id)
            _mark("ca_overdue", ca.owner, "Overdue CA", ca.org_id, "ca", ca.id)
            audit("CA_OVERDUE", "ca", ca.id, {"deadline": str(ca.deadline)}, org_id=ca.org_id)


def job_whatsapp_queue(app):
    whatsapp.process_queue(limit=20)
    from . import sms as sms_engine
    sms_engine.process_sms_queue(limit=30)
    # v2 push queue — free, works closed like alarm, cost saver
    try:
        from . import push as push_engine
        push_engine.process_push_queue(limit=30)
    except Exception:
        pass

def job_queue_estimator(app):
    """Update queue estimates from closed JourneySegments — free AI-like logic."""
    try:
        from .models import JourneySegment
        from . import queue_estimator
        # Find recently closed segments not yet used for estimate (last 1h)
        cutoff = now_naive() - timedelta(hours=1)
        segs = db.session.query(JourneySegment).filter(
            JourneySegment.ended_at.isnot(None),
            JourneySegment.seconds.isnot(None),
            JourneySegment.ended_at >= cutoff
        ).limit(200).all()
        for seg in segs:
            queue_estimator.update_estimate_from_segment(seg)
        db.session.commit()
    except Exception:
        db.session.rollback()

def job_personal_tv_updater(app):
    """Keep PersonalTvSession live — update position/wait from tickets/intakes/visits."""
    try:
        from .models_v2 import PersonalTvSession
        from . import personal_tv as ptv
        # Update sessions seen in last 2h that are not DONE
        cutoff = now_naive() - timedelta(hours=2)
        sessions = db.session.query(PersonalTvSession).filter(
            PersonalTvSession.updated_at >= cutoff,
            PersonalTvSession.current_stage.notin_(["DONE", "CANCELLED"])
        ).limit(100).all()
        for sess in sessions:
            try:
                if sess.ticket_id:
                    from .models import QueueTicket
                    ticket = db.session.get(QueueTicket, sess.ticket_id)
                    if ticket:
                        ptv.update_session_from_ticket(sess, ticket)
                if sess.intake_id:
                    from .models import ReceptionIntake
                    intake = db.session.get(ReceptionIntake, sess.intake_id)
                    if intake:
                        ptv.update_session_from_intake(sess, intake)
                if sess.visit_id:
                    from .models import PatientVisit
                    visit = db.session.get(PatientVisit, sess.visit_id)
                    if visit:
                        ptv.update_session_from_visit(sess, visit)
            except Exception:
                continue
        db.session.commit()
    except Exception:
        db.session.rollback()


def job_nightly_backup(app):
    """Engine-independent nightly backup (SQLite AND PostgreSQL).

    The previous implementation silently returned on PostgreSQL, so production
    had no backups at all despite the UI claiming otherwise. See app/backup.py.

    A backup is a FULL read of every table — the single largest routine query
    this app points at the database. On a metered-egress host (Supabase free:
    5 GB/month) an accidental second run per day would double the largest line
    item, so a hard in-memory minimum interval backstops the per-day Setting
    guard: even if the Setting read fails or races, a backup can never run
    more than once per MIN_BACKUP_INTERVAL_HOURS per process.
    """
    import time as _time
    from .backup import create_backup, prune_backups
    from .config import Config

    global _last_backup_monotonic
    if _last_backup_monotonic and \
            (_time.monotonic() - _last_backup_monotonic) < Config.MIN_BACKUP_INTERVAL_HOURS * 3600:
        app.logger.info("nightly backup skipped — another one ran less than "
                        "%sh ago (in-memory guard)", Config.MIN_BACKUP_INTERVAL_HOURS)
        return
    try:
        create_backup(app, kind="nightly")
        prune_backups(keep=Config.BACKUP_KEEP)
        _last_backup_monotonic = _time.monotonic()
    except Exception as exc:                     # noqa: BLE001
        app.logger.exception("nightly backup FAILED: %s", exc)
        db.session.rollback()
        raise


def job_retention_purge(app):
    """Enforce the configured data-retention period (NDPA 2023).

    The `retention_days` setting existed but nothing ever acted on it, so the
    hospital promised a retention limit and kept patient data forever.

    We ANONYMISE rather than hard-delete: statistics (scores, SLA performance,
    satisfaction trends) stay intact for management reporting, while the
    personal identifiers that make a record sensitive are destroyed. Every pass
    is audit-logged, and already-anonymised rows are skipped so it is idempotent.
    """
    from .models import Appointment, PatientFeedback, QueueTicket
    now = now_naive()
    for org in db.session.query(Organization).all():
        try:
            days = int(services.get_setting(org.id, "retention_days") or 2190)
        except (TypeError, ValueError):
            days = 2190
        days = max(30, days)                      # never purge more aggressively than 30 days
        cutoff = now - timedelta(days=days)
        purged = 0

        for c in (db.session.query(Complaint)
                  .filter(Complaint.org_id == org.id,
                          Complaint.submitted_at < cutoff,
                          Complaint.anonymized_at.is_(None)).limit(500).all()):
            c.phone = "[erased]"
            c.description = "[erased under data-retention policy]"
            c.attachment_path = None
            c.anonymized_at = now
            purged += 1

        for a in (db.session.query(Appointment)
                  .filter(Appointment.org_id == org.id,
                          Appointment.created_at < cutoff,
                          Appointment.anonymized_at.is_(None)).limit(500).all()):
            a.patient_name, a.phone = "[erased]", "[erased]"
            a.anonymized_at = now
            purged += 1

        for f in (db.session.query(PatientFeedback)
                  .filter(PatientFeedback.org_id == org.id,
                          PatientFeedback.created_at < cutoff,
                          PatientFeedback.anonymized_at.is_(None)).limit(500).all()):
            f.phone = None
            if f.comment:
                f.comment = "[erased under data-retention policy]"
            f.anonymized_at = now
            purged += 1

        for t in (db.session.query(QueueTicket)
                  .filter(QueueTicket.org_id == org.id,
                          QueueTicket.created_at < cutoff,
                          QueueTicket.anonymized_at.is_(None)).limit(500).all()):
            t.patient_name, t.phone = "[erased]", None
            t.anonymized_at = now
            purged += 1

        if purged:
            audit("RETENTION_PURGE", "system", None,
                  {"records": purged, "retention_days": days}, org_id=org.id)
            app.logger.info("retention: anonymised %d record(s) for org %s", purged, org.code)


def job_patient_flow(app):
    """Watch the flow: close forgotten stretches, and SPEAK about hold-ups.

    Voice is a standing requirement of every feature. A dashboard nobody opens
    is a dashboard nobody acts on, so the two things worth interrupting a
    working day for are said out loud: a patient who looks forgotten, and a
    department holding the whole hospital up.

    Deliberately quiet otherwise. An alert that fires constantly is ignored
    within a week, and then the one that mattered is ignored too.

    Wrapped per-organisation: a fault measuring one hospital must never stop
    the others, and must never stop the jobs that follow.
    """
    from . import tracking
    for org in db.session.query(Organization).all():
        try:
            closed = tracking.close_abandoned(org.id)
            if closed:
                app.logger.info("flow: closed %s abandoned stretch(es) for org %s",
                                closed, org.id)
            tracking.announce_forgotten(org.id)
            tracking.announce_bottleneck(org.id)

            # Role Management: keep the teamwork noticeboard honest, and warn
            # HODs while there is still time to act rather than after.
            from . import deptwork, escalation
            stale = deptwork.close_forgotten_claims(org.id)
            if stale:
                app.logger.info("flow: closed %s forgotten work claim(s) for org %s",
                                stale, org.id)
            escalation.warn_hods_running_out(org.id)
            db.session.commit()
        except Exception:                                  # noqa: BLE001
            app.logger.exception("patient-flow job failed for org %s", org.id)
            db.session.rollback()


# ------------------------------------------------------------------ tick v2 — push + queue estimator + personal TV
JOB_SEQUENCE = (job_duty_reminders, job_overdue_inspection, job_complaint_sla,
                job_corrective_actions, job_whatsapp_queue, job_queue_estimator,
                job_personal_tv_updater, job_patient_flow,
                job_retention_purge)


def tick(app):
    """Run one full automation pass (used by the scheduler thread and by tests/CLI)."""
    with app.app_context():
        # Row-Level Security scopes ordinary requests to one hospital. The
        # automation genuinely works across all of them (SLA escalation,
        # reminders, retries), so it declares that intent explicitly rather
        # than relying on an unset variable — which would see nothing.
        from .rls import all_orgs
        all_orgs()
        try:
            for job in JOB_SEQUENCE:
                try:
                    job(app)
                except Exception as exc:  # noqa: BLE001 — one job must not kill the rest
                    app.logger.exception("Scheduler job %s failed: %s", job.__name__, exc)
                    db.session.rollback()
            db.session.commit()
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Scheduler tick failed: %s", exc)
            db.session.rollback()


def _loop(app, interval: int):
    """Scheduler main loop. Must NEVER exit — it is the hospital's automation.

    A bare `except Exception` cannot catch everything that can end a thread, so
    the sleep is outside the try and the whole body is defensive. If the process
    is out of memory or the DB is unreachable we back off and keep trying rather
    than dying silently and leaving SLAs un-escalated.

    FIX 2026-08-21: last_backup_day lived in memory. Render restarts constantly,
    so memory resets and backup ran 4x/day (twice 9 seconds apart), blowing the
    Supabase quota. Now stored in Setting table so it survives restarts.

    F-002 (multi-process): WEB_CONCURRENCY>1 or >1 dyno means several identical
    schedulers run in parallel. Jobs are idempotent but the nightly backup was
    NOT (quota) and SLA escalations would fire 2-3x. A PostgreSQL SESSION-scoped
    advisory lock held on a dedicated connection elects ONE leader per fleet:
    lock loss (worker killed / connection dropped) auto-releases, so leadership
    fails over within one interval. On SQLite (single-process pilot) every loop
    is the leader.
    """
    from sqlalchemy import text

    SCHEDULER_LEADER_LOCK_KEY = 736559103   # sibling of audit chain lock
    leader_conn = None
    consecutive_failures = 0
    while True:
        try:
            if db.engine.url.get_backend_name() == "postgresql":
                if leader_conn is None:
                    try:
                        leader_conn = db.engine.connect()
                        # defensive: make sure we start from a clean slate
                        leader_conn.rollback()
                    except Exception:  # noqa: BLE001 — DB down; retry next tick
                        app.logger.exception("Scheduler could not open leader-election connection")
                        leader_conn = None
                        time.sleep(interval)
                        continue
                is_leader = leader_conn.execute(text(
                    f"SELECT pg_try_advisory_lock({SCHEDULER_LEADER_LOCK_KEY})"
                )).scalar()
                if not is_leader:
                    time.sleep(interval)   # another instance is the leader
                    continue
            tick(app)
            today = now_naive().date()
            # Check if backup already done today (from DB, not memory)
            need_backup = False
            try:
                with app.app_context():
                    from .models import Organization, Setting
                    from .rls import all_orgs

                    all_orgs()
                    # If no org yet (first boot), skip backup check
                    orgs = db.session.query(Organization).all()
                    if orgs:
                        # Check first org's last backup date — backup is global
                        last = Setting.get(orgs[0].id, "last_backup_day")
                        if last != today.isoformat() and now_naive().hour >= 2:
                            need_backup = True
                    db.session.commit()
            except Exception:
                # If we can't read settings, err on side of not backing up
                # repeatedly — next tick will try again
                need_backup = False
                try:
                    db.session.rollback()
                except Exception:
                    pass

            if need_backup:
                with app.app_context():
                    job_nightly_backup(app)
                    # Mark as done in Setting table for ALL orgs (survives restarts)
                    try:
                        from .models import Organization, Setting
                        from .rls import all_orgs

                        all_orgs()
                        for org in db.session.query(Organization).all():
                            Setting.set(org.id, "last_backup_day", today.isoformat())
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
            consecutive_failures = 0
        except BaseException as exc:                  # noqa: BLE001 - stay alive
            consecutive_failures += 1
            try:
                app.logger.exception("scheduler loop error (%d in a row): %s",
                                     consecutive_failures, exc)
            except Exception:                         # noqa: BLE001 - logging must not kill us
                pass
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        # Exponential-ish backoff while unhealthy, so a hard-down database does
        # not spin the CPU, but recovery is still detected within a minute or two.
        delay = interval if consecutive_failures == 0 else min(interval * consecutive_failures, 300)
        time.sleep(delay)


def start_scheduler(app, interval: int = 30):
    global _started
    with _lock:
        if _started:
            return
        global _thread_ref
        t = threading.Thread(target=_loop, args=(app, interval), daemon=True, name="hms-scheduler")
        t.start()
        _thread_ref = t
        _started = True


def is_alive() -> bool | None:
    """True if the scheduler thread is running, False if it died, None if disabled.

    The scheduler drives reminders, SLA escalation and backups. If its thread
    dies unnoticed, complaints stop escalating and nobody finds out until a
    patient does — so /api/v1/health surfaces it.
    """
    import os
    if os.environ.get("DISABLE_SCHEDULER") == "1":
        return None
    if not _started:
        return None
    thread = _thread_ref
    return bool(thread and thread.is_alive())


def ensure_running(app) -> bool:
    """Restart the scheduler thread if it has died. Self-healing.

    The thread can die during a bad boot — e.g. the database was still waking
    up on the very first tick. Without this it stays dead until someone
    redeploys, and duty reminders plus SLA escalation silently never happen.
    Called from the health endpoint, so any monitoring ping also repairs it.
    """
    global _started, _thread_ref
    import os
    if os.environ.get("DISABLE_SCHEDULER") == "1":
        return False
    with _lock:
        thread = _thread_ref
        if thread is not None and thread.is_alive():
            return False
        t = threading.Thread(target=_loop, args=(app, 30), daemon=True,
                             name="hms-scheduler")
        t.start()
        _thread_ref = t
        _started = True
        app.logger.warning("scheduler was not running — restarted it")
        return True
