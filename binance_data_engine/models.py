"""Typed market-data models."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

def utc_datetime(value: datetime | str | int | float) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    else:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def decimal_value(value: Any) -> Decimal:
    return Decimal(str(value))

@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal | None = None
    trades: int | None = None
    taker_buy_base_volume: Decimal | None = None
    taker_buy_quote_volume: Decimal | None = None
    source: str = "binance"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("open_time", "close_time"):
            data[key] = data[key].isoformat().replace("+00:00", "Z")
        for key, value in list(data.items()):
            if isinstance(value, Decimal):
                data[key] = str(value)
        return data

@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "warning"
    index: int | None = None
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
