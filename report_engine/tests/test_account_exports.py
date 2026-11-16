"""Tests for the privacy-conscious Binance transaction statement parser."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from report_engine.account_exports import collect_binance_account_exports


START = datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 11, 17, 0, 0, tzinfo=timezone.utc)
HEADER = "User_ID,UTC_Time,Account,Operation,Coin,Change,Remark\n"


class AccountExportTests(unittest.TestCase):
    def write_csv(self, path: Path, rows: str):
        path.write_text(HEADER + rows, encoding="utf-8")

    def test_aggregates_supported_operations_without_retaining_user_id_or_remark(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "transaction-history.csv"
            rows = (
                "private-user-123,2026-11-16T10:00:00Z,Spot,Deposit,USDT,100,private deposit note\n"
                "private-user-123,2026-11-16T10:01:00Z,USD-M Futures,Realized Profit and Loss,USDT,12.5,private remark\n"
                "private-user-123,2026-11-16T10:02:00Z,USD-M Futures,Funding Fee,USDT,-0.5,\n"
                "private-user-123,2026-11-16T10:03:00Z,Spot,Transaction Fee,BNB,-0.01,\n"
                "private-user-123,2026-11-16T10:04:00Z,Spot,Withdraw,USDT,-20,\n"
                "private-user-123,2026-11-16T10:05:00Z,Spot,Transfer Between Spot and Futures,USDT,10,\n"
                "private-user-123,2026-11-16T10:06:00Z,Spot,Transaction Buy,BTC,-0.001,\n"
                "private-user-123,2026-11-16T10:07:00Z,Spot,Transaction Sold,USDT,60,\n"
                "private-user-123,2026-11-17T00:00:00Z,Spot,Deposit,USDT,500,outside half-open window\n"
            )
            self.write_csv(path, rows)
            result = collect_binance_account_exports(temp, START, END)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["events_in_window"], 8)
            totals = result["aggregates_by_event_and_asset"]
            self.assertEqual(totals["deposit"]["USDT"], "100")
            self.assertEqual(totals["realized_pnl"]["USDT"], "12.5")
            self.assertEqual(totals["funding_fee"]["USDT"], "-0.5")
            self.assertEqual(totals["commission"]["BNB"], "-0.01")
            self.assertEqual(totals["withdrawal"]["USDT"], "-20")
            self.assertEqual(totals["internal_transfer"]["USDT"], "10")
            self.assertEqual(totals["trade_spend"]["BTC"], "-0.001")
            self.assertEqual(totals["trade_receive"]["USDT"], "60")
            serialized = str(result)
            self.assertNotIn("private-user-123", serialized)
            self.assertNotIn("private deposit note", serialized)
            self.assertEqual(result["portfolio_equity_status"], "not_available")
            self.assertEqual(result["flow_adjusted_return_status"], "not_available")

    def test_duplicate_rows_across_overlapping_exports_are_counted_once(self):
        with TemporaryDirectory() as temp:
            rows = "uid,2026-11-16T10:00:00Z,Spot,Deposit,USDT,10,\n"
            self.write_csv(Path(temp) / "part-a.csv", rows)
            self.write_csv(Path(temp) / "part-b.csv", rows)
            result = collect_binance_account_exports(temp, START, END)
            self.assertEqual(result["events_in_window"], 1)
            self.assertEqual(result["duplicate_rows"], 1)
            self.assertEqual(result["aggregates_by_event_and_asset"]["deposit"]["USDT"], "10")

    def test_naive_utc_time_is_explicitly_assumed_and_marks_partial(self):
        with TemporaryDirectory() as temp:
            self.write_csv(
                Path(temp) / "statement.csv",
                "uid,2026-11-16 10:00:00,Spot,Deposit,USDT,10,\n",
            )
            result = collect_binance_account_exports(temp, START, END)
            self.assertEqual(result["status"], "partial")
            self.assertTrue(any("interpreted as UTC" in item for item in result["assumptions"]))

    def test_unsupported_schema_is_partial_not_silently_ignored(self):
        with TemporaryDirectory() as temp:
            Path(temp, "futures-income.csv").write_text(
                "Date(UTC),type,Amount,Asset,Symbol,Transaction ID\n"
                "2026-11-16T10:00:00Z,FUNDING_FEE,-0.5,USDT,BTCUSDT,123\n",
                encoding="utf-8",
            )
            result = collect_binance_account_exports(temp, START, END)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["unsupported_files"], ["account_export_001"])

    def test_missing_directory_is_unavailable_and_does_not_infer_account_data(self):
        with TemporaryDirectory() as temp:
            result = collect_binance_account_exports(Path(temp) / "missing", START, END)
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["events_in_window"], 0)
            self.assertEqual(result["portfolio_equity_status"], "not_available")


if __name__ == "__main__":
    unittest.main()
