# SEC EDGAR Company Facts adapter

## Provider and access model

The adapter in `report_engine/sec_edgar.py` uses the public SEC EDGAR Company Facts endpoint:

`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

The SEC states that its submissions and XBRL data APIs are public and do not require API keys. Automated requests must declare a descriptive User-Agent; SEC fair-access guidance states a maximum of 10 requests per second. MASTER ARSENAL therefore requires an explicit User-Agent supplied through the constructor or `MASTER_ARSENAL_SEC_USER_AGENT`; it does not invent a contact identity or store credentials.

## Supported metrics

The first implementation extracts a bounded set of USD facts where the issuer reports a supported US-GAAP concept:

- Revenue (alternative concepts are tried in order; never summed together).
- Operating income.
- Net income.
- Operating cash flow.
- Total assets.
- Cash and cash equivalents.

Duration metrics are filtered to annual (300–400 days) or quarterly (70–110 days) reporting periods. Instant metrics use point-in-time observations. Unsupported/missing concepts are listed as missing and are never replaced with zero.

## Identity and provenance

The caller must provide an exact CIK and the already validated instrument key. The adapter does not map ticker symbols to CIKs. It verifies that the returned CIK matches the requested CIK, retains the SEC entity name, taxonomy concept, form, accession number, filing date, period end, source URL, and retrieval timestamp.

10-K, 20-F, and 40-F facts are classified as audited-financial-statement sources; 10-Q, 6-K, and 8-K facts are classified as issuer disclosures. These labels identify filing types and do not replace analyst review of the actual filing. The adapter does not infer that every XBRL fact is audited simply because it is published by the SEC.

## Deliberate limitations

- No ticker-to-CIK resolution or issuer/instrument matching.
- No total-debt aggregation, free-cash-flow calculation, valuation multiples, peer analysis, or financial restatement reconciliation.
- No attempt to add alternative XBRL concepts together.
- No claim that missing XBRL concepts equal zero.
- No live API call is part of the offline test suite; tests use deterministic fixtures and an injected transport.
- The adapter does not parse narrative 10-K/10-Q sections such as risk factors or management discussion.
- Financial metrics need context: fiscal calendars, accounting policies, discontinued operations, segment reporting, restatements, currency and unit differences, and one-off items can materially affect interpretation.

## Runtime configuration

Set `MASTER_ARSENAL_SEC_USER_AGENT` to a descriptive application name and responsible contact string before using the default HTTP transport. Do not put secrets or personal account credentials in this value. If no valid User-Agent is configured, the adapter fails closed.

## Verification

Offline tests cover CIK normalization and response matching, User-Agent propagation, annual/quarterly period filtering, point-in-time facts, source attribution, and missing-value behavior. Live endpoint availability and the current SEC response are not certified by those offline tests.
