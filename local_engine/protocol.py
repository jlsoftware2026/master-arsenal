"""Versioned, strict JSON job protocol."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any
from uuid import UUID, uuid4

SCHEMA_VERSION = "ma.job/v1"
JOB_TYPES = frozenset({
    "market.opening_report", "market.closing_report", "market.intraday_snapshot",
    "skills.audit", "engine.health_check", "engine.validate_data",
})
REQUESTERS = frozenset({"chatgpt", "claude", "user"})
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)


class JobValidationError(ValueError):
    """Raised when a job does not conform to the supported protocol."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_job(job_type: str, parameters: dict[str, Any] | None = None,
            requested_by: str = "user") -> dict[str, Any]:
    default_output = (
        {"format": "pdf", "directory": "reports/intraday"}
        if job_type == "market.intraday_snapshot"
        else {"format": "json", "directory": "reports"}
    )
    job = {
        "schema": SCHEMA_VERSION, "job_id": str(uuid4()), "created_at_utc": utc_now(),
        "requested_by": requested_by, "job_type": job_type, "parameters": parameters or {},
        "output": default_output,
        "approval": {"required": True, "granted": False},
    }
    validate_job(job)
    return job


def validate_job(job: Any) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise JobValidationError("Job root must be a JSON object")
    required = {"schema", "job_id", "created_at_utc", "requested_by", "job_type",
                "parameters", "output", "approval"}
    if set(job) != required:
        missing, extra = sorted(required - set(job)), sorted(set(job) - required)
        raise JobValidationError(f"Invalid job fields; missing={missing}, unknown={extra}")
    if job["schema"] != SCHEMA_VERSION:
        raise JobValidationError(f"Unsupported schema: {job['schema']!r}")
    job_id = job["job_id"]
    if not isinstance(job_id, str) or not UUID_RE.fullmatch(job_id):
        raise JobValidationError("job_id must be a canonical UUID")
    try:
        if str(UUID(job_id)) != job_id.lower():
            raise ValueError
    except ValueError as exc:
        raise JobValidationError("job_id must be a canonical UUID") from exc
    stamp = job["created_at_utc"]
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else None
    except ValueError as exc:
        raise JobValidationError("created_at_utc must be an ISO-8601 UTC timestamp") from exc
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise JobValidationError("created_at_utc must be an ISO-8601 UTC timestamp")
    if not isinstance(job["requested_by"], str) or job["requested_by"] not in REQUESTERS:
        raise JobValidationError("requested_by must be chatgpt, claude, or user")
    if not isinstance(job["job_type"], str) or job["job_type"] not in JOB_TYPES:
        raise JobValidationError(f"Unsupported job_type: {job['job_type']!r}")
    if not isinstance(job["parameters"], dict):
        raise JobValidationError("parameters must be an object")
    output = job["output"]
    if not isinstance(output, dict) or set(output) != {"format", "directory"}:
        raise JobValidationError("output must contain exactly format and directory")
    if not isinstance(output["format"], str) or output["format"] not in {"json", "pdf"}:
        raise JobValidationError("output.format must be json or pdf")
    directory = output["directory"]
    win_path = PureWindowsPath(directory) if isinstance(directory, str) else PureWindowsPath(".")
    posix_path = Path(directory) if isinstance(directory, str) else Path(".")
    if (not isinstance(directory, str) or not directory or posix_path.is_absolute()
            or win_path.is_absolute() or ".." in posix_path.parts or ".." in win_path.parts):
        raise JobValidationError("output.directory must be relative and must not traverse parent directories")
    approval = job["approval"]
    if not isinstance(approval, dict) or set(approval) != {"required", "granted"}:
        raise JobValidationError("approval must contain exactly required and granted")
    if not isinstance(approval["required"], bool) or not isinstance(approval["granted"], bool):
        raise JobValidationError("approval flags must be booleans")
    if not approval["required"] and not approval["granted"]:
        raise JobValidationError("Jobs not requiring approval must explicitly be marked granted")
    return job


def load_job(path: Path) -> dict[str, Any]:
    try:
        return validate_job(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JobValidationError(f"Cannot read valid UTF-8 JSON job: {exc}") from exc
