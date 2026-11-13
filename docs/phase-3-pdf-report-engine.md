# Phase 3 — PDF Report Engine

## Implemented in the current development increment

- ReportLab is the shared PDF rendering dependency.
- `report_engine.pdf` provides shared styles, page templates, headers/footers, page numbering, tables, and atomic artifact writing.
- `report_engine.intraday` validates the UTC intraday report contract and generates the first report type.
- BTCUSDT and ETHUSDT are mandatory.
- Output naming follows `snapshot-mercado-YYYY-MM-DD_HH-mm.pdf`, based on the UTC cutoff.
- PDF artifacts are checked for a PDF header, EOF marker, and minimum size before atomic publication.
- Fixture-based tests exercise output generation, required symbols, UTC enforcement, and reporting-window boundaries.

## Input contract

The intraday composer accepts an already-acquired report dictionary. Required fields:
- `window_start_utc`: UTC midnight at the start of the report date.
- `cutoff_utc`: later time on the same UTC date; treated as exclusive.
- `generated_at_utc`: UTC timestamp at or after cutoff.
- `symbols`: mapping containing BTCUSDT and ETHUSDT.

The composer renders optional executive summary, ticker and indicator values, validation issues, derivatives/macro/news context, bullish and bearish scenarios, risks, limitations, and provenance when supplied. It does not fetch data, invent missing analysis, or infer forecasts.

## Current limitations

- The first PDF workflow is a renderer/composer accepting structured evidence; it is not yet wired to live Binance acquisition or a Local Engine job handler.
- The Binance snapshot currently returns recent rolling klines, not a complete UTC-day historical window. A dedicated intraday acquisition pipeline must be implemented before the skill can claim full-day coverage.
- Macro/news acquisition and source citation contracts remain to be integrated.
- Opening, closing, and independent audit PDF composers remain outstanding.
- The artifact checks are basic structural checks, not a full independent PDF parser or visual QA.
- The original Claude skill source files remain unrecovered; current skill specifications are provisional.

## Verification

Run:
```bash
python -m pip install -e .
python -m unittest discover -s report_engine/tests -v
```
