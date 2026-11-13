"""Vector market charts shared by MASTER ARSENAL PDF reports."""
from __future__ import annotations

import math
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable


INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")
ACCENT = colors.HexColor("#1D4ED8")
GRID = colors.HexColor("#CBD5E1")


def _finite_values(values: Iterable[object]) -> list[float]:
    result = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("Chart values must be finite numbers, not booleans")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Chart values must be finite numbers") from exc
        if not math.isfinite(number):
            raise ValueError("Chart values must be finite numbers")
        result.append(number)
    if not result:
        raise ValueError("A market chart requires at least one data point")
    return result


def _sample(values: list[float], labels: list[str], limit: int = 60):
    if len(values) <= limit:
        return values, labels
    indexes = sorted({round(i * (len(values) - 1) / (limit - 1)) for i in range(limit)})
    return [values[i] for i in indexes], [labels[i] for i in indexes]


class MarketChart(Flowable):
    """A dependency-light vector line or bar chart rendered directly into the PDF."""

    def __init__(self, title: str, values: Iterable[object], labels: Iterable[str] | None = None,
                 kind: str = "line", width: float = 170 * mm, height: float = 48 * mm):
        super().__init__()
        if kind not in {"line", "bar"}:
            raise ValueError("Chart kind must be 'line' or 'bar'")
        self.title = str(title)
        raw_values = _finite_values(values)
        raw_labels = [str(x) for x in labels] if labels is not None else [
            str(i + 1) for i in range(len(raw_values))
        ]
        if len(raw_labels) != len(raw_values):
            raise ValueError("Chart labels and values must have equal lengths")
        self.values, self.labels = _sample(raw_values, raw_labels)
        self.kind = kind
        self.width = width
        self.height = height

    def draw(self):
        canvas = self.canv
        left, right, bottom, top = 13 * mm, self.width - 4 * mm, 11 * mm, self.height - 9 * mm
        plot_width, plot_height = right - left, top - bottom
        low, high = min(self.values), max(self.values)
        if self.kind == "bar":
            low = min(0.0, low)
            high = max(0.0, high)
        if math.isclose(low, high):
            padding = max(abs(high) * 0.05, 1.0)
            low, high = low - padding, high + padding
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(INK)
        canvas.drawString(0, self.height - 6 * mm, self.title[:100])
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.45)
        for tick in range(5):
            y = bottom + plot_height * tick / 4
            canvas.line(left, y, right, y)
            value = low + (high - low) * tick / 4
            canvas.setFont("Helvetica", 6)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(left - 2 * mm, y - 2, f"{value:.5g}")
        canvas.setStrokeColor(MUTED)
        canvas.line(left, bottom, left, top)
        canvas.line(left, bottom, right, bottom)
        count = len(self.values)
        x_at = lambda i: left + (plot_width * i / max(1, count - 1))
        y_at = lambda value: bottom + (value - low) / (high - low) * plot_height
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6)
        if self.kind == "line":
            canvas.setStrokeColor(ACCENT)
            canvas.setLineWidth(1.4)
            for i in range(1, count):
                canvas.line(x_at(i - 1), y_at(self.values[i - 1]),
                            x_at(i), y_at(self.values[i]))
            canvas.setFillColor(ACCENT)
            for i, value in enumerate(self.values):
                canvas.circle(x_at(i), y_at(value), 1.2, stroke=0, fill=1)
        else:
            canvas.setFillColor(ACCENT)
            zero = y_at(0.0)
            slot = plot_width / max(1, count)
            bar_width = max(0.6, min(5.0, slot * 0.65))
            for i, value in enumerate(self.values):
                y = y_at(value)
                canvas.rect(x_at(i) - bar_width / 2, min(zero, y), bar_width,
                            max(0.5, abs(y - zero)), stroke=0, fill=1)
        for i in sorted({0, count // 2, count - 1}):
            label = self.labels[i]
            canvas.drawCentredString(x_at(i), bottom - 4 * mm, label[-8:])
        canvas.restoreState()
