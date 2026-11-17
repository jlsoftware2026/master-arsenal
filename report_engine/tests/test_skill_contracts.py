"""Static contract checks for the four adapted MASTER ARSENAL skills."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def read_skill(name: str) -> str:
    path = SKILLS / name / "SKILL.md"
    return path.read_text(encoding="utf-8")


class AdaptedSkillContractTests(unittest.TestCase):
    def test_all_four_adaptations_preserve_identity_and_local_engine_contract(self):
        names = (
            "binance-apertura-mercado",
            "binance-cierre-mercado",
            "binance-momento-mercado",
            "binance-revision-skills",
        )
        for name in names:
            with self.subTest(skill=name):
                text = read_skill(name)
                self.assertTrue(text.startswith("---\n"))
                self.assertIn(f"name: {name}", text)
                self.assertIn("version:", text)
                self.assertIn("last_reviewed:", text)
                self.assertIn(f"# {name}", text)
                self.assertIn("## Local Engine workflow", text)
                self.assertIn("submit → validate → explicit approval → execute", text)
                self.assertIn("integrity", text.lower())
                self.assertIn("Pre-investment", text)
                self.assertIn("## Version history", text)
                self.assertIn("PDF", text)

    def test_opening_preserves_previous_dominican_day_and_premarket_timing(self):
        text = read_skill("binance-apertura-mercado")
        for required in (
            "15–20 minutes before the U.S. regular open",
            "previous completed America/Santo_Domingo local calendar day",
            "last completed U.S. cash session",
            "BTCUSDT and ETHUSDT",
            "250-candle pre-session warm-up",
            "Bullish/long and bearish/short scenarios",
            "not applicable",
            "not supplied",
        ):
            with self.subTest(requirement=required):
                self.assertIn(required, text)

    def test_closing_preserves_partial_day_and_same_date_scorecard(self):
        text = read_skill("binance-cierre-mercado")
        for required in (
            "15–20 minutes after 4:00 p.m. ET",
            "partial until local midnight",
            "exact cutoff",
            "unfinished final candle",
            "Same-date opening forecast scorecard",
            "no opening forecast was available",
            "flow-adjusted returns remain unavailable",
        ):
            with self.subTest(requirement=required):
                self.assertIn(required, text)

    def test_intraday_preserves_exact_cutoff_and_local_vs_rolling_change(self):
        text = read_skill("binance-momento-mercado")
        for required in (
            "execution-time America/Santo_Domingo local time",
            "exact local cutoff",
            "rolling 24-hour ticker change",
            "Do not predict the rest of the session",
            "snapshot-mercado_YYYY-MM-DD_HH-mm.pdf",
            "250-candle historical warm-up",
        ):
            with self.subTest(requirement=required):
                self.assertIn(required, text)

    def test_audit_preserves_severity_verdicts_and_independence(self):
        text = read_skill("binance-revision-skills")
        for required in (
            "Crítico, Alto, Medio o Bajo",
            "No aprobado",
            "Aprobado con reservas",
            "Aprobado",
            "independently recalculates",
            "exact local Git HEAD",
            "self-certify",
            "No aprobado",
        ):
            with self.subTest(requirement=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
