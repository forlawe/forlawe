"""PDF report generation (ReportLab) — inspection reports and management summaries.

Every PDF carries a verification code + QR code so printed copies can be
authenticated against the digital archive.
"""
from __future__ import annotations

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Image, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import scoring

ACCENT = colors.HexColor("#0e5a8a")
LIGHT = colors.HexColor("#eef4f8")
RED = colors.HexColor("#c0262c")
GREEN = colors.HexColor("#1a7f37")
AMBER = colors.HexColor("#b58900")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontSize=17, textColor=ACCENT,
                                spaceAfter=2, alignment=TA_LEFT),
        "subtitle": ParagraphStyle("st", parent=ss["Normal"], fontSize=10, textColor=colors.HexColor("#44546a")),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, textColor=ACCENT,
                             spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle("s", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#586069")),
        "center": ParagraphStyle("c", parent=ss["Normal"], fontSize=9, alignment=TA_CENTER),
    }


def _qr_image(data: str, size_mm=22):
    try:
        import qrcode
        img = qrcode.make(data, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=size_mm * mm, height=size_mm * mm)
    except Exception:
        return None


def _logo(path: str | None):
    if path and os.path.isabs(path) and os.path.exists(path):
        try:
            return Image(path, width=18 * mm, height=18 * mm)
        except Exception:
            return None
    return None


def rating_color(rating: str):
    if rating == "EXCELLENT":
        return GREEN
    if rating == "GOOD":
        return colors.HexColor("#4d9e3f")
    if rating.startswith("FAIR"):
        return AMBER
    if rating == "POOR":
        return colors.HexColor("#d97706")
    return RED


