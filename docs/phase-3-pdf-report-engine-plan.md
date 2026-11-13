# MASTER ARSENAL — Phase 3 PDF Report Engine Plan

## Status

Phase 3 kickoff and design baseline. This document does not claim that PDF generation is implemented.

Base branch: `develop`  
Working branch: `feature/phase-3-pdf-report-engine`  
Scope: shared PDF infrastructure and the first end-to-end intraday snapshot report.

## Objectives

1. Produce detailed, reproducible PDF reports exclusively for all four market skills.
2. Reuse one rendering and layout layer rather than maintaining four independent PDF generators.
3. Preserve data provenance, UTC boundaries, validation results, missing-data disclosures, and uncertainty throughout the report pipeline.
4. Keep report-window and analytical decisions in the skill/report orchestration layer; the Binance acquisition engine remains read-only and does not generate forecasts.
5. Make report generation deterministic enough to test without live Binance connectivity.

## Proposed component boundaries

- **Report data contract:** typed, validated report input assembled from Binance snapshots and skill-owned analysis.
- **Report builder/orchestrator:** selects report type, validates required sections and evidence, and passes structured content to the renderer.
- **Shared PDF renderer:** page layout, typography, headers/footers, page numbering, tables, charts, metadata, and output validation.
- **Report-specific composers:** opening, closing, intraday, and audit sections. These compose content; they do not duplicate low-level PDF layout code.
- **Artifact validation:** verifies PDF signature/readability, expected metadata, required sections, output naming, and non-empty content.

## Delivery sequence

### Phase 3.1 — PDF foundation
- Select and document the PDF library.
- Add shared styles, page templates, headers/footers, page numbering, tables, chart embedding, metadata, and atomic output writing.
- Add unit tests for renderer primitives and malformed/empty inputs.

### Phase 3.2 — Intraday snapshot PDF
- Define a versioned report input schema.
- Enforce UTC window `[00:00 UTC, cutoff)` and explicit cutoff metadata.
- Require BTCUSDT and ETHUSDT.
- Include market overview, asset sections, indicator tables, validation/data-quality disclosures, macro/news context where sourced, bullish and bearish scenarios, invalidation levels, and risk/uncertainty notes.
- Output filename: `snapshot-mercado-YYYY-MM-DD_HH-mm.pdf`.

### Phase 3.3 — Opening and closing PDFs
- Implement report-specific UTC window selection and data completeness checks.
- Opening: previous completed market day/session.
- Closing: market day/session that has just closed.
- Output filenames: `apertura-mercado_YYYY-MM-DD.pdf` and `cierre-mercado_YYYY-MM-DD.pdf`.

### Phase 3.4 — Independent skills audit PDF
- Audit source data, UTC windows, calculations, evidence links, consistency, scenario balance, required sections, and PDF integrity.
- Do not let the audit simply trust the report generator's own success status.
- Output filename: `auditoria-skills-binance_YYYY-MM-DD.pdf`.

### Phase 3.5 — End-to-end verification
- Fixture-driven tests for each report type.
- Test missing candles, stale/partial data, indicator warm-up, unavailable endpoints, invalid windows, and PDF write failures.
- Verify filenames, UTC timestamps, metadata, required sections, and PDF readability.
- Run the full cross-platform GitHub Actions matrix.

## Report content and evidence rules

- Binance remains the primary market-data source.
- BTCUSDT and ETHUSDT are mandatory for core market reports.
- Every market value must retain symbol, interval, source, retrieval time, and applicable window.
- Missing, stale, partial, or invalid data must be disclosed; it must never be silently imputed into a signal.
- Technical indicators must disclose warm-up insufficiency.
- News and macro statements must carry source and publication/retrieval timestamps.
- Forecasts are scenarios, not guarantees. Include bullish and bearish cases, assumptions, invalidation conditions, and material risks.
- The audit report must identify limitations and failed checks rather than self-certifying.

## Dependency decision requiring owner approval

The repository currently declares no runtime dependencies. A PDF implementation requires choosing a rendering library. **ReportLab is the proposed default** because it supports programmatic multi-page PDF generation, tables, vector drawing, metadata, and deterministic fixture-based testing.

No dependency has been added in this kickoff commit. Before implementation, the repository owner should approve ReportLab (or specify another library). Adding a runtime dependency is intentionally treated as a material architectural change.

## Explicitly out of scope for this phase

- Trading, order placement, account access, or API credential storage.
- Bypassing Binance geographic restrictions.
- OpenJarvis/MCP integration.
- Replacing the existing Local Engine job protocol.
- Claiming parity with the original Claude `.skill` sources, which have not yet been recovered verbatim.
- Production certification or investment advice.

## Acceptance criteria

- All four report types produce actual readable PDFs with the required filenames.
- Shared rendering infrastructure is reused across report types.
- Report windows are correct and timezone-aware.
- BTCUSDT and ETHUSDT are required in core market reports.
- Data gaps, source provenance, stale/partial responses, and uncertainty are visible.
- No report is marked successful if PDF generation or artifact validation fails.
- Offline tests cover the complete report pipeline; live API validation is separately reported and never inferred from fixture tests.
- All configured Ubuntu/Windows and Python 3.11/3.12 CI jobs pass.
