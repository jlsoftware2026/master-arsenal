"""Internal, source-linked evidence manifests and independent market-data checks."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from binance_data_engine.engine import analyze_candles
from binance_data_engine.models import Candle
from binance_data_engine.validation import interval_milliseconds
from binance_data_engine.validation import validate_candles

EVIDENCE_SCHEMA = "ma.report-evidence/v1"
CORE_SYMBOLS = ("BTCUSDT", "ETHUSDT")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_evidence_manifest(
    report: dict[str, Any],
    report_type: str,
    pdf_path: str | Path,
    manifest_directory: str | Path,
) -> Path:
    """Atomically persist internal raw evidence outside the user-facing PDF folders."""
    if report_type not in {"opening", "closing", "intraday"}:
        raise ValueError("report_type must be opening, closing, or intraday")
    pdf = Path(pdf_path).resolve(strict=True)
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError("pdf_path must reference an existing PDF artifact")
    payload = {
        "schema": EVIDENCE_SCHEMA,
        "report_type": report_type,
        "pdf_filename": pdf.name,
        "pdf_sha256": _sha256(pdf),
        "manifest_generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "report": report,
    }
    destination_directory = Path(manifest_directory)
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{pdf.stem}.evidence.json"
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=".tmp",
                                     dir=destination_directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination


def _strict_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO-8601 UTC string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must explicitly use UTC")
    return parsed.astimezone(timezone.utc)


def _make_candles(rows: Any, symbol: str, interval: str) -> list[Candle]:
    if not isinstance(rows, list):
        raise ValueError(f"{symbol}: candle evidence must be a list")
    candles = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{symbol}: candle {index} must be an object")
        if row.get("symbol") != symbol or row.get("interval") != interval:
            raise ValueError(f"{symbol}: candle {index} symbol or interval does not match manifest.")
        candles.append(Candle(
            symbol=symbol, interval=interval,
            open_time=_strict_utc(row["open_time"]),
            close_time=_strict_utc(row["close_time"]),
            open=Decimal(str(row["open"])), high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])), close=Decimal(str(row["close"])),
            volume=Decimal(str(row["volume"])),
        ))
    return candles


def _same_value(expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected is actual
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(
            _same_value(expected[key], actual[key]) for key in expected
        )
    if isinstance(expected, (int, float, Decimal)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float, Decimal)) or isinstance(actual, bool):
            return False
        return math.isclose(float(expected), float(actual), rel_tol=1e-9, abs_tol=1e-10)
    return expected == actual


def audit_evidence_manifest(path: str | Path, workspace_root: str | Path) -> dict[str, Any]:
    """Revalidate UTC windows, candle completeness, and indicator calculations."""
    manifest_path = Path(path).resolve(strict=True)
    root = Path(workspace_root).resolve()
    if not manifest_path.is_relative_to(root):
        raise ValueError("Evidence manifest escapes the workspace")
    if manifest_path.stat().st_size > 50_000_000:
        raise ValueError("Evidence manifest exceeds the 50 MB safety limit")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    findings: list[str] = []
    if payload.get("schema") != EVIDENCE_SCHEMA:
        findings.append("Unsupported evidence manifest schema.")
    report_type = payload.get("report_type")
    if report_type not in {"opening", "closing", "intraday"}:
        findings.append("Unknown report type.")
    report = payload.get("report")
    if not isinstance(report, dict):
        return {"manifest": manifest_path.name, "status": "failed",
                "findings": findings + ["Missing report evidence object."]}
    pdf_path = (root / "reports" / {
        "opening": "opening", "closing": "closing", "intraday": "intraday"
    }.get(report_type, "invalid") / str(payload.get("pdf_filename", ""))).resolve()
    if not pdf_path.is_relative_to(root) or not pdf_path.is_file():
        findings.append("Linked PDF artifact is missing or escapes its fixed report directory.")
    elif _sha256(pdf_path) != payload.get("pdf_sha256"):
        findings.append("Linked PDF SHA-256 does not match the evidence manifest.")

    start_key, end_key = (
        ("window_start_utc", "cutoff_utc") if report_type == "intraday"
        else ("session_start_utc", "session_end_utc")
    )
    try:
        start = _strict_utc(report[start_key])
        end = _strict_utc(report[end_key])
        if start.tzinfo is None or end <= start:
            raise ValueError("Invalid report time window.")
        if start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0):
            raise ValueError("Report window is not UTC.")
        if report_type != "intraday" and end != start + timedelta(days=1):
            findings.append("Completed session is not exactly 24 hours.")
        if report_type == "intraday" and start.date() != end.date():
            findings.append("Intraday window crosses a UTC date boundary.")
        generated_at = _strict_utc(report.get("generated_at_utc"))
        if generated_at < end:
            findings.append("Report generation timestamp precedes the exclusive window end.")
        if report.get("source") != "Binance public REST API":
            findings.append("Report source is not identified as Binance public REST API.")
        if report.get("read_only") is not True:
            findings.append("Report is not explicitly marked read-only.")
    except Exception as exc:
        return {"manifest": manifest_path.name, "status": "failed",
                "findings": findings + [f"Invalid report window: {type(exc).__name__}: {exc}"]}

    symbols = report.get("symbols")
    if not isinstance(symbols, dict):
        symbols = {}
    checked = []
    for symbol in CORE_SYMBOLS:
        item = symbols.get(symbol)
        if not isinstance(item, dict):
            findings.append(f"{symbol}: mandatory symbol evidence missing.")
            continue
        try:
            report_candles = _make_candles(item.get("candles"), symbol, report.get("interval", "1h"))
            history_data = item.get("indicator_history") or {}
            history_candles = _make_candles(history_data.get("candles"), symbol, report.get("interval", "1h"))
            if len(report_candles) != item.get("candle_count"):
                findings.append(f"{symbol}: report candle count does not match raw evidence.")
            interval_ms = interval_milliseconds(report.get("interval", "1h"))
            if interval_ms is None:
                findings.append(f"{symbol}: unsupported interval in evidence.")
            else:
                elapsed_ms = int((end - start).total_seconds() * 1000)
                if elapsed_ms % interval_ms:
                    findings.append(f"{symbol}: report window is not aligned to the candle interval.")
                expected_window = elapsed_ms // interval_ms
                if len(report_candles) != expected_window:
                    findings.append(f"{symbol}: report window is missing expected candles.")
                if report_candles and report_candles[0].open_time != start:
                    findings.append(f"{symbol}: first report candle does not start at the declared window start.")
                if report_candles and report_candles[-1].close_time != end - timedelta(milliseconds=1):
                    findings.append(f"{symbol}: final report candle does not close at the exclusive window boundary.")
            expected_history = history_data.get("expected_candle_count",
                                                (report.get("indicator_methodology") or {}).get("lookback_candles"))
            pagination = item.get("pagination") or {}
            if pagination.get("complete") is not True or pagination.get("returned") != len(report_candles):
                findings.append(f"{symbol}: report pagination evidence is incomplete or inconsistent.")
            history_pagination = history_data.get("pagination") or {}
            if history_pagination.get("complete") is not True or history_pagination.get("returned") != len(history_candles):
                findings.append(f"{symbol}: indicator-history pagination evidence is incomplete or inconsistent.")
            if expected_history is not None and len(history_candles) != expected_history:
                findings.append(f"{symbol}: indicator warm-up candle count is incomplete.")
            if not report_candles:
                findings.append(f"{symbol}: report window contains no candles.")
            for candle in report_candles:
                if candle.open_time < start or candle.open_time >= end or candle.close_time >= end:
                    findings.append(f"{symbol}: report candle falls outside the declared UTC window.")
                    break
            if history_candles and report_candles:
                interval_ms = interval_milliseconds(report.get("interval", "1h"))
                if interval_ms is not None and history_candles[-1].close_time + timedelta(milliseconds=1) != report_candles[0].open_time:
                    findings.append(f"{symbol}: indicator warm-up does not join the report window continuously.")
            combined = history_candles + report_candles
            validation = validate_candles(combined, report.get("interval", "1h"))
            errors = [issue for issue in validation if issue.severity == "error"]
            if errors:
                findings.append(f"{symbol}: raw candle validation failed: " +
                                "; ".join(issue.code for issue in errors))
            recalculated = analyze_candles(combined)
            if not _same_value(recalculated, item.get("indicators")):
                findings.append(f"{symbol}: stored indicators do not match independent recalculation.")
            checked.append(symbol)
        except Exception as exc:
            findings.append(f"{symbol}: evidence could not be independently checked: {type(exc).__name__}: {exc}")

    for list_key in ("macro_sources", "news_sources"):
        for source_item in report.get(list_key) or []:
            try:
                published = _strict_utc(source_item.get("published_at_utc"))
                if not (start <= published < end):
                    findings.append(f"{list_key}: publication timestamp falls outside the report window.")
                if not str(source_item.get("url", "")).startswith("https://"):
                    findings.append(f"{list_key}: source item has no HTTPS URL.")
            except Exception:
                findings.append(f"{list_key}: source item has an invalid publication timestamp.")
    context_sources = report.get("context_sources") or []
    for source in context_sources:
        if not isinstance(source, dict):
            findings.append("Malformed macro/news feed provenance record.")
            continue
        url = source.get("feed_url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            findings.append("Macro/news feed record has no HTTPS source URL.")
    return {
        "manifest": manifest_path.name,
        "report_type": report_type,
        "pdf_filename": payload.get("pdf_filename"),
        "symbols_checked": checked,
        "indicator_recalculation": "passed" if not any("indicators do not match" in item for item in findings) else "failed",
        "status": "passed" if not findings else "failed",
        "findings": findings,
    }


def audit_cross_report_consistency(
    manifest_paths: list[str | Path], workspace_root: str | Path
) -> dict[str, Any]:
    """Compare exact OHLCV evidence for matching symbol/interval/open-time keys."""
    root = Path(workspace_root).resolve()
    observed: dict[tuple[str, str, str], tuple[dict[str, Any], str]] = {}
    overlaps = 0
    mismatches = []
    for candidate in manifest_paths:
        manifest_path = Path(candidate).resolve(strict=True)
        if not manifest_path.is_relative_to(root):
            mismatches.append(f"{manifest_path.name}: manifest escaped workspace.")
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            report = payload["report"]
            interval = report["interval"]
            symbols = report["symbols"]
            for symbol in CORE_SYMBOLS:
                for candle in symbols[symbol]["candles"]:
                    key = (symbol, interval, candle["open_time"])
                    values = {field: candle.get(field) for field in
                              ("open", "high", "low", "close", "volume", "close_time")}
                    if key in observed:
                        overlaps += 1
                        previous, previous_file = observed[key]
                        if previous != values:
                            mismatches.append(
                                f"{symbol} {interval} {key[2]} differs between "
                                f"{previous_file} and {manifest_path.name}."
                            )
                    else:
                        observed[key] = (values, manifest_path.name)
        except Exception as exc:
            mismatches.append(f"{manifest_path.name}: could not compare evidence: {type(exc).__name__}: {exc}")
    status = "failed" if mismatches else ("passed" if overlaps else "not_verified")
    return {
        "status": status,
        "overlapping_candles_checked": overlaps,
        "mismatches": mismatches,
        "manifests_compared": len(manifest_paths),
    }
