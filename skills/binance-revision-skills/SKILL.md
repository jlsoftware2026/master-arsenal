# binance-revision-skills

## Purpose
Independently audit the other three market-report workflows, their source data, and generated PDF artifacts.

## Local Engine workflow
- Job type: `skills.audit`
- Fixed output directory: `reports/audit`
- Filename: `auditoria-skills-binance_YYYY-MM-DD.pdf`
- No caller-supplied parameters are accepted.
- The job must pass submit → validate → explicit approval → execute.

## Required audit scope
1. **Temporal correctness:** date, timezone, session boundaries, intraday cutoff, candle close semantics.
2. **Data integrity:** Binance source provenance, retrieval timestamps, completeness, gaps, duplicates, stale responses, pagination, and symbol/interval correctness.
3. **Methodology:** indicator calculations and warm-up requirements; assumptions; derivatives, macro/news attribution; scenario logic; reproducibility.
4. **Cross-report consistency:** comparable values and claims agree when reporting windows overlap; explain legitimate differences.
5. **Testing:** distinguish offline unit tests from live API/feed tests; record exact commands, results, and limitations.
6. **PDF quality:** required sections, readable charts/tables, metadata, filenames, page integrity, and evidence traceability.
7. **Findings:** classify severity, cite inspectable evidence, explain impact, and recommend corrective actions.

## Current automated checks
The Local Engine scans the fixed opening, closing, and intraday report folders, hashes discovered PDFs, independently parses each artifact, extracts text, checks text bounds, raster-renders pages, validates filename prefixes, and checks for mandatory BTC/ETH, scenario, macro/news, provenance, and feed-status sections. Missing artifacts and failed structural/content checks are explicit findings. An empty artifact set is insufficient evidence, never a pass.

## Independence and integrity
Do not certify a skill based solely on its own assertions. The current automated audit is primarily a PDF structural/readability audit; it does not yet independently recalculate every indicator or fully validate all news claims, scenario quality, or market-analysis semantics. Mark those areas NOT VERIFIED unless separate evidence is supplied. The audit itself must be a PDF; if PDF generation fails, report the blocker and do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude audit checklist, scoring thresholds, and report layout have not yet been reconciled against the original .skill source.