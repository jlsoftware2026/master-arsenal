"""Dependency-free technical indicators with explicit warm-up behavior."""
from math import sqrt

def _floats(values):
    return [float(x) for x in values]

def ema(values, period: int):
    data = _floats(values)
    if period < 1: raise ValueError("period must be >= 1")
    out = [None] * len(data)
    if len(data) < period: return out
    current = sum(data[:period]) / period
    out[period - 1] = current
    alpha = 2.0 / (period + 1)
    for i in range(period, len(data)):
        current = data[i] * alpha + current * (1 - alpha)
        out[i] = current
    return out

def sma(values, period: int):
    data = _floats(values)
    if period < 1: raise ValueError("period must be >= 1")
    out = [None] * len(data)
    for i in range(period - 1, len(data)):
        out[i] = sum(data[i-period+1:i+1]) / period
    return out

def rsi(values, period: int = 14):
    data = _floats(values)
    if period < 1: raise ValueError("period must be >= 1")
    out = [None] * len(data)
    if len(data) <= period: return out
    changes = [data[i] - data[i-1] for i in range(1, len(data))]
    gain = sum(max(x, 0.0) for x in changes[:period]) / period
    loss = sum(max(-x, 0.0) for x in changes[:period]) / period
    def value(g, l):
        return 100.0 if l == 0 and g > 0 else (50.0 if l == 0 else 100.0 - 100.0 / (1.0 + g/l))
    out[period] = value(gain, loss)
    for i in range(period + 1, len(data)):
        change = changes[i-1]
        gain = (gain * (period-1) + max(change, 0.0)) / period
        loss = (loss * (period-1) + max(-change, 0.0)) / period
        out[i] = value(gain, loss)
    return out

def macd(values, fast: int = 12, slow: int = 26, signal: int = 9):
    if fast >= slow: raise ValueError("fast period must be less than slow period")
    data = _floats(values)
    f, s = ema(data, fast), ema(data, slow)
    line = [None if a is None or b is None else a-b for a,b in zip(f,s)]
    valid = [x for x in line if x is not None]
    sig = ema(valid, signal)
    signal_line, cursor = [None] * len(data), 0
    for i, x in enumerate(line):
        if x is not None:
            signal_line[i] = sig[cursor]
            cursor += 1
    hist = [None if a is None or b is None else a-b for a,b in zip(line, signal_line)]
    return {"macd": line, "signal": signal_line, "histogram": hist}

def true_range(high, low, close):
    h,l,c = _floats(high), _floats(low), _floats(close)
    if not (len(h) == len(l) == len(c)): raise ValueError("high, low, close lengths differ")
    return [h[0]-l[0] if i == 0 else max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(len(h))]

def atr(high, low, close, period: int = 14):
    data = true_range(high, low, close)
    if period < 1: raise ValueError("period must be >= 1")
    out = [None] * len(data)
    if len(data) < period: return out
    current = sum(data[:period]) / period
    out[period-1] = current
    for i in range(period, len(data)):
        current = (current * (period-1) + data[i]) / period
        out[i] = current
    return out

def bollinger(values, period: int = 20, deviations: float = 2.0):
    data = _floats(values)
    if period < 1 or deviations < 0: raise ValueError("invalid Bollinger parameters")
    mid, upper, lower = [None]*len(data), [None]*len(data), [None]*len(data)
    for i in range(period-1, len(data)):
        window = data[i-period+1:i+1]
        mean = sum(window)/period
        std = sqrt(sum((x-mean)**2 for x in window)/period)
        mid[i], upper[i], lower[i] = mean, mean+deviations*std, mean-deviations*std
    return {"middle": mid, "upper": upper, "lower": lower}