# =============================================================== inspection PDF
def build_inspection_pdf(org, inspection, scores_by_no: dict, dest_path: str,
                         verify_url: str, corrective_actions: list | None = None) -> str:
    st = _styles()
    doc = SimpleDocTemplate(dest_path, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Inspection Report {inspection.ref}", author=org.name)
    story = []

    # ---- header
    header_cells = []
    logo = _logo(org.logo_path)
    left = [Paragraph(org.name, st["title"]),
            Paragraph("Daily Admin Manager Inspection Report", st["subtitle"])]
    if logo:
        header_cells.append([logo, left])
        ht = Table(header_cells, colWidths=[22 * mm, 140 * mm])
        ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(ht)
    else:
        story += left
    story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=8))

    # ---- meta table
    def place(obj):
        parts = [obj.department.name]
        if inspection.section:
            parts.append(inspection.section.name)
        if inspection.unit:
            parts.append(inspection.unit.name)
        return " › ".join(parts)

    meta = [
        ["Inspection Ref", inspection.ref, "Date", inspection.duty_date.strftime("%A, %d %B %Y")],
        ["Admin Manager", inspection.inspector.name, "Status", inspection.status.title()],
        ["Department / Unit", place(inspection), "Submitted", inspection.submitted_at.strftime("%d %b %Y %H:%M") if inspection.submitted_at else "—"],
        ["Started", inspection.started_at.strftime("%H:%M") if inspection.started_at else "—",
         "GPS", "Captured" if inspection.gps_captured else ("Not captured" if inspection.gps_mode != "disabled" else "Disabled")],
    ]
    mt = Table(meta, colWidths=[32 * mm, 62 * mm, 24 * mm, 56 * mm])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d4de")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(mt)
    story.append(Spacer(1, 8))

    # ---- scores table
    story.append(Paragraph("Evaluation — Five Criteria (1 = Critical … 5 = Excellent)", st["h2"]))
    rows = [["#", "Criterion", "Score", "Rating", "Explanation"]]
    for no in range(1, 6):
        s = scores_by_no.get(no)
        score_val = s.score if s else "—"
        expl = (s.explanation if s and s.explanation else
                ("(mandatory explanation missing)" if s and s.score <= 2 else ""))
        rows.append([str(no), scoring.CRITERIA[no]["title"], str(score_val),
                     scoring.SCORE_LABELS.get(s.score, "") if s else "",
                     Paragraph(expl or "—", st["body"])])
    rows.append(["", "TOTAL", f"{inspection.total_score or '—'} / 25",
                 inspection.rating or "—", f"{inspection.percent or 0}%"])
    t = Table(rows, colWidths=[8 * mm, 46 * mm, 14 * mm, 50 * mm, 56 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d4de")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    # highlight poor scores
    for i, no in enumerate(range(1, 6), start=1):
        s = scores_by_no.get(no)
        if s and s.score <= 2:
            t.setStyle(TableStyle([("TEXTCOLOR", (2, i), (2, i), RED),
                                   ("FONTNAME", (2, i), (2, i), "Helvetica-Bold")]))
    story.append(t)

    # ---- overall rating banner
    story.append(Spacer(1, 6))
    banner = Table([[Paragraph(f"Overall rating: {inspection.rating}", st["title"])]],
                   colWidths=[174 * mm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rating_color(inspection.rating or "")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(banner)

    # ---- findings + corrective actions
    flagged = scoring.flagged_criteria({n: (scores_by_no[n].score if scores_by_no.get(n) else 3) for n in range(1, 6)})
    if flagged:
        story.append(Paragraph("Critical / Poor Findings", st["h2"]))
        for no in flagged:
            s = scores_by_no[no]
            story.append(Paragraph(f"• <b>{scoring.CRITERIA[no]['title']} (score {s.score})</b> — "
                                   f"{s.explanation or 'no explanation provided'}", st["body"]))
    if corrective_actions:
        story.append(Paragraph("Recommended Corrective Actions", st["h2"]))
        for ca in corrective_actions:
            story.append(Paragraph(f"• {ca.action_required} (owner: {ca.owner.name}, "
                                   f"deadline: {ca.deadline.strftime('%d %b %Y')})", st["body"]))

    # ---- Admin Manager's closing comment
    if getattr(inspection, "final_comment", None):
        story.append(Paragraph("Admin Manager's Comment", st["h2"]))
        # escape(): the comment is free text typed by a human and reportlab
        # renders a mini-HTML dialect, so stray < or & would corrupt the PDF.
        from xml.sax.saxutils import escape as _esc
        story.append(Paragraph(_esc(inspection.final_comment), st["body"]))

    # ---- verification footer
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c9d4de")))
    qr = _qr_image(verify_url)
    footer_left = [
        Paragraph("Digital Verification", st["h2"]),
        Paragraph(f"Verification code: <b>{inspection.verify_code}</b>", st["body"]),
        Paragraph("Scan the QR code or visit the verification page to confirm this report "
                  "was generated by the hospital system and has not been altered.", st["small"]),
        Paragraph(f"Generated {datetime.now().strftime('%d %b %Y %H:%M')} • {org.name} • "
                  f"Hospital Admin Manager Suite v1.0", st["small"]),
    ]
    if qr:
        ft = Table([[footer_left, qr]], colWidths=[140 * mm, 28 * mm])
        ft.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(ft)
    else:
        story += footer_left

    doc.build(story)
    return dest_path


# =============================================================== QR poster pack (§43A)
def build_poster_pdf(org, posters: list[dict], dest_path: str) -> str:
    """posters: [{title, subtitle, url, steps:[...]}] — one A4 page each."""
    import io as _io
    import qrcode as _qrcode
    st = _styles()
    doc = SimpleDocTemplate(dest_path, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"{org.name} — QR Posters", author=org.name)
    story = []
    for i, p in enumerate(posters):
        if i > 0:
            from reportlab.platypus import PageBreak
            story.append(PageBreak())
        # header band
        band = Table([[Paragraph(org.name, ParagraphStyle(
            "pb", parent=st["title"], fontSize=16, textColor=colors.white))]],
            colWidths=[182 * mm])
        band.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ]))
        story.append(band)
        story.append(Spacer(1, 12))
        story.append(Paragraph(p["title"], ParagraphStyle("pt", parent=st["title"],
                                                          fontSize=26, alignment=TA_CENTER)))
        story.append(Paragraph(p["subtitle"], ParagraphStyle("ps", parent=st["subtitle"],
                                                             fontSize=12, alignment=TA_CENTER)))
        story.append(Spacer(1, 10))
        # QR
        img = _qrcode.make(p["url"], box_size=14, border=3)
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        qr = Image(buf, width=88 * mm, height=88 * mm)
        qt = Table([[qr]], colWidths=[182 * mm])
        qt.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(qt)
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Or open: <b>{p['url']}</b>", st["center"]))
        story.append(Spacer(1, 12))
        # steps
        step_rows = [[Paragraph(f"<b>{idx + 1}.</b>  {s}", ParagraphStyle(
            "stp", parent=st["body"], fontSize=12, leading=17))] for idx, s in enumerate(p["steps"])]
        steps = Table(step_rows, colWidths=[170 * mm])
        steps.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ]))
        st_wrap = Table([[steps]], colWidths=[182 * mm])
        st_wrap.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(st_wrap)
        story.append(Spacer(1, 16))
        story.append(Paragraph("No account · No app · Works on any phone", st["center"]))
    doc.build(story)
    return dest_path


# =============================================================== generic summary PDF
def build_summary_pdf(org, title: str, subtitle: str, table_header: list[str],
                      table_rows: list[list], dest_path: str, notes: list[str] | None = None,
                      verify_code: str = None) -> str:
    st = _styles()
    doc = SimpleDocTemplate(dest_path, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm, title=title, author=org.name)
    story = [Paragraph(org.name, st["title"]), Paragraph(title, st["subtitle"]),
             Paragraph(subtitle, st["small"]),
             HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=8)]
    if table_rows:
        data = [table_header] + table_rows
        ncols = len(table_header)
        avail = 180 * mm
        widths = [avail / ncols] * ncols
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d4de")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No records for the selected period.", st["body"]))
    if notes:
        story.append(Paragraph("Notes", st["h2"]))
        for n in notes:
            story.append(Paragraph(f"• {n}", st["body"]))
    if verify_code:
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"Verification code: <b>{verify_code}</b>", st["small"]))
    doc.build(story)
    return dest_path
