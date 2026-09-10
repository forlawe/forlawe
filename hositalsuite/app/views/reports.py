"""Report center: PDF + Excel/CSV exports, department performance, digital archive."""
from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timedelta

from flask import (Blueprint, Response, abort, render_template,
                   request)
from flask_login import current_user

from .. import pdfgen, storage, scoring, services
from ..audit import audit
from ..config import Config
from ..models import (Complaint, CorrectiveAction, Department, DutyRoster,
                      Inspection, Organization, ReportFile, db, new_code,
                      now_naive)
from ..security import require_role

bp = Blueprint("reports", __name__, url_prefix="/reports")

# Anyone with management sight, plus the Admin Manager and HODs who file/act on reports.
MGR = ("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR",
       "ADMIN_MANAGER", "HOD")


def _org() -> Organization:
    return db.session.get(Organization, current_user.org_id)


def _csv_response(header: list[str], rows: list[list], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    resp = Response(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return resp


def _archive_pdf(kind: str, title: str, path: str, verify_code: str,
                 entity_type: str = None, entity_id: int = None) -> ReportFile:
    rf = ReportFile(org_id=current_user.org_id, kind=kind, title=title, path=path,
                    verify_code=verify_code, entity_type=entity_type, entity_id=entity_id,
                    created_by_id=current_user.id)
    db.session.add(rf)
    return rf


# ------------------------------------------------------------------ center
@bp.get("")
@require_role(*MGR)
def center():
    archive = (db.session.query(ReportFile).filter_by(org_id=current_user.org_id)
               .order_by(ReportFile.created_at.desc()).limit(100).all())
    return render_template("reports_center.html", archive=archive, today=now_naive().date())


# ------------------------------------------------------------------ daily inspection report
@bp.get("/inspection-daily")
@require_role(*MGR)
def inspection_daily():
    try:
        day = date.fromisoformat(request.args.get("date") or now_naive().date().isoformat())
    except ValueError:
        day = now_naive().date()
    fmt = request.args.get("format", "pdf")
    items = (db.session.query(Inspection)
             .filter_by(org_id=current_user.org_id, duty_date=day, status="SUBMITTED")
             .order_by(Inspection.submitted_at).all())
    header = ["Ref", "Department", "Admin Manager", "Staff", "Cleanliness", "Equipment",
              "Records", "Safety", "Total", "Percent", "Rating", "Explanations"]
    rows = []
    for i in items:
        sc = {s.criterion_no: s for s in i.scores}
        expls = "; ".join(f"C{n}: {sc[n].explanation}" for n in range(1, 6)
                          if sc.get(n) and sc[n].score <= 2 and sc[n].explanation)
        place = i.department.name + (f" / {i.section.name}" if i.section else "") + \
                (f" / {i.unit.name}" if i.unit else "")
        rows.append([i.ref, place, i.inspector.name] +
                    [sc.get(n).score if sc.get(n) else "" for n in range(1, 6)] +
                    [i.total_score, f"{i.percent}%", i.rating, expls])

    if fmt == "csv":
        return _csv_response(header, rows, f"daily-inspection-{day}.csv")

    org = _org()
    notes = []
    if not items:
        st = services.inspection_state(org.id, day)
        notes.append("No inspection was submitted on this date." if st["state"] != "completed"
                     else "")
    path = "reports/" + f"daily-{day}-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Daily Inspection Report", day.strftime("%A, %d %B %Y"),
                             header, rows, path, notes=[n for n in notes if n], verify_code=code)
    _archive_pdf("daily", f"Daily Inspection Report {day}", path, code)
    audit("REPORT_GENERATED", "report", None, {"kind": "daily", "date": str(day)})
    db.session.commit()
    return storage.send(path, as_attachment=True, download_name=f"daily-inspection-{day}.pdf",
                        mimetype="application/pdf")


# ------------------------------------------------------------------ weekly / monthly summaries
def _period_rows(start: date, end: date):
    items = (db.session.query(Inspection)
             .filter(Inspection.org_id == current_user.org_id, Inspection.status == "SUBMITTED",
                     Inspection.duty_date >= start, Inspection.duty_date <= end)
             .order_by(Inspection.duty_date).all())
    rows = []
    for i in items:
        place = i.department.name + (f" / {i.section.name}" if i.section else "") + \
                (f" / {i.unit.name}" if i.unit else "")
        rows.append([i.duty_date.isoformat(), i.ref, place, i.inspector.name,
                     i.total_score, f"{i.percent}%", i.rating, i.critical_count or 0])
    return rows


@bp.get("/weekly")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR")
def weekly():
    try:
        start = date.fromisoformat(request.args.get("start") or
                                   (now_naive().date() - timedelta(days=7)).isoformat())
    except ValueError:
        start = now_naive().date() - timedelta(days=7)
    end = start + timedelta(days=6)
    fmt = request.args.get("format", "pdf")
    header = ["Date", "Ref", "Department", "Admin Manager", "Total /25", "Percent", "Rating", "Critical"]
    rows = _period_rows(start, end)
    if fmt == "csv":
        return _csv_response(header, rows, f"weekly-{start}.csv")
    org = _org()
    avg = round(sum(r[4] for r in rows) / len(rows), 1) if rows else 0
    notes = [f"Period: {start} to {end}", f"Inspections: {len(rows)}", f"Average score: {avg}/25"]
    path = "reports/" + f"weekly-{start}-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Weekly Inspection Summary", f"{start} — {end}", header, rows,
                             path, notes=notes, verify_code=code)
    _archive_pdf("weekly", f"Weekly Summary {start}", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


@bp.get("/monthly")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR")
def monthly():
    month = request.args.get("month") or now_naive().strftime("%Y-%m")
    try:
        start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    except ValueError:
        start = now_naive().date().replace(day=1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    fmt = request.args.get("format", "pdf")
    header = ["Date", "Ref", "Department", "Admin Manager", "Total /25", "Percent", "Rating", "Critical"]
    rows = _period_rows(start, end)

    # complaints in month
    comps = (db.session.query(Complaint)
             .filter(Complaint.org_id == current_user.org_id,
                     Complaint.submitted_at >= datetime.combine(start, datetime.min.time()),
                     Complaint.submitted_at < datetime.combine(end + timedelta(days=1), datetime.min.time())).all())
    escalated = [c for c in comps if c.escalated]
    resolved = [c for c in comps if c.status in ("RESOLVED", "CLOSED")]

    if fmt == "csv":
        return _csv_response(header, rows, f"monthly-{month}.csv")
    org = _org()
    avg = round(sum(r[4] for r in rows) / len(rows), 1) if rows else 0
    notes = [f"Period: {start} to {end}",
             f"Inspections completed: {len(rows)} (average {avg}/25)",
             f"Complaints received: {len(comps)}",
             f"Complaints resolved: {len(resolved)}",
             f"Complaints escalated to MD/CEO: {len(escalated)}"]
    path = "reports/" + f"monthly-{month}-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Monthly Management Report", start.strftime("%B %Y"),
                             header, rows, path, notes=notes, verify_code=code)
    _archive_pdf("monthly", f"Monthly Report {month}", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


# ------------------------------------------------------------------ department performance
@bp.get("/departments/<int:dept_id>")
@require_role(*MGR)
def department_report(dept_id: int):
    dept = db.session.get(Department, dept_id)
    if not dept or dept.org_id != current_user.org_id:
        abort(404)
    days = min(int(request.args.get("days", type=int) or 30), 365)
    hist = services.department_history(current_user.org_id, dept.id, limit=days)
    fmt = request.args.get("format", "html")
    criterion_avgs = {}
    for no in range(1, 6):
        vals = [s.score for i in hist for s in i.scores if s.criterion_no == no]
        criterion_avgs[no] = round(sum(vals) / len(vals), 1) if vals else None
    recurring = services.recurring_flags_for_department(current_user.org_id, dept.id)
    weekly_avg = round(sum(i.total_score for i in hist[:7]) / min(len(hist), 7), 1) if hist else None
    monthly_avg = round(sum(i.total_score for i in hist[:30]) / min(len(hist), 30), 1) if hist else None

    if fmt == "csv":
        header = ["Date", "Ref", "Inspector", "C1", "C2", "C3", "C4", "C5", "Total", "Rating"]
        rows = []
        for i in hist:
            sc = {s.criterion_no: s.score for s in i.scores}
            rows.append([i.duty_date.isoformat(), i.ref, i.inspector.name] +
                        [sc.get(n, "") for n in range(1, 6)] + [i.total_score, i.rating])
        return _csv_response(header, rows, f"dept-{dept.name.replace(' ', '_')}.csv")
    if fmt == "pdf":
        org = _org()
        header = ["Date", "Ref", "Inspector", "Total /25", "Rating"]
        rows = [[i.duty_date.isoformat(), i.ref, i.inspector.name, i.total_score, i.rating]
                for i in hist]
        notes = ["Criterion averages: " + ", ".join(
            f"{scoring.CRITERIA[n]['title']}: {criterion_avgs[n]}" for n in range(1, 6)
            if criterion_avgs[n] is not None)] + (["Recurring: " + r for r in recurring] or [])
        path = "reports/" + f"dept-{dept.id}-{new_code(4)}.pdf"
        code = new_code(10)
        storage.build_summary(org, f"Department Performance — {dept.name}",
                                 f"Last {days} inspections", header, rows, path,
                                 notes=notes, verify_code=code)
        _archive_pdf("dept", f"Dept Report {dept.name}", path, code, "department", dept.id)
        db.session.commit()
        return storage.send(path, as_attachment=True, mimetype="application/pdf")

    return render_template("department_report.html", dept=dept, hist=hist,
                           criterion_avgs=criterion_avgs, recurring=recurring,
                           weekly_avg=weekly_avg, monthly_avg=monthly_avg, criteria=scoring.CRITERIA)


# ------------------------------------------------------------------ complaint reports
@bp.get("/complaints")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR", "ADMIN_MANAGER")
def complaints_report():
    fmt = request.args.get("format", "pdf")
    q = db.session.query(Complaint).filter(Complaint.org_id == current_user.org_id)
    items = q.order_by(Complaint.submitted_at.desc()).limit(500).all()
    header = ["Ref", "Submitted", "Department", "Category", "Status", "Escalated",
              "SLA deadline", "Resolved at", "Source"]
    rows = [[c.ref, c.submitted_at.strftime("%Y-%m-%d %H:%M"), c.department.name, c.category,
             c.status, "YES" if c.escalated else "no",
             c.sla_deadline_at.strftime("%Y-%m-%d %H:%M"),
             c.resolved_at.strftime("%Y-%m-%d %H:%M") if c.resolved_at else "", c.source]
            for c in items]
    if fmt == "csv":
        return _csv_response(header, rows, "complaints-report.csv")
    org = _org()
    esc = len([c for c in items if c.escalated])
    notes = [f"Total complaints: {len(items)}", f"Escalated: {esc}",
             f"Open: {len([c for c in items if c.status in ('NEW','ACKNOWLEDGED','IN_PROGRESS','ESCALATED')])}"]
    path = "reports/" + f"complaints-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Complaint Report", now_naive().strftime("%d %B %Y"),
                             header, rows, path, notes=notes, verify_code=code)
    _archive_pdf("complaints", "Complaint Report", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


@bp.get("/escalations")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR")
def escalations_report():
    fmt = request.args.get("format", "csv")
    items = (db.session.query(Complaint)
             .filter(Complaint.org_id == current_user.org_id, Complaint.escalated.is_(True))
             .order_by(Complaint.escalated_at.desc()).all())
    header = ["Ref", "Department", "Category", "Submitted", "SLA deadline", "Escalated at", "Status"]
    rows = [[c.ref, c.department.name, c.category, c.submitted_at.strftime("%Y-%m-%d %H:%M"),
             c.sla_deadline_at.strftime("%Y-%m-%d %H:%M"),
             c.escalated_at.strftime("%Y-%m-%d %H:%M") if c.escalated_at else "", c.status]
            for c in items]
    if fmt == "csv":
        return _csv_response(header, rows, "escalation-report.csv")
    org = _org()
    path = "reports/" + f"escalations-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Escalation Report", now_naive().strftime("%d %B %Y"),
                             header, rows, path, verify_code=code)
    _archive_pdf("escalation", "Escalation Report", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


# ------------------------------------------------------------------ corrective actions
@bp.get("/corrective-actions")
@require_role(*MGR)
def ca_report():
    fmt = request.args.get("format", "csv")
    items = (db.session.query(CorrectiveAction)
             .filter(CorrectiveAction.org_id == current_user.org_id)
             .order_by(CorrectiveAction.deadline).all())
    header = ["Finding", "Required action", "Owner", "Deadline", "Status", "Completed at"]
    rows = [[ca.finding, ca.action_required, ca.owner.name, ca.deadline.isoformat(),
             ca.status, ca.completed_at.strftime("%Y-%m-%d") if ca.completed_at else ""]
            for ca in items]
    if fmt == "csv":
        return _csv_response(header, rows, "corrective-actions.csv")
    org = _org()
    path = "reports/" + f"ca-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Corrective Action Report", now_naive().strftime("%d %B %Y"),
                             header, rows, path, verify_code=code)
    _archive_pdf("ca", "Corrective Action Report", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


# ------------------------------------------------------------------ compliance
@bp.get("/compliance")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR")
def compliance_report():
    """Admin Manager inspection compliance: roster days vs submitted inspections."""
    days = min(int(request.args.get("days", type=int) or 30), 365)
    end = now_naive().date()
    start = end - timedelta(days=days - 1)
    roster = (db.session.query(DutyRoster)
              .filter(DutyRoster.org_id == current_user.org_id, DutyRoster.duty_date >= start,
                      DutyRoster.duty_date <= end).all())
    submitted = {(i.duty_date, i.inspector_id) for i in
                 db.session.query(Inspection).filter(
                     Inspection.org_id == current_user.org_id, Inspection.status == "SUBMITTED",
                     Inspection.duty_date >= start).all()}
    header = ["Date", "Admin Manager on duty", "Inspection submitted", "Ref"]
    rows, done = [], 0
    by_date = {}
    for i in db.session.query(Inspection).filter(
            Inspection.org_id == current_user.org_id, Inspection.status == "SUBMITTED",
            Inspection.duty_date >= start).all():
        by_date.setdefault(i.duty_date, i)
    for r in sorted(roster, key=lambda x: x.duty_date):
        ok = (r.duty_date, r.user_id) in submitted or r.duty_date in by_date
        done += 1 if ok else 0
        rows.append([r.duty_date.isoformat(), r.user.name, "YES" if ok else "MISSED",
                     by_date[r.duty_date].ref if r.duty_date in by_date else ""])
    fmt = request.args.get("format", "csv")
    if fmt == "csv":
        return _csv_response(header, rows, "am-compliance.csv")
    org = _org()
    rate = round(100 * done / len(roster)) if roster else 0
    path = "reports/" + f"compliance-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Admin Manager Compliance Report", f"{start} — {end}",
                             header, rows, path,
                             notes=[f"Compliance rate: {rate}% ({done}/{len(roster)} duty days)"],
                             verify_code=code)
    _archive_pdf("compliance", "AM Compliance Report", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


# ------------------------------------------------------------------ referrals (§14)
@bp.get("/referrals")
@require_role("SUPER_ADMIN", "MD_CEO", "DMD", "DCST", "APEX_NURSE", "HEAD_ADMIN_HR", "ADMIN_MANAGER")
def referrals_report():
    from .. import referrals as refeng
    fmt = request.args.get("format", "csv")
    stats = refeng.analytics(current_user.org_id, days=365)
    header = ["Code", "Kind", "Source", "Label", "Active", "Created",
              "Clicks", "Bookings", "Feedback", "Queue"]
    rows = []
    for row in stats["rows"]:
        r = row["referral"]
        rows.append([
            r.code, r.kind, r.source, r.note or "",
            "yes" if r.active else "no",
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            row["clicks"], row["books"], row["feedback"], row["queue"],
        ])
    if fmt == "csv":
        return _csv_response(header, rows, "referrals-report.csv")
    org = _org()
    notes = [
        f"Share-links issued: {stats['codes']} ({stats['active']} active)",
        f"Clicks (all time in this export window): {stats['clicks']}",
        f"Bookings attributed to a share-link: {stats['books']}",
        f"Conversion rate: {stats['conversion']}%",
        f"Repeat visits (same phone booked again): {stats['repeats']}",
        "No prizes or incentives are offered — this is attribution only.",
    ]
    path = "reports/" + f"referrals-{new_code(4)}.pdf"
    code = new_code(10)
    storage.build_summary(org, "Referral & Repeat-Visit Report",
                             now_naive().strftime("%d %B %Y"),
                             header, rows, path, notes=notes, verify_code=code)
    _archive_pdf("referrals", "Referral Report", path, code)
    db.session.commit()
    return storage.send(path, as_attachment=True, mimetype="application/pdf")


# ------------------------------------------------------------------ archive
@bp.get("/archive/<int:rid>/download")
@require_role(*MGR)
def archive_download(rid: int):
    rf = db.session.get(ReportFile, rid)
    if not rf or rf.org_id != current_user.org_id or not storage.exists(rf.path):
        abort(404)
    audit("REPORT_DOWNLOADED", "report", rf.id, {"title": rf.title})
    db.session.commit()
    return storage.send(rf.path, as_attachment=True, mimetype="application/pdf")
