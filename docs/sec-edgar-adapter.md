# SEC EDGAR Company Facts adapter

## Provider and access model

The adapter in `report_engine/sec_edgar.py` uses the public SEC EDGAR Company Facts endpoint:

`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

The SEC states that its submissions and XBRL data APIs are public and do not require API keys. Automated requests must declare a descriptive User-Agent; SEC fair-access guidance states a maximum of 10 requests per second. MASTER ARSENAL therefore requires an explicit User-Agent supplied through the constructor or `MASTER_ARSENAL_SEC_USER_AGENT`; it does not invent a contact identity or store credentials.

## Supported metrics

The adapter extracts a bounded set of USD facts where the issuer reports a supported US-GAAP concept:

- Revenue (alternative concepts are tried in order; never summed together).
- Gross profit, operating income, and net income.
- Capital expenditures and operating cash flow.
- Total assets, current assets, current liabilities, stockholders' equity, and cash/equivalents.

Duration metrics are filtered to annual (300–400 days) or quarterly (70–110 days) reporting periods. Instant metrics use point-in-time observations. Unsupported/missing concepts are listed as missing and are never replaced with zero.

The derived-ratio engine in `report_engine/fundamentals.py` calculates same-period gross/operating/net/cash-flow margins, free cash flow and its margin, current ratio, cash-to-current-liabilities, and period-end ROA/ROE proxies. It requires matching period ends and currencies, preserves the contributing fact IDs and formula, and skips ambiguous/missing/zero-denominator inputs. ROA/ROE use period-end rather than average balances. No growth rates, total-debt aggregation, valuation multiples, or peer comparisons are calculated.

## Identity and provenance

The adapter supports two identity paths. The explicit path accepts a caller-supplied CIK and the already validated instrument key, then verifies that the returned CIK matches the request. The automatic listed-equity path resolves the exact ticker, exchange, and issuer name against the SEC `company_tickers_exchange.json` directory before requesting Company Facts. The lookup requires all three identity fields, rejects exchange mismatches, refuses ambiguous matches, and withholds a CIK when the SEC issuer name does not match the candidate issuer after conservative corporate-suffix normalization. It is restricted to `listed_equity`; tokenized equity continues to require an explicit CIK and documented underlying-issuer mapping. Both paths retain the SEC entity name, taxonomy concept, form, accession number, filing date, period end, source URL, and retrieval timestamp.

10-K, 20-F, and 40-F facts are classified as audited-financial-statement sources; 10-Q, 6-K, and 8-K facts are classified as issuer disclosures. These labels identify filing types and do not replace analyst review of the actual filing. The adapter does not infer that every XBRL fact is audited simply because it is published by the SEC.

## Deliberate limitations

- The SEC itself periodically updates ticker associations but does not guarantee their accuracy or scope. A resolved directory row is a candidate mapping, not proof of security ownership, legal identity, or current exchange listing.
- Exact ticker/exchange/name matching is intentionally conservative; a mismatch or ambiguous record requires manual issuer/CIK review.
- The mapping directory is downloaded for each lookup; persistent caching and historical ticker mappings are not implemented.
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


## Automatic listed-equity ticker resolution

The opportunity workflow may use:

`sec_edgar: { "resolve_ticker": true, "period": "annual" }`

The resolver derives the ticker, exchange, and issuer name only from the normalized `listed_equity` instrument record. It queries the official SEC exchange-aware directory at `https://www.sec.gov/files/company_tickers_exchange.json` with the configured SEC User-Agent. A single exact ticker/exchange/issuer match is required before the CIK is used for Company Facts. `not_found`, `issuer_name_mismatch`, and `ambiguous` results fail closed; the workflow does not guess or select the first result.

For a manually confirmed CIK (including tokenized-equity underlying issuers), retain the explicit configuration:

`sec_edgar: { "cik": "0000000123", "issuer_name": "Example Corp", "period": "annual" }`

Do not provide both `cik` and `resolve_ticker=true`. The lookup records the directory URL, retrieval timestamp, exact exchange, issuer name, and limitations in provider status and the opportunity manifest.

The SEC documents both the exchange-aware ticker map and its limitation that ticker associations are periodically updated but not guaranteed for accuracy or scope: [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). Offline fixtures validate parsing and fail-closed matching; they do not certify live endpoint availability or issuer identity.
