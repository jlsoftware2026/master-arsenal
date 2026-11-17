"""Tests for transparent token supply, unlock, and holder calculations."""
import unittest

from report_engine.tokenomics import calculate_tokenomics

KEY = "crypto|abc|usd|ethereum|0xabc"
CUTOFF = "2026-11-17T16:00:00Z"


def obs(field, value, **extra):
    result = {
        "instrument_key": KEY, "value": str(value), "unit": "token",
        "as_of_utc": "2026-11-17T15:00:00Z",
        "source_name": "Protocol documentation",
        "source_url": "https://example.org/tokenomics",
        "source_reference": "Token supply table, section 2",
        "fact_id": field,
    }
    result.update(extra)
    return result


def unlock(event_id, amount, at):
    return {
        "event_id": event_id, "amount": str(amount), "unlock_at_utc": at,
        "source_name": "Vesting schedule", "source_url": "https://example.org/vesting",
        "source_reference": "Vesting schedule row " + event_id,
        "as_of_utc": "2026-11-17T15:00:00Z",
    }


class TokenomicsTests(unittest.TestCase):
    def test_supply_ratios_and_fdv_are_calculated_from_explicit_inputs(self):
        result = calculate_tokenomics(
            instrument_key=KEY, as_of_utc=CUTOFF,
            circulating_supply=obs("circ", 60), total_supply=obs("total", 80),
            max_supply=obs("max", 100),
            price={**obs("price", "2.50"), "quote_currency": "USD"},
        )
        self.assertEqual(result["supply"]["circulating_pct_of_total"], "75.000000")
        self.assertEqual(result["supply"]["circulating_pct_of_max"], "60.000000")
        self.assertEqual(result["valuation"]["market_cap"], "150.00")
        self.assertEqual(result["valuation"]["fully_diluted_valuation"], "250.00")

    def test_unlocks_are_bucketed_by_30_90_and_365_day_horizons(self):
        result = calculate_tokenomics(
            instrument_key=KEY, as_of_utc=CUTOFF,
            circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
            unlock_events=[
                unlock("u30", 5, "2026-12-01T00:00:00Z"),
                unlock("u90", 10, "2027-01-15T00:00:00Z"),
                unlock("u365", 15, "2027-10-01T00:00:00Z"),
                unlock("later", 20, "2028-01-01T00:00:00Z"),
            ],
        )
        self.assertEqual(result["unlock_schedule"]["known_unlocks_pct_of_circulating"]["30d"], "5.000000")
        self.assertEqual(result["unlock_schedule"]["known_unlocks_pct_of_circulating"]["90d"], "15.000000")
        self.assertEqual(result["unlock_schedule"]["known_unlocks_pct_of_circulating"]["365d"], "30.000000")
        self.assertEqual(result["unlock_schedule"]["known_future_unlock_total"], "50")

    def test_unlock_events_at_or_before_cutoff_are_excluded(self):
        result = calculate_tokenomics(
            instrument_key=KEY, as_of_utc=CUTOFF,
            circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
            unlock_events=[unlock("past", 10, "2026-11-17T15:00:00Z")],
        )
        self.assertEqual(result["unlock_schedule"]["known_future_unlock_total"], "0")

    def test_holder_concentration_is_explicitly_partial_when_coverage_is_below_100(self):
        holders = [
            {"holder_id": "wallet-a", "instrument_key": KEY, "balance": "20", "category": "treasury",
             "as_of_utc": "2026-11-17T15:00:00Z", "source_name": "Explorer",
             "source_url": "https://example.org/holders", "source_reference": "Top holders snapshot"},
            {"holder_id": "wallet-b", "instrument_key": KEY, "balance": "10", "category": "exchange",
             "as_of_utc": "2026-11-17T15:00:00Z", "source_name": "Explorer",
             "source_url": "https://example.org/holders", "source_reference": "Top holders snapshot"},
        ]
        result = calculate_tokenomics(
            instrument_key=KEY, as_of_utc=CUTOFF,
            circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
            holder_balances=holders, holder_coverage_pct=40,
        )
        self.assertEqual(result["holder_concentration"]["status"], "partial")
        self.assertEqual(result["holder_concentration"]["top_1_observed_pct"], "20.000000")
        self.assertEqual(result["holder_concentration"]["top_5_observed_pct"], "30.000000")

    def test_missing_unlocks_and_holder_data_are_not_reported_as_zero(self):
        result = calculate_tokenomics(
            instrument_key=KEY, as_of_utc=CUTOFF,
            circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
        )
        self.assertEqual(result["unlock_schedule"]["status"], "not_supplied")
        self.assertIsNone(result["unlock_schedule"]["events"])
        self.assertEqual(result["holder_concentration"]["status"], "not_assessed")
        self.assertIsNone(result["holders"])

    def test_rejects_supply_from_another_instrument(self):
        wrong = obs("circ", 100, instrument_key="crypto|other|usd")
        with self.assertRaisesRegex(ValueError, "instrument_key"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=wrong, total_supply=obs("total", 150),
            )

    def test_rejects_future_dated_supply_or_price(self):
        future = obs("circ", 100, as_of_utc="2026-11-17T16:01:00Z")
        with self.assertRaisesRegex(ValueError, "after the analysis cutoff"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=future, total_supply=obs("total", 150),
            )

    def test_rejects_misaligned_supply_and_price_observations(self):
        with self.assertRaisesRegex(ValueError, "same UTC calendar date"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 60),
                total_supply=obs("total", 80, as_of_utc="2026-11-16T15:00:00Z"),
            )
        with self.assertRaisesRegex(ValueError, "same UTC calendar date"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 60), total_supply=obs("total", 80),
                price={**obs("price", "2.50", as_of_utc="2026-11-16T15:00:00Z"), "quote_currency": "USD"},
            )

    def test_rejects_supply_ordering_inconsistency(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 110), total_supply=obs("total", 100),
            )
        with self.assertRaisesRegex(ValueError, "cannot be below"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 60), total_supply=obs("total", 80),
                max_supply=obs("max", 70),
            )

    def test_rejects_duplicate_unlock_or_holder_ids(self):
        event = unlock("same", 1, "2026-12-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "unique"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
                unlock_events=[event, event],
            )

    def test_rejects_future_observed_unlock_schedule(self):
        event = unlock("u1", 10, "2026-12-01T00:00:00Z")
        event["as_of_utc"] = "2026-11-17T16:01:00Z"
        with self.assertRaisesRegex(ValueError, "after the analysis cutoff"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
                unlock_events=[event],
            )

    def test_rejects_unlocks_without_source_provenance(self):
        event = {"event_id": "u1", "amount": 10, "unlock_at_utc": "2026-12-01T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "source_name"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
                unlock_events=[event],
            )

    def test_rejects_holder_balances_above_circulating_supply(self):
        holders = [{
            "holder_id": "wallet-a", "instrument_key": KEY, "balance": 101,
            "category": "unknown", "as_of_utc": "2026-11-17T15:00:00Z",
            "source_name": "Explorer", "source_url": "https://example.org/holders",
            "source_reference": "Top holders snapshot",
        }]
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
                holder_balances=holders, holder_coverage_pct=50,
            )

    def test_holder_list_requires_explicit_coverage(self):
        with self.assertRaisesRegex(ValueError, "holder_coverage_pct"):
            calculate_tokenomics(
                instrument_key=KEY, as_of_utc=CUTOFF,
                circulating_supply=obs("circ", 100), total_supply=obs("total", 150),
                holder_balances=[],
            )


if __name__ == "__main__":
    unittest.main()
