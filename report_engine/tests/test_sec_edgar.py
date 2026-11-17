"""Offline tests for the read-only SEC EDGAR Company Facts adapter."""
from datetime import datetime, timezone
import unittest

from report_engine.sec_edgar import SECEdgarCompanyFacts, _normalize_cik

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)
KEY = "listed_equity|exm|usd|example corp|nasdaq"


def companyfacts_fixture():
    return {
        "cik": 123,
        "entityName": "EXAMPLE CORP",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [
                        {"val": 1200, "start": "2025-01-01", "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                        {"val": 900, "start": "2025-01-01", "end": "2025-09-30",
                         "filed": "2025-10-30", "form": "10-Q", "accn": "0000000001-25-000003"},
                    ]}
                },
                "OperatingIncomeLoss": {
                    "units": {"USD": [
                        {"val": 200, "start": "2025-01-01", "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
                "GrossProfit": {
                    "units": {"USD": [
                        {"val": 600, "start": "2025-01-01", "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": [
                        {"val": 50, "start": "2025-01-01", "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
                "AssetsCurrent": {
                    "units": {"USD": [
                        {"val": 700, "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
                "LiabilitiesCurrent": {
                    "units": {"USD": [
                        {"val": 300, "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
                "StockholdersEquity": {
                    "units": {"USD": [
                        {"val": 500, "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
                "Assets": {
                    "units": {"USD": [
                        {"val": 5000, "end": "2025-12-31",
                         "filed": "2026-02-20", "form": "10-K", "accn": "0000000001-26-000001"},
                    ]}
                },
            }
        },
    }


class SECEdgarTests(unittest.TestCase):
    def test_cik_is_zero_padded(self):
        self.assertEqual(_normalize_cik("123"), "0000000123")

    def test_invalid_cik_rejected(self):
        for value in ("abc", "0", "-1", "10000000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _normalize_cik(value)

    def test_user_agent_is_required(self):
        with self.assertRaisesRegex(ValueError, "User-Agent is required"):
            SECEdgarCompanyFacts(user_agent="")

    def test_fetch_uses_explicit_user_agent_and_exact_cik(self):
        seen = {}
        def fake(url, headers, timeout):
            seen.update(url=url, headers=headers, timeout=timeout)
            return companyfacts_fixture()
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org", fetch_json=fake)
        result = adapter.fetch_facts(cik="123", instrument_key=KEY,
                                     issuer_name="Example Corp", retrieved_at=NOW)
        self.assertIn("CIK0000000123.json", seen["url"])
        self.assertEqual(seen["headers"]["User-Agent"], "MASTER ARSENAL contact@example.org")
        self.assertEqual(result["provider_entity_name"], "EXAMPLE CORP")

    def test_annual_duration_metric_selects_annual_filing(self):
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: companyfacts_fixture())
        result = adapter.fetch_facts(cik=123, instrument_key=KEY,
                                     issuer_name="Example Corp", retrieved_at=NOW)
        revenue = next(f for f in result["facts"] if f["dimension"] == "revenue")
        self.assertEqual(revenue["value"], "1200")
        self.assertIn("form 10-K", revenue["source_reference"])

    def test_instant_metric_is_selected(self):
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: companyfacts_fixture())
        result = adapter.fetch_facts(cik=123, instrument_key=KEY,
                                     issuer_name="Example Corp", retrieved_at=NOW)
        assets = next(f for f in result["facts"] if f["dimension"] == "total_assets")
        self.assertEqual(assets["value"], "5000")

    def test_extracts_additional_margin_and_liquidity_inputs(self):
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: companyfacts_fixture())
        result = adapter.fetch_facts(cik=123, instrument_key=KEY,
                                     issuer_name="Example Corp", retrieved_at=NOW)
        dimensions = {fact["dimension"] for fact in result["facts"]}
        self.assertTrue({"gross_profit", "capital_expenditures", "current_assets",
                         "current_liabilities", "stockholders_equity"}.issubset(dimensions))

    def test_missing_concepts_are_not_zero_filled(self):
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: companyfacts_fixture())
        result = adapter.fetch_facts(cik=123, instrument_key=KEY,
                                     issuer_name="Example Corp", retrieved_at=NOW)
        self.assertIn("net_income", result["missing_dimensions"])
        self.assertFalse(any(f["dimension"] == "net_income" for f in result["facts"]))

    def test_quarterly_filter_does_not_use_ytd_values(self):
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: companyfacts_fixture())
        result = adapter.fetch_facts(cik=123, instrument_key=KEY,
                                     issuer_name="Example Corp", period="quarterly",
                                     retrieved_at=NOW)
        self.assertIn("revenue", result["missing_dimensions"])

    def test_rejects_missing_entity_metadata(self):
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: {"facts": {}})
        with self.assertRaisesRegex(ValueError, "entityName"):
            adapter.fetch_facts(cik=123, instrument_key=KEY,
                                issuer_name="Example Corp", retrieved_at=NOW)

    def test_rejects_response_for_different_cik(self):
        fixture = companyfacts_fixture()
        fixture["cik"] = 999
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org",
                                       fetch_json=lambda *args: fixture)
        with self.assertRaisesRegex(ValueError, "does not match"):
            adapter.fetch_facts(cik=123, instrument_key=KEY,
                                issuer_name="Example Corp", retrieved_at=NOW)

    def test_caller_mapping_is_preserved_without_ticker_resolution(self):
        seen = {}
        def fake(url, headers, timeout):
            seen["url"] = url
            return companyfacts_fixture()
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org", fetch_json=fake)
        result = adapter.fetch_facts(cik=123, instrument_key="user-supplied-key",
                                     issuer_name="Example Corp", retrieved_at=NOW)
        self.assertEqual(result["instrument_key"], "user-supplied-key")
        self.assertTrue(seen["url"].endswith("CIK0000000123.json"))


    def test_resolves_exact_ticker_exchange_and_issuer_name(self):
        seen = {}
        fixture = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [
                [320193, "APPLE INC.", "AAPL", "Nasdaq"],
                [1045810, "NVIDIA CORP", "NVDA", "Nasdaq"],
            ],
        }
        def fake(url, headers, timeout):
            seen.update(url=url, headers=headers)
            return fixture
        adapter = SECEdgarCompanyFacts("MASTER ARSENAL contact@example.org", fetch_json=fake)
        result = adapter.resolve_ticker(
            ticker="aapl", exchange="NASDAQ", issuer_name="Apple Inc",
            retrieved_at=NOW,
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["cik"], "0000320193")
        self.assertEqual(result["issuer_name"], "APPLE INC.")
        self.assertEqual(seen["url"], "https://www.sec.gov/files/company_tickers_exchange.json")
        self.assertEqual(seen["headers"]["User-Agent"], "MASTER ARSENAL contact@example.org")

    def test_ticker_lookup_does_not_ignore_exchange(self):
        fixture = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[123, "EXAMPLE CORP", "EXM", "Nasdaq"]],
        }
        adapter = SECEdgarCompanyFacts(
            "MASTER ARSENAL contact@example.org", fetch_json=lambda *args: fixture
        )
        result = adapter.resolve_ticker(
            ticker="EXM", exchange="NYSE", issuer_name="Example Corp", retrieved_at=NOW
        )
        self.assertEqual(result["status"], "not_found")
        self.assertNotIn("cik", result)

    def test_ticker_lookup_rejects_issuer_name_mismatch(self):
        fixture = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[123, "OTHER COMPANY INC", "EXM", "Nasdaq"]],
        }
        adapter = SECEdgarCompanyFacts(
            "MASTER ARSENAL contact@example.org", fetch_json=lambda *args: fixture
        )
        result = adapter.resolve_ticker(
            ticker="EXM", exchange="Nasdaq", issuer_name="Example Corp", retrieved_at=NOW
        )
        self.assertEqual(result["status"], "issuer_name_mismatch")
        self.assertNotIn("cik", result)

    def test_duplicate_exact_directory_records_are_ambiguous(self):
        fixture = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [
                [123, "EXAMPLE CORP", "EXM", "Nasdaq"],
                [456, "EXAMPLE CORP", "EXM", "Nasdaq"],
            ],
        }
        adapter = SECEdgarCompanyFacts(
            "MASTER ARSENAL contact@example.org", fetch_json=lambda *args: fixture
        )
        result = adapter.resolve_ticker(
            ticker="EXM", exchange="Nasdaq", issuer_name="Example Corp", retrieved_at=NOW
        )
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertNotIn("cik", result)

    def test_ticker_lookup_requires_exact_identity_fields(self):
        adapter = SECEdgarCompanyFacts(
            "MASTER ARSENAL contact@example.org", fetch_json=lambda *args: {}
        )
        for fields in ({"ticker": "EXM"}, {"ticker": "EXM", "exchange": "Nasdaq"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                adapter.resolve_ticker(**fields)

    def test_ticker_lookup_rejects_malformed_directory(self):
        adapter = SECEdgarCompanyFacts(
            "MASTER ARSENAL contact@example.org",
            fetch_json=lambda *args: {"fields": ["ticker"], "data": []},
        )
        with self.assertRaisesRegex(ValueError, "required columns"):
            adapter.resolve_ticker(
                ticker="EXM", exchange="Nasdaq", issuer_name="Example Corp", retrieved_at=NOW
            )



if __name__ == "__main__":
    unittest.main()
