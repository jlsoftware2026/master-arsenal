# MASTER ARSENAL — Architecture and Integration Contract

## Components
- **Binance Data Engine:** shared public read-only acquisition, normalization, validation, and technical-indicator calculations.
- **Opening report skill:** analyzes the previous completed market session.
- **Closing report skill:** analyzes the session that has just closed.
- **Intraday snapshot skill:** analyzes the UTC day from 00:00 through the requested/current cutoff.
- **Audit skill:** independently checks the other skills and their evidence.

## Data and time
- Binance is the primary market-data source.
- BTCUSDT and ETHUSDT are mandatory for core market reports.
- Normalize timestamps to timezone-aware UTC values at ingestion.
- Use half-open time windows [start, end) for historical acquisition.
- Preserve source, symbol, interval, retrieval time, requested window, and pagination/completeness metadata.
- Never silently fill missing candles or convert missing data into a market signal.

## Validation
Validate OHLC relationships, positive prices, non-negative volumes, timestamp ordering, duplicate candles, expected cadence, and response completeness. Surface gaps and partial acquisition in report evidence.

## Safety boundary
The engine is public read-only market-data infrastructure. It must not place orders, manage accounts, request API secrets, or execute trades.

## Reporting contract
Each of the four skills generates a detailed PDF as its required deliverable. If PDF generation is unavailable or fails, report the blocker; do not substitute chat text or another format and do not claim a PDF was produced.

The engine does not decide the reporting window, generate forecasts, write PDFs, or certify its own correctness. Each skill owns its analysis and report logic; the audit skill independently reviews it.

## Forecasting and uncertainty
Forecasts must be scenario-based, evidence-linked, and explicitly uncertain. Include both bullish/long and bearish/short cases, assumptions, invalidation conditions, and risk factors. Do not present a forecast as a guaranteed outcome.

## Current implementation
The initial read-only REST client, candle validation, indicators, snapshot orchestration, and CLI are implemented in this branch. See [Binance API contract](binance-api-contract.md) and [implementation status](implementation-status.md) for endpoint scope, test results, and outstanding validation.
