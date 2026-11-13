# Phase 3 — PDF Report Engine

## Implemented in the current development increment

- ReportLab is the shared PDF rendering dependency.
- `report_engine.pdf` provides shared styles, page templates, headers/footers, page numbering, tables, and atomic artifact writing.
- `report_engine.charts.MarketChart` renders vector close-price line charts and volume bar charts directly into PDFs, with finite-value and label validation and bounded downsampling.
- `report_engine.qa.inspect_pdf_artifact` independently parses each PDF with PyMuPDF, extracts text, checks text bounds and page dimensions, raster-renders every page, rejects blank/unreadable pages, and can optionally write PNG previews.
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
- Intraday PDFs now undergo independent PyMuPDF parsing and rendered-page checks after ReportLab generation. QA checks parsing, extractable text on every page, text-span bounds, and nonblank raster rendering. It is structural/render QA, not human visual sign-off or semantic correctness verification.
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

The allowlisted `JobRunner` dispatches `market.intraday_snapshot` only after the existing lifecycle has moved the job from inbox through validation and explicit approval to the validated state.

Create a template:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL new-job market.intraday_snapshot --output intraday-job.json
```

Edit the generated JSON `parameters` object with an explicit UTC cutoff aligned to the selected interval:
```json
{
  "cutoff_utc": "2026-11-13T03:00:00Z",
  "interval": "1h",
  "market": "spot"
}
```

Submit, validate, explicitly approve, execute, and inspect:
```bash
ma-local --workspace ./MASTER-ARSENAL-LOCAL submit intraday-job.json
ma-local --workspace ./MASTER-ARSENAL-LOCAL validate JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL approve JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL run JOB_UUID
ma-local --workspace ./MASTER-ARSENAL-LOCAL status JOB_UUID
```

The handler accepts only `cutoff_utc`, `interval`, and `market`; requires an explicit UTC cutoff; and fixes output to PDF in `reports/intraday`. It uses Binance public read-only market-data endpoints only. It does not accept arbitrary paths, commands, or job-supplied code. Before marking a job complete, it checks the PDF signature and EOF marker and records the workspace-relative artifact path, file size, and SHA-256 digest. Acquisition, validation, or rendering errors move the job to `failed`.

The workflow is local and synchronous. The handler requires a caller-supplied cutoff rather than silently choosing a reporting time. Live execution requires outbound network access to Binance public market-data endpoints; fixture-based CI does not certify live endpoint availability. No credentials, private account endpoints, trading operations, or geographic restrictions are used or bypassed.


## Shared charts and independent PDF quality assurance

The shared `MarketChart` flowable draws vector graphics directly into the PDF (no external chart-image service). It validates finite numeric values, validates label/value counts, and downsamples long series deterministically while preserving endpoints. The intraday composer adds close-price line charts and base-volume bar charts for BTCUSDT and ETHUSDT whenever candle evidence is present; no chart is fabricated when candle evidence is absent.

PyMuPDF is used as an independent reader/rendering implementation after ReportLab writes the artifact. Example:
```python
from report_engine import inspect_pdf_artifact

result = inspect_pdf_artifact(
    "reports/intraday/snapshot-mercado-2026-11-13_03-00.pdf",
    render_directory="reports/qa-previews",
)
print(result["checks"])
```

The QA routine parses the document, checks that every page has extractable text, validates text spans against page bounds, renders each page to a raster image, and rejects blank pages. PNG previews are optional and are written only when an explicit preview directory is supplied. The intraday composer removes the newly generated artifact if independent QA fails. These automated checks do not replace human review of chart readability, analytical accuracy, or investment conclusions.
