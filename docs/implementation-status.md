# Implementation status

Last updated: 2026-11-13

## Implemented in this branch
- Read-only Spot and USDⓈ-M Futures public REST client.
- UTC timestamp normalization and Decimal-based OHLCV candle model.
- Bounded retries for HTTP 418/429, transient 5xx, and network errors.
- Retry-After support and response weight/retrieval metadata capture.
- Spot/Futures kline retrieval and historical pagination with half-open [start, end) boundaries.
- Futures 200-day historical kline request chunking.
- Duplicate suppression, pagination progress guard, and incomplete-page metadata.
- Candle validation for OHLC, price/volume signs, timestamp ordering, duplicates, and fixed-interval gaps.
- EMA, SMA, RSI, MACD, ATR, and Bollinger calculations with explicit warm-up nulls.
- Snapshot orchestration requiring BTCUSDT and ETHUSDT.
- 24-hour ticker, mark/index premium, current/historical open interest, funding history, global long/short ratio, basis, mark-price and index-price candle methods.
- CLI snapshot command; JSON output only (the four report skills still own PDF production).

## Offline verification
Command:
`python -m unittest discover -s binance_data_engine/tests -v`

Result on the local development environment: **26 tests passed**. Tests use controlled fixtures and mocked HTTP responses. They cover parsing, UTC normalization, OHLC validation, gap detection, indicator warm-up, retry behavior, Spot/Futures page limits, half-open pagination, and Futures 200-day chunking.

Additional local checks:
- Editable package installation succeeded with `--no-build-isolation` using the already-installed setuptools.
- CLI help command succeeded.
- Live Spot and Futures connectivity attempts could not complete because the execution environment could not resolve external DNS (network unavailable). This is an environment limitation, not a passing live test. A manual GitHub Actions workflow, `Binance live smoke test`, is available under Actions → Binance live smoke test → Run workflow; it probes server time, BTCUSDT/ETHUSDT candles and 24h tickers, plus basic Futures premium index and open interest.

## Not yet validated
- Live Binance API connectivity from this execution environment.
- Live endpoint schemas and access behavior for every Futures metric.
- End-to-end snapshot against current BTCUSDT and ETHUSDT exchange responses.
- GitHub Actions run for the new engine commits (pending after push).
- Persistence, reproducible historical data archives, and provenance manifests beyond per-response metadata.
- PDF generation, chart rendering, and full report-skill execution.
- Exact parity with the original Claude .skill files. Their original detailed parameters/checklists have not been recovered.

## Release posture
This is an initial implementation candidate, not production-certified. Do not use its output as a trading signal without independent review, live data verification, and risk controls.
