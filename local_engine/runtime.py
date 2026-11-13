"""Workspace, cross-process-safe job lifecycle, approval gate, and dispatcher."""
from __future__ import annotations

import json
import os
import platform
import re
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

from . import __version__
from .protocol import JobValidationError, load_job, utc_now, validate_job

from binance_data_engine.client import BinancePublicClient
from report_engine import generate_intraday_snapshot_pdf

DIRECTORIES = (
    "config", "jobs/inbox", "jobs/validated", "jobs/awaiting_approval", "jobs/running",
    "jobs/completed", "jobs/failed", "jobs/cancelled", "jobs/archive",
    "reports/opening", "reports/closing", "reports/intraday", "reports/audit",
    "data/cache", "data/snapshots", "data/manifests", "logs",
    "skills/binance-apertura-mercado", "skills/binance-cierre-mercado",
    "skills/binance-momento-mercado", "skills/binance-revision-skills", "temp",
)
STATES = ("inbox", "validated", "awaiting_approval", "running", "completed", "failed", "cancelled", "archive")
JOB_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_LOCAL_LOCKS: dict[str, threading.Lock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


class Workspace:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for relative in DIRECTORIES:
            target = self.root / relative
            # Check every existing component before mkdir: mkdir(parents=True)
            # follows symlinks, so checking only after creation is too late.
            current = self.root
            for part in Path(relative).parts:
                current = current / part
                resolved = current.resolve()
                if not resolved.is_relative_to(self.root):
                    raise ValueError(f"Workspace path escapes root: {relative}")
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
        if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
            raise ValueError("job_id must be a canonical UUID")
        try:
            if str(UUID(job_id)) != job_id.lower():
                raise ValueError
        except ValueError as exc:
            raise ValueError("job_id must be a canonical UUID") from exc
        return self.directory(f"jobs/{state}") / f"{job_id}.json"


class JobManager:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.workspace.initialize()

    @contextmanager
    def _workspace_lock(self) -> Iterator[None]:
        """Serialize lifecycle operations across processes on this local workspace."""
        lock_path = self.workspace.directory("logs") / "job-manager.lock"
        lock_key = str(self.workspace.root)
        with _LOCAL_LOCKS_GUARD:
            local_lock = _LOCAL_LOCKS.setdefault(lock_key, threading.Lock())
        with local_lock, lock_path.open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt
                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

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
        with self._workspace_lock():
            if any(self.workspace.job_path(state, job["job_id"]).exists() for state in STATES):
                raise JobValidationError(f"Duplicate job_id: {job['job_id']}")
            record = {**job, "status": "inbox", "updated_at_utc": utc_now()}
            destination = self.workspace.job_path("inbox", job["job_id"])
            # Exclusive creation is a second guard against accidental replacement.
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(record, stream, indent=2, ensure_ascii=False)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                try:
                    destination.unlink()
                except OSError:
                    pass
                raise
            return record

    def _find(self, job_id: str):
        matches = [
            (state, self.workspace.job_path(state, job_id))
            for state in STATES
            if self.workspace.job_path(state, job_id).is_file()
        ]
        if len(matches) > 1:
            states = ", ".join(state for state, _ in matches)
            raise JobValidationError(f"Job {job_id} exists in multiple lifecycle states: {states}")
        return matches[0] if matches else None

    def get(self, job_id: str) -> dict[str, Any]:
        with self._workspace_lock():
            found = self._find(job_id)
            if not found:
                raise FileNotFoundError(f"Job not found: {job_id}")
            record = json.loads(found[1].read_text(encoding="utf-8"))
            # The directory is authoritative if recovery observes a crash between
            # writing the transition record and renaming it into the next state.
            record["status"] = found[0]
            return record

    def _move(self, job: dict[str, Any], old_state: str, new_state: str) -> None:
        source = self.workspace.job_path(old_state, job["job_id"])
        target = self.workspace.job_path(new_state, job["job_id"])
        if not source.is_file():
            raise JobValidationError(f"Job is no longer in state {old_state}")
        if target.exists():
            raise JobValidationError(f"Job already exists in state {new_state}")
        job["status"] = new_state
        job["updated_at_utc"] = utc_now()
        # Update the record first, then atomically rename it. If interrupted
        # between these operations, the source directory remains authoritative
        # and get() normalizes the visible status from that directory.
        self._atomic_write(source, job)
        # Both directories are within one workspace filesystem. This rename is
        # atomic: after it, the job exists only in the destination state.
        os.replace(source, target)

    def validate_pending(self, job_id: str) -> str:
        with self._workspace_lock():
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
        with self._workspace_lock():
            found = self._find(job_id)
            if not found or found[0] != "awaiting_approval":
                raise JobValidationError("Only jobs awaiting approval can be approved")
            state, path = found
            job = json.loads(path.read_text(encoding="utf-8"))
            job["approval"]["granted"] = True
            validate_job({k: v for k, v in job.items() if k not in {"status", "updated_at_utc"}})
            self._move(job, state, "validated")

    def claim(self, job_id: str) -> dict[str, Any]:
        with self._workspace_lock():
            found = self._find(job_id)
            if not found or found[0] != "validated":
                raise JobValidationError("Only validated jobs can be executed")
            job = json.loads(found[1].read_text(encoding="utf-8"))
            if job["approval"]["required"] and not job["approval"]["granted"]:
                raise JobValidationError("Job has not received explicit approval")
            self._move(job, "validated", "running")
            return job

    def finish(self, job_id: str, result: dict[str, Any], success: bool = True) -> None:
        with self._workspace_lock():
            found = self._find(job_id)
            if not found or found[0] != "running":
                raise JobValidationError("Only running jobs can be completed")
            job = json.loads(found[1].read_text(encoding="utf-8"))
            job["result"] = result
            self._move(job, "running", "completed" if success else "failed")


class JobRunner:
    def __init__(self, manager: JobManager):
        self.manager = manager
        self.handlers = {
            "engine.health_check": self._health_check,
            "market.intraday_snapshot": self._intraday_snapshot,
        }

    def _health_check(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "engine": "MASTER ARSENAL Local Engine", "engine_version": __version__,
            "python_version": sys.version.split()[0], "platform": platform.platform(),
            "workspace": str(self.manager.workspace.root),
            "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "implemented_job_types": sorted(self.handlers), "read_only": True,
        }

    def _intraday_snapshot(self, job: dict[str, Any]) -> dict[str, Any]:
        parameters = job["parameters"]
        allowed = {"cutoff_utc", "interval", "market"}
        unknown = set(parameters) - allowed
        if unknown:
            raise ValueError(f"Unknown intraday parameters: {sorted(unknown)}")
        cutoff_text = parameters.get("cutoff_utc")
        if not isinstance(cutoff_text, str):
            raise ValueError("parameters.cutoff_utc is required as an ISO-8601 UTC string")
        try:
            cutoff = datetime.fromisoformat(cutoff_text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("parameters.cutoff_utc must be an ISO-8601 UTC string") from exc
        if cutoff.tzinfo is None or cutoff.utcoffset().total_seconds() != 0:
            raise ValueError("parameters.cutoff_utc must include a UTC timezone")
        interval = parameters.get("interval", "1h")
        market = parameters.get("market", "spot")
        if not isinstance(interval, str):
            raise ValueError("parameters.interval must be a string")
        if market not in {"spot", "usdm"}:
            raise ValueError("parameters.market must be 'spot' or 'usdm'")
        if job["output"]["format"] != "pdf":
            raise ValueError("market.intraday_snapshot requires output.format='pdf'")

        output_directory = self.manager.workspace.directory(job["output"]["directory"])
        artifact = generate_intraday_snapshot_pdf(
            BinancePublicClient(), cutoff, output_directory,
            interval=interval, market=market,
        )
        resolved_artifact = artifact.resolve()
        if not resolved_artifact.is_relative_to(self.manager.workspace.root):
            raise ValueError("Generated report artifact escaped the workspace")
        if not resolved_artifact.is_file():
            raise ValueError("PDF report generation did not produce an artifact")
        return {
            "report_type": "market.intraday_snapshot",
            "format": "pdf",
            "artifact_path": str(resolved_artifact.relative_to(self.manager.workspace.root)),
            "window_start_utc": cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
                                      .isoformat().replace("+00:00", "Z"),
            "cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
            "market": market,
            "interval": interval,
            "read_only": True,
        }

    def run(self, job_id: str) -> dict[str, Any]:
        job = self.manager.claim(job_id)
        handler = self.handlers.get(job["job_type"])
        if handler is None:
            message = f"Job type {job['job_type']!r} is defined but not implemented by this runtime"
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
