# Binance API contract

## Official references
- [Binance Spot REST API](https://developers.binance.com/en/docs/products/spot/rest-api)
- [Binance USDⓈ-M Futures documentation](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/Introduction)
- [Binance API catalog](https://developers.binance.com/en/docs/catalog)

The endpoint catalog and parameters can change. Re-check the official documentation before production releases.

## Hosts and access
- Spot public market data: https://data-api.binance.vision
- USDⓈ-M Futures public market data: https://fapi.binance.com
- All current engine requests are HTTP GET only. No API key, secret, signature, account endpoint, order endpoint, or trading method is implemented.

## Implemented endpoints
| Data | Market | Endpoint |
|---|---|---|
| Server time | Spot | GET /api/v3/time |
| Server time | USDⓈ-M | GET /fapi/v1/time |
| Exchange information | Spot / USDⓈ-M | GET /api/v3/exchangeInfo / GET /fapi/v1/exchangeInfo |
| Candles | Spot / USDⓈ-M | GET /api/v3/klines / GET /fapi/v1/klines |
| 24-hour ticker | Spot / USDⓈ-M | GET /api/v3/ticker/24hr / GET /fapi/v1/ticker/24hr |
| Mark/index premium | USDⓈ-M | GET /fapi/v1/premiumIndex |
| Current open interest | USDⓈ-M | GET /fapi/v1/openInterest |
| Historical open interest | USDⓈ-M | GET /futures/data/openInterestHist |
| Funding history | USDⓈ-M | GET /fapi/v1/fundingRate |
| Global long/short account ratio | USDⓈ-M | GET /futures/data/globalLongShortAccountRatio |
| Basis | USDⓈ-M | GET /futures/data/basis |
| Mark-price candles | USDⓈ-M | GET /fapi/v1/markPriceKlines |
| Index-price candles | USDⓈ-M | GET /fapi/v1/indexPriceKlines |

Historical open-interest and positioning statistics are time-limited by Binance (currently documented as latest 30 days for relevant statistics endpoints). The snapshot records endpoint errors as unavailable data; it does not fabricate or backfill missing values.

## Request behavior
- Timestamps are sent and interpreted as Unix milliseconds; returned candle times are timezone-aware UTC.
- Historical kline windows are half-open [start, end); request endTime is end_ms - 1 because Binance uses an inclusive end boundary.
- Spot kline page limit is capped at 1,000; USDⓈ-M Futures kline page limit is capped at 1,500.
- USDⓈ-M Futures historical kline requests are chunked to at most 200 days per request.
- Pagination deduplicates by candle open time, requires forward progress, and reports page count and completeness.
- HTTP 418/429 and transient 5xx/network errors receive bounded retries. Retry-After is honored when present; otherwise exponential backoff is used.
- Successful responses retain available used-weight headers and retrieval timestamps.

## Caveats
- A successful HTTP response does not prove the data is complete, fresh enough for a specific report, or free of candle gaps. Validation warnings must be reviewed by the report skill.
- A live endpoint can reject a symbol, period, or market-specific parameter. Such a result must remain explicitly unavailable.
- The engine does not currently implement persistence, WebSocket streaming, liquidation feeds, or a PDF renderer.
