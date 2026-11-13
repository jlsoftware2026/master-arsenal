"""Independent parser and rendered-page QA tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from report_engine import build_intraday_snapshot_pdf
from report_engine.qa import inspect_pdf_artifact
from report_engine.charts import MarketChart
import fitz
from report_engine.tests.test_intraday_pdf import fixture


class PdfQualityTests(unittest.TestCase):
    def test_independent_parser_extracts_and_renders_every_page(self):
        with TemporaryDirectory() as temp:
            pdf = build_intraday_snapshot_pdf(fixture(), temp)
            previews = Path(temp) / "previews"
            result = inspect_pdf_artifact(pdf, render_directory=previews)
            self.assertGreaterEqual(result["page_count"], 1)
            self.assertTrue(result["checks"]["parsed"])
            self.assertTrue(result["checks"]["extractable_text"])
            self.assertTrue(result["checks"]["text_within_page_bounds"])
            self.assertTrue(result["checks"]["rendered_pages_nonblank"])
            self.assertEqual(len(list(previews.glob("page-*.png"))), result["page_count"])
            self.assertTrue(all(page["text_characters"] >= 20 for page in result["pages"]))

    def test_intraday_composer_embeds_close_and_volume_charts(self):
        data = fixture()
        for symbol in ("BTCUSDT", "ETHUSDT"):
            data["symbols"][symbol]["candles"] = [
                {"open_time": f"2026-11-13T{hour:02d}:00:00Z",
                 "close_time": f"2026-11-13T{hour:02d}:59:59Z",
                 "close": str(100 + hour), "volume": str(10 + hour)}
                for hour in range(16)
            ]
        with TemporaryDirectory() as temp:
            pdf = build_intraday_snapshot_pdf(data, temp)
            with fitz.open(pdf) as document:
                text = "\\n".join(page.get_text() for page in document)
            self.assertIn("BTCUSDT close price", text)
            self.assertIn("BTCUSDT base-asset volume", text)
            self.assertIn("ETHUSDT close price", text)
            self.assertIn("ETHUSDT base-asset volume", text)

    def test_chart_rejects_non_finite_values_and_mismatched_labels(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            MarketChart("Invalid", [1, float("nan")])
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            MarketChart("Invalid", [1, 2], ["only-one"])

    def test_rejects_non_pdf_path(self):
        with TemporaryDirectory() as temp:
            text_file = Path(temp) / "report.txt"
            text_file.write_text("not a PDF", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"\.pdf"):
                inspect_pdf_artifact(text_file)

    def test_rejects_missing_file(self):
        with TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                inspect_pdf_artifact(Path(temp) / "missing.pdf")


if __name__ == "__main__":
    unittest.main()
