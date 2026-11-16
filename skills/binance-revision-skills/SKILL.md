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
The Local Engine scans the fixed opening, closing, and intraday report folders, hashes discovered PDFs, independently parses each artifact, extracts text, checks text bounds, raster-renders pages, validates filename prefixes, and checks mandatory BTC/ETH, scenario, macro/news, provenance, and feed-status sections. It also reads internal source-linked evidence manifests, verifies the PDF digest, revalidates raw candle windows, recalculates technical indicators independently, and compares overlapping OHLCV candles across reports. Missing manifests, missing artifacts, failed checks, or absent CI evidence remain explicit findings. An empty artifact set is insufficient evidence, never a pass.

## Original-skill desk-check matrix

The audit PDF records each case with status, severity, evidence, and corrective action:
1. Dominican local midnight, previous-local-day opening, exact partial closing cutoff, and intraday cutoff default.
2. U.S. weekends and exchange holidays; use the last completed cash session without changing the Binance local-day reference.
3. U.S. daylight-saving transitions and premarket/regular/postmarket session classification.
4. Missing private Binance account access: disclose unavailable data and never substitute public market candles for account data.
5. External deposits and withdrawals: do not count them as trading profit or loss.
6. Missing historical account balances: do not claim portfolio return where opening equity cannot be reconstructed.
7. Same-date opening forecast versus closing outcome scorecard, when the opening forecast exists.
8. Raw candle integrity, report/evidence digests, package integrity, and version/change history.
9. Offline CI versus live API/feed verification; report exact evidence and limitations.
10. PDF section, filename, chart, table, page, and provenance checks.

Severity is Critical, High, Medium, or Low. The verdict is No aprobado when unresolved Critical/High findings remain; Aprobado con reservas when only Medium findings remain; and Aprobado only when no unresolved findings remain. Unavailable/not implemented checks must remain visible and must not be counted as passed.

## Independence and integrity
Do not certify a skill based solely on its own assertions. The current automated audit independently recalculates stored indicators from retained raw candles and compares overlapping report candles. It does not yet verify the factual accuracy of every news claim, certify scenario quality, or prove parity with the original Claude skill source. CI and live endpoint results must be attached separately; the local audit does not fetch or trust external CI status. Mark those areas NOT VERIFIED unless separate evidence is supplied. The audit itself must be a PDF; if PDF generation fails, report the blocker and do not substitute another format.

## Status
Adapted against the user-supplied original Claude audit skill. The PDF now records a desk-check matrix, severity levels, Spanish verdict, and change-history section. U.S. calendar/DST coverage, private-account reconciliation, package integrity, scorecard linkage, and final cross-platform CI evidence remain incomplete; the audit must not certify full source-skill parity.