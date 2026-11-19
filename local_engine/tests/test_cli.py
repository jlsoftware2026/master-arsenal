"""Command-line contract tests for Local Engine job creation."""
import unittest
from pathlib import Path

from local_engine.cli import build_parser
from local_engine.paths import default_workspace


class LocalEngineCliTests(unittest.TestCase):
    def test_new_job_accepts_investment_opportunity_report(self):
        args = build_parser().parse_args(["new-job", "investment.opportunity_report"])
        self.assertEqual(args.command, "new-job")
        self.assertEqual(args.job_type, "investment.opportunity_report")

    def test_new_job_defaults_to_persistent_user_data(self):
        args = build_parser().parse_args(["new-job", "engine.health_check"])
        self.assertIsNone(args.output)
        self.assertEqual(args.workspace, default_workspace())

    def test_new_job_allows_custom_workspace_output_resolution(self):
        args = build_parser().parse_args(["--workspace", "custom-data", "new-job", "engine.health_check"])
        output = args.output or (args.workspace / "health-check-job.json")
        self.assertEqual(output, Path("custom-data") / "health-check-job.json")


if __name__ == "__main__":
    unittest.main()
