"""Offline tests for exact-commit GitHub Actions evidence verification."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlparse, parse_qs

from report_engine.github_ci import (
    EXPECTED_JOBS,
    GitHubActionsEvidence,
    resolve_git_head_sha,
    resolve_github_repository,
)

SHA = "a" * 40


class GitHubActionsEvidenceTests(unittest.TestCase):
    def test_passes_only_when_exact_sha_run_and_all_four_jobs_succeed(self):
        calls = []

        def fake(url):
            calls.append(url)
            if "/actions/runs?" in url:
                return {"workflow_runs": [{
                    "id": 123, "run_number": 7, "name": "Python tests",
                    "head_sha": SHA, "event": "pull_request",
                    "status": "completed", "conclusion": "success",
                    "created_at": "2026-11-17T12:00:00Z",
                    "html_url": "https://github.com/example/repo/actions/runs/123",
                }]}
            return {"jobs": [{
                "name": name, "status": "completed", "conclusion": "success"
            } for name in EXPECTED_JOBS]}

        result = GitHubActionsEvidence(fetch_json=fake).verify("example/repo", SHA)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["run_id"], 123)
        self.assertEqual({job["name"] for job in result["jobs"]}, EXPECTED_JOBS)
        self.assertEqual(len(calls), 2)
        self.assertIn(SHA, calls[0])

    def test_rejects_run_for_different_commit(self):
        def fake(url):
            return {"workflow_runs": [{
                "id": 123, "name": "Python tests", "head_sha": "b" * 40,
                "event": "pull_request", "status": "completed", "conclusion": "success",
            }]}
        result = GitHubActionsEvidence(fetch_json=fake).verify("example/repo", SHA)
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("exact local commit", result["reason"])

    def test_failed_or_missing_matrix_job_fails_verification(self):
        def fake(url):
            if "/actions/runs?" in url:
                return {"workflow_runs": [{
                    "id": 123, "name": "Python tests", "head_sha": SHA,
                    "event": "pull_request", "status": "completed", "conclusion": "success",
                    "created_at": "2026-11-17T12:00:00Z",
                }]}
            jobs = [{
                "name": name, "status": "completed", "conclusion": "success"
            } for name in EXPECTED_JOBS if name != "tests (windows-latest, 3.12)"]
            jobs.append({
                "name": "tests (windows-latest, 3.12)",
                "status": "completed", "conclusion": "failure",
            })
            return {"jobs": jobs}
        result = GitHubActionsEvidence(fetch_json=fake).verify("example/repo", SHA)
        self.assertEqual(result["status"], "failed")

    def test_in_progress_run_is_not_verified(self):
        def fake(url):
            return {"workflow_runs": [{
                "id": 123, "name": "Python tests", "head_sha": SHA,
                "event": "pull_request", "status": "in_progress", "conclusion": None,
                "created_at": "2026-11-17T12:00:00Z",
            }]}
        result = GitHubActionsEvidence(fetch_json=fake).verify("example/repo", SHA)
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("in progress", result["reason"])

    def test_api_error_is_not_misreported_as_pass(self):
        def fake(url):
            raise OSError("offline")
        result = GitHubActionsEvidence(fetch_json=fake).verify("example/repo", SHA)
        self.assertEqual(result["status"], "not_verified")
        self.assertIn("retrieval failed", result["reason"])

    def test_resolves_detached_head(self):
        with TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            git.mkdir()
            (git / "HEAD").write_text(SHA + "\n", encoding="ascii")
            self.assertEqual(resolve_git_head_sha(temp), SHA)

    def test_resolves_loose_branch_ref(self):
        with TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            (git / "refs" / "heads").mkdir(parents=True)
            (git / "HEAD").write_text("ref: refs/heads/feature/test\n", encoding="ascii")
            (git / "refs" / "heads" / "feature" / "test").parent.mkdir(parents=True, exist_ok=True)
            (git / "refs" / "heads" / "feature" / "test").write_text(SHA, encoding="ascii")
            self.assertEqual(resolve_git_head_sha(temp), SHA)

    def test_resolves_github_origin(self):
        with TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            git.mkdir()
            (git / "config").write_text(
                '[remote "origin"]\n\turl = https://github.com/example/repo.git\n',
                encoding="utf-8",
            )
            self.assertEqual(resolve_github_repository(temp), "example/repo")

    def test_invalid_repository_override_fails_closed(self):
        with TemporaryDirectory() as temp:
            git = Path(temp) / ".git"
            git.mkdir()
            (git / "config").write_text(
                '[remote "origin"]\n\turl = https://github.com/example/repo.git\n',
                encoding="utf-8",
            )
            # Avoid mutating process-global environment in a parallel test runner.
            import os
            previous = os.environ.get("MASTER_ARSENAL_GITHUB_REPOSITORY")
            try:
                os.environ["MASTER_ARSENAL_GITHUB_REPOSITORY"] = "https://evil.example/repo"
                self.assertIsNone(resolve_github_repository(temp))
            finally:
                if previous is None:
                    os.environ.pop("MASTER_ARSENAL_GITHUB_REPOSITORY", None)
                else:
                    os.environ["MASTER_ARSENAL_GITHUB_REPOSITORY"] = previous


if __name__ == "__main__":
    unittest.main()
