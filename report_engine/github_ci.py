"""Read-only GitHub Actions evidence for the exact local source revision."""
from __future__ import annotations

import configparser
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
MAX_RESPONSE_BYTES = 2_000_000
EXPECTED_JOBS = {
    "tests (ubuntu-latest, 3.11)",
    "tests (ubuntu-latest, 3.12)",
    "tests (windows-latest, 3.11)",
    "tests (windows-latest, 3.12)",
}


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{40}", value) is not None


def resolve_git_head_sha(repository_root: Path | str) -> str | None:
    """Resolve HEAD from a normal .git directory without invoking a shell."""
    root = Path(repository_root).resolve()
    git_dir = root / ".git"
    if not git_dir.is_dir():
        return None
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if _valid_sha(head):
            return head.lower()
        if not head.startswith("ref: "):
            return None
        ref = head[5:].strip()
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", ref) or ".." in ref:
            return None
        loose = git_dir / ref
        if loose.is_file():
            value = loose.read_text(encoding="ascii").strip()
            return value.lower() if _valid_sha(value) else None
        packed = git_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="ascii").splitlines():
                fields = line.split()
                if len(fields) == 2 and fields[1] == ref and _valid_sha(fields[0]):
                    return fields[0].lower()
    except (OSError, UnicodeError):
        return None
    return None


def resolve_github_repository(repository_root: Path | str) -> str | None:
    """Read origin from .git/config or an explicit repository environment value."""
    configured = os.environ.get("MASTER_ARSENAL_GITHUB_REPOSITORY", "").strip()
    if configured:
        return configured if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", configured) else None
    config_path = Path(repository_root).resolve() / ".git" / "config"
    if not config_path.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
        origin = parser.get('remote "origin"', "url", fallback="")
    except (OSError, configparser.Error):
        return None
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?",
        origin.strip(),
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


class GitHubActionsEvidence:
    """Verify the four required PR matrix jobs for the exact local Git commit."""

    def __init__(
        self,
        *,
        fetch_json: Callable[[str], dict[str, Any]] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")
        self.timeout_seconds = float(timeout_seconds)
        self._fetch_json = fetch_json or self._http_fetch_json

    def _http_fetch_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "MASTER-ARSENAL-read-only-ci-audit",
        }, method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("GitHub Actions API response exceeds the 2 MB safety limit")
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("GitHub Actions API response must be a JSON object")
        return decoded

    def verify(self, repository: str | None, commit_sha: str | None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": "ma.github-actions-evidence/v1",
            "repository": repository,
            "commit_sha": commit_sha.lower() if _valid_sha(commit_sha) else None,
            "status": "not_verified",
            "run_id": None,
            "run_number": None,
            "run_url": None,
            "jobs": [],
            "verified_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reason": None,
        }
        if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            result["reason"] = "GitHub repository identity could not be resolved safely."
            return result
        if not _valid_sha(commit_sha):
            result["reason"] = "Local Git HEAD commit SHA could not be resolved."
            return result
        try:
            query = urlencode({"head_sha": commit_sha.lower(), "event": "pull_request", "per_page": 20})
            runs_payload = self._fetch_json(f"{API_ROOT}/repos/{repository}/actions/runs?{query}")
            runs = runs_payload.get("workflow_runs")
            if not isinstance(runs, list):
                raise ValueError("GitHub Actions workflow_runs response is malformed")
            candidates = [
                item for item in runs if isinstance(item, dict)
                and str(item.get("head_sha", "")).lower() == commit_sha.lower()
                and item.get("event") == "pull_request"
                and item.get("name") == "Python tests"
            ]
            if not candidates:
                result["reason"] = "No pull-request Python tests run was found for the exact local commit."
                return result
            run = max(candidates, key=lambda item: str(item.get("created_at", "")))
            result.update({
                "run_id": run.get("id"),
                "run_number": run.get("run_number"),
                "run_url": run.get("html_url"),
            })
            if run.get("status") != "completed":
                result["reason"] = "The exact-commit GitHub Actions run is still in progress."
                return result
            run_id = run.get("id")
            if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
                raise ValueError("GitHub Actions run ID is invalid")
            jobs_payload = self._fetch_json(
                f"{API_ROOT}/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100"
            )
            jobs = jobs_payload.get("jobs")
            if not isinstance(jobs, list):
                raise ValueError("GitHub Actions jobs response is malformed")
            by_name = {item.get("name"): item for item in jobs if isinstance(item, dict)}
            summaries = []
            for name in sorted(EXPECTED_JOBS):
                item = by_name.get(name)
                summaries.append({
                    "name": name,
                    "status": item.get("status") if item else "missing",
                    "conclusion": item.get("conclusion") if item else None,
                })
            result["jobs"] = summaries
            run_complete = run.get("status") == "completed" and run.get("conclusion") == "success"
            jobs_complete = all(
                by_name.get(name, {}).get("status") == "completed"
                and by_name.get(name, {}).get("conclusion") == "success"
                for name in EXPECTED_JOBS
            )
            if run_complete and jobs_complete:
                result["status"] = "passed"
                result["reason"] = "Exact-commit pull-request workflow and all four OS/Python matrix jobs succeeded."
            else:
                result["status"] = "failed"
                result["reason"] = "The exact-commit workflow or one or more required matrix jobs did not succeed."
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            result["reason"] = f"GitHub Actions evidence retrieval failed: {type(exc).__name__}: {exc}"
        return result
