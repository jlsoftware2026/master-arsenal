# Original Claude Skills — Phase 3 Reconciliation

**Source of truth:** the four user-supplied Claude `.skill` packages received on 2026-11-16.  
**Target branch:** `feature/phase-3-pdf-report-engine`.  
**Status:** Dominican timezone windows, partial closing, Spanish PDF localization, and the current code test matrix are implemented and verified on the feature branch. Remaining original-skill requirements are still outstanding. Phase 3 is not merge-ready.

## Executive finding

The current implementation is a strong PDF/data-engine foundation, and the three report windows now use `America/Santo_Domingo` local calendar semantics. It is not yet behaviorally equivalent to the original skills: broader U.S. equity-market price coverage, private Binance account analysis, activation timing, and complete original-package/audit verification remain outstanding. Same-date range-scenario scorecard linkage is now implemented. The XNYS holiday/session calendar and session-state classifier are now integrated.

## Requirement comparison

| Area | Original Claude requirement | Current Phase 3 implementation | Required adaptation |
|---|---|---|---|
| Primary timezone | `America/Santo_Domingo`; show local timestamps and ET where relevant | Implemented: local-day boundaries drive acquisition, PDF validation, filenames, charts, and evidence manifests; local, UTC, and relevant ET timestamps are shown | DST-aware ET/local scheduled cash-session times are displayed; XNYS holiday, early-close, last/next-session, and premarket/regular/postmarket/closed classification are integrated and independently recalculated by the audit |
| Opening Binance window | Previous local calendar day, 00:00–23:59:59 | Implemented: previous Dominican local calendar day is acquired via UTC-converted half-open boundaries | Verify on final CI head and preserve previous-local-date behavior |
| Closing Binance window | Current local calendar day; partial until local midnight | Implemented: partial current local-day windows and historical completed local days are supported; exact cutoff is retained and unfinished candles are excluded | Verify partial closing regression and final CI head |
| Intraday window | Local midnight through exact requested local cutoff; use current local time if omitted | Implemented: local cutoff is accepted; omission resolves execution-time local time; final incomplete candle is excluded | Verify explicit/omitted cutoff and cross-UTC-date regressions on final CI head |
| U.S. market session | 9:30 a.m.–4:00 p.m. ET with DST-aware conversion; weekends/holidays handled | Integrated XNYS calendar with holidays, early closes, last/next session, and exact-time state classification | Verify independent calendar reconciliation in final CI; U.S. price feeds remain separate and outstanding |
| U.S. market coverage | S&P 500, Nasdaq Composite and/or Nasdaq 100, Dow, Russell 2000, VIX, futures, Treasury 10Y, DXY, WTI, gold, sectors, breadth, leaders/laggards | Binance BTC/ETH candles, optional USD-M derivatives, selected RSS feeds | Add attributed public-market data adapters; explicitly disclose unavailable series rather than omit silently |
| Binance private account | Read-only connector or user exports; otherwise mark account unavailable | Public Binance REST only | Keep private-account section explicitly unavailable until a supported read-only connector/export parser exists; never imply public candles are account data |
| Portfolio accounting | Equity/balance, realized/unrealized PnL, fees/funding, positions, flows; deposits/withdrawals excluded from return | No private account ledger or flow-adjusted return calculation | Add an export ingestion and reconciliation workflow before claiming account performance |
| Opening timing | 15–20 minutes before U.S. regular open; premarket context for the session opening today | Completed crypto day summary | Add scheduling/activation semantics and distinguish the Binance reference day from the U.S. session date |
| Closing timing | Normally 15–20 minutes after 4:00 p.m. ET; if not closed, offer an intraday cut | Completed crypto day report | Validate session state; provide partial Binance day and provisional/official equity close state |
| Closing scorecard | Compare the latest same-date opening forecast with actual results, if present | Integrated: integrity-checks the same-date opening evidence manifest and compares prior-day range references with closing-day OHLC; no opening report is explicitly not applicable | Verify scorecard behavior on final CI head; expand only if the original source requires additional forecast fields |
| Intraday market narrative | Chronological session evolution, premarket/regular/postmarket state, daily move vs rolling 24h | Crypto candle charts and conditional scenarios | Add U.S. session-state context and distinguish local-day performance from rolling 24h |
| News/macro | Current, reliable sources, timestamps, catalysts and market relevance | Date-bounded RSS feed context; limited publisher coverage | Expand source coverage and preserve unavailable-source disclosures; headlines remain context, not causation |
| Audit | Original checklist, severity levels, ten desk-check cases, acceptance criteria, version/change log | PDF/evidence QA and raw candle recalculation; original parity not yet checked | Audit timezone, sessions, portfolio accounting, original edge-case matrix, source parity and package/version integrity |

