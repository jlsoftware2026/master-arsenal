# MASTER ARSENAL

Central development repository for MASTER ARSENAL — Binance Data Engine and AI skills.

## Project components

- `binance_data_engine/`: shared, public read-only Binance market-data acquisition and indicator engine.
- `skills/`: four independent report-generation and audit skills.
- `docs/`: architecture, data contracts, validation rules, and development notes.

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

## Development

Run the offline test suite:

```bash
python -m unittest discover -s binance_data_engine/tests -v
```

Install the package once its Python project metadata is present:

```bash
python -m pip install -e .
```

See [docs/architecture.md](docs/architecture.md) for the current integration contract.

> **Implementation status:** this repository is being bootstrapped. Do not treat a scaffold, offline test, or documentation draft as proof of live Binance connectivity or production readiness.
