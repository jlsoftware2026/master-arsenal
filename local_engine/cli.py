"""CLI entry point for the Local Engine foundation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .protocol import JobValidationError, new_job
from .runtime import JobManager, JobRunner, Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ma-local", description="MASTER ARSENAL Local Engine")
    parser.add_argument("--workspace", type=Path, default=Path("MASTER-ARSENAL-LOCAL"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="initialize the workspace")
    create = sub.add_parser("new-job", help="write a sample job JSON")
    create.add_argument("job_type", choices=(
        "engine.health_check", "market.opening_report", "market.closing_report",
        "market.intraday_snapshot", "skills.audit", "engine.validate_data"))
    create.add_argument("--output", type=Path, default=Path("health-check-job.json"))
    submit = sub.add_parser("submit", help="submit a JSON job to the inbox")
    submit.add_argument("job_file", type=Path)
    for command, help_text in (("validate", "validate and route a job"), ("approve", "explicitly approve a job"),
                               ("run", "execute a validated job"), ("status", "show a job record")):
        action = sub.add_parser(command, help=help_text)
        action.add_argument("job_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            workspace = Workspace(args.workspace)
            workspace.initialize()
            print(f"Workspace initialized: {workspace.root}")
            return 0
        if args.command == "new-job":
            job = new_job(args.job_type)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
            print(f"Job template created: {args.output} (approval required)")
            return 0
        manager = JobManager(Workspace(args.workspace))
        if args.command == "submit":
            record = manager.submit_file(args.job_file)
            print(f"Submitted job: {record['job_id']}")
        elif args.command == "validate":
            print(f"Job {args.job_id}: {manager.validate_pending(args.job_id)}")
        elif args.command == "approve":
            manager.approve(args.job_id)
            print(f"Job approved and validated: {args.job_id}")
        elif args.command == "run":
            result = JobRunner(manager).run(args.job_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["status"] == "completed" else 2
        elif args.command == "status":
            print(json.dumps(manager.get(args.job_id), indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, JobValidationError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
