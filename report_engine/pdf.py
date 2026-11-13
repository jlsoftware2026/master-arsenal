"""Shared ReportLab rendering primitives and atomic PDF artifact validation."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)


INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")
ACCENT = colors.HexColor("#1D4ED8")
PALE = colors.HexColor("#EFF6FF")
GRID = colors.HexColor("#CBD5E1")


def report_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("MA_Title", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=21, leading=26, textColor=INK, alignment=TA_LEFT,
                                spaceAfter=5 * mm),
        "subtitle": ParagraphStyle("MA_Subtitle", parent=base["Normal"], fontSize=9,
                                   leading=13, textColor=MUTED, spaceAfter=5 * mm),
        "h1": ParagraphStyle("MA_H1", parent=base["Heading1"], fontSize=14, leading=18,
                             textColor=INK, spaceBefore=5 * mm, spaceAfter=2 * mm),
        "h2": ParagraphStyle("MA_H2", parent=base["Heading2"], fontSize=10, leading=13,
                             textColor=ACCENT, spaceBefore=3 * mm, spaceAfter=1.5 * mm),
        "body": ParagraphStyle("MA_Body", parent=base["BodyText"], fontSize=8.5,
                               leading=12, textColor=INK, spaceAfter=2 * mm),
        "small": ParagraphStyle("MA_Small", parent=base["BodyText"], fontSize=7,
                                leading=9, textColor=MUTED),
        "cell": ParagraphStyle("MA_Cell", parent=base["BodyText"], fontSize=7.2,
                               leading=9, textColor=INK),
        "cell_header": ParagraphStyle("MA_CellHeader", parent=base["BodyText"],
                                      fontName="Helvetica-Bold", fontSize=7.2,
                                      leading=9, textColor=colors.white),
        "center": ParagraphStyle("MA_Center", parent=base["BodyText"], fontSize=8,
                                 leading=11, alignment=TA_CENTER, textColor=INK),
    }


def paragraph(text: object, style):
    from xml.sax.saxutils import escape
    return Paragraph(escape(str(text)), style)


def section_heading(title: str, styles):
    return Paragraph(title, styles["h1"])


def key_value_table(rows: Iterable[tuple[str, object]], styles, col_widths=None):
    data = [[paragraph(k, styles["cell_header"]), paragraph(v, styles["cell"])] for k, v in rows]
    table = Table(data, colWidths=col_widths or [42 * mm, 125 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), ACCENT),
        ("BACKGROUND", (1, 0), (1, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def data_table(headers: list[str], rows: list[list[object]], styles, widths=None):
    data = [[paragraph(x, styles["cell_header"]) for x in headers]]
    data.extend([[paragraph(x, styles["cell"]) for x in row] for row in rows])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


class ArsenalDocTemplate(BaseDocTemplate):
    def __init__(self, filename, title, author="MASTER ARSENAL"):
        super().__init__(str(filename), pagesize=A4, rightMargin=18 * mm,
                         leftMargin=18 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
                         title=title, author=author, subject="MASTER ARSENAL market report")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=self._decorate)])

    def _decorate(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, height - 13 * mm, width - 18 * mm, height - 13 * mm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(INK)
        canvas.drawString(18 * mm, height - 10 * mm, "MASTER ARSENAL")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()


def write_pdf_atomic(destination: Path, story, title: str) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=".tmp",
                                      dir=destination.parent)
    os.close(fd)
    try:
        doc = ArsenalDocTemplate(temporary, title)
        doc.build(story)
        payload = Path(temporary).read_bytes()
        if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-2048:]:
            raise ValueError("Generated artifact failed basic PDF integrity checks")
        if len(payload) < 512:
            raise ValueError("Generated PDF is unexpectedly small")
        with open(temporary, "rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        return destination
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