## Per-skill source requirements to preserve

### `binance-apertura-mercado`

- Trigger phrases include “apertura de mercado”, “preapertura”, and “resumen antes de abrir”.
- Generate 15–20 minutes before the U.S. regular open.
- Binance reference period is exclusively the previous `America/Santo_Domingo` calendar day.
- U.S. premarket data refers to the session that will open on the local request date.
- Weekend/holiday: use the last completed U.S. equity session for index context, without changing the Binance local-calendar reference day.
- Include the specified index, volatility, futures, rates, dollar, commodities, Asia/Europe, economic/Fed/earnings/geopolitical catalysts, watchlist, crypto, scenarios, sources, cutoff and limitations.
- Binance account section must be marked unavailable if no authorized read-only connection or user export exists.

### `binance-cierre-mercado`

- Trigger phrases include “cierre de mercado”, “resumen de cierre”, and “cómo cerró el mercado”.
- Normally generate 15–20 minutes after 4:00 p.m. ET, with DST-aware conversion.
- U.S. equity data refers to the current local date's session, or the last completed session on weekends/holidays.
- Binance period is the current local calendar day. Before local midnight, it is an accumulated partial day with an exact cutoff, not a completed daily result.
- Include independent close confirmation where possible, previous-session comparison, breadth/sectors, and the same-date opening forecast scorecard only when that forecast exists.
- Do not count deposits as profit or withdrawals as losses; avoid double-counting unrealized PnL.

### `binance-momento-mercado`

- Trigger phrases include “estado del mercado ahora”, “resumen a las [hora]”, “snapshot intradía”, and “cómo va el mercado”.
- Window begins at local midnight and ends at the exact requested local cutoff; if omitted, resolve current local time at execution.
- Explicitly classify U.S. equities as premarket, regular session, or postmarket.
- Distinguish local-day change from rolling 24-hour change and never include post-cutoff events/data.
- No close prediction unless requested; if requested, label it as a scenario.

### `binance-revision-skills`

- Independently inspect the three operational skills, package integrity, semantic consistency, date/time rules, PnL rules, source traceability, and report layout.
- Required desk checks include the specified dates/times, weekends, holidays, U.S. DST, missing account access, external deposits/withdrawals, missing historical balances, and snapshot with omitted cutoff.
- Severity taxonomy: Crítico, Alto, Medio, Bajo.
- Acceptance requires differentiated triggers, consistent local-time windows, safe account access, no fabricated data, valid packages, and identifiable version/change history.
- Audit result must be Aprobado / Aprobado con reservas / No aprobado; unresolved critical/high findings cannot be passed.
- Original audit output structure and maintenance/versioning instructions must be retained.

## Implementation progress and remaining merge blockers

