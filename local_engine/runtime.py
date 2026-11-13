"""Workspace, atomic job lifecycle, approval gate, and allowlisted dispatcher."""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .protocol import JobValidationError, load_job, utc_now, validate_job

DIRECTORIES = (
    "config", "jobs/inbox", "jobs/validated", "jobs/awaiting_approval", "jobs/running",
    "jobs/completed", "jobs/failed", "jobs/cancelled", "jobs/archive",
    "reports/opening", "reports/closing", "reports/intraday", "reports/audit",
    "data/cache", "data/snapshots", "data/manifests", "logs",
    "skills/binance-apertura-mercado", "skills/binance-cierre-mercado",
    "skills/binance-momento-mercado", "skills/binance-revision-skills", "temp",
)
STATES = ("inbox", "validated", "awaiting_approval", "running", "completed", "failed", "cancelled", "archive")


class Workspace:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for relative in DIRECTORIES:
            target = self.root / relative
            target.mkdir(parents=True, exist_ok=True)
            if not target.resolve().is_relative_to(self.root):
                raise ValueError(f"Workspace path escapes root: {relative}")

    def directory(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Path escapes the workspace")
        return candidate

    def job_path(self, state: str, job_id: str) -> Path:
        if state not in STATES:
            raise ValueError("Unknown job state")
        return self.directory(f"jobs/{state}") / f"{job_id}.json"


class JobManager:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.workspace.initialize()

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def submit_file(self, source: Path) -> dict[str, Any]:
        return self.submit(load_job(source))

    def submit(self, job: dict[str, Any]) -> dict[str, Any]:
        validate_job(job)
        if any(self.workspace.job_path(state, job["job_id"]).exists() for state in STATES):
            raise JobValidationError(f"Duplicate job_id: {job['job_id']}")
        record = {**job, "status": "inbox", "updated_at_utc": utc_now()}
        self._atomic_write(self.workspace.job_path("inbox", job["job_id"]), record)
        return record

    def _find(self, job_id: str):
        for state in STATES:
            path = self.workspace.job_path(state, job_id)
            if path.is_file():
                return state, path
        return None

    def get(self, job_id: str) -> dict[str, Any]:
        found = self._find(job_id)
        if not found:
            raise FileNotFoundError(f"Job not found: {job_id}")
        return json.loads(found[1].read_text(encoding="utf-8"))

    def _move(self, job: dict[str, Any], old_state: str, new_state: str) -> None:
        source = self.workspace.job_path(old_state, job["job_id"])
        target = self.workspace.job_path(new_state, job["job_id"])
        if target.exists():
            raise JobValidationError(f"Job already exists in state {new_state}")
        job["status"] = new_state
        job["updated_at_utc"] = utc_now()
        self._atomic_write(target, job)
        source.unlink()

    def validate_pending(self, job_id: str) -> str:
        found = self._find(job_id)
        if not found or found[0] != "inbox":
            raise JobValidationError("Only inbox jobs can be validated")
        state, path = found
        job = json.loads(path.read_text(encoding="utf-8"))
        validate_job({k: v for k, v in job.items() if k not in {"status", "updated_at_utc"}})
        target = "awaiting_approval" if job["approval"]["required"] and not job["approval"]["granted"] else "validated"
        self._move(job, state, target)
        return target

    def approve(self, job_id: str) -> None:
        found = self._find(job_id)
        if not found or found[0] != "awaiting_approval":
            raise JobValidationError("Only jobs awaiting approval can be approved")
        state, path = found
        job = json.loads(path.read_text(encoding="utf-8"))
        job["approval"]["granted"] = True
        validate_job({k: v for k, v in job.items() if k not in {"status", "updated_at_utc"}})
        self._move(job, state, "validated")

    def claim(self, job_id: str) -> dict[str, Any]:
        found = self._find(job_id)
        if not found or found[0] != "validated":
            raise JobValidationError("Only validated jobs can be executed")
        job = json.loads(found[1].read_text(encoding="utf-8"))
        if job["approval"]["required"] and not job["approval"]["granted"]:
            raise JobValidationError("Job has not received explicit approval")
        self._move(job, "validated", "running")
        return job

    def finish(self, job_id: str, result: dict[str, Any], success: bool = True) -> None:
        found = self._find(job_id)
        if not found or found[0] != "running":
            raise JobValidationError("Only running jobs can be completed")
        job = json.loads(found[1].read_text(encoding="utf-8"))
        job["result"] = result
        self._move(job, "running", "completed" if success else "failed")


class JobRunner:
    def __init__(self, manager: JobManager):
        self.manager = manager
        self.handlers = {"engine.health_check": self._health_check}

    def _health_check(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "engine": "MASTER ARSENAL Local Engine", "engine_version": __version__,
            "python_version": sys.version.split()[0], "platform": platform.platform(),
            "workspace": str(self.manager.workspace.root),
            "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "implemented_job_types": sorted(self.handlers), "read_only": True,
        }

    def run(self, job_id: str) -> dict[str, Any]:
        job = self.manager.claim(job_id)
        handler = self.handlers.get(job["job_type"])
        if handler is None:
            message = f"Job type {job['job_type']!r} is defined but not implemented in Phase 2"
            self.manager.finish(job_id, {"error": message}, success=False)
            return {"status": "failed", "error": message}
        try:
            result = handler(job)
        except Exception as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
            self.manager.finish(job_id, result, success=False)
            return {"status": "failed", **result}
        self.manager.finish(job_id, result, success=True)
        return {"status": "completed", "result": result}
