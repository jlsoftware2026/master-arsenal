"""Command-line contract tests for Local Engine job creation."""
from local_engine.cli import build_parser


def test_new_job_accepts_investment_opportunity_report():
    args = build_parser().parse_args(["new-job", "investment.opportunity_report"])
    assert args.command == "new-job"
    assert args.job_type == "investment.opportunity_report"



def test_new_job_defaults_to_persistent_user_data():
    from local_engine.paths import default_workspace

    args = build_parser().parse_args(["new-job", "engine.health_check"])
    assert args.output == default_workspace() / "health-check-job.json"
