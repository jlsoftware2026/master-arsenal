"""PDF composers for completed UTC market-day opening and closing reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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


def _local_time(value: Any) -> str:
    if not isinstance(value, str):
        return "Not supplied"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "Invalid timestamp"
        return parsed.astimezone(ZoneInfo("America/Santo_Domingo")).isoformat()
    except ValueError:
        return "Invalid timestamp"


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
    required = {"session_start_utc", "session_end_utc", "generated_at_utc", "symbols",
                "report_timezone", "report_date_local", "window_start_local", "cutoff_local", "window_semantics", "is_partial"}
    missing = required - set(report)
    if missing:
        raise ValueError(f"Missing required report fields: {sorted(missing)}")
    start = _utc(report["session_start_utc"], "session_start_utc")
    end = _utc(report["session_end_utc"], "session_end_utc")
    generated = _utc(report["generated_at_utc"], "generated_at_utc")
    if report["report_timezone"] != "America/Santo_Domingo":
        raise ValueError("Report timezone must be America/Santo_Domingo")
    if report["window_semantics"] != "[start, cutoff)" or not isinstance(report["is_partial"], bool):
        raise ValueError("Report must declare half-open window semantics and a boolean partial-day status")
    try:
        local_start = datetime.fromisoformat(report["window_start_local"])
        local_end = datetime.fromisoformat(report["cutoff_local"])
        report_date = datetime.fromisoformat(report["report_date_local"]).date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Local report date and window timestamps must be valid ISO-8601 values") from exc
    if local_start.tzinfo is None or local_end.tzinfo is None:
        raise ValueError("Local report window timestamps must include their UTC offsets")
    if local_start.astimezone(timezone.utc) != start or local_end.astimezone(timezone.utc) != end:
        raise ValueError("Local and UTC report window boundaries do not match")
    expected_local_start = start.astimezone(ZoneInfo("America/Santo_Domingo"))
    expected_local_end = end.astimezone(ZoneInfo("America/Santo_Domingo"))
    if (local_start.replace(tzinfo=None) != expected_local_start.replace(tzinfo=None)
            or local_start.utcoffset() != expected_local_start.utcoffset()
            or local_end.replace(tzinfo=None) != expected_local_end.replace(tzinfo=None)
            or local_end.utcoffset() != expected_local_end.utcoffset()):
        raise ValueError("Local timestamps do not match the IANA America/Santo_Domingo rules")
    if local_start.date() != report_date:
        raise ValueError("Local report start must match report_date_local")
    if report.get("is_partial") is True:
        if local_end.date() != report_date:
            raise ValueError("Partial local report cutoff must remain on report_date_local")
    elif local_end.date() != report_date + timedelta(days=1) or local_end.time().isoformat() != "00:00:00":
        raise ValueError("Completed local report must end at the next local midnight")
    if end <= start:
        raise ValueError("Report window cutoff must be later than its start")
    if generated < end:
        raise ValueError("generated_at_utc cannot precede the report cutoff")
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
                raise ValueError(f"{symbol}.candles[{index}] is outside the report window")
            if previous is not None and opened <= previous:
                raise ValueError(f"{symbol} candles must be strictly ordered and unique")
            previous = opened
    return start, end, generated


def _indicator_rows(indicators: Any) -> list[list[str]]:
    indicators = indicators if isinstance(indicators, dict) else {}
    definitions = (
        ("ema_20", "EMA 20"), ("ema_50", "EMA 50"), ("ema_200", "EMA 200"),
        ("rsi_14", "RSI 14"), ("macd", "MACD"), ("atr_14", "ATR 14"),
        ("bollinger_20", "Bollinger 20"), ("volume_sma_20", "Volume SMA 20"),
    )
    return [[label, _text(indicators.get(key))] for key, label in definitions]


def _ticker_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return "Not supplied"
    if value.get("status") != "ok":
        return f"Unavailable: {value.get('error', 'No endpoint detail')}"
    data = value.get("data")
    if not isinstance(data, dict):
        return "Ticker data unavailable"
    keys = ("lastPrice", "priceChangePercent", "highPrice", "lowPrice", "volume", "quoteVolume")
    return "; ".join(f"{key}: {data[key]}" for key in keys if key in data) or "No selected ticker fields supplied"


def _derivatives_summary(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "Not supplied"
    rows = []
    display_keys = ("lastFundingRate", "markPrice", "indexPrice", "openInterest",
                    "sumOpenInterest", "longShortRatio", "basis")
    for name, result in value.items():
        if not isinstance(result, dict):
            rows.append(f"{name}: unavailable")
            continue
        status = result.get("status", "not verified")
        data = result.get("data")
        if isinstance(data, list):
            data = data[-1] if data else None
        selected = []
        if isinstance(data, dict):
            selected = [f"{key}={data[key]}" for key in display_keys if key in data]
        suffix = ", ".join(selected) if selected else "latest value not available"
        rows.append(f"{name}: {status} ({suffix})")
    return "; ".join(rows)

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
            _text(item.get("summary") or item.get("relevance", "No summary or relevance note supplied")),
        ])
    return rows


def _build_session_pdf(report: dict[str, Any], output_directory: Path | str, kind: str) -> Path:
    start, end, generated = _validate(report)
    if kind not in {"opening", "closing"}:
        raise ValueError("kind must be 'opening' or 'closing'")
    if kind == "opening" and report.get("is_partial") is True:
        raise ValueError("Opening reports must use the previous completed local calendar day")
    date_text = report["report_date_local"]
    filename = ("apertura-mercado_" if kind == "opening" else "cierre-mercado_") + date_text + ".pdf"
    title = "Market Opening Report" if kind == "opening" else "Market Closing Report"
    styles = report_styles()
    story = [
        Paragraph(title, styles["title"]),
        Paragraph("America/Santo_Domingo local-calendar analysis for BTCUSDT and ETHUSDT", styles["subtitle"]),
        key_value_table([
            ("Local reporting window", f"{report['window_start_local']} to {report['cutoff_local']} ({report['report_timezone']})"),
            ("UTC evidence window", f"{start.isoformat().replace('+00:00', 'Z')} to {end.isoformat().replace('+00:00', 'Z')} (cutoff exclusive)"),
            ("Window status", "PARTIAL LOCAL DAY" if report.get("is_partial") else "COMPLETED LOCAL DAY"),
            ("Generated at UTC", generated.isoformat().replace("+00:00", "Z")),
            ("Primary source", report.get("source", "Not specified")),
            ("Market", report.get("market", "Not specified")),
            ("Interval", report.get("interval", "Not specified")),
            ("Data status", report.get("data_status", "Not independently certified")),
            ("Binance account analytics", report.get("binance_account_data_status", "unavailable")),
            ("U.S. equity-market coverage", report.get("us_equity_market_data_status", "not_integrated")),
            ("Opening forecast scorecard", report.get("opening_forecast_scorecard_status", "not_available")),
            ("Activation timing", report.get("activation_timing_status", "not_automated")),
            ("Report perspective", "Previous Dominican local calendar day for the upcoming U.S. session" if kind == "opening"
             else ("Accumulated Dominican local day through the exact stated cutoff" if report.get("is_partial")
                   else "Completed Dominican local calendar day")),
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
                ("First open local", _local_time(item.get("first_open_time_utc"))),
                ("First open UTC", item.get("first_open_time_utc", "Not supplied")),
                ("Last close local", _local_time(item.get("last_close_time_utc"))),
                ("Last close UTC", item.get("last_close_time_utc", "Not supplied")),
                ("Price performance", _text(item.get("performance"))),
                ("24h ticker", _ticker_summary(item.get("ticker_24h"))),
                ("Indicator warm-up candles", (item.get("indicator_history") or {}).get("candle_count", "Not supplied")),
                ("Candle pagination", "complete" if (item.get("pagination") or {}).get("complete") else "not verified"),
                ("Derivatives context", _derivatives_summary(item.get("derivatives"))),
            ], styles),
            data_table(["Technical indicator", "Value"], _indicator_rows(item.get("indicators")), styles,
                       widths=[45*mm, 120*mm]),
        ])
        issues = item.get("validation") or []
        if issues:
            issue_rows = [[
                str(issue.get("code", "unknown")),
                str(issue.get("severity", "warning")),
                str(issue.get("message", "")),
            ] for issue in issues if isinstance(issue, dict)]
            if issue_rows:
                story.extend([
                    section_heading(f"{symbol} data validation issues", styles),
                    data_table(["Issue", "Severity", "Details"], issue_rows, styles,
                               widths=[28*mm, 22*mm, 115*mm]),
                ])
        else:
            story.append(paragraph(
                f"{symbol}: no validation issues were supplied; this is not proof of live data completeness.",
                styles["small"],
            ))
        candles = item.get("candles") or []
        if candles:
            labels = [datetime.fromisoformat(str(c.get("open_time", "")).replace("Z", "+00:00")).astimezone(ZoneInfo("America/Santo_Domingo")).strftime("%H:%M") for c in candles]
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
    context_sources = report.get("context_sources") or []
    if context_sources:
        context_rows = [[
            str(item.get("publisher", "Unknown")),
            str(item.get("kind", "Unknown")),
            str(item.get("status", "not verified")),
            str(item.get("retrieved_at_utc", "Not supplied")),
            str(item.get("matching_items", item.get("error", "Not supplied"))),
            str(item.get("feed_url", "URL not supplied")),
        ] for item in context_sources if isinstance(item, dict)]
        if context_rows:
            story.extend([
                section_heading("Macro/news feed retrieval register", styles),
                data_table(["Publisher", "Type", "Status", "Retrieved UTC", "Items / error", "Feed URL"],
                           context_rows, styles, widths=[25*mm, 15*mm, 18*mm, 30*mm, 40*mm, 37*mm]),
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
