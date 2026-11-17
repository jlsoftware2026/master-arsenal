"""Tests for standalone pre-investment opportunity PDF composition."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from report_engine.instruments import build_instrument_record
from report_engine.opportunity import (
    audit_opportunity_manifest, build_opportunity_report_pdf, write_opportunity_manifest,
)
from report_engine.research import build_research_packet
from report_engine.scenarios import calculate_long_scenarios
from report_engine.position_sizing import calculate_cash_position_size
from report_engine.fundamentals import calculate_financial_ratios, calculate_valuation_multiples
from report_engine.peer_comparables import calculate_peer_comparables
from report_engine.tokenomics import calculate_tokenomics

NOW = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)
KEY = "listed_equity|exm|usd|example corp|nasdaq"


def report_fixture():
    instrument = build_instrument_record({
        "asset_class": "listed_equity", "name": "Example Corp",
        "symbol": "EXM", "quote_currency": "USD",
        "issuer": "Example Corp", "exchange": "NASDAQ",
    })
    facts = [{
        "fact_id": "fact-1", "instrument_key": KEY,
        "dimension": "revenue", "label": "FY revenue", "value": "1000000",
        "unit": "USD", "source_kind": "issuer_disclosure",
        "evidence_quality": "verified_source", "source_name": "Issuer filing",
        "source_url": "https://example.com/filing",
        "source_reference": "FY2025 revenue note",
        "as_of_utc": "2026-11-17T15:00:00Z",
        "retrieved_at_utc": "2026-11-17T15:30:00Z",
    }]
    packet = build_research_packet(KEY, facts, now=NOW,
                                   freshness_limits_hours={"revenue": 24})
    scenarios = calculate_long_scenarios(
        instrument_key=KEY, quote_currency="USD",
        reference_entry_price=100, invalidation_price=80,
        bull_case={"price": 150, "assumptions": "Launch succeeds."},
        base_case={"price": 115, "assumptions": "Adoption is moderate."},
        bear_case={"price": 65, "assumptions": "Launch is delayed."},
        invalidation_basis="Thesis fails below 80.", horizon="12 months",
        as_of_utc="2026-11-17T16:00:00Z",
    )
    sizing = calculate_cash_position_size(
        instrument_key=KEY, as_of_utc="2026-11-17T16:00:00Z",
        entry_price_basis="Hypothetical reference price.",
        invalidation_basis="Thesis invalidation assumption.",
        available_capital=10000, quote_currency="USD",
        entry_price=100, invalidation_price=80,
        risk_budget_pct=1, max_allocation_pct=50,
    )
    return {
        "generated_at_utc": "2026-11-17T16:00:00Z",
        "freshness_limits_hours": {"revenue": 24},
        "instrument": instrument, "research_packet": packet,
        "fundamental_metrics": calculate_financial_ratios(packet["facts"], instrument_key=KEY),
        "conclusion": "potential_candidate_for_further_diligence",
        "executive_summary": ["Evidence is preliminary.", "Further diligence is required."],
        "scenarios": scenarios, "position_sizing": sizing,
        "risks": ["Competition may pressure margins."],
        "thesis_invalidation": ["Clinical or commercial milestones fail."],
        "provider_status": {"sec": "fixture evidence only"},
    }


class OpportunityPdfTests(unittest.TestCase):
    def test_builds_valid_opportunity_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = build_opportunity_report_pdf(report_fixture(), directory)
            self.assertTrue(path.is_file())
            self.assertEqual(path.suffix, ".pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
            self.assertIn("oportunidad-listed_equity-EXM", path.name)


    def test_conflicting_source_values_are_disclosed_in_opportunity_pdf(self):
        report = report_fixture()
        first = report["research_packet"]["facts"][0]
        second = dict(first)
        second.update({
            "fact_id": "fact-002", "value": "1300000",
            "source_name": "Second issuer disclosure",
            "source_url": "https://example.org/second-filing",
            "source_reference": "FY2025 revenue reconciliation",
        })
        report["research_packet"] = build_research_packet(
            KEY, [first, second], now=NOW,
            freshness_limits_hours={"revenue": 24},
        )
        report["fundamental_metrics"] = calculate_financial_ratios(
            report["research_packet"]["facts"], instrument_key=KEY
        )
        report["conclusion"] = "insufficient_evidence"
        with tempfile.TemporaryDirectory() as directory:
            path = build_opportunity_report_pdf(report, directory)
            import pymupdf as fitz
            with fitz.open(path) as document:
                extracted = " ".join(page.get_text("text") for page in document)
        self.assertIn("Conflictos de evidencia no resueltos", extracted)
        self.assertIn("1300000", extracted)
        self.assertIn("1000000", extracted)


    def test_crypto_opportunity_pdf_and_audit_recalculate_tokenomics(self):
        report = report_fixture()
        instrument = build_instrument_record({
            "asset_class": "crypto", "name": "Example Token",
            "symbol": "EXM", "quote_currency": "USD",
            "network": "Ethereum", "contract_address": "0xABC",
        })
        key = instrument["instrument_key"]
        facts = [dict(item, instrument_key=key) for item in report["research_packet"]["facts"]]
        report["instrument"] = instrument
        report["research_packet"] = build_research_packet(
            key, facts, now=NOW, freshness_limits_hours={"revenue": 24}
        )
        report["fundamental_metrics"] = None
        report["valuation_metrics"] = None
        report["scenarios"] = None
        report["position_sizing"] = None
        report["conclusion"] = "wait_for_confirmation"
        inputs = {
            "instrument_key": key, "as_of_utc": "2026-11-17T16:00:00Z",
            "circulating_supply": {
                "instrument_key": key, "value": "60", "unit": "token",
                "as_of_utc": "2026-11-17T15:00:00Z",
                "source_name": "Protocol docs", "source_url": "https://example.org/supply",
                "source_reference": "Supply table", "fact_id": "circ",
            },
            "total_supply": {
                "instrument_key": key, "value": "80", "unit": "token",
                "as_of_utc": "2026-11-17T15:00:00Z",
                "source_name": "Protocol docs", "source_url": "https://example.org/supply",
                "source_reference": "Supply table", "fact_id": "total",
            },
            "max_supply": {
                "instrument_key": key, "value": "100", "unit": "token",
                "as_of_utc": "2026-11-17T15:00:00Z",
                "source_name": "Protocol docs", "source_url": "https://example.org/supply",
                "source_reference": "Supply table", "fact_id": "max",
            },
            "price": {
                "instrument_key": key, "value": "2.50", "quote_currency": "USD",
                "as_of_utc": "2026-11-17T15:00:00Z",
                "source_name": "Exchange data", "source_url": "https://example.org/price",
                "source_reference": "Spot ticker", "fact_id": "price",
            },
            "unlock_events": [{
                "event_id": "unlock-1", "amount": "5",
                "unlock_at_utc": "2026-12-01T00:00:00Z",
                "as_of_utc": "2026-11-17T15:00:00Z",
                "source_name": "Vesting schedule", "source_url": "https://example.org/vesting",
                "source_reference": "Schedule row 1",
            }],
        }
        report["tokenomics_inputs"] = inputs
        report["tokenomics"] = calculate_tokenomics(**inputs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            pdf = build_opportunity_report_pdf(report, pdf_dir)
            manifest = write_opportunity_manifest(report, pdf, manifest_dir)
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["tokenomics_status"], "passed")
            import pymupdf as fitz
            with fitz.open(pdf) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            self.assertIn("Calendario de desbloqueos conocidos", extracted)
            self.assertIn("Concentración de tenedores observada", extracted)

    def test_tokenomics_is_rejected_for_non_crypto_instrument(self):
        report = report_fixture()
        report["tokenomics"] = {"schema": "ma.tokenomics/v1", "instrument_key": KEY}
        report["tokenomics_inputs"] = {"instrument_key": KEY}
        with self.assertRaisesRegex(ValueError, "only supported for crypto"):
            build_opportunity_report_pdf(report, tempfile.mkdtemp())

    def test_opportunity_manifest_recalculates_packet_scenarios_and_sizing(self):
        report = report_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            pdf = build_opportunity_report_pdf(report, pdf_dir)
            manifest = write_opportunity_manifest(report, pdf, manifest_dir)
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertGreaterEqual(result["pdf_page_count"], 1)
            self.assertEqual(result["fundamental_metrics_status"], "passed")
            self.assertEqual(result["scenario_status"], "passed")
            self.assertEqual(result["position_sizing_status"], "passed")
            self.assertEqual(result["fact_count"], 1)


    def test_audit_checks_recorded_sec_ticker_mapping_consistency(self):
        report = report_fixture()
        report["provider_status"] = {
            "sec_edgar": {
                "cik": "0000000123",
                "ticker_resolution": {
                    "status": "resolved", "ticker": "EXM", "exchange": "NASDAQ",
                    "issuer_name": "EXAMPLE CORP",
                    "source_url": "https://www.sec.gov/files/company_tickers_exchange.json",
                    "retrieved_at_utc": "2026-11-17T15:45:00Z",
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            manifest = write_opportunity_manifest(
                report, build_opportunity_report_pdf(report, pdf_dir), manifest_dir
            )
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["issuer_mapping_status"], "passed")

            import json
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["provider_status"]["sec_edgar"]["ticker_resolution"]["exchange"] = "NYSE"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            tampered = audit_opportunity_manifest(manifest, root)
            self.assertEqual(tampered["status"], "failed")
            self.assertEqual(tampered["issuer_mapping_status"], "failed")
            self.assertTrue(any("exchange does not match" in item for item in tampered["findings"]))

    def test_manual_sec_cik_is_disclosed_as_not_independently_verified(self):
        report = report_fixture()
        report["provider_status"] = {
            "sec_edgar": {"cik": "0000000123", "ticker_resolution": None}
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            manifest = write_opportunity_manifest(
                report, build_opportunity_report_pdf(report, pdf_dir), manifest_dir
            )
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["issuer_mapping_status"], "manual_cik_not_independently_verified")



    def test_audit_checks_recorded_binance_spot_product_consistency(self):
        report = report_fixture()
        candidate = {
            "asset_class": "crypto", "name": "Bitcoin",
            "symbol": "BTC", "quote_currency": "USDT",
            "venue": {"name": "Binance", "product_id": "BTCUSDT", "market_type": "spot"},
        }
        evidence = {
            "status": "verified", "venue": "Binance",
            "product_id": "BTCUSDT", "market_type": "spot",
            "observed_at_utc": "2026-11-17T15:45:00Z",
            "source_url": "https://api.binance.com/api/v3/exchangeInfo",
            "evidence_note": "Exact product metadata verified.",
        }
        instrument = build_instrument_record(candidate, evidence, now=NOW)
        crypto_key = instrument["instrument_key"]
        facts = [dict(item, instrument_key=crypto_key) for item in report["research_packet"]["facts"]]
        report["instrument"] = instrument
        report["research_packet"] = build_research_packet(
            crypto_key, facts, now=NOW,
            freshness_limits_hours={"revenue": 24},
        )
        report["fundamental_metrics"] = calculate_financial_ratios(
            report["research_packet"]["facts"], instrument_key=crypto_key
        )
        report["scenarios"] = None
        report["position_sizing"] = None
        report["provider_status"] = {
            "binance_spot": {
                "status": "verified", "product_id": "BTCUSDT", "market_type": "spot",
                "base_asset": "BTC", "quote_asset": "USDT",
                "product_status": "TRADING", "is_spot_trading_allowed": True,
                "observed_at_utc": "2026-11-17T15:45:00Z",
                "source_url": "https://api.binance.com/api/v3/exchangeInfo",
                "reason": None, "evidence_note": "Exact product metadata verified.",
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            manifest = write_opportunity_manifest(
                report, build_opportunity_report_pdf(report, pdf_dir), manifest_dir
            )
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["venue_mapping_status"], "passed")

            import json
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["provider_status"]["binance_spot"]["product_id"] = "BTCBUSD"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            tampered = audit_opportunity_manifest(manifest, root)
            self.assertEqual(tampered["status"], "failed")
            self.assertEqual(tampered["venue_mapping_status"], "failed")
            self.assertTrue(any("product ID" in item for item in tampered["findings"]))


    def test_opportunity_manifest_detects_scenario_recalculation_tampering(self):
        report = report_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            manifest = write_opportunity_manifest(report, build_opportunity_report_pdf(report, pdf_dir),
                                                  manifest_dir)
            import json
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["scenarios"]["bull_reward_to_risk"] = "999.0000"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("scenario recalculation" in item.lower() for item in result["findings"]))

    def test_opportunity_manifest_detects_pdf_tampering(self):
        report = report_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            manifest = write_opportunity_manifest(report, build_opportunity_report_pdf(report, pdf_dir),
                                                  manifest_dir)
            pdf = pdf_dir / f"{manifest.name.removesuffix('.opportunity.json')}.pdf"
            pdf.write_bytes(pdf.read_bytes() + b"tampered")
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("SHA-256" in item for item in result["findings"]))

    def test_opportunity_manifest_rejects_manifest_outside_fixed_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            result = audit_opportunity_manifest(outside, root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("escapes" in item for item in result["findings"]))

    def test_rejects_mismatched_research_packet_instrument(self):
        report = report_fixture()
        report["research_packet"]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "does not match instrument"):
                build_opportunity_report_pdf(report, directory)

    def test_insufficient_evidence_cannot_support_potential_candidate(self):
        report = report_fixture()
        report["research_packet"] = build_research_packet(KEY, [], now=NOW)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "insufficient evidence"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_unknown_conclusion(self):
        report = report_fixture()
        report["conclusion"] = "strong_buy"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "conclusion"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_scenario_for_different_instrument(self):
        report = report_fixture()
        report["scenarios"]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "scenario instrument_key"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_probability_or_expected_return_fields(self):
        report = report_fixture()
        report["scenarios"]["probabilities"] = {"bull": 0.5}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must not contain"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_position_sizing_for_different_instrument(self):
        report = report_fixture()
        report["position_sizing"]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "position sizing instrument_key"):
                build_opportunity_report_pdf(report, directory)

    def test_rejects_invalid_fact_in_packet(self):
        report = report_fixture()
        report["research_packet"]["facts"][0]["instrument_key"] = "different"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "research fact"):
                build_opportunity_report_pdf(report, directory)


    def test_valuation_multiples_are_rendered_and_independently_audited(self):
        report = report_fixture()
        facts = list(report["research_packet"]["facts"])
        facts.extend([
            {
                "fact_id": "net-income-2025", "instrument_key": KEY,
                "dimension": "net_income", "label": "FY net income",
                "value": "100000", "unit": "USD",
                "source_kind": "issuer_disclosure", "evidence_quality": "verified_source",
                "source_name": "Issuer filing", "source_url": "https://example.com/filing",
                "source_reference": "FY2025 net income",
                "as_of_utc": "2025-12-31T23:59:59Z",
                "retrieved_at_utc": "2026-11-17T15:30:00Z",
            },
            {
                "fact_id": "equity-2025", "instrument_key": KEY,
                "dimension": "stockholders_equity", "label": "FY book equity",
                "value": "500000", "unit": "USD",
                "source_kind": "issuer_disclosure", "evidence_quality": "verified_source",
                "source_name": "Issuer filing", "source_url": "https://example.com/filing",
                "source_reference": "FY2025 balance sheet",
                "as_of_utc": "2025-12-31T23:59:59Z",
                "retrieved_at_utc": "2026-11-17T15:30:00Z",
            },
        ])
        report["research_packet"] = build_research_packet(
            KEY, facts, now=NOW, freshness_limits_hours={"revenue": 24}
        )
        report["fundamental_metrics"] = calculate_financial_ratios(
            report["research_packet"]["facts"], instrument_key=KEY
        )
        report["valuation_metrics"] = calculate_valuation_multiples(
            report["research_packet"]["facts"],
            instrument_key=KEY,
            market_cap={
                "value": "5000000", "unit": "USD",
                "as_of_utc": "2026-11-17T15:45:00Z",
                "source_id": "market-cap-fixture",
                "source_url": "https://example.com/market-cap",
            },
            earnings_period_basis="annual",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            pdf = build_opportunity_report_pdf(report, pdf_dir)
            import pymupdf as fitz
            with fitz.open(pdf) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            self.assertIn("Múltiplos de valoración", extracted)
            self.assertIn("price_to_earnings", extracted)
            manifest = write_opportunity_manifest(report, pdf, manifest_dir)
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["valuation_metrics_status"], "passed")

            import json
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["valuation_metrics"]["metrics"]["price_to_earnings"]["value"] = "999.0000"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            tampered = audit_opportunity_manifest(manifest, root)
            self.assertEqual(tampered["status"], "failed")
            self.assertEqual(tampered["valuation_metrics_status"], "failed")
            self.assertTrue(any("valuation-multiple recalculation" in item for item in tampered["findings"]))

    def test_opportunity_report_rejects_valuation_metrics_for_another_instrument(self):
        report = report_fixture()
        report["valuation_metrics"] = {
            "schema": "ma.valuation-multiples/v1",
            "instrument_key": "different",
            "metrics": {}, "missing_metrics": {}, "status": "insufficient_evidence",
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "valuation_metrics must match"):
                build_opportunity_report_pdf(report, directory)


    def test_peer_comparables_are_rendered_and_independently_audited(self):
        def entity(key, name, market_cap, net_income, revenue, equity):
            return {
                "instrument_key": key, "asset_class": "listed_equity", "name": name,
                "facts": [
                    {"fact_id": key + "-ni", "instrument_key": key, "dimension": "net_income",
                     "value": str(net_income), "unit": "USD", "as_of_utc": "2025-12-31T23:59:59Z",
                     "source_url": "https://example.org/filing", "evidence_quality": "verified_source"},
                    {"fact_id": key + "-rev", "instrument_key": key, "dimension": "revenue",
                     "value": str(revenue), "unit": "USD", "as_of_utc": "2025-12-31T23:59:59Z",
                     "source_url": "https://example.org/filing", "evidence_quality": "verified_source"},
                    {"fact_id": key + "-eq", "instrument_key": key, "dimension": "stockholders_equity",
                     "value": str(equity), "unit": "USD", "as_of_utc": "2025-12-31T23:59:59Z",
                     "source_url": "https://example.org/filing", "evidence_quality": "verified_source"},
                ],
                "market_cap": {
                    "value": str(market_cap), "unit": "USD",
                    "as_of_utc": "2026-11-17T15:45:00Z",
                    "source_id": key + "-market-cap",
                    "source_url": "https://example.org/market-cap",
                },
                "earnings_period_basis": "annual",
            }

        def selected_peer(key, name, market_cap, net_income, revenue, equity):
            result = entity(key, name, market_cap, net_income, revenue, equity)
            result["selection_criteria"] = {
                "sector": "Healthcare", "business_model": "Branded therapeutics",
                "geography": "United States", "market_cap_band": "Large cap",
                "revenue_model": "Product sales", "accounting_basis": "US GAAP",
                "rationale": "Comparable commercial-stage portfolio and operating model.",
            }
            return result

        report = report_fixture()
        candidate = entity(KEY, "Example Corp", 5000, 100, 1000, 2000)
        peers = [
            selected_peer("listed_equity|peer1", "Peer One", 2000, 100, 500, 1000),
            selected_peer("listed_equity|peer2", "Peer Two", 3000, 100, 600, 1200),
            selected_peer("listed_equity|peer3", "Peer Three", 6000, 100, 1000, 2000),
        ]
        report["peer_comparables"] = calculate_peer_comparables(candidate, peers)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            pdf = build_opportunity_report_pdf(report, pdf_dir)
            import pymupdf as fitz
            with fitz.open(pdf) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            self.assertIn("Comparables de valoración", extracted)
            self.assertIn("Peer One", extracted)
            manifest = write_opportunity_manifest(report, pdf, manifest_dir)
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["peer_comparables_status"], "passed")

            import json
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["peer_comparables"]["metrics"]["price_to_earnings"]["median"] = "999.0000"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            tampered = audit_opportunity_manifest(manifest, root)
            self.assertEqual(tampered["status"], "failed")
            self.assertEqual(tampered["peer_comparables_status"], "failed")
            self.assertTrue(any("peer-comparables recalculation" in item for item in tampered["findings"]))

    def test_opportunity_report_rejects_peer_comparables_for_another_instrument(self):
        report = report_fixture()
        report["peer_comparables"] = {
            "schema": "ma.peer-comparables/v1",
            "candidate_instrument_key": "different",
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "peer_comparables must match"):
                build_opportunity_report_pdf(report, directory)



class BiotechOpportunityIntegrationTests(unittest.TestCase):
    def test_biotech_runway_is_rendered_and_independently_audited(self):
        import json
        import pymupdf as fitz
        from report_engine.biotech_valuation import assess_biotech_valuation

        report = report_fixture()
        inputs = {
            "instrument_key": KEY,
            "development_stage": "clinical",
            "analysis_cutoff_utc": "2026-11-17T16:00:00Z",
            "cash": {
                "instrument_key": KEY, "value": "120000000", "currency": "USD",
                "as_of_utc": "2026-11-17T15:00:00Z", "source_id": "cash-q3",
                "source_url": "https://example.org/cash",
                "evidence_quality": "verified_source",
            },
            "quarterly_net_cash_burn": {
                "instrument_key": KEY, "value": "30000000", "currency": "USD",
                "as_of_utc": "2026-11-17T15:00:00Z", "source_id": "burn-q3",
                "source_url": "https://example.org/cashflow",
                "evidence_quality": "verified_source",
            },
            "clinical_catalysts": [{
                "nct_id": "NCT01234567", "phase": ["PHASE3"],
                "status": "RECRUITING", "primary_completion_date": "2027-06-30",
                "source_url": "https://clinicaltrials.gov/study/NCT01234567",
                "attribution_basis": "Issuer filing reference.",
            }],
        }
        report["biotech_valuation_inputs"] = inputs
        report["biotech_valuation"] = assess_biotech_valuation(**inputs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_dir = root / "reports" / "opportunities"
            manifest_dir = root / "data" / "manifests" / "opportunities"
            pdf_dir.mkdir(parents=True)
            pdf = build_opportunity_report_pdf(report, pdf_dir)
            with fitz.open(pdf) as document:
                extracted = " ".join(page.get_text("text") for page in document)
            self.assertIn("Diligencia biotech", extracted)
            self.assertIn("12.00", extracted)
            manifest = write_opportunity_manifest(report, pdf, manifest_dir)
            result = audit_opportunity_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual(result["biotech_valuation_status"], "passed")
            self.assertEqual(result["biotech_valuation_quality_status"], "partial")

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["biotech_valuation"]["metrics"]["cash_runway_months"]["value"] = "99.00"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            tampered = audit_opportunity_manifest(manifest, root)
            self.assertEqual(tampered["status"], "failed")
            self.assertEqual(tampered["biotech_valuation_status"], "failed")
            self.assertTrue(any("biotech valuation/runway" in item for item in tampered["findings"]))

if __name__ == "__main__":
    unittest.main()
