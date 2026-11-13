"""Intraday snapshot report composer and PDF output contract."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer

from .pdf import (
    data_table, key_value_table, paragraph, report_styles, section_heading,
    write_pdf_atomic,
)

REQUIRED_SYMBOLS = ("BTCUSDT", "ETHUSDT")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC string") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"{field} must include a UTC timezone")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _display(value: Any) -> str:
    if value is None:
        return "Insufficient data / unavailable"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_display(v)}" for k, v in value.items())
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    return str(value)


def _metric_rows(indicators: dict[str, Any]) -> list[list[str]]:
    keys = ("ema_20", "ema_50", "ema_200", "rsi_14", "macd", "atr_14",
            "bollinger_20", "volume_sma_20")
    labels = ("EMA 20", "EMA 50", "EMA 200", "RSI 14", "MACD", "ATR 14",
              "Bollinger 20", "Volume SMA 20")
    return [[label, _display(indicators.get(key))] for key, label in zip(keys, labels)]


def _validate_input(report: dict[str, Any]):
    if not isinstance(report, dict):
        raise ValueError("Report input must be an object")
    required = {"window_start_utc", "cutoff_utc", "generated_at_utc", "symbols"}
    missing = required - set(report)
    if missing:
        raise ValueError(f"Missing required report fields: {sorted(missing)}")
    start = _utc(report["window_start_utc"], "window_start_utc")
    cutoff = _utc(report["cutoff_utc"], "cutoff_utc")
    generated = _utc(report["generated_at_utc"], "generated_at_utc")
    if start.hour or start.minute or start.second or start.microsecond:
        raise ValueError("Intraday report window must begin at 00:00 UTC")
    if start.date() != cutoff.date() or cutoff <= start:
        raise ValueError("cutoff_utc must be later than 00:00 UTC on the same UTC date")
    if generated < cutoff:
        raise ValueError("generated_at_utc cannot precede the report cutoff")
    symbols = report["symbols"]
    if not isinstance(symbols, dict):
        raise ValueError("symbols must be an object keyed by symbol")
    absent = [symbol for symbol in REQUIRED_SYMBOLS if symbol not in symbols]
    if absent:
        raise ValueError(f"Mandatory symbols missing: {', '.join(absent)}")
    for symbol in REQUIRED_SYMBOLS:
        if not isinstance(symbols[symbol], dict):
            raise ValueError(f"{symbol} report data must be an object")
    return start, cutoff, generated


def build_intraday_snapshot_pdf(report: dict[str, Any], output_directory: Path | str) -> Path:
    """Build and validate an intraday PDF from already-acquired, structured evidence.

    This function does not fetch market data or invent analysis. Scenario, news, and
    macro sections are rendered only when supplied by the upstream report composer.
    """
    start, cutoff, generated = _validate_input(report)
    date_text = cutoff.strftime("%Y-%m-%d")
    time_text = cutoff.strftime("%H-%M")
    destination = Path(output_directory) / f"snapshot-mercado-{date_text}_{time_text}.pdf"
    styles = report_styles()
    story = [
        Paragraph("Intraday Market Snapshot", styles["title"]),
        Paragraph("UTC-day market review with source and data-quality disclosures",
                  styles["subtitle"]),
        key_value_table([
            ("Reporting window", f"{_iso_utc(start)} to {_iso_utc(cutoff)} (cutoff exclusive)"),
            ("Generated at UTC", _iso_utc(generated)),
            ("Primary source", report.get("source", "Not specified")),
            ("Market", report.get("market", "Not specified")),
            ("Interval", report.get("interval", "Not specified")),
            ("Data status", report.get("data_status", "Not independently certified")),
        ], styles),
        Spacer(1, 4 * mm),
        section_heading("Executive summary", styles),
        paragraph(report.get("executive_summary", "No executive summary was supplied."), styles["body"]),
    ]

    for symbol in REQUIRED_SYMBOLS:
        item = report["symbols"][symbol]
        indicators = item.get("indicators") or {}
        story.extend([
            section_heading(symbol, styles),
            key_value_table([
                ("Candles", item.get("candle_count", "Not supplied")),
                ("First candle UTC", item.get("first_open_time_utc", "Not supplied")),
                ("Last candle close UTC", item.get("last_close_time_utc", "Not supplied")),
                ("24h ticker", _display(item.get("ticker_24h"))),
                ("Data response", item.get("response_metadata", {}).get("retrieved_at_utc", "Not supplied")),
            ], styles),
            Spacer(1, 2 * mm),
            data_table(["Technical indicator", "Value"], _metric_rows(indicators), styles,
                       widths=[45 * mm, 122 * mm]),
        ])
        issues = item.get("validation") or []
        story.append(Paragraph("Data validation: " + (
            f"{len(issues)} issue(s) reported; inspect source details." if issues
            else "No validation issues supplied; absence of issues is not proof of live completeness."
        ), styles["small"]))
        if issues:
            issue_rows = [[str(x.get("code", "unknown")), str(x.get("severity", "warning")),
                           str(x.get("message", ""))] for x in issues if isinstance(x, dict)]
            if issue_rows:
                story.append(data_table(["Issue", "Severity", "Details"], issue_rows, styles,
                                        widths=[30 * mm, 25 * mm, 112 * mm]))
        story.append(Spacer(1, 3 * mm))

    for section_key, title in (
        ("derivatives_context", "Derivatives context"),
        ("macro_context", "Macroeconomic context"),
        ("news_context", "Relevant news"),
        ("bullish_scenario", "Bullish / long scenario"),
        ("bearish_scenario", "Bearish / short scenario"),
        ("risk_factors", "Risk factors and invalidation"),
        ("methodology_limitations", "Methodology and limitations"),
    ):
        if section_key in report:
            story.extend([section_heading(title, styles),
                          paragraph(_display(report[section_key]), styles["body"])])

    provenance = report.get("provenance") or []
    story.append(section_heading("Source and provenance notes", styles))
    if provenance:
        rows = [[str(x.get("source", "Not specified")),
                 str(x.get("retrieved_at_utc", "Not specified")),
                 str(x.get("note", ""))] for x in provenance if isinstance(x, dict)]
        story.append(data_table(["Source", "Retrieved at UTC", "Note"], rows, styles,
                                widths=[42 * mm, 45 * mm, 80 * mm]))
    else:
        story.append(paragraph(
            "No separate provenance manifest was supplied. Values above retain only the "
            "metadata present in the report input.", styles["body"]))

    story.append(Spacer(1, 4 * mm))
    story.append(paragraph(
        "Disclaimer: This document is an informational market analysis, not investment advice. "
        "Scenarios are conditional and uncertain; they are not guaranteed outcomes.",
        styles["small"]))
    return write_pdf_atomic(destination, story, f"MASTER ARSENAL Intraday Snapshot {date_text}")
