# MASTER ARSENAL

Central development repository for MASTER ARSENAL — Binance Data Engine and AI skills.

## Project components
- `binance_data_engine/`: shared public read-only Binance market-data client, validation, indicators, snapshot orchestration, and CLI.
- `skills/`: four independent report-generation and audit skill specifications.
- `docs/`: architecture, API contract, implementation status, and validation evidence.

## Core principles
1. Binance is the primary market-data source.
2. BTCUSDT and ETHUSDT are mandatory core instruments.
3. All timestamps are normalized to UTC; report windows are owned by the individual skills.
4. Market-data gaps, stale responses, partial acquisition, and unverified claims must be disclosed.
5. The engine is read-only: no trading, order placement, account actions, or credential storage.
6. Every skill produces a detailed PDF report. If PDF generation fails, it must report the blocker and must not claim a report exists.
7. Changes are developed on feature branches and integrated through pull requests. `main` is the stable line; `develop` is the integration line.

## Skills
- `binance-apertura-mercado`: previous completed market session.
- `binance-cierre-mercado`: market session that has just closed.
- `binance-momento-mercado`: intraday snapshot from 00:00 UTC to the requested/current cutoff.
- `binance-revision-skills`: independent audit of data, methodology, consistency, tests, and PDF quality.

## Install and use
Requires Python 3.11+.

```bash
python -m pip install -e .
ma-binance snapshot --symbols BTCUSDT ETHUSDT --interval 1h --limit 250 --market spot --output snapshot.json
ma-binance snapshot --symbols BTCUSDT ETHUSDT --interval 1h --limit 250 --market usdm --output futures.json
```

## Tests
```bash
python -m unittest discover -s binance_data_engine/tests -v
```

See [docs/binance-api-contract.md](docs/binance-api-contract.md) for endpoint behavior and [docs/implementation-status.md](docs/implementation-status.md) for verified scope and limitations.

> **Status:** initial implementation candidate. Offline unit tests are not evidence of live API connectivity or production readiness. The report skills' PDF generation and original Claude-source parity remain outstanding.
