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

- The intraday acquisition and PDF composition are connected through `generate_intraday_snapshot_pdf`; the Local Engine job handler is not yet implemented.
- The general Binance snapshot still returns rolling klines; the dedicated intraday path separately requests the exact UTC-day window.
- Macro/news acquisition and source citation contracts remain to be integrated.
- Opening, closing, and independent audit PDF composers remain outstanding.
- The artifact checks are basic structural checks, not a full independent PDF parser or visual QA.
- The original Claude skill source files remain unrecovered; current skill specifications are provisional.

## Verification

Run:
```bash
python -m pip install -e .
python -m unittest discover -s binance_data_engine/tests -v
python -m unittest discover -s report_engine/tests -v
```


## UTC intraday acquisition increment

- `report_engine.acquisition.acquire_intraday_evidence` now requests a bounded UTC-day range from 00:00 UTC to the exclusive cutoff for BTCUSDT and ETHUSDT.
- Only completed candles are retained; a candle whose close timestamp reaches or exceeds the cutoff is excluded.
- The cutoff must align exactly to the selected fixed-duration interval. Every expected candle open and inclusive close boundary is checked; missing, duplicate, misaligned, out-of-window, invalid, or incompletely paginated data produces explicit error issues and `data_status=incomplete`. No values are interpolated.
- Binance server time is checked against the requested cutoff. Candle-page response metadata, pagination counts, ticker metadata, and per-symbol provenance are retained. A local clock behind the cutoff is treated as an error rather than fabricating a generation timestamp.
- `generate_intraday_snapshot_pdf` delegates to the strict Binance UTC-day acquisition contract, then connects validated evidence to PDF composition in one callable workflow.
- The PDF composer rejects first/last candle timestamps outside the declared report window and validates supplied candle lists for count consistency, ordering, uniqueness, and cutoff compliance. The PDF displays the candle retrieval timestamp from the nested provenance metadata.

This increment still does not connect the workflow to the Local Engine job dispatcher. Live network execution is also not certified by fixture-based CI; geographic/API availability must be assessed separately and no restrictions are bypassed.
