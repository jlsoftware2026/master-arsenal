"""Offline tests for evidence manifests and independent market-data auditing."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from binance_data_engine.engine import analyze_candles
from binance_data_engine.models import Candle
from report_engine.evidence import (
    audit_cross_report_consistency, audit_evidence_manifest, write_evidence_manifest,
)

START = datetime(2026, 11, 16, 4, tzinfo=timezone.utc)
CUTOFF = START + timedelta(hours=3)


def _candle(symbol, opened, index):
    price = Decimal("100") + index
    return Candle(
        symbol=symbol, interval="1h", open_time=opened,
        close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
        open=price, high=price + 1, low=price - 1, close=price,
        volume=Decimal("10"),
    )


def _report():
    symbols = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        history = [_candle(symbol, START - timedelta(hours=250-index), index)
                   for index in range(250)]
        candles = [_candle(symbol, START + timedelta(hours=index), 250+index)
                   for index in range(3)]
        symbols[symbol] = {
            "candles": [item.to_dict() for item in candles],
            "candle_count": len(candles),
            "expected_candle_count": 3,
            "indicator_history": {
                "candles": [item.to_dict() for item in history],
                "candle_count": len(history),
                "expected_candle_count": 250,
                "pagination": {"complete": True, "returned": len(history)},
            },
            "pagination": {"complete": True, "returned": len(candles)},
            "indicators": analyze_candles(history + candles),
        }
    return {
        "window_start_utc": START.isoformat().replace("+00:00", "Z"),
        "report_timezone": "America/Santo_Domingo",
        "report_date_local": "2026-11-16",
        "window_start_local": "2026-11-16T00:00:00-04:00",
        "cutoff_local": "2026-11-16T03:00:00-04:00",
        "is_partial": True,
        "cutoff_utc": CUTOFF.isoformat().replace("+00:00", "Z"),
        "generated_at_utc": (CUTOFF + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "interval": "1h",
        "source": "Binance public REST API",
        "read_only": True,
        "indicator_methodology": {"lookback_candles": 250, "report_window_excludes_lookback": True},
        "symbols": symbols,
    }


class EvidenceManifestTests(unittest.TestCase):
    def _write(self, root, stem, report):
        pdf_dir = root / "reports" / "intraday"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf = pdf_dir / f"{stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\nfixture\n%%EOF")
        manifest_dir = root / "data" / "manifests"
        manifest = write_evidence_manifest(report, "intraday", pdf, manifest_dir)
        return pdf, manifest

    def test_manifest_hash_and_indicator_recalculation_pass(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            _, manifest = self._write(root, "snapshot-mercado-2026-11-16_03-00", _report())
            result = audit_evidence_manifest(manifest, root)
            self.assertEqual(result["status"], "passed", result["findings"])
            self.assertEqual(result["symbols_checked"], ["BTCUSDT", "ETHUSDT"])
            self.assertEqual(result["indicator_recalculation"], "passed")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["report_window"]["report_timezone"], "America/Santo_Domingo")
            self.assertEqual(len(payload["raw_candle_evidence_sha256"]), 64)

    def test_raw_candle_evidence_hash_tampering_is_detected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            _, manifest = self._write(root, "snapshot-mercado-2026-11-16_03-00", _report())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["report"]["symbols"]["BTCUSDT"]["candles"][0]["close"] = "999"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = audit_evidence_manifest(manifest, root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("Raw candle evidence SHA-256" in item for item in result["findings"]))

    def test_indicator_tampering_is_detected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            report = _report()
            report["symbols"]["BTCUSDT"]["indicators"]["ema_200"] = 1
            _, manifest = self._write(root, "snapshot-mercado-2026-11-16_03-00", report)
            result = audit_evidence_manifest(manifest, root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("indicators do not match" in item for item in result["findings"]))

    def test_cross_report_consistency_detects_mismatched_overlapping_candles(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            _, first = self._write(root, "snapshot-mercado-2026-11-16_03-00", _report())
            report2 = _report()
            report2["symbols"]["BTCUSDT"]["candles"][0]["close"] = "999"
            _, second = self._write(root, "snapshot-mercado-2026-11-16_04-00", report2)
            result = audit_cross_report_consistency([first, second], root)
            self.assertEqual(result["status"], "failed")
            self.assertGreater(result["overlapping_candles_checked"], 0)
            self.assertTrue(result["mismatches"])

    def test_manifest_pdf_hash_mismatch_is_detected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pdf, manifest = self._write(root, "snapshot-mercado-2026-11-16_03-00", _report())
            pdf.write_bytes(b"%PDF-1.4\nchanged\n%%EOF")
            result = audit_evidence_manifest(manifest, root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("SHA-256" in item for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
