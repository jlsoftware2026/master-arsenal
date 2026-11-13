# binance-revision-skills

## Purpose
Independently audit the other three market-report skills, their source data, analysis, and generated PDF artifacts.

## Required audit scope
1. **Temporal correctness:** date, timezone, session boundaries, intraday cutoff, candle close semantics.
2. **Data integrity:** Binance source provenance, retrieval timestamps, completeness, gaps, duplicates, stale responses, pagination, and symbol/interval correctness.
3. **Methodology:** indicator calculations, warm-up requirements, assumptions, derivatives/macro/news attribution, scenario logic, and reproducibility.
4. **Cross-report consistency:** comparable values and claims agree when reporting windows overlap; explain legitimate differences.
5. **Testing:** distinguish offline unit tests from live API tests; record exact commands, results, and limitations.
6. **PDF quality:** required sections, readable charts/tables, metadata, filenames, page integrity, and evidence traceability.
7. **Findings:** classify severity, cite evidence, explain impact, and recommend corrective actions.

## Output
auditoria-skills-binance_YYYY-MM-DD.pdf

## Independence and integrity
Do not certify a skill based solely on its own assertions. Verify against raw source evidence and reproducible calculations where possible. Mark unavailable evidence as not verified rather than passing it. The audit itself must be a PDF; if PDF generation fails, report the blocker and do not substitute another format.

## Status
Provisional ChatGPT adaptation. Exact original Claude audit checklist and scoring thresholds have not yet been reconciled against the original .skill source.