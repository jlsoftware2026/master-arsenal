# Original Claude Skills — Phase 3 Reconciliation

**Source of truth:** the four user-supplied Claude `.skill` packages received on 2026-11-16.  
**Target branch:** `feature/phase-3-pdf-report-engine`.  
**Status:** reconciliation in progress; Phase 3 is not merge-ready.

## Executive finding

The current implementation is a strong PDF/data-engine foundation, but it is not yet behaviorally equivalent to the original skills. In particular, the report windows are UTC calendar days while all three original reporting skills define calendar days in `America/Santo_Domingo`. The original skills also specify broader U.S. equity-market coverage and private Binance account analysis that the current public-market-data-only engine cannot claim to provide.

## Requirement comparison

| Area | Original Claude requirement | Current Phase 3 implementation | Required adaptation |
|---|---|---|---|
| Primary timezone | `America/Santo_Domingo`; show local timestamps and ET where relevant | UTC-day windows and UTC-oriented report labels | Use IANA timezone conversion for every report boundary, display local time and UTC provenance |
| Opening Binance window | Previous local calendar day, 00:00–23:59:59 | Previous completed UTC day | Select previous Dominican calendar date and convert both local-midnight boundaries to UTC |
| Closing Binance window | Current local calendar day; partial until local midnight | Requires a completed UTC day | Support partial current local-day data after Wall Street close; label exact local cutoff and never call it a full day |
| Intraday window | Local midnight through exact requested local cutoff; use current local time if omitted | Explicit UTC cutoff and UTC midnight | Accept/resolve local cutoff, convert local midnight and cutoff to UTC, exclude post-cutoff candles |
| U.S. market session | 9:30 a.m.–4:00 p.m. ET with DST-aware conversion; weekends/holidays handled | Not represented as a full U.S. cash-session calendar | Add an exchange-calendar/session-state layer and report last completed session on holidays/weekends |
| U.S. market coverage | S&P 500, Nasdaq Composite and/or Nasdaq 100, Dow, Russell 2000, VIX, futures, Treasury 10Y, DXY, WTI, gold, sectors, breadth, leaders/laggards | Binance BTC/ETH candles, optional USD-M derivatives, selected RSS feeds | Add attributed public-market data adapters; explicitly disclose unavailable series rather than omit silently |
| Binance private account | Read-only connector or user exports; otherwise mark account unavailable | Public Binance REST only | Keep private-account section explicitly unavailable until a supported read-only connector/export parser exists; never imply public candles are account data |
| Portfolio accounting | Equity/balance, realized/unrealized PnL, fees/funding, positions, flows; deposits/withdrawals excluded from return | No private account ledger or flow-adjusted return calculation | Add an export ingestion and reconciliation workflow before claiming account performance |
| Opening timing | 15–20 minutes before U.S. regular open; premarket context for the session opening today | Completed crypto day summary | Add scheduling/activation semantics and distinguish the Binance reference day from the U.S. session date |
| Closing timing | Normally 15–20 minutes after 4:00 p.m. ET; if not closed, offer an intraday cut | Completed crypto day report | Validate session state; provide partial Binance day and provisional/official equity close state |
| Closing scorecard | Compare the latest same-date opening forecast with actual results, if present | No persisted forecast linkage | Add same-date opening-report lookup and scorecard; omit if no forecast exists |
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
- Severity taxonomy: Critical, High, Medium, Low.
- Acceptance requires differentiated triggers, consistent local-time windows, safe account access, no fabricated data, valid packages, and identifiable version/change history.
- Audit result must be Aprobado / Aprobado con reservas / No aprobado; unresolved critical/high findings cannot be passed.
- Original audit output structure and maintenance/versioning instructions must be retained.

## Critical implementation blockers before merge

1. **Dominican local-day semantics:** the current acquisition, report validation, filenames/date labels, manifests, and audit are UTC-calendar-based. All must use the same explicitly recorded local reporting date and its UTC-converted half-open interval.
2. **Closing partial-day support:** the current completed-day acquisition rejects an unfinished day; original closing skill explicitly requires a partial local-day snapshot when run after the U.S. close but before local midnight.
3. **Intraday local cutoff:** the current handler requires `cutoff_utc`; it does not implement the original local-time activation/default behavior.
4. **U.S. market context:** current report evidence does not include the full required equity indices, VIX, Treasury, DXY, WTI, gold, breadth/sectors or exchange-calendar handling.
5. **Private account section:** current implementation has no Binance private-account connection or export parser. It must render an explicit “not available” section and must not imply that public BTC/ETH market candles represent the user's account.
6. **Closing scorecard:** no linkage currently compares an opening forecast with the same-date close.
7. **Audit parity:** the audit must implement the original desk-check matrix and verdict/severity rules; existing PDF/raw-candle checks alone do not establish source-skill compliance.

## Merge gate

Do not merge Phase 3 until blockers 1–3 are implemented and regression-tested, blockers 4–6 are either implemented or explicitly represented as unavailable/not verified in the PDF and audit, all four workflows pass the cross-platform CI matrix, and the audit reports no unresolved critical/high temporal or data-integrity findings.

This document records source-derived requirements and the observed code gap. It does not claim that the listed adaptations have already been implemented.
