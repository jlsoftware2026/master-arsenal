"""PDF composers for completed UTC market-day opening and closing reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from .charts import MarketChart
from .pdf import data_table, key_value_table, paragraph, report_styles, section_heading, write_pdf_atomic
from .qa import inspect_pdf_artifact

REQUIRED_SYMBOLS = ("BTCUSDT", "ETHUSDT")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must include a UTC timezone")
    return parsed.astimezone(timezone.utc)


def _text(value: Any) -> str:
    if value is None:
        return "Not supplied"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(_text(item) for item in value) if value else "None supplied"
    return str(value)


def _validate(report: dict[str, Any]):
    if not isinstance(report, dict):
        raise ValueError("Report input must be an object")
    required = {"session_start_utc", "session_end_utc", "generated_at_utc", "symbols"}
    missing = required - set(report)
    if missing:
        raise ValueError(f"Missing required report fields: {sorted(missing)}")
    start = _utc(report["session_start_utc"], "session_start_utc")
    end = _utc(report["session_end_utc"], "session_end_utc")
    generated = _utc(report["generated_at_utc"], "generated_at_utc")
    if start.hour or start.minute or start.second or start.microsecond:
        raise ValueError("Completed market-day session must begin at 00:00 UTC")
    if end != start + timedelta(days=1):
        raise ValueError("Completed market-day session must cover exactly one UTC day")
    if generated < end:
        raise ValueError("generated_at_utc cannot precede the completed session end")
    symbols = report["symbols"]
    if not isinstance(symbols, dict):
        raise ValueError("symbols must be an object keyed by symbol")
    absent = [symbol for symbol in REQUIRED_SYMBOLS if symbol not in symbols]
    if absent:
        raise ValueError(f"Mandatory symbols missing: {', '.join(absent)}")
    for symbol in REQUIRED_SYMBOLS:
        item = symbols[symbol]
        if not isinstance(item, dict):
            raise ValueError(f"{symbol} report data must be an object")
        candles = item.get("candles", [])
        if not isinstance(candles, list):
            raise ValueError(f"{symbol}.candles must be a list")
        previous = None
        for index, candle in enumerate(candles):
            if not isinstance(candle, dict):
                raise ValueError(f"{symbol}.candles[{index}] must be an object")
            opened = _utc(candle.get("open_time"), f"{symbol}.candles[{index}].open_time")
            closed = _utc(candle.get("close_time"), f"{symbol}.candles[{index}].close_time")
            if opened < start or opened >= end or closed < opened or closed >= end:
                raise ValueError(f"{symbol}.candles[{index}] is outside the completed session")
            if previous is not None and opened <= previous:
                raise ValueError(f"{symbol} candles must be strictly ordered and unique")
            previous = opened
    return start, end, generated


def _source_rows(items: Any) -> list[list[str]]:
    if not isinstance(items, list):
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append([
            _text(item.get("title", "Untitled source")),
            _text(item.get("publisher", item.get("source", "Not supplied"))),
            _text(item.get("published_at_utc", "Not supplied")),
            _text(item.get("url", "URL not supplied")),
            _text(item.get("relevance", item.get("summary", "No relevance note supplied"))),
        ])
    return rows


def _build_session_pdf(report: dict[str, Any], output_directory: Path | str, kind: str) -> Path:
    start, end, generated = _validate(report)
    if kind not in {"opening", "closing"}:
        raise ValueError("kind must be 'opening' or 'closing'")
    date_text = start.strftime("%Y-%m-%d")
    filename = ("apertura-mercado_" if kind == "opening" else "cierre-mercado_") + date_text + ".pdf"
    title = "Market Opening Report" if kind == "opening" else "Market Closing Report"
    styles = report_styles()
    story = [
        Paragraph(title, styles["title"]),
        Paragraph("Completed UTC market-day analysis for BTCUSDT and ETHUSDT", styles["subtitle"]),
        key_value_table([
            ("Session", f"{start.isoformat().replace('+00:00', 'Z')} to {end.isoformat().replace('+00:00', 'Z')}"),
            ("Generated at UTC", generated.isoformat().replace("+00:00", "Z")),
            ("Primary source", report.get("source", "Not specified")),
            ("Market", report.get("market", "Not specified")),
            ("Interval", report.get("interval", "Not specified")),
            ("Data status", report.get("data_status", "Not independently certified")),
            ("Report perspective", "Pre-session context from the prior completed day" if kind == "opening"
             else "Observed results from the just-completed day"),
        ], styles),
        Spacer(1, 4 * mm),
        section_heading("Executive summary", styles),
        paragraph(report.get("executive_summary", "No executive summary was supplied."), styles["body"]),
    ]
    for symbol in REQUIRED_SYMBOLS:
        item = report["symbols"][symbol]
        story.extend([
            section_heading(symbol, styles),
            key_value_table([
                ("Candles in session", item.get("candle_count", len(item.get("candles", [])))),
                ("First open UTC", item.get("first_open_time_utc", "Not supplied")),
                ("Last close UTC", item.get("last_close_time_utc", "Not supplied")),
                ("Price performance", _text(item.get("performance"))),
                ("24h ticker", _text(item.get("ticker_24h"))),
                ("Technical indicators", _text(item.get("indicators"))),
                ("Derivatives context", _text(item.get("derivatives"))),
            ], styles),
        ])
        candles = item.get("candles") or []
        if candles:
            labels = [str(c.get("open_time", ""))[11:16] for c in candles]
            closes = [c["close"] for c in candles]
            volumes = [c["volume"] for c in candles]
            story.extend([
                MarketChart(f"{symbol} close price — session only", closes, labels, "line"),
                Spacer(1, 2 * mm),
                MarketChart(f"{symbol} base-asset volume — session only", volumes, labels, "bar"),
            ])
    for heading, key in (
        ("Market structure and technical interpretation", "technical_analysis"),
        ("Bullish / long scenario", "bullish_scenario"),
        ("Bearish / short scenario", "bearish_scenario"),
        ("Assumptions and invalidation levels", "assumptions_and_invalidation"),
        ("Risk assessment", "risks"),
        ("Macroeconomic context", "macro_context"),
        ("Relevant market news", "news"),
        ("Data limitations", "limitations"),
        ("Methodology", "methodology"),
    ):
        value = report.get(key)
        if value is None:
            continue
        story.extend([section_heading(heading, styles), paragraph(_text(value), styles["body"])])
    for heading, key in (("Macroeconomic source register", "macro_sources"),
                         ("News source register", "news_sources")):
        rows = _source_rows(report.get(key))
        if rows:
            story.extend([
                section_heading(heading, styles),
                data_table(["Title", "Publisher", "Published UTC", "Source URL", "Relevance"],
                           rows, styles, widths=[32*mm, 22*mm, 24*mm, 42*mm, 45*mm]),
            ])
    provenance = report.get("provenance")
    if provenance:
        story.extend([section_heading("Data provenance", styles), paragraph(_text(provenance), styles["body"])])
    story.extend([
        section_heading("Important notice", styles),
        paragraph(
            "This report is informational and is not investment advice. Market scenarios are conditional, "
            "uncertain interpretations rather than guarantees. Verify source data and risk independently.",
            styles["small"],
        ),
    ])
    destination = Path(output_directory) / filename
    written = write_pdf_atomic(destination, story, title)
    try:
        inspect_pdf_artifact(written)
    except Exception:
        written.unlink(missing_ok=True)
        raise
    return written


def build_opening_report_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Build a PDF opening report for a previously completed UTC market day."""
    return _build_session_pdf(report, output_directory, "opening")


def build_closing_report_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Build a PDF closing report for a just-completed UTC market day."""
    return _build_session_pdf(report, output_directory, "closing")