The feature branch now contains the following timezone work:
1. **Dominican local-day semantics:** opening, closing, and intraday acquisition resolve America/Santo_Domingo boundaries and convert them to UTC only at the Binance request boundary. PDFs, filenames, chart axes, and evidence manifests carry local and UTC timestamps.
2. **Partial closing day:** closing supports a current local-day cutoff; the requested cutoff is retained and any unfinished final candle is excluded. Historical closing dates without a cutoff use the completed local day.
3. **Intraday cutoff:** cutoff_local is supported, and an omitted cutoff resolves execution-time Dominican local time. A legacy UTC cutoff remains accepted for compatibility.
4. **Evidence traceability:** evidence schema v2 stores local-window metadata, PDF SHA-256, and a canonical raw-candle/warm-up evidence SHA-256. The audit independently verifies these fields.
5. **Regression coverage:** tests cover local-midnight conversion, previous-local-day opening, partial closing, optional intraday cutoff, cross-UTC-date windows, unfinished-candle exclusion, evidence-manifest filename binding, DST-aware ET/local session-time conversion, seven-point executive summaries, Spanish PDF marker validation, and Windows line-ending behavior. The full matrix passed on commit `03f6a8e5931f6a8da8a659b43dd4ee3d3b0cd386` in Actions run `43925472913`: Ubuntu/Windows × Python 3.11/3.12, with 27 Binance, 29 Local Engine, and 67 PDF Report Engine tests passing in each job. The Local Engine integration test generates opening, partial closing, and intraday (omitted-cutoff) reports and audits all three artifacts/manifests together. OPEN-01, CLOSE-01, INTRA-01 and LANG-01 pass; US-01/US-02 calendar behavior is implemented on the feature branch but must be rerun and independently reconciled on the final CI head.

Remaining source-derived blockers:
- **U.S. market context/prices:** index, VIX, Treasury, DXY, WTI, gold, breadth/sectors, and attributed market-price feeds are not integrated. The XNYS exchange calendar now handles holidays, early closes, DST-aware session boundaries, and premarket/regular/postmarket/closed classification; final CI and independent audit reconciliation remain required.
- **Private Binance account section:** no private-account connector or user-export parser exists. Reports explicitly mark account analytics unavailable and never represent public candles as account data.
- **Opening/closing timing and scorecard:** automated activation timing remains unimplemented. Same-date opening-to-closing range-scenario reconciliation is implemented when a valid opening manifest exists; no same-date opening report is explicitly marked not applicable.
- **Audit parity:** a per-skill results table, desk-check matrix with expected/observed evidence and impact, Spanish severity/verdict, changes applied, pending items, files reviewed, and version/change history have been added. Weekend/holiday, U.S. DST, private-account/flow, activation dispatch, and scorecard cases remain unresolved. The original archive and extracted-file hashes are recorded, but the original ZIP payloads are not embedded in the repository; package integrity therefore remains NOT VERIFIED. Full source-skill audit parity is not yet achieved.
- **Spanish PDF parity:** the three operational composers and the audit PDF have been localized. LANG-01 verifies Spanish markers in all three operational PDF types; final artifact-level verification remains pending.

## Merge gate

Do not merge Phase 3 until any subsequent code changes pass the full cross-platform CI matrix, the remaining source-derived gaps are either implemented or clearly disclosed in both reports and audit, and no unresolved Crítico/Alto temporal or data-integrity findings remain.

This document records source-derived requirements and the observed code gap. It does not claim that the listed adaptations have already been implemented.


## Additional source-parity finding
- The original three operational skills specify Spanish-language PDF reports. The opening, closing, and intraday composers and the audit PDF have been localized. LANG-01 requires all three operational PDF types to pass independent Spanish-marker QA; the PDF marker regression tests passed in run `43921585562`.
- The original intraday filename is `snapshot-mercado_YYYY-MM-DD_HH-mm.pdf` (underscore after `mercado`); the implementation and tests use this exact contract. Opening filenames use the local request date, while the report body and evidence manifest retain the previous local Binance reference date.
- Original archive SHA-256 and extracted SKILL.md SHA-256 values are recorded in `docs/original-skills-source/manifest.json`. The ZIP payloads are not embedded in the repository, so runtime package-integrity status remains NOT VERIFIED.
