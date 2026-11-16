"""Workspace, cross-process-safe job lifecycle, approval gate, and dispatcher."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

from . import __version__
from .protocol import JobValidationError, load_job, utc_now, validate_job

from binance_data_engine.client import BinancePublicClient
from report_engine.timezone import REPORT_TIMEZONE, current_local_report_date

from report_engine import (
    build_skills_audit_pdf, generate_closing_report_pdf,
    generate_intraday_snapshot_pdf, generate_opening_report_pdf,
    audit_cross_report_consistency, audit_evidence_manifest, audit_market_report_artifact,
)

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
            "market.opening_report": self._opening_report,
            "market.closing_report": self._closing_report,
            "market.intraday_snapshot": self._intraday_snapshot,
            "skills.audit": self._skills_audit,
        }

    def _health_check(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "engine": "MASTER ARSENAL Local Engine", "engine_version": __version__,
            "python_version": sys.version.split()[0], "platform": platform.platform(),
            "workspace": str(self.manager.workspace.root),
            "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "implemented_job_types": sorted(self.handlers), "read_only": True,
        }

    def _evidence_manifest_metadata(self, artifact: Path) -> dict[str, Any]:
        directory = self.manager.workspace.directory("data/manifests")
        manifest = (directory / f"{artifact.stem}.evidence.json").resolve(strict=True)
        if not manifest.is_relative_to(directory) or not manifest.is_file():
            raise ValueError("Report evidence manifest is missing or escaped its fixed directory")
        raw = manifest.read_bytes()
        if len(raw) > 50_000_000:
            raise ValueError("Report evidence manifest exceeds the 50 MB safety limit")
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("schema") != "ma.report-evidence/v2":
            raise ValueError("Report evidence manifest schema is invalid")
        if payload.get("pdf_filename") != artifact.name:
            raise ValueError("Evidence manifest PDF filename does not match the generated artifact")
        if payload.get("pdf_sha256") != hashlib.sha256(artifact.read_bytes()).hexdigest():
            raise ValueError("Evidence manifest PDF digest does not match the generated artifact")
        return {
            "manifest_path": manifest.relative_to(self.manager.workspace.root).as_posix(),
            "manifest_size_bytes": len(raw),
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _session_report(self, job: dict[str, Any], kind: str) -> dict[str, Any]:
        parameters = job["parameters"]
        allowed = {"session_date_local", "session_date_utc", "cutoff_local", "interval", "market"}
        unknown = set(parameters) - allowed
        if unknown:
            raise ValueError(f"Unknown {kind} report parameters: {sorted(unknown)}")
        session_date_text = parameters.get("session_date_local", parameters.get("session_date_utc"))
        if "session_date_local" in parameters and "session_date_utc" in parameters:
            raise ValueError("Specify session_date_local only; session_date_utc is a legacy alias")
        session_date = None
        if session_date_text is not None:
            if not isinstance(session_date_text, str):
                raise ValueError("parameters.session_date_local must be YYYY-MM-DD")
            try:
                session_date = datetime.strptime(session_date_text, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValueError("parameters.session_date_local must be YYYY-MM-DD") from exc
            if session_date.isoformat() != session_date_text:
                raise ValueError("parameters.session_date_local must be canonical YYYY-MM-DD")
        cutoff_text = parameters.get("cutoff_local")
        if kind == "opening" and cutoff_text is not None:
            raise ValueError("Opening reports do not accept cutoff_local; they use the previous completed local day")
        cutoff_local = None
        if cutoff_text is not None:
            if not isinstance(cutoff_text, str):
                raise ValueError("parameters.cutoff_local must be an ISO-8601 local datetime")
            try:
                cutoff_local = datetime.fromisoformat(cutoff_text)
            except ValueError as exc:
                raise ValueError("parameters.cutoff_local must be an ISO-8601 local datetime") from exc
        interval = parameters.get("interval", "1h")
        market = parameters.get("market", "spot")
        if not isinstance(interval, str):
            raise ValueError("parameters.interval must be a string")
        if not isinstance(market, str) or market not in {"spot", "usdm"}:
            raise ValueError("parameters.market must be 'spot' or 'usdm'")
        relative_directory = "reports/opening" if kind == "opening" else "reports/closing"
        expected_output = "market.opening_report" if kind == "opening" else "market.closing_report"
        if (job["output"]["format"] != "pdf" or job["output"]["directory"] != relative_directory):
            raise ValueError(f"{expected_output} output is fixed to PDF in {relative_directory}")
        output_directory = self.manager.workspace.directory(relative_directory)
        generator = generate_opening_report_pdf if kind == "opening" else generate_closing_report_pdf
        artifact = generator(
            BinancePublicClient(), output_directory, session_date=session_date,
            interval=interval, market=market,
            manifest_directory=self.manager.workspace.directory("data/manifests"),
            **({"cutoff_local": cutoff_local} if kind == "closing" and cutoff_local is not None else {}),
        )
        resolved = artifact.resolve(strict=True)
        if not resolved.is_relative_to(output_directory):
            raise ValueError(f"Generated {kind} report escaped its workspace directory")
        if not resolved.is_file() or resolved.suffix.lower() != ".pdf":
            raise ValueError(f"{kind.capitalize()} report did not produce a PDF artifact")
        payload = resolved.read_bytes()
        if len(payload) < 16 or not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-1024:]:
            raise ValueError(f"{kind.capitalize()} report failed PDF integrity checks")
        digest = hashlib.sha256(payload).hexdigest()
        manifest_metadata = self._evidence_manifest_metadata(resolved)
        manifest_file = self.manager.workspace.directory(manifest_metadata["manifest_path"])
        manifest_report = json.loads(manifest_file.read_text(encoding="utf-8"))["report"]
        return {
            "report_type": expected_output,
            "format": "pdf",
            "artifact_path": resolved.relative_to(self.manager.workspace.root).as_posix(),
            "filename": resolved.name,
            "size_bytes": len(payload),
            "sha256": digest,
            **manifest_metadata,
            "report_date_local": manifest_report["report_date_local"],
            "window_start_local": manifest_report["window_start_local"],
            "cutoff_local": manifest_report["cutoff_local"],
            "window_start_utc": manifest_report["session_start_utc"],
            "cutoff_utc": manifest_report["session_end_utc"],
            "market": market,
            "interval": interval,
            "source": "Binance public REST API",
            "read_only": True,
        }

    def _opening_report(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._session_report(job, "opening")

    def _closing_report(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._session_report(job, "closing")

    def _skills_audit(self, job: dict[str, Any]) -> dict[str, Any]:
        if job["parameters"]:
            raise ValueError("skills.audit does not accept caller-supplied parameters")
        if (job["output"]["format"] != "pdf"
                or job["output"]["directory"] != "reports/audit"):
            raise ValueError("skills.audit output is fixed to PDF in reports/audit")
        generated = datetime.now(timezone.utc)
        audit_date_utc = generated.date().isoformat()
        audit_date_local = current_local_report_date(generated).isoformat()
        artifacts = []
        findings = []
        for report_type, relative_directory in (
            ("opening", "reports/opening"),
            ("closing", "reports/closing"),
            ("intraday", "reports/intraday"),
        ):
            directory = self.manager.workspace.directory(relative_directory)
            for candidate in sorted(directory.glob("*.pdf")):
                resolved = candidate.resolve(strict=True)
                if not resolved.is_relative_to(directory):
                    findings.append({
                        "severity": "critical", "title": "Artifact escaped report directory",
                        "evidence": str(candidate), "recommendation": "Quarantine and investigate the path.",
                    })
                    continue
                payload = resolved.read_bytes()
                item = {
                    "filename": resolved.name, "report_type": report_type,
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                try:
                    qa = audit_market_report_artifact(resolved, report_type)
                    item.update({
                        "qa_status": qa["status"],
                        "page_count": qa["structural_qa"]["page_count"],
                        "issues": "; ".join(qa["missing_markers"]) if qa["missing_markers"]
                                  else "Structural and required-content checks passed.",
                    })
                    if qa["status"] != "passed":
                        findings.append({
                            "severity": "high", "title": f"Required report content missing: {resolved.name}",
                            "evidence": item["issues"],
                            "recommendation": "Regenerate the report with all required sections and source registers.",
                        })
                except Exception as exc:
                    item.update({
                        "qa_status": "failed", "page_count": "Unknown",
                        "issues": f"{type(exc).__name__}: {exc}",
                    })
                    findings.append({
                        "severity": "high", "title": f"PDF structural QA failed: {resolved.name}",
                        "evidence": item["issues"],
                        "recommendation": "Regenerate the artifact and inspect the source evidence.",
                    })
                artifacts.append(item)
        findings.append({
            "severity": "warning", "title": "CI and live-test evidence not attached",
            "evidence": "The local workspace contains no trusted CI test-run manifest.",
            "recommendation": "Attach verified GitHub Actions results and separate live endpoint checks before certifying test coverage.",
        })
        manifest_directory = self.manager.workspace.directory("data/manifests")
        manifest_paths = sorted(manifest_directory.glob("*.evidence.json"))
        evidence_manifests = []
        for manifest_path in manifest_paths:
            resolved_manifest = manifest_path.resolve(strict=True)
            if not resolved_manifest.is_relative_to(manifest_directory):
                findings.append({
                    "severity": "critical", "title": "Evidence manifest escaped fixed directory",
                    "evidence": str(manifest_path),
                    "recommendation": "Quarantine the manifest and investigate workspace integrity.",
                })
                continue
            try:
                audit_result = audit_evidence_manifest(
                    resolved_manifest, self.manager.workspace.root
                )
                evidence_manifests.append(audit_result)
                if audit_result["status"] != "passed":
                    findings.append({
                        "severity": "high", "title": f"Raw evidence audit failed: {resolved_manifest.name}",
                        "evidence": "; ".join(audit_result.get("findings", [])),
                        "recommendation": "Reacquire source data and regenerate the affected report and manifest.",
                    })
            except Exception as exc:
                findings.append({
                    "severity": "high", "title": f"Evidence manifest could not be audited: {resolved_manifest.name}",
                    "evidence": f"{type(exc).__name__}: {exc}",
                    "recommendation": "Quarantine malformed evidence and regenerate the report.",
                })
        cross_report = audit_cross_report_consistency(
            [path for path in manifest_paths if path.is_file()],
            self.manager.workspace.root,
        )
        if cross_report["status"] == "failed":
            findings.append({
                "severity": "high", "title": "Cross-report candle evidence mismatch",
                "evidence": "; ".join(cross_report["mismatches"]),
                "recommendation": "Reconcile the source acquisition and regenerate inconsistent reports.",
            })
        elif cross_report["status"] == "not_verified":
            findings.append({
                "severity": "warning", "title": "No overlapping report candles available",
                "evidence": "Cross-report comparison could not be performed on the available manifests.",
                "recommendation": "Generate reports with overlapping windows to enable consistency checks.",
            })
        manifest_names = {item.get("pdf_filename") for item in evidence_manifests}
        for item in artifacts:
            if item["filename"] not in manifest_names:
                findings.append({
                    "severity": "high", "title": f"Evidence manifest missing for {item['filename']}",
                    "evidence": "No matching source-linked manifest was found.",
                    "recommendation": "Regenerate the report through the Local Engine evidence workflow.",
                })
        if not manifest_paths:
            findings.append({
                "severity": "warning", "title": "No raw evidence manifests available",
                "evidence": "No source-linked raw-candle manifests were found in data/manifests.",
                "recommendation": "Generate market reports through Local Engine before running a full audit.",
            })
        if not artifacts:
            findings.append({
                "severity": "warning", "title": "No market report artifacts available",
                "evidence": "No opening, closing, or intraday PDF files were found in the workspace.",
                "recommendation": "Generate reports before attempting a full cross-report audit.",
            })
        manifest_reports = []
        for manifest_path in manifest_paths:
            try:
                manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_report = manifest_payload.get("report")
                if isinstance(manifest_report, dict):
                    manifest_reports.append({
                        "report_type": manifest_payload.get("report_type"),
                        "report": manifest_report,
                        "manifest": manifest_path.name,
                    })
            except Exception:
                continue

        def check(check_id, title, status, severity, evidence, recommendation):
            return {
                "id": check_id, "case": title, "status": status, "severity": severity,
                "evidence": evidence, "recommendation": recommendation,
            }

        opening_reports = [x["report"] for x in manifest_reports if x["report_type"] == "opening"]
        closing_reports = [x["report"] for x in manifest_reports if x["report_type"] == "closing"]
        intraday_reports = [x["report"] for x in manifest_reports if x["report_type"] == "intraday"]
        all_reports = [x["report"] for x in manifest_reports]
        local_windows_ok = bool(all_reports) and all(
            item.get("report_timezone") == REPORT_TIMEZONE
            and item.get("window_semantics") == "[start, cutoff)"
            and isinstance(item.get("is_partial"), bool)
            for item in all_reports
        )
        opening_dates_ok = bool(opening_reports) and all(
            isinstance(item.get("requested_report_date_local"), str)
            and item.get("cutoff_resolution") == "previous_local_calendar_day"
            and item.get("report_date_local") == (
                datetime.fromisoformat(item["requested_report_date_local"]).date()
                - timedelta(days=1)
            ).isoformat()
            for item in opening_reports
        )
        closing_windows_ok = bool(closing_reports) and all(
            item.get("cutoff_resolution") in {
                "explicit_local_cutoff", "execution_time_local_default", "completed_historical_local_day"
            }
            and item.get("report_date_local") == item.get("requested_report_date_local")
            for item in closing_reports
        )
        account_disclosed = bool(all_reports) and all(
            item.get("binance_account_data_status") == "unavailable" for item in all_reports
        )
        scorecard_missing = bool(closing_reports) and all(
            item.get("opening_forecast_scorecard_status") == "not_implemented"
            for item in closing_reports
        )
        desk_checks = [
            check("TIME-01", "Dominican local-day boundaries", "passed" if local_windows_ok else "not_verified",
                  "critical", "All retained manifests declare the IANA timezone and half-open window." if local_windows_ok
                  else "No complete set of valid local-window manifests is available.",
                  "Regenerate and independently audit every operational report."),
            check("OPEN-01", "Opening uses previous local calendar day", "passed" if opening_dates_ok else "not_verified",
                  "high", "Opening request dates and reference dates were reconciled from evidence manifests." if opening_dates_ok
                  else "No opening evidence proves the previous-local-day rule.",
                  "Generate an opening report and retain its request-date evidence."),
            check("CLOSE-01", "Closing partial-day cutoff", "passed" if closing_windows_ok else "not_verified",
                  "high", "Closing manifests declare explicit, execution-time, or historical-complete cutoff resolution." if closing_windows_ok
                  else "No closing evidence proves partial-day cutoff handling.",
                  "Generate a current-day closing report before local midnight and inspect the exact cutoff."),
            check("INTRA-01", "Intraday omitted-cutoff default", "passed" if any(
                      x.get("cutoff_resolution") == "execution_time_local_default" for x in intraday_reports
                  ) else "not_exercised" if intraday_reports else "not_verified",
                  "medium", "An intraday report records execution-time local cutoff." if any(
                      x.get("cutoff_resolution") == "execution_time_local_default" for x in intraday_reports
                  ) else "No retained intraday report proves the omitted-cutoff path.",
                  "Run an intraday job with no cutoff parameter."),
            check("US-01", "U.S. exchange weekends and holidays", "not_implemented", "high",
                  "No exchange-calendar adapter is integrated.",
                  "Implement and independently test weekend/holiday last-session selection."),
            check("US-02", "U.S. cash-session DST and state", "not_implemented", "high",
                  "Premarket/regular/postmarket classification and DST-aware session calendar are not integrated.",
                  "Add an authoritative exchange calendar and test both U.S. DST transitions."),
            check("ACCT-01", "Missing private Binance account access", "disclosed" if account_disclosed else "not_verified",
                  "medium", "Reports explicitly label private account analytics unavailable." if account_disclosed
                  else "No retained report proves account-data unavailability is disclosed.",
                  "Keep the unavailable disclosure until an authorized read-only source or export parser exists."),
            check("ACCT-02", "External deposits/withdrawals excluded from PnL", "not_applicable", "high",
                  "No private account ledger or portfolio return calculation is implemented.",
                  "Implement ledger reconciliation before reporting portfolio returns; exclude deposits/withdrawals from PnL."),
            check("ACCT-03", "Missing historical account balances", "not_applicable", "medium",
                  "No private account history or balance snapshots are ingested.",
                  "Require complete historical balances before making account-performance claims."),
            check("SCORE-01", "Same-date opening forecast scorecard", "not_implemented" if scorecard_missing else "not_verified",
                  "high", "Closing reports disclose that scorecard linkage is not implemented." if scorecard_missing
                  else "No closing report proves scorecard linkage or explicit unavailability.",
                  "Persist opening scenarios and compare them with same-date observed outcomes."),
            check("PKG-01", "Original skill package integrity and version history", "not_verified", "high",
                  "The local workspace does not contain a signed source-package integrity record.",
                  "Add package hashes, version identifiers, and inspectable change history to the audit input."),
            check("CI-01", "Cross-platform CI evidence on audited code head", "not_verified", "high",
                  "No trusted CI run manifest is attached to this local workspace audit.",
                  "Attach the final-head Ubuntu/Windows Python 3.11/3.12 Actions run and inspect all jobs."),
        ]
        unresolved = [
            item for item in desk_checks
            if item["severity"] in {"critical", "high"}
            and item["status"] in {"failed", "not_implemented", "not_verified", "not_applicable"}
        ]
        medium_unresolved = [
            item for item in desk_checks
            if item["severity"] == "medium"
            and item["status"] in {"failed", "not_implemented", "not_verified", "not_applicable", "not_exercised"}
        ]
        audit_verdict = (
            "No aprobado" if unresolved else
            "Aprobado con reservas" if medium_unresolved else
            "Aprobado"
        )
        for item in unresolved:
            findings.append({
                "severity": item["severity"], "title": f"Desk check {item['id']}: {item['case']}",
                "evidence": item["evidence"], "recommendation": item["recommendation"],
            })
        change_history = [
            {
                "date": audit_date_local, "version": __version__,
                "change": "Phase 3 PDF reporting with Dominican local-day windows and evidence schema v2.",
            },
            {
                "date": audit_date_local, "version": "original-skill-parity",
                "change": "U.S. market/calendar, private-account, scorecard, and full audit-matrix parity remain incomplete.",
            },
        ]
        report = {
            "audit_date_utc": audit_date_utc,
            "audit_date_local": audit_date_local,
            "report_timezone": REPORT_TIMEZONE,
            "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
            "report_engine_version": __version__,
            "audit_verdict": audit_verdict,
            "desk_checks": desk_checks,
            "change_history": change_history,
            "artifacts": artifacts,
            "evidence_manifests": evidence_manifests,
            "cross_report_consistency": cross_report,
            "findings": findings,
            "test_evidence": [],
        }
        output_directory = self.manager.workspace.directory("reports/audit")
        artifact = build_skills_audit_pdf(report, output_directory)
        resolved = artifact.resolve(strict=True)
        if not resolved.is_relative_to(output_directory):
            raise ValueError("Generated audit escaped reports/audit")
        payload = resolved.read_bytes()
        if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-1024:]:
            raise ValueError("Skills audit failed PDF integrity checks")
        return {
            "report_type": "skills.audit", "format": "pdf",
            "artifact_path": resolved.relative_to(self.manager.workspace.root).as_posix(),
            "filename": resolved.name, "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "artifacts_inspected": len(artifacts),
            "evidence_manifests_checked": len(evidence_manifests),
            "cross_report_consistency_status": cross_report["status"],
            "overlapping_candles_checked": cross_report["overlapping_candles_checked"],
            "findings_count": len(findings),
            "read_only": True,
        }

    def _intraday_snapshot(self, job: dict[str, Any]) -> dict[str, Any]:
        parameters = job["parameters"]
        allowed = {"cutoff_utc", "cutoff_local", "interval", "market"}
        unknown = set(parameters) - allowed
        if unknown:
            raise ValueError(f"Unknown intraday parameters: {sorted(unknown)}")
        if "cutoff_utc" in parameters and "cutoff_local" in parameters:
            raise ValueError("Specify cutoff_local or cutoff_utc, not both")
        cutoff = None
        cutoff_text = parameters.get("cutoff_utc")
        if cutoff_text is not None:
            if not isinstance(cutoff_text, str):
                raise ValueError("parameters.cutoff_utc must be an ISO-8601 UTC string")
            try:
                cutoff = datetime.fromisoformat(cutoff_text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("parameters.cutoff_utc must be an ISO-8601 UTC string") from exc
            if cutoff.tzinfo is None or cutoff.utcoffset().total_seconds() != 0:
                raise ValueError("parameters.cutoff_utc must include a UTC timezone")
        cutoff_local_text = parameters.get("cutoff_local")
        cutoff_local = None
        if cutoff_local_text is not None:
            if not isinstance(cutoff_local_text, str):
                raise ValueError("parameters.cutoff_local must be an ISO-8601 local datetime")
            try:
                cutoff_local = datetime.fromisoformat(cutoff_local_text)
            except ValueError as exc:
                raise ValueError("parameters.cutoff_local must be an ISO-8601 local datetime") from exc
        interval = parameters.get("interval", "1h")
        market = parameters.get("market", "spot")
        if not isinstance(interval, str):
            raise ValueError("parameters.interval must be a string")
        if not isinstance(market, str) or market not in {"spot", "usdm"}:
            raise ValueError("parameters.market must be 'spot' or 'usdm'")
        if (job["output"]["format"] != "pdf"
                or job["output"]["directory"] != "reports/intraday"):
            raise ValueError(
                "market.intraday_snapshot output is fixed to PDF in reports/intraday"
            )

        output_directory = self.manager.workspace.directory("reports/intraday")
        artifact = generate_intraday_snapshot_pdf(
            BinancePublicClient(), cutoff, output_directory,
            interval=interval, market=market,
            manifest_directory=self.manager.workspace.directory("data/manifests"),
            cutoff_local=cutoff_local,
        )
        resolved_artifact = artifact.resolve(strict=True)
        if not resolved_artifact.is_relative_to(output_directory):
            raise ValueError("Generated report artifact escaped reports/intraday")
        if not resolved_artifact.is_file() or resolved_artifact.suffix.lower() != ".pdf":
            raise ValueError("PDF report generation did not produce a PDF artifact")
        size_bytes = resolved_artifact.stat().st_size
        if size_bytes < 16:
            raise ValueError("Generated PDF is unexpectedly small")
        with resolved_artifact.open("rb") as stream:
            header = stream.read(5)
            stream.seek(max(0, size_bytes - 1024))
            tail = stream.read()
        if header != b"%PDF-" or b"%%EOF" not in tail:
            raise ValueError("Generated artifact failed PDF signature checks")
        digest = hashlib.sha256(resolved_artifact.read_bytes()).hexdigest()
        manifest_metadata = self._evidence_manifest_metadata(resolved_artifact)
        manifest_file = self.manager.workspace.directory(manifest_metadata["manifest_path"])
        manifest_report = json.loads(manifest_file.read_text(encoding="utf-8"))["report"]
        return {
            "report_type": "market.intraday_snapshot",
            "format": "pdf",
            "artifact_path": resolved_artifact.relative_to(self.manager.workspace.root).as_posix(),
            "filename": resolved_artifact.name,
            "size_bytes": size_bytes,
            "sha256": digest,
            **manifest_metadata,
            "report_date_local": manifest_report["report_date_local"],
            "window_start_local": manifest_report["window_start_local"],
            "cutoff_local": manifest_report["cutoff_local"],
            "window_start_utc": manifest_report["window_start_utc"],
            "cutoff_utc": manifest_report["cutoff_utc"],
            "market": market,
            "interval": interval,
            "source": "Binance public REST API",
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
