"""Read-only parser for the common Binance transaction-history CSV export schema.

Only the documented transaction-statement schema is accepted. User IDs and
remarks are never copied into report evidence. Unsupported schemas are
reported explicitly; no account equity or return is inferred from events.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 20_000_000
MAX_TOTAL_BYTES = 100_000_000
MAX_ROWS_PER_FILE = 100_000
MAX_FILES = 100
REQUIRED_HEADERS = {"userid", "utctime", "account", "operation", "coin", "change", "remark"}
EVENT_TYPES = (
    "realized_pnl", "commission", "funding_fee", "deposit", "withdrawal",
    "internal_transfer", "trade_spend", "trade_receive", "interest", "other",
)


def _header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lstrip("\ufeff").lower())


def _timestamp(value: str) -> tuple[datetime, bool]:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("UTC_Time is empty")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assumed_utc = parsed.tzinfo is None
    if assumed_utc:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc), assumed_utc


def _decimal(value: str) -> Decimal:
    raw = (value or "").strip()
    if "," in raw and not re.fullmatch(r"[+-]?\\d{1,3}(,\\d{3})+(\\.\\d+)?", raw):
        raise ValueError("Change uses an unsupported decimal separator")
    try:
        amount = Decimal(raw.replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError("Change is not a valid decimal") from exc
    if not amount.is_finite():
        raise ValueError("Change must be finite")
    return amount


def _event_type(operation: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", (operation or "").lower()).strip()
    if "realized profit" in value or "realized pnl" in value or "realized pnl" in value:
        return "realized_pnl"
    if "funding fee" in value or value == "funding":
        return "funding_fee"
    if "commission" in value or "transaction fee" in value or value == "fee":
        return "commission"
    if value == "deposit" or value.startswith("deposit "):
        return "deposit"
    if value == "withdraw" or value == "withdrawal" or value.startswith("withdraw "):
        return "withdrawal"
    if "transfer" in value:
        return "internal_transfer"
    if value in {"transaction buy", "transaction spend", "buy", "spend"}:
        return "trade_spend"
    if value in {"transaction sold", "transaction revenue", "sell", "revenue"}:
        return "trade_receive"
    if "interest" in value or "reward" in value or "distribution" in value:
        return "interest"
    return "other"


def collect_binance_account_exports(
    directory: str | Path | None,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[str, Any]:
    """Aggregate Binance transaction statement events in [start_utc, end_utc)."""
    if start_utc.tzinfo is None or end_utc.tzinfo is None:
        raise ValueError("Account export window boundaries must be timezone-aware")
    start = start_utc.astimezone(timezone.utc)
    end = end_utc.astimezone(timezone.utc)
    if start >= end:
        raise ValueError("Account export window must be positive")
    empty_aggregates = {event: {} for event in EVENT_TYPES}
    if directory is None:
        return {
            "status": "unavailable", "source": "local Binance CSV exports",
            "window_start_utc": start.isoformat().replace("+00:00", "Z"),
            "window_end_utc": end.isoformat().replace("+00:00", "Z"),
            "files": [], "file_count": 0, "rows_scanned": 0, "events_in_window": 0,
            "duplicate_rows": 0, "parse_errors": [], "unsupported_files": [],
            "aggregates_by_event_and_asset": empty_aggregates,
            "event_counts": {event: 0 for event in EVENT_TYPES},
            "assumptions": ["No account export directory was configured."],
            "limitations": (
                "No private account export was supplied. Public candles are not account balances, "
                "portfolio equity, realized PnL, or unrealized PnL."
            ),
            "portfolio_equity_status": "not_available",
            "flow_adjusted_return_status": "not_available",
        }

    supplied_root = Path(directory).expanduser()
    if supplied_root.is_symlink():
        return {
            "status": "failed", "source": "local Binance CSV exports",
            "window_start_utc": start.isoformat().replace("+00:00", "Z"),
            "window_end_utc": end.isoformat().replace("+00:00", "Z"),
            "files": [], "file_count": 0, "rows_scanned": 0, "events_in_window": 0,
            "duplicate_rows": 0, "parse_errors": ["The fixed account-export directory must not be a symlink."],
            "unsupported_files": [], "aggregates_by_event_and_asset": empty_aggregates,
            "event_counts": {event: 0 for event in EVENT_TYPES},
            "assumptions": [], "limitations": "Unsafe import directory.",
            "portfolio_equity_status": "not_available",
            "flow_adjusted_return_status": "not_available",
        }
    root = supplied_root.resolve()
    if not root.exists() or not root.is_dir():
        files = []
    else:
        files = sorted(
            path for path in root.iterdir()
            if path.suffix.lower() == ".csv" and not path.is_symlink()
        )
    if len(files) > MAX_FILES:
        return {
            "status": "failed", "source": "local Binance CSV exports",
            "window_start_utc": start.isoformat().replace("+00:00", "Z"),
            "window_end_utc": end.isoformat().replace("+00:00", "Z"),
            "files": [], "file_count": len(files), "rows_scanned": 0, "events_in_window": 0,
            "duplicate_rows": 0, "parse_errors": ["More than 100 CSV files in the fixed import directory."],
            "unsupported_files": [], "aggregates_by_event_and_asset": empty_aggregates,
            "event_counts": {event: 0 for event in EVENT_TYPES},
            "assumptions": [], "limitations": "Import limit exceeded.",
            "portfolio_equity_status": "not_available",
            "flow_adjusted_return_status": "not_available",
        }
    try:
        total_bytes = sum(path.stat().st_size for path in files)
    except OSError as exc:
        total_bytes = MAX_TOTAL_BYTES + 1
        total_size_error = f"Cannot inspect account export sizes: {type(exc).__name__}"
    else:
        total_size_error = None
    if total_bytes > MAX_TOTAL_BYTES:
        return {
            "status": "failed", "source": "local Binance CSV exports",
            "window_start_utc": start.isoformat().replace("+00:00", "Z"),
            "window_end_utc": end.isoformat().replace("+00:00", "Z"),
            "files": [], "file_count": len(files), "rows_scanned": 0, "events_in_window": 0,
            "duplicate_rows": 0, "parse_errors": [total_size_error or "Total CSV import size exceeds the 100 MB limit."],
            "unsupported_files": [], "aggregates_by_event_and_asset": empty_aggregates,
            "event_counts": {event: 0 for event in EVENT_TYPES},
            "assumptions": [], "limitations": "Import total-size limit exceeded.",
            "portfolio_equity_status": "not_available",
            "flow_adjusted_return_status": "not_available",
        }
    if not files:
        return {
            "status": "unavailable", "source": "local Binance CSV exports",
            "window_start_utc": start.isoformat().replace("+00:00", "Z"),
            "window_end_utc": end.isoformat().replace("+00:00", "Z"),
            "files": [], "file_count": 0, "rows_scanned": 0, "events_in_window": 0,
            "duplicate_rows": 0, "parse_errors": [], "unsupported_files": [],
            "aggregates_by_event_and_asset": empty_aggregates,
            "event_counts": {event: 0 for event in EVENT_TYPES},
            "assumptions": [], "limitations": "No CSV exports were found in data/account_exports.",
            "portfolio_equity_status": "not_available",
            "flow_adjusted_return_status": "not_available",
        }

    aggregates: dict[str, dict[str, Decimal]] = {event: defaultdict(Decimal) for event in EVENT_TYPES}
    counts = {event: 0 for event in EVENT_TYPES}
    file_records: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    unsupported_files: list[str] = []
    assumptions: set[str] = set()
    seen: set[tuple[str, str, str, str, str]] = set()
    rows_scanned = events_in_window = duplicates = 0
    supported_files = 0

    for file_index, path in enumerate(files, start=1):
        file_id = f"account_export_{file_index:03d}"
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root):
                parse_errors.append(f"{file_id}: file resolves outside the fixed import directory")
                continue
            size = resolved.stat().st_size
            if size <= 0 or size > MAX_FILE_BYTES:
                parse_errors.append(f"{file_id}: file is empty or exceeds the 20 MB limit")
                continue
            raw = resolved.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text, newline=""))
            if not reader.fieldnames:
                unsupported_files.append(file_id)
                continue
            mapping = {_header(name): name for name in reader.fieldnames}
            if not REQUIRED_HEADERS.issubset(mapping):
                unsupported_files.append(file_id)
                continue
            supported_files += 1
            file_rows = file_events = 0
            for row_number, row in enumerate(reader, start=2):
                file_rows += 1
                rows_scanned += 1
                if file_rows > MAX_ROWS_PER_FILE:
                    parse_errors.append(f"{file_id}: more than 100,000 rows")
                    break
                try:
                    timestamp, assumed_utc = _timestamp(row.get(mapping["utctime"], ""))
                    if assumed_utc:
                        assumptions.add("Naive UTC_Time values were interpreted as UTC; verify the export timezone setting.")
                    asset = (row.get(mapping["coin"], "") or "").strip().upper()
                    if not asset or not re.fullmatch(r"[A-Z0-9._-]{1,24}", asset):
                        raise ValueError("Coin is empty or malformed")
                    amount = _decimal(row.get(mapping["change"], ""))
                    operation = row.get(mapping["operation"], "")
                    event_type = _event_type(operation)
                    if not start <= timestamp < end:
                        continue
                    # Do not store User_ID or Remark. The normalized event key is
                    # sufficient to collapse overlapping exports without retaining PII.
                    key = (
                        timestamp.isoformat(), event_type, asset, str(amount),
                        (row.get(mapping["account"], "") or "").strip().lower(),
                    )
                    if key in seen:
                        duplicates += 1
                        continue
                    seen.add(key)
                    aggregates[event_type][asset] += amount
                    counts[event_type] += 1
                    events_in_window += 1
                    file_events += 1
                except Exception as exc:
                    parse_errors.append(f"{file_id}: row {row_number}: {type(exc).__name__}: {exc}")
            file_records.append({
                "file_id": file_id, "sha256": digest, "bytes": size,
                "format": "binance_transaction_history_csv",
                "rows_scanned": file_rows, "events_in_window": file_events,
            })
        except Exception as exc:
            parse_errors.append(f"{file_id}: {type(exc).__name__}: {exc}")

    status = (
        "partial" if supported_files == 0 and (unsupported_files or parse_errors) else
        "unavailable" if supported_files == 0 else
        "complete" if not parse_errors and not unsupported_files and not assumptions and counts["other"] == 0 else
        "partial"
    )
    return {
        "status": status,
        "source": "local Binance CSV exports",
        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
        "window_end_utc": end.isoformat().replace("+00:00", "Z"),
        "files": file_records,
        "file_count": len(files),
        "supported_file_count": supported_files,
        "rows_scanned": rows_scanned,
        "events_in_window": events_in_window,
        "duplicate_rows": duplicates,
        "parse_errors": parse_errors,
        "unsupported_files": unsupported_files,
        "aggregates_by_event_and_asset": {
            event: {asset: format(amount, "f") for asset, amount in sorted(values.items())}
            for event, values in aggregates.items()
        },
        "event_counts": counts,
        "unknown_operation_count": counts["other"],
        "assumptions": sorted(assumptions),
        "limitations": (
            "This parser supports Binance transaction-history CSV files with the documented User_ID, UTC_Time, "
            "Account, Operation, Coin, Change, Remark schema. It aggregates balance-change events only. It does not "
            "calculate total account equity, open-position unrealized PnL, full spot cost basis, tax PnL, or "
            "flow-adjusted portfolio returns; daily balance snapshots and complete position histories are required."
        ),
        "portfolio_equity_status": "not_available",
        "flow_adjusted_return_status": "not_available",
    }
