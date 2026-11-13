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

- `JobRunner` now dispatches approved `market.intraday_snapshot` jobs to the Binance acquisition and PDF composition workflow. The handler accepts only `cutoff_utc`, `interval`, and `market`; requires an explicit UTC cutoff; fixes output to `reports/intraday`; and records the PDF path, size, SHA-256, report window, market, interval, and read-only provenance.
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
- The cutoff must align exactly to the selected fixed-duration interval. Every expected candle open and inclusive close boundary is checked; missing, duplicate, misaligned, out-of-window, invalid, or incompletely paginated data fails closed before PDF publication. No values are interpolated or silently repaired.
- Binance server time is checked against the requested cutoff. Candle-page response metadata, pagination metadata, ticker metadata, and per-symbol provenance are retained. A local clock behind the cutoff is treated as an error rather than fabricating a generation timestamp.
- `generate_intraday_snapshot_pdf` delegates to the strict Binance UTC-day acquisition contract, then connects validated evidence to PDF composition in one callable workflow.
- The PDF composer rejects first/last candle timestamps outside the declared report window and validates supplied candle lists for count consistency, ordering, uniqueness, and cutoff compliance. The PDF displays the candle retrieval timestamp from Binance response metadata.

Live network execution is not certified by fixture-based CI; geographic/API availability must be assessed separately and no restrictions are bypassed.


## Local Engine integration — intraday snapshot

The approved `market.intraday_snapshot` job now invokes the strict Binance acquisition and PDF pipeline.

Create a job template:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job market.intraday_snapshot --output intraday-job.json
```

The template defaults to PDF output in `reports/intraday`. Edit its `parameters` object to include a UTC cutoff aligned to the interval:
```json
{
  "cutoff_utc": "2026-11-13T18:00:00Z",
  "interval": "1h",
  "market": "spot"
}
```

Submit, validate, approve, and run:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL submit intraday-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL validate JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL approve JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL run JOB_UUID
```

The completed job record stores the relative PDF artifact path and report window. The handler rejects missing/unknown parameters, non-UTC cutoffs, non-PDF output, unsafe workspace destinations, and incomplete Binance evidence. It uses public read-only endpoints only. Live execution still depends on the user's network and Binance endpoint eligibility.


## Local Engine intraday job workflow

Create a job template:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job market.intraday_snapshot --output intraday-job.json
```

Edit the generated JSON `parameters` object with an explicit completed UTC cutoff:
```json
{
  "cutoff_utc": "2026-11-13T03:00:00Z",
  "interval": "1h",
  "market": "spot"
}
```

Submit, validate, explicitly approve, and run:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL submit intraday-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL validate JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL approve JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL run JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL status JOB_UUID
```

The handler does not run before the job reaches the validated state with its explicit approval granted. It uses only Binance public read-only endpoints, rejects unsupported parameters and any output destination other than `reports/intraday`, and verifies the generated PDF signature before completing the job. The job result records the workspace-relative artifact path and SHA-256 digest. Acquisition, validation, or rendering errors move the job to `failed`; no successful result is recorded.

The workflow remains local and synchronous. It does not execute shell commands, accept job-supplied code, use Binance credentials, access private account endpoints, or submit trades. A live job requires outbound network access to Binance public market-data endpoints.
