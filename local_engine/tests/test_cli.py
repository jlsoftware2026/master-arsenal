"""Command-line contract tests for Local Engine job creation."""
from local_engine.cli import build_parser


def test_new_job_accepts_investment_opportunity_report():
    args = build_parser().parse_args(["new-job", "investment.opportunity_report"])
    assert args.command == "new-job"
    assert args.job_type == "investment.opportunity_report"
