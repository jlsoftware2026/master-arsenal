"""Workspace, cross-process-safe job lifecycle, approval gate, and dispatcher."""
from __future__ import annotations

import hashlib
import io
import json
import math
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
from zipfile import ZipFile

from . import __version__
from .protocol import JobValidationError, load_job, utc_now, validate_job

from binance_data_engine.client import BinancePublicClient
from report_engine.account_exports import collect_binance_account_exports
from report_engine.timezone import REPORT_TIMEZONE, current_local_report_date
from report_engine.us_market_calendar import classify_us_equity_session
from report_engine.instruments import build_instrument_record
from report_engine.binance_venue import BinanceSpotProductVerifier
from report_engine.research import build_research_packet
from report_engine.sec_edgar import SECEdgarCompanyFacts
from report_engine.clinical_trials import ClinicalTrialsGov
from report_engine.defillama import DeFiLlamaProtocolResearch
from report_engine.scenarios import calculate_long_scenarios
from report_engine.position_sizing import calculate_cash_position_size
from report_engine.fundamentals import calculate_financial_ratios
from report_engine.opportunity import write_opportunity_manifest, audit_opportunity_manifest
from report_engine.github_ci import GitHubActionsEvidence, resolve_git_head_sha, resolve_github_repository

from report_engine import (
    build_skills_audit_pdf, build_opportunity_report_pdf, generate_closing_report_pdf,
    generate_intraday_snapshot_pdf, generate_opening_report_pdf,
    audit_cross_report_consistency, audit_evidence_manifest, audit_market_report_artifact,
)

def verify_original_skill_packages(repository_root: Path | str) -> dict[str, Any]:
    """Verify original .skill archives, embedded source files, and ChatGPT adaptations."""
    root = Path(repository_root).resolve()
    manifest_path = root / "docs" / "original-skills-source" / "manifest.json"
    expected_names = {
        "binance-apertura-mercado", "binance-cierre-mercado",
        "binance-momento-mercado", "binance-revision-skills",
    }
    findings: list[str] = []
    packages: list[dict[str, Any]] = []
    manifest_bytes: bytes | None = None
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        manifest_bytes = manifest_text.encode("utf-8")
        manifest = json.loads(manifest_text)
        declared = manifest.get("packages")
        if not isinstance(declared, list):
            raise ValueError("Original skill source manifest has no packages list")
        declared_names = {item.get("name") for item in declared if isinstance(item, dict)}
        if declared_names != expected_names or len(declared) != len(expected_names):
            raise ValueError("Original skill source manifest must contain exactly the four named packages")

        for item in declared:
            name = item["name"]
            archive_sha = item.get("archive_sha256")
            source_sha = item.get("source_skill_sha256")
            for label, value in (("archive", archive_sha), ("SKILL.md", source_sha)):
                if not isinstance(value, str) or len(value) != 64:
                    raise ValueError(f"{name}: recorded original {label} SHA-256 is invalid")
                try:
                    int(value, 16)
                except ValueError as exc:
                    raise ValueError(f"{name}: recorded {label} SHA-256 must be hexadecimal") from exc

            archive_size = item.get("archive_bytes")
            source_size = item.get("source_skill_bytes")
            if not isinstance(archive_size, int) or archive_size <= 0:
                raise ValueError(f"{name}: original archive byte count is invalid")
            if not isinstance(source_size, int) or source_size <= 0:
                raise ValueError(f"{name}: original SKILL.md byte count is invalid")

            expected_member = [f"{name}/SKILL.md"]
            if item.get("zip_members") != expected_member:
                raise ValueError(f"{name}: recorded original package structure is invalid")

            payload_relative = f"artifacts/original-skills/{name}.skill"
            if item.get("repository_payload") != payload_relative:
                raise ValueError(f"{name}: repository payload path does not match the controlled package location")
            payload_path = (root / payload_relative).resolve()
            if not payload_path.is_relative_to(root) or not payload_path.is_file():
                raise ValueError(f"{name}: original .skill package is missing or outside the repository")
            archive_bytes = payload_path.read_bytes()
            if len(archive_bytes) != archive_size:
                raise ValueError(f"{name}: original archive byte count does not match the manifest")
            actual_archive_sha = hashlib.sha256(archive_bytes).hexdigest()
            if actual_archive_sha != archive_sha:
                raise ValueError(f"{name}: original archive SHA-256 does not match the manifest")

            with ZipFile(io.BytesIO(archive_bytes), "r") as archive:
                actual_members = [member for member in archive.namelist() if not member.endswith("/")]
                if actual_members != expected_member:
                    raise ValueError(f"{name}: original ZIP members do not match the expected single SKILL.md")
                source_bytes = archive.read(expected_member[0])
            if len(source_bytes) != source_size:
                raise ValueError(f"{name}: embedded SKILL.md byte count does not match the manifest")
            actual_source_sha = hashlib.sha256(source_bytes).hexdigest()
            if actual_source_sha != source_sha:
                raise ValueError(f"{name}: embedded SKILL.md SHA-256 does not match the manifest")

            adapted_path = root / "skills" / name / "SKILL.md"
            adapted_bytes = adapted_path.read_bytes()
            adapted_text = adapted_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            canonical_adapted_bytes = adapted_text.encode("utf-8")
            if not adapted_text.startswith("---\n") or "\n---\n" not in adapted_text[4:]:
                raise ValueError(f"{name}: adapted SKILL.md YAML frontmatter is missing")
            frontmatter = adapted_text.split("\n---", 1)[0]
            fields = {}
            for line in frontmatter.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip().strip("'\\"")
            body = adapted_text.split("\n---\n", 1)[1].lstrip("\n")
            if fields.get("name") != name or not body.startswith(f"# {name}\n"):
                raise ValueError(f"{name}: ChatGPT adaptation metadata/heading does not match source package")
            if not fields.get("version") or not fields.get("last_reviewed"):
                raise ValueError(f"{name}: adapted skill version and review date are required")
            if "## Local Engine workflow" not in body or "PDF" not in body:
                raise ValueError(f"{name}: ChatGPT adaptation is missing the Local Engine/PDF contract")

            packages.append({
                "name": name,
                "status": "passed",
                "archive_sha256": actual_archive_sha,
                "source_skill_sha256": actual_source_sha,
                "adapted_skill_sha256": hashlib.sha256(canonical_adapted_bytes).hexdigest(),
                "adapted_version": fields.get("version"),
                "last_reviewed": fields.get("last_reviewed"),
                "archive_members": actual_members,
                "archive_bytes": len(archive_bytes),
                "source_skill_bytes": len(source_bytes),
                "source_payload": payload_relative,
            })
    except Exception as exc:
        findings.append(f"{type(exc).__name__}: {exc}")

    all_verified = len(packages) == len(expected_names) and not findings
    return {
        "status": "passed" if all_verified else "failed",
        "adaptation_status": "passed" if all_verified and all(
            item.get("status") == "passed" for item in packages
        ) else "failed",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest() if manifest_bytes is not None else None,
        "packages": packages,
        "findings": findings,
    }

DIRECTORIES = (
    "config", "jobs/inbox", "jobs/validated", "jobs/awaiting_approval", "jobs/running",
    "jobs/completed", "jobs/failed", "jobs/cancelled", "jobs/archive",
    "reports/opening", "reports/closing", "reports/intraday", "reports/audit",
    "data/cache", "data/snapshots", "data/manifests", "data/account_exports", "logs",
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
            "investment.opportunity_report": self._opportunity_report,
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
        if parameters.get("session_date_local") is not None and parameters.get("session_date_utc") is not None:
            raise ValueError("Supply session_date_local or the legacy session_date_utc alias, not both")
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
            account_export_directory=self.manager.workspace.directory("data/account_exports"),
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
        opportunity_artifacts = []
        opportunity_report_directory = self.manager.workspace.directory("reports/opportunities")
        opportunity_manifest_directory = self.manager.workspace.directory("data/manifests/opportunities")
        opportunity_pdfs = sorted(opportunity_report_directory.glob("*.pdf"))
        opportunity_manifest_files = sorted(opportunity_manifest_directory.glob("*.opportunity.json"))
        opportunity_manifest_by_name = {
            item.name.removesuffix(".opportunity.json") + ".pdf": item
            for item in opportunity_manifest_files
        }
        audited_opportunity_manifests: set[str] = set()
        for candidate in opportunity_pdfs:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(opportunity_report_directory):
                opportunity_artifacts.append({
                    "filename": candidate.name, "qa_status": "failed",
                    "issues": "Opportunity PDF escaped its fixed directory.",
                })
                findings.append({
                    "severity": "Crítico", "title": "El PDF de oportunidad salió del directorio fijo",
                    "evidence": str(candidate),
                    "recommendation": "Poner el archivo en cuarentena e investigar la ruta.",
                })
                continue
            manifest_path = opportunity_manifest_by_name.get(resolved.name)
            if manifest_path is None:
                item = {
                    "filename": resolved.name, "qa_status": "not_verified",
                    "issues": "No se encontró un manifiesto de evidencia de oportunidad.",
                    "size_bytes": resolved.stat().st_size,
                    "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
                }
                opportunity_artifacts.append(item)
                findings.append({
                    "severity": "Alto", "title": f"Falta manifiesto de oportunidad: {resolved.name}",
                    "evidence": item["issues"],
                    "recommendation": "Regenerar el informe mediante investment.opportunity_report para crear su manifiesto vinculado.",
                })
                continue
            audited_opportunity_manifests.add(manifest_path.name)
            audit_result = audit_opportunity_manifest(manifest_path, self.manager.workspace.root)
            item = {
                "filename": resolved.name,
                "manifest": manifest_path.name,
                "qa_status": audit_result["status"],
                "issues": "; ".join(audit_result.get("findings", [])) or "PDF, paquete de evidencia y cálculos recalculados.",
                "size_bytes": resolved.stat().st_size,
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
                "instrument_key": audit_result.get("instrument_key"),
                "fact_count": audit_result.get("fact_count", 0),
                "fundamental_metrics_status": audit_result.get("fundamental_metrics_status", "not_applicable"),
                "fundamental_metrics_quality_status": audit_result.get("fundamental_metrics_quality_status", "not_applicable"),
"issuer_mapping_status": audit_result.get("issuer_mapping_status", "not_applicable"),
"venue_mapping_status": audit_result.get("venue_mapping_status", "not_applicable"),
                "scenario_status": audit_result.get("scenario_status", "not_applicable"),
                "position_sizing_status": audit_result.get("position_sizing_status", "not_applicable"),
            }
            opportunity_artifacts.append(item)
            if audit_result["status"] != "passed":
                findings.append({
                    "severity": "Alto", "title": f"Falló la auditoría del informe de oportunidad: {resolved.name}",
                    "evidence": item["issues"],
                    "recommendation": "Revisar la integridad del PDF, reconstrucción de evidencia y recálculo independiente de escenarios/dimensionamiento.",
                })
        for manifest_path in opportunity_manifest_files:
            if manifest_path.name not in audited_opportunity_manifests:
                orphan_result = audit_opportunity_manifest(manifest_path, self.manager.workspace.root)
                opportunity_artifacts.append({
                    "filename": orphan_result.get("pdf_filename", "PDF ausente"),
                    "manifest": manifest_path.name,
                    "qa_status": "failed",
                    "issues": "; ".join(orphan_result.get("findings", [])),
                })
                findings.append({
                    "severity": "Alto", "title": f"Manifiesto de oportunidad huérfano: {manifest_path.name}",
                    "evidence": "; ".join(orphan_result.get("findings", [])),
                    "recommendation": "Restaurar el PDF vinculado o retirar de forma controlada el manifiesto huérfano.",
                })
        opportunity_audit_status = (
            "not_exercised" if not opportunity_pdfs and not opportunity_manifest_files
            else "passed" if opportunity_artifacts and all(x.get("qa_status") == "passed" for x in opportunity_artifacts)
            else "failed"
        )
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
                        "severity": "Crítico", "title": "El archivo PDF salió del directorio de informes",
                        "evidence": str(candidate), "recommendation": "Poner el archivo en cuarentena e investigar la ruta.",
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
                                  else "Las comprobaciones estructurales y de contenido obligatorio fueron aprobadas.",
                    })
                    if qa["status"] != "passed":
                        findings.append({
                            "severity": "Alto", "title": f"Falta contenido obligatorio en el informe: {resolved.name}",
                            "evidence": item["issues"],
                            "recommendation": "Regenerar el informe con todas las secciones obligatorias y los registros de fuentes.",
                        })
                except Exception as exc:
                    item.update({
                        "qa_status": "failed", "page_count": "Desconocido",
                        "issues": f"{type(exc).__name__}: {exc}",
                    })
                    findings.append({
                        "severity": "Alto", "title": f"Falló la inspección estructural del PDF: {resolved.name}",
                        "evidence": item["issues"],
                        "recommendation": "Regenerar el archivo e inspeccionar la evidencia de origen.",
                    })
                artifacts.append(item)
        manifest_directory = self.manager.workspace.directory("data/manifests")
        manifest_paths = sorted(manifest_directory.glob("*.evidence.json"))
        evidence_manifests = []
        manifest_reports = []
        verified_manifest_paths = []
        for manifest_path in manifest_paths:
            resolved_manifest = manifest_path.resolve(strict=True)
            if not resolved_manifest.is_relative_to(manifest_directory):
                findings.append({
                    "severity": "Crítico", "title": "El manifiesto de evidencia salió del directorio fijo",
                    "evidence": str(manifest_path),
                    "recommendation": "Poner el manifiesto en cuarentena e investigar la integridad del espacio de trabajo.",
                })
                continue
            verified_manifest_paths.append(resolved_manifest)
            try:
                manifest_payload = json.loads(resolved_manifest.read_text(encoding="utf-8"))
                manifest_report = manifest_payload.get("report")
                if isinstance(manifest_report, dict):
                    manifest_reports.append({
                        "report_type": manifest_payload.get("report_type"),
                        "report": manifest_report,
                        "manifest": resolved_manifest.name,
                    })
                audit_result = audit_evidence_manifest(
                    resolved_manifest, self.manager.workspace.root
                )
                evidence_manifests.append(audit_result)
                if audit_result["status"] != "passed":
                    findings.append({
                        "severity": "Alto", "title": f"Falló la auditoría de evidencia sin procesar: {resolved_manifest.name}",
                        "evidence": "; ".join(audit_result.get("findings", [])),
                        "recommendation": "Volver a adquirir los datos de origen y regenerar el informe y el manifiesto afectados.",
                    })
            except Exception as exc:
                findings.append({
                    "severity": "Alto", "title": f"No se pudo auditar el manifiesto de evidencia: {resolved_manifest.name}",
                    "evidence": f"{type(exc).__name__}: {exc}",
                    "recommendation": "Poner la evidencia malformada en cuarentena y regenerar el informe.",
                })
        cross_report = audit_cross_report_consistency(
            verified_manifest_paths,
            self.manager.workspace.root,
        )
        if cross_report["status"] == "failed":
            findings.append({
                "severity": "Alto", "title": "Discrepancia entre velas de evidencia de informes distintos",
                "evidence": "; ".join(cross_report["mismatches"]),
                "recommendation": "Conciliar la adquisición de origen y regenerar los informes inconsistentes.",
            })
        elif cross_report["status"] == "not_verified":
            findings.append({
                "severity": "Medio", "title": "No hay velas superpuestas entre informes",
                "evidence": "No se pudo comparar informes entre sí con los manifiestos disponibles.",
                "recommendation": "Generar informes con ventanas superpuestas para habilitar las comprobaciones de coherencia.",
            })
        manifest_names = {item.get("pdf_filename") for item in evidence_manifests}
        for item in artifacts:
            if item["filename"] not in manifest_names:
                findings.append({
                    "severity": "Alto", "title": f"Falta el manifiesto de evidencia de {item['filename']}",
                    "evidence": "No se encontró un manifiesto vinculado a la fuente correspondiente.",
                    "recommendation": "Regenerar el informe mediante el flujo de evidencia del Local Engine.",
                })
        if not manifest_paths:
            findings.append({
                "severity": "Alto", "title": "No hay manifiestos de evidencia sin procesar",
                "evidence": "No se encontraron manifiestos de velas sin procesar vinculados a la fuente en data/manifests.",
                "recommendation": "Generar informes de mercado mediante Local Engine antes de ejecutar una auditoría completa.",
            })
        if not artifacts:
            findings.append({
                "severity": "Alto", "title": "No hay informes de mercado disponibles",
                "evidence": "No se encontraron archivos PDF de apertura, cierre o intradía en el espacio de trabajo.",
                "recommendation": "Generar informes antes de intentar una auditoría completa entre informes.",
            })
        expected_by_id = {
            "LANG-01": "El contenido y los encabezados de los informes operativos se entregan en español, como en las Skills originales.",
            "SKILL-01": "La estructura del ZIP original y los hashes de origen pueden verificarse de forma independiente.",
            "SKILL-02": "Las cuatro adaptaciones conservan nombres, metadatos, versionado y flujo de trabajo PDF.",
            "SKILL-03": "Los tres flujos operativos comparten contratos coherentes de fechas, datos y procedencia.",
            "SKILL-04": "Las frases originales activan el flujo correcto en el momento requerido.",
            "PDF-01": "Los PDF operativos se pueden analizar y renderizar, y contienen las secciones requeridas.",
            "CONTENT-01": "Las secciones originales de mercado, cuenta, escenarios, riesgos y fuentes están implementadas o declaradas como no disponibles.",
            "TIME-01": "Los límites horarios dominicanos se convierten correctamente a intervalos UTC semiabiertos.",
            "OPEN-01": "La fecha de referencia de Binance para apertura es el día calendario local anterior.",
            "CLOSE-01": "El cierre conserva la hora local exacta y excluye velas sin completar.",
            "INTRA-01": "Si no se indica hora de corte intradía, se utiliza la hora local de ejecución.",
            "US-01": "En fines de semana y festivos se utiliza la última sesión bursátil estadounidense completada.",
            "US-02": "La conversión ET/DST y la clasificación de la sesión estadounidense son correctas.",
            "ACCT-01": "Los informes separan la actividad transaccional importada de la valoración completa de cartera.",
            "ACCT-02": "Los depósitos y retiros externos se excluyen del rendimiento de trading.",
            "ACCT-03": "No se afirma rendimiento de cartera sin saldos históricos.",
            "SCORE-01": "El cierre compara el pronóstico de apertura de esa misma fecha cuando existe.",
            "PKG-01": "Los bytes y hashes del archivo original se verifican de forma independiente.",
            "CI-01": "El commit final supera CI en Ubuntu/Windows con Python 3.11/3.12.",
            "OPPORTUNITY-01": "Los informes de oportunidad conservan un manifiesto vinculado al PDF y superan la reconstrucción independiente de evidencia y cálculos.",
        }
        impact_by_severity = {
            "Crítico": "Puede producir fechas incorrectas, datos inventados, acceso inseguro o conclusiones materialmente falsas.",
            "Alto": "Afecta los cálculos, el período analizado o la interpretación del mercado.",
            "Medio": "Reduce la coherencia, cobertura o claridad.",
            "Bajo": "Mejora de estilo o no esencial.",
        }

        def check(check_id, title, status, severity, evidence, recommendation):
            return {
                "id": check_id, "case": title, "status": status, "severity": severity,
                "expected": expected_by_id.get(check_id, "El comportamiento requerido debe verificarse."),
                "observed": evidence, "impact": impact_by_severity.get(severity, "Impacto no clasificado."),
                "evidence": evidence, "recommendation": recommendation,
            }

        opening_reports = [x["report"] for x in manifest_reports if x["report_type"] == "opening"]
        closing_reports = [x["report"] for x in manifest_reports if x["report_type"] == "closing"]
        intraday_reports = [x["report"] for x in manifest_reports if x["report_type"] == "intraday"]
        all_reports = [x["report"] for x in manifest_reports]
        def calendar_evidence_reconciles(report):
            evidence = report.get("us_equity_calendar")
            if not isinstance(evidence, dict) or evidence.get("status") != "ok":
                return False
            try:
                as_of = datetime.fromisoformat(evidence["as_of_utc"].replace("Z", "+00:00"))
                recomputed = classify_us_equity_session(as_of)
            except (KeyError, TypeError, ValueError):
                return False
            if recomputed.get("status") != "ok":
                return False
            fields = (
                "session_state", "is_session_date", "session_date_et",
                "session_open_utc", "session_close_utc", "early_close",
                "last_completed_session_date", "last_completed_session_close_utc",
                "next_session_date", "next_session_open_utc",
            )
            return all(evidence.get(field) == recomputed.get(field) for field in fields)
        us_calendar_ok = bool(all_reports) and all(
            calendar_evidence_reconciles(item) for item in all_reports
        )
        us_calendar_failed = any(
            isinstance(item.get("us_equity_calendar"), dict)
            and item["us_equity_calendar"].get("status") == "ok"
            and not calendar_evidence_reconciles(item)
            for item in all_reports
        )
        def market_data_provenance_reconciles(report):
            snapshot = report.get("us_equity_market_data")
            if not isinstance(snapshot, dict) or snapshot.get("status") not in {"partial", "unavailable"}:
                return False
            if not isinstance(snapshot.get("provider"), str) or "Yahoo Finance" not in snapshot["provider"]:
                return False
            try:
                as_of = datetime.fromisoformat(snapshot["as_of_utc"].replace("Z", "+00:00"))
                expected = int(snapshot["expected_instruments"])
                available_count = int(snapshot["available_instruments"])
            except (KeyError, TypeError, ValueError, AttributeError):
                return False
            if as_of.tzinfo is None or expected <= 0 or available_count < 0 or available_count > expected:
                return False
            calendar_reference = (report.get("us_equity_calendar") or {}).get("as_of_utc")
            if calendar_reference != snapshot.get("as_of_utc"):
                return False
            groups = snapshot.get("groups")
            if not isinstance(groups, dict):
                return False
            quotes = [entry for values in groups.values() if isinstance(values, list) for entry in values]
            if len(quotes) != expected:
                return False
            valid_count = 0
            unavailable_symbols = []
            for entry in quotes:
                if not isinstance(entry, dict):
                    return False
                if entry.get("status") != "ok":
                    if (
                        not isinstance(entry.get("symbol"), str)
                        or not str(entry.get("source", "")).startswith("Yahoo Finance")
                        or not str(entry.get("source_url", "")).startswith("https://query1.finance.yahoo.com/v8/finance/chart/")
                        or not isinstance(entry.get("retrieved_at_utc"), str)
                    ):
                        return False
                    unavailable_symbols.append(entry.get("symbol"))
                    continue
                try:
                    price = float(entry["last_price"])
                    observed = datetime.fromisoformat(entry["observed_at_utc"].replace("Z", "+00:00"))
                except (KeyError, TypeError, ValueError, AttributeError):
                    return False
                if not math.isfinite(price) or price <= 0 or observed.tzinfo is None or observed > as_of:
                    return False
                if not str(entry.get("source", "")).startswith("Yahoo Finance"):
                    return False
                try:
                    retrieved = datetime.fromisoformat(entry["retrieved_at_utc"].replace("Z", "+00:00"))
                except (KeyError, TypeError, ValueError, AttributeError):
                    return False
                if retrieved.tzinfo is None:
                    return False
                if not str(entry.get("source_url", "")).startswith("https://query1.finance.yahoo.com/v8/finance/chart/"):
                    return False
                valid_count += 1
            return (
                valid_count == available_count
                and unavailable_symbols == snapshot.get("unavailable_symbols")
                and snapshot.get("status") == ("unavailable" if valid_count == 0 else "partial")
            )
        market_data_provenance_ok = bool(all_reports) and all(
            market_data_provenance_reconciles(item) for item in all_reports
        )
        def account_export_evidence_findings(report):
            findings = []
            snapshot = report.get("binance_account_data")
            if not isinstance(snapshot, dict):
                return ["account export evidence is missing"]
            if snapshot.get("status") not in {"complete", "partial"}:
                findings.append("CSV import status is " + str(snapshot.get("status")))
            try:
                account_start = datetime.fromisoformat(snapshot["window_start_utc"].replace("Z", "+00:00"))
                account_end = datetime.fromisoformat(snapshot["window_end_utc"].replace("Z", "+00:00"))
                report_start = datetime.fromisoformat(report["window_start_utc"].replace("Z", "+00:00"))
                report_end = datetime.fromisoformat(report["cutoff_utc"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError, AttributeError):
                return findings + ["report/account UTC window is missing or invalid"]
            if (
                account_start.tzinfo is None or account_end.tzinfo is None
                or report_start.tzinfo is None or report_end.tzinfo is None
                or account_start.astimezone(timezone.utc) != report_start.astimezone(timezone.utc)
                or account_end.astimezone(timezone.utc) != report_end.astimezone(timezone.utc)
            ):
                findings.append("account export window does not match report window")
            if (
                snapshot.get("file_count", 0) <= 0
                or snapshot.get("supported_file_count") != snapshot.get("file_count")
                or snapshot.get("parse_errors")
                or snapshot.get("unsupported_files")
                or snapshot.get("unknown_operation_count", 0) != 0
            ):
                findings.append("CSV files are unsupported, partial, ambiguous, or contain parse errors")
            allowed_assumptions = {
                "Naive UTC_Time values were interpreted as UTC; verify the export timezone setting."
            }
            if not set(snapshot.get("assumptions") or []).issubset(allowed_assumptions):
                findings.append("CSV contains an unsupported timestamp or parsing assumption")
            files = snapshot.get("files")
            if not isinstance(files, list) or len(files) != snapshot.get("file_count"):
                return findings + ["CSV manifest file count is inconsistent"]
            try:
                account_directory = self.manager.workspace.directory("data/account_exports")
                csv_paths = sorted(
                    path for path in account_directory.iterdir()
                    if path.suffix.lower() == ".csv" and not path.is_symlink()
                )
            except OSError:
                return findings + ["fixed account export directory is missing or inaccessible"]
            if len(csv_paths) != snapshot.get("file_count"):
                findings.append("CSV file set changed after report generation")
                return findings
            for item in files:
                if not isinstance(item, dict):
                    findings.append("CSV manifest entry is malformed")
                    continue
                digest = item.get("sha256")
                file_id = item.get("file_id")
                if (
                    not isinstance(file_id, str)
                    or not file_id.startswith("account_export_")
                    or not isinstance(digest, str)
                    or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest.lower())
                    or item.get("format") != "binance_transaction_history_csv"
                    or not isinstance(item.get("bytes"), int)
                    or item["bytes"] <= 0
                    or item["bytes"] > 20_000_000
                    or not isinstance(item.get("rows_scanned"), int)
                ):
                    findings.append("CSV manifest metadata is malformed")
                    continue
                try:
                    file_index = int(file_id.rsplit("_", 1)[1]) - 1
                    source_path = csv_paths[file_index]
                    if source_path.stat().st_size != item["bytes"]:
                        findings.append("CSV file size changed after report generation")
                        continue
                    raw = source_path.read_bytes()
                except (ValueError, IndexError, OSError):
                    findings.append("CSV source file cannot be reopened for integrity verification")
                    continue
                if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != digest:
                    findings.append("CSV SHA-256 changed after report generation")
            try:
                recomputed = collect_binance_account_exports(
                    account_directory, report_start, report_end
                )
            except Exception:
                return findings + ["independent CSV re-parse failed"]
            for field in (
                "status", "files", "file_count", "supported_file_count", "rows_scanned",
                "events_in_window", "duplicate_rows", "parse_errors", "unsupported_files",
                "aggregates_by_event_and_asset", "event_counts", "unknown_operation_count",
                "assumptions",
            ):
                if snapshot.get(field) != recomputed.get(field):
                    findings.append("independent CSV re-parse differs for " + field)
            return findings

        account_export_findings = []
        for item in all_reports:
            findings = account_export_evidence_findings(item)
            if findings:
                account_export_findings.append(
                    str(item.get("report_type", "report")) + ": " + "; ".join(findings)
                )
        account_export_ok = bool(all_reports) and not account_export_findings
        local_windows_ok = bool(all_reports) and len(evidence_manifests) == len(manifest_paths) and all(
            item.get("status") == "passed" for item in evidence_manifests
        ) and all(
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
        closing_windows_ok = bool(closing_reports) and any(
            item.get("is_partial") is True for item in closing_reports
        ) and all(
            item.get("cutoff_resolution") in {
                "explicit_local_cutoff", "execution_time_local_default", "completed_historical_local_day"
            }
            and item.get("report_date_local") == item.get("requested_report_date_local")
            for item in closing_reports
        )
        source_skill_integrity = verify_original_skill_packages(Path(__file__).resolve().parents[1])
        repository_root = Path(__file__).resolve().parents[1]
        if os.environ.get("GITHUB_ACTIONS", "").lower() == "true" or os.environ.get("CI", "").lower() == "true":
            ci_evidence = {
                "status": "not_verified", "repository": None, "commit_sha": None,
                "run_id": None, "jobs": [],
                "reason": "La auditoría ejecutada dentro de CI no consulta ni se autocertifica con su propia ejecución.",
            }
        else:
            ci_repository = resolve_github_repository(repository_root)
            ci_commit_sha = resolve_git_head_sha(repository_root)
            ci_evidence = GitHubActionsEvidence().verify(ci_repository, ci_commit_sha)
        if ci_evidence["status"] != "passed":
            findings.append({
                "severity": "Alto", "title": "No se verificó CI multiplataforma para el commit local",
                "evidence": ci_evidence.get("reason") or "No hay evidencia de CI exacta para el commit local.",
                "recommendation": "Ejecutar la matriz PR en Ubuntu/Windows con Python 3.11/3.12 para el commit exacto y volver a auditar.",
            })
        account_scope_disclosed = bool(all_reports) and all(
            isinstance(item.get("binance_account_data"), dict)
            and item["binance_account_data"].get("portfolio_equity_status") == "not_available"
            and item["binance_account_data"].get("flow_adjusted_return_status") == "not_available"
            for item in all_reports
        )
        account_export_not_supplied = bool(all_reports) and all(
            account_scope_disclosed
            and isinstance(item.get("binance_account_data"), dict)
            and item["binance_account_data"].get("status") in {
                "unavailable", "not_available", "not_supplied", "not_applicable"
            }
            for item in all_reports
        )
        content_disclosure_ok = bool(all_reports) and all(
            item.get("binance_account_data_status") in {
                "unavailable", "not_available", "not_supplied", "not_applicable", "complete", "partial"
            }
            and item.get("us_equity_market_data_status") in {
                "unavailable", "not_available", "not_integrated", "partial", "complete"
            }
            and isinstance(item.get("limitations"), str) and bool(item["limitations"].strip())
            and bool(item.get("bullish_scenario")) and bool(item.get("bearish_scenario"))
            and isinstance(item.get("macro_context"), str)
            and isinstance(item.get("news"), str)
            for item in all_reports
        )
        skill_contracts_ok = (
            source_skill_integrity.get("adaptation_status") == "passed"
            and ci_evidence.get("status") == "passed"
        )
        scorecard_statuses = [
            item.get("opening_forecast_scorecard_status", "not_verified")
            for item in closing_reports
        ]
        scorecard_ok = bool(scorecard_statuses) and all(
            status in {"passed", "not_applicable"} for status in scorecard_statuses
        )
        scorecard_failed = any(status == "failed" for status in scorecard_statuses)
        artifact_qa_ok = bool(artifacts) and all(item.get("qa_status") == "passed" for item in artifacts)
        passed_report_types = {item.get("report_type") for item in artifacts if item.get("qa_status") == "passed"}
        all_operational_artifacts_ok = artifact_qa_ok and {"opening", "closing", "intraday"}.issubset(passed_report_types)
        language_parity_ok = all_operational_artifacts_ok
        desk_checks = [
            check("LANG-01", "Idioma de los informes operativos",
                  "passed" if language_parity_ok else "not_verified", "Alto",
                  "Los tres tipos de informe (apertura, cierre e intradía) superaron la inspección independiente de marcadores en español."
                  if language_parity_ok else "No hay evidencia de QA para los tres tipos de informe con marcadores de contenido en español.",
                  "Generar y auditar de forma independiente los PDF de apertura, cierre e intradía; mantener títulos, secciones, tablas y avisos en español."),
            check("SKILL-01", "Metadatos y estructura ZIP de los paquetes originales",
                  source_skill_integrity["status"], "Alto",
                  "Los cuatro paquetes ZIP originales están versionados; se recalcularon sus SHA-256 y los hashes/tamaños de sus SKILL.md internos."
                  if source_skill_integrity["status"] == "passed" else "; ".join(source_skill_integrity["findings"]),
                  "Mantener versionados los paquetes .skill originales y recalcular sus hashes, tamaños y miembros ZIP en cada auditoría."),
            check("SKILL-02", "Identidad de adaptaciones y compatibilidad Local Engine/PDF",
                  source_skill_integrity.get("adaptation_status", "failed"), "Alto",
                  "Los cuatro archivos adaptados conservan la identidad esperada y el contrato Local Engine/PDF."
                  if source_skill_integrity.get("adaptation_status") == "passed"
                  else "; ".join(source_skill_integrity["findings"]),
                  "Mantener sincronizados los nombres de las adaptaciones, los tipos de trabajo del Local Engine y los contratos de salida exclusivamente PDF."),
            check("SKILL-03", "Coherencia funcional y semántica entre Skills",
                  "passed" if skill_contracts_ok else "not_verified",
                  "Medio" if skill_contracts_ok else "Alto",
                  "Las cuatro adaptaciones pasan las pruebas estáticas de contrato y el commit auditado supera la matriz CI exacta."
                  if skill_contracts_ok else "No hay evidencia de pruebas de contrato y CI exitosas para el commit auditado.",
                  "Mantener las pruebas de contrato sincronizadas con los requisitos fuente y ejecutarlas en cada cambio."),
            check("SKILL-04", "Activación por frases y horario", "partial", "Medio",
                  "Las frases de activación y ventanas objetivo están descritas en los metadatos/instrucciones de cada Skill; la ejecución sigue siendo manual y el Local Engine no programa automáticamente.",
                  "Conservar la activación manual hasta que se apruebe por separado una función de programación automática."),
            check("PDF-01", "Estructura, legibilidad y diseño de PDF",
                  "passed" if all_operational_artifacts_ok else "not_verified", "Alto",
                  "Los PDF de apertura, cierre e intradía superaron el análisis y renderizado independiente."
                  if all_operational_artifacts_ok else "No existe evidencia QA independiente aprobada para los tres tipos de PDF operativos.",
                  "Generar PDF de apertura, cierre e intradía y adjuntar los resultados independientes de QA con PyMuPDF."),
            check("CONTENT-01", "Paridad de secciones y datos de mercado",
                  "partial" if content_disclosure_ok else "not_verified",
                  "Medio" if content_disclosure_ok else "Alto",
                  "Los informes incluyen escenarios, contexto macro/noticias, estado de cuenta/mercado y limitaciones explícitas; amplitud bursátil, líderes/rezagados y contabilidad completa siguen fuera de cobertura."
                  if content_disclosure_ok else "No se demuestra que todos los informes incluyan escenarios, contexto y declaraciones explícitas de disponibilidad/limitaciones.",
                  "Mantener visibles las carencias de cobertura y ampliar fuentes de mercado/contabilidad solo con evidencia fiable."),
            check("TIME-01", "Límites del día calendario dominicano", "passed" if local_windows_ok else "not_verified",
                  "Crítico", "Todos los manifiestos conservados declaran la zona horaria IANA y la ventana semiabierta." if local_windows_ok
                  else "No hay un conjunto completo de manifiestos válidos de ventanas locales.",
                  "Volver a generar y auditar de forma independiente cada informe operativo."),
            check("OPEN-01", "Apertura: día calendario local anterior", "passed" if opening_dates_ok else "not_verified",
                  "Alto", "Las fechas de solicitud y referencia de apertura se reconciliaron mediante los manifiestos de evidencia." if opening_dates_ok
                  else "No hay evidencia de apertura que demuestre la regla del día local anterior.",
                  "Generar un informe de apertura y conservar la evidencia de la fecha de solicitud."),
            check("CLOSE-01", "Cierre parcial hasta la hora de corte", "passed" if closing_windows_ok else "not_verified",
                  "Alto", "Los manifiestos de cierre declaran hora de corte explícita, de ejecución o día histórico completado." if closing_windows_ok
                  else "No hay evidencia de cierre que demuestre el tratamiento del día parcial.",
                  "Generar un informe de cierre del día actual antes de medianoche local e inspeccionar la hora de corte exacta."),
            check("INTRA-01", "Hora de corte predeterminada del snapshot", "passed" if any(
                      x.get("cutoff_resolution") == "execution_time_local_default" for x in intraday_reports
                  ) else "not_exercised" if intraday_reports else "not_verified",
                  "Medio", "Un informe intradía registra la hora local de ejecución como corte." if any(
                      x.get("cutoff_resolution") == "execution_time_local_default" for x in intraday_reports
                  ) else "No hay un informe intradía conservado que demuestre la ruta sin hora de corte explícita.",
                  "Ejecutar un trabajo intradía sin parámetro de hora de corte."),
            check("US-01", "Fines de semana y festivos bursátiles de EE. UU.",
                  "passed" if us_calendar_ok else "failed" if us_calendar_failed else "not_verified", "Alto",
                  "La evidencia XNYS de cada informe se recalculó de forma independiente y coincide con la última sesión completada y la siguiente sesión."
                  if us_calendar_ok else "La evidencia del calendario XNYS está ausente, no disponible o no coincide con una recalculación independiente.",
                  "Conservar manifiestos de apertura, cierre e intradía y corregir cualquier discrepancia de calendario."),
            check("ACCOUNT-01", "Importación CSV de actividad de cuenta con integridad verificable",
                  "passed" if account_export_ok else "not_applicable" if account_export_not_supplied else "not_verified",
                  "Medio" if account_export_not_supplied or account_export_ok else "Alto",
                  "Los archivos CSV admitidos tienen hashes SHA-256, esquema y ventana verificables; la hora UTC asumida desde UTC_Time queda expresamente advertida."
                  if account_export_ok else "No se suministró un CSV de actividad; el informe declara la cuenta como no disponible y no infiere saldo cero."
                  if account_export_not_supplied else "; ".join(account_export_findings[:5]) or "No hay exportaciones compatibles completas y trazables para esta ventana.",
                  "Importar un historial Binance solo cuando exista y sea necesario; no bloquear la investigación preinversión por ausencia de CSV."),
            check("ACCOUNT-02", "Patrimonio, PnL no realizado y rentabilidad ajustada por flujos",
                  "not_applicable" if account_export_not_supplied else "not_implemented",
                  "Medio" if account_export_not_supplied else "Alto",
                  "Sin exportación de cuenta no se calcula PnL ni patrimonio; si hay actividad importada, todavía se requieren balances/posiciones completos para valorar cartera.",
                  "No afirmar equity ni rentabilidad hasta implementar y conciliar estados de cuenta, balances y posiciones completas."),
            check("US-DATA-01", "Proveniencia y corte de cotizaciones estadounidenses",
                  "passed" if market_data_provenance_ok else "not_verified", "Medio",
                  "Las cotizaciones disponibles tienen proveedor, URL de origen y timestamp no posterior al corte; los símbolos no disponibles se declaran."
                  if market_data_provenance_ok else "No hay evidencia suficiente para verificar proveedor, URL, timestamp y cobertura del snapshot bursátil.",
                  "Conservar el manifiesto con URLs y marcas temporales originales; no completar valores faltantes por inferencia."),
            check("US-02", "Horario bursátil y cambio horario de EE. UU.",
                  "passed" if us_calendar_ok else "failed" if us_calendar_failed else "not_verified", "Medio",
                  "La clasificación premercado/regular/posmercado, los horarios ET/local y cierres anticipados coinciden con el calendario XNYS recalculado."
                  if us_calendar_ok else "La clasificación de sesión y los límites ET/DST no se pudieron reconciliar de forma independiente.",
                  "Regenerar los informes con evidencia XNYS verificable y volver a ejecutar la auditoría."),
            check("ACCT-01", "Límites del análisis de actividad y cartera Binance",
                  "passed" if account_scope_disclosed else "not_verified", "Medio",
                  "Los informes separan los movimientos CSV importados de patrimonio, PnL no realizado y rentabilidad ajustada por flujos."
                  if account_scope_disclosed else "No se demuestra que las limitaciones del análisis de cuenta estén declaradas.",
                  "Mantener la distinción entre actividad transaccional y valoración de cartera hasta disponer de balances y posiciones completos."),
            check("ACCT-02", "Exclusión de depósitos y retiros del PnL", "not_applicable", "Alto",
                  "No está implementado el libro mayor de la cuenta privada ni el cálculo del rendimiento de cartera.",
                  "Implementar conciliación del libro mayor antes de informar rendimientos; excluir depósitos/retiros del PnL."),
            check("ACCT-03", "Saldos históricos de cuenta incompletos", "not_applicable", "Medio",
                  "Se pueden importar movimientos de transacciones; no se ingieren snapshots históricos de balance ni posiciones abiertas completas.",
                  "Exigir saldos históricos completos antes de afirmar rendimiento de cuenta."),
            check("SCORE-01", "Comparación del pronóstico de apertura y el cierre",
                  "passed" if scorecard_ok else "failed" if scorecard_failed else "not_verified",
                  "Alto",
                  "Los informes de cierre concilian escenarios con el manifiesto íntegro de apertura de la misma fecha, o declaran que no existe un informe de apertura."
                  if scorecard_ok else "La evidencia de apertura/cierre falta, no pudo verificarse o contiene una discrepancia.",
                  "Conservar el manifiesto de apertura de la misma fecha y regenerar el cierre para conciliar los rangos observados."),
            check("PKG-01", "Integridad de paquetes originales e historial de versiones",
                  source_skill_integrity["status"],
                  "Medio" if source_skill_integrity["status"] == "passed" else "Alto",
                  "Los cuatro paquetes .skill originales y sus SKILL.md internos superaron la verificación de hash, tamaño y estructura."
                  if source_skill_integrity["status"] == "passed" else "; ".join(source_skill_integrity["findings"]),
                  "Conservar los paquetes originales sin modificarlos y mantener actualizado el manifiesto de hashes y versiones."),
            check("CI-01", "Evidencia CI multiplataforma del commit auditado",
                  ci_evidence["status"], "Alto",
                  (f"Repositorio: {ci_evidence.get('repository')}; commit: {ci_evidence.get('commit_sha')}; "
                   f"run: {ci_evidence.get('run_id')}; {ci_evidence.get('reason')}; "
                   f"trabajos: {ci_evidence.get('jobs')}."),
                  "Corregir cualquier fallo o ejecutar la matriz completa para el commit local exacto; no reutilizar resultados de otro SHA."),
            check("OPPORTUNITY-01", "Integridad y recálculo de informes de oportunidad",
                  opportunity_audit_status, "Medio" if opportunity_audit_status == "not_exercised" else "Alto",
                  (f"Se auditaron {len(opportunity_artifacts)} artefactos de oportunidad; estado: {opportunity_audit_status}."),
                  "Generar informes de oportunidad mediante Local Engine y conservar el manifiesto SHA-256 para permitir reconstrucción independiente."),
        ]
        unresolved = [
            item for item in desk_checks
            if item["severity"] in {"Crítico", "Alto"}
            and item["status"] in {"failed", "not_implemented", "not_verified"}
        ]
        medium_unresolved = [
            item for item in desk_checks
            if item["severity"] == "Medio"
            and item["status"] in {"failed", "not_implemented", "not_verified", "not_exercised", "partial"}
        ]
        audit_verdict = (
            "No aprobado" if unresolved else
            "Aprobado con reservas" if medium_unresolved else
            "Aprobado"
        )
        temporal_by_skill = {
            "binance-apertura-mercado": "passed" if opening_dates_ok else "not_verified",
            "binance-cierre-mercado": "passed" if closing_windows_ok else "not_verified",
            "binance-momento-mercado": "passed" if any(
                item.get("report_type") == "intraday" and item.get("status") == "passed"
                for item in evidence_manifests
            ) else "not_verified",
            "binance-revision-skills": "passed" if local_windows_ok else "not_verified",
        }
        security_ok = bool(all_reports) and all(
            item.get("read_only") is True and item.get("source") == "Binance public REST API"
            for item in all_reports
        )
        skill_results = []
        for skill_name in (
            "binance-apertura-mercado", "binance-cierre-mercado",
            "binance-momento-mercado", "binance-revision-skills",
        ):
            skill_results.append({
                "name": skill_name,
                "package_integrity": source_skill_integrity["status"],
                "temporal_coherence": temporal_by_skill[skill_name],
                "data_security": "passed" if security_ok else "not_verified",
                "methodology": "passed" if skill_contracts_ok else "not_verified",
                "status": (
                    "No aprobado"
                    if temporal_by_skill[skill_name] != "passed" or not security_ok
                    or not skill_contracts_ok or source_skill_integrity["status"] == "failed"
                    else "Aprobado con reservas"
                    if source_skill_integrity["status"] == "not_verified"
                    else "Aprobado"
                ),
            })
        executive_summary = [
            "Los tres flujos operativos utilizan ventanas de calendario local America/Santo_Domingo.",
            "Apertura utiliza el día local anterior; cierre admite días locales parciales; intradía admite una hora de corte explícita o la hora de ejecución.",
            "Las velas sin completar se excluyen y se conserva por separado el límite de la última vela cerrada.",
            "El esquema de evidencia v2 registra ventanas locales/UTC y hashes SHA-256; el QA de PDF y las pruebas de escritorio son independientes.",
            "Los metadatos de las Skills adaptadas están versionados; los hashes de los archivos originales están registrados, pero el contenido ZIP no se verifica dentro del repositorio.",
            "El calendario XNYS, las cotizaciones best-effort de Yahoo Finance y el scorecard de apertura/cierre se verifican desde sus marcas de tiempo y manifiestos. La importación local de movimientos Binance CSV está integrada; siguen pendientes amplitud/acciones líderes y valoración completa de cartera. CI se consulta de forma independiente contra GitHub Actions y se vincula al SHA local exacto.",
        ]
        changes_applied = [
            "Implementación de adquisición por día local dominicano y validación PDF para apertura, cierre e intradía.",
            "Añadido soporte para cierres parciales y hora de corte local predeterminada según el momento de ejecución para intradía.",
            "Añadido esquema de evidencia v2 con metadatos de ventana, hash del PDF y hash de velas originales/período de calentamiento.",
            "Integrado calendario bursátil XNYS con feriados, cierres anticipados, DST y clasificación de sesión; la auditoría recalcula la evidencia de calendario de forma independiente.",
            "Añadida importación local de CSV de historial de transacciones Binance con hashes SHA-256, deduplicación, agregación por evento/activo y verificación independiente; no calcula equity ni rentabilidad de cartera.",
            "Añadido scorecard de escenarios de apertura/cierre para la misma fecha, vinculado a un manifiesto de apertura con integridad verificada; la ausencia de apertura se marca como no aplicable.",
            "Añadidas pruebas de escritorio, severidades/veredictos en español, fecha local de auditoría e historial de versiones/cambios.",
            "Localizados los tres PDF operativos y la auditoría; añadidos resúmenes ejecutivos de siete puntos y referencias horarias ET/local con reglas DST.",
            "Ajustada la nomenclatura del PDF de apertura para usar la fecha local de solicitud y reforzada la auditoría de nombres de archivo/manifiestos.",
            "Añadidos versionado en frontmatter y requisitos originales de activación/secciones a las cuatro instrucciones adaptadas.",
        ]
        pending_items = [
            item["case"] + ": " + item["recommendation"]
            for item in unresolved + medium_unresolved
        ]
        reviewed_files = (
            [item.get("filename", "Archivo desconocido") for item in artifacts]
            + [item.get("manifest", "Manifiesto de evidencia desconocido") for item in evidence_manifests]
        )
        for item in unresolved:
            findings.append({
                "severity": item["severity"], "title": f"Prueba de escritorio {item['id']}: {item['case']}",
                "evidence": item["evidence"], "recommendation": item["recommendation"],
            })
        for item in medium_unresolved:
            findings.append({
                "severity": item["severity"], "title": f"Prueba de escritorio {item['id']}: {item['case']}",
                "evidence": item["evidence"], "recommendation": item["recommendation"],
            })
        change_history = [
            {
                "date": audit_date_local, "version": __version__,
                "change": "Motor PDF de Fase 3 con días calendario dominicanos, calendario bursátil XNYS, snapshot bursátil Yahoo best-effort, importación de actividad Binance CSV, scorecard de escenarios de apertura/cierre, resúmenes de siete puntos y esquema de evidencia v2; los hashes de los ZIP originales están registrados, pero sus bytes no están incluidos en el runtime.",
            },
            {
                "date": audit_date_local, "version": "original-skill-parity",
                "change": "La cobertura de amplitud/acciones líderes del mercado estadounidense y la valoración completa de cartera siguen incompletas; el calendario XNYS, las cotizaciones best-effort y la importación CSV de actividad están integrados. El scorecard de apertura/cierre está implementado; la paridad total de la matriz de auditoría sigue pendiente.",
            },
        ]
        report = {
            "audit_date_utc": audit_date_utc,
            "audit_date_local": audit_date_local,
            "report_timezone": REPORT_TIMEZONE,
            "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
            "report_engine_version": __version__,
            "audit_verdict": audit_verdict,
            "opening_window_status": next((x["status"] for x in desk_checks if x["id"] == "OPEN-01"), "not_verified"),
            "closing_window_status": next((x["status"] for x in desk_checks if x["id"] == "CLOSE-01"), "not_verified"),
            "intraday_cutoff_status": next((x["status"] for x in desk_checks if x["id"] == "INTRA-01"), "not_verified"),
            "language_parity_status": next((x["status"] for x in desk_checks if x["id"] == "LANG-01"), "not_verified"),
            "us_session_status": next((x["status"] for x in desk_checks if x["id"] == "US-02"), "not_verified"),
            "us_holiday_status": next((x["status"] for x in desk_checks if x["id"] == "US-01"), "not_verified"),
            "desk_checks": desk_checks,
            "skill_results": skill_results,
            "executive_summary": executive_summary,
            "changes_applied": changes_applied,
            "pending_items": pending_items,
            "files_reviewed": reviewed_files,
            "change_history": change_history,
            "source_skill_integrity": source_skill_integrity,
            "artifacts": artifacts,
            "opportunity_artifacts": opportunity_artifacts,
            "opportunity_audit_status": opportunity_audit_status,
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
            "opportunity_reports_checked": len(opportunity_artifacts),
            "opportunity_audit_status": opportunity_audit_status,
            "opportunity_artifacts": opportunity_artifacts,
            "evidence_manifests_checked": len(evidence_manifests),
            "cross_report_consistency_status": cross_report["status"],
            "overlapping_candles_checked": cross_report["overlapping_candles_checked"],
            "findings_count": len(findings),
            "desk_checks_count": len(desk_checks),
            "audit_verdict": audit_verdict,
            "opening_window_status": next((x["status"] for x in desk_checks if x["id"] == "OPEN-01"), "not_verified"),
            "closing_window_status": next((x["status"] for x in desk_checks if x["id"] == "CLOSE-01"), "not_verified"),
            "intraday_cutoff_status": next((x["status"] for x in desk_checks if x["id"] == "INTRA-01"), "not_verified"),
            "language_parity_status": next((x["status"] for x in desk_checks if x["id"] == "LANG-01"), "not_verified"),
            "us_session_status": next((x["status"] for x in desk_checks if x["id"] == "US-02"), "not_verified"),
            "us_holiday_status": next((x["status"] for x in desk_checks if x["id"] == "US-01"), "not_verified"),
            "scorecard_status": next((x["status"] for x in desk_checks if x["id"] == "SCORE-01"), "not_verified"),
            "account_export_status": next((x["status"] for x in desk_checks if x["id"] == "ACCOUNT-01"), "not_verified"),
            "account_export_findings": account_export_findings,
            "us_market_data_provenance_status": next((x["status"] for x in desk_checks if x["id"] == "US-DATA-01"), "not_verified"),
            "audit_date_local": audit_date_local,
            "read_only": True,
        }

    def _opportunity_report(self, job: dict[str, Any]) -> dict[str, Any]:
        """Build a pre-investment PDF from explicit identities and approved public-source lookups."""
        parameters = job["parameters"]
        allowed = {
            "instrument_candidate", "venue_evidence", "binance_spot_check", "research_facts",
            "freshness_limits_hours", "sec_edgar", "clinical_trials",
            "defillama", "scenario_inputs", "position_sizing_inputs",
            "conclusion", "executive_summary", "risks", "thesis_invalidation",
            "unresolved_questions", "methodology_notes",
        }
        unknown = set(parameters) - allowed
        if unknown:
            raise ValueError(f"Unknown investment opportunity parameters: {sorted(unknown)}")
        candidate = parameters.get("instrument_candidate")
        if not isinstance(candidate, dict):
            raise ValueError("instrument_candidate must be an asset identity object")
        binance_spot_check = parameters.get("binance_spot_check", False)
        if not isinstance(binance_spot_check, bool):
            raise ValueError("binance_spot_check must be boolean")
        venue_evidence = parameters.get("venue_evidence")
        binance_spot_result = None
        if binance_spot_check:
            if venue_evidence is not None:
                raise ValueError("Supply venue_evidence or binance_spot_check=true, not both")
            binance_spot_result = BinanceSpotProductVerifier().verify_spot_product(candidate)
            candidate = dict(candidate)
            if binance_spot_result.get("status") == "verified":
                candidate["venue"] = {
                    "name": "Binance",
                    "product_id": binance_spot_result["product_id"],
                    "market_type": "spot",
                }
            venue_evidence = binance_spot_result
        instrument = build_instrument_record(candidate, venue_evidence)
        instrument_key = instrument["instrument_key"]
        facts = parameters.get("research_facts", [])
        if not isinstance(facts, list) or len(facts) > 500:
            raise ValueError("research_facts must be a list containing at most 500 facts")
        facts = list(facts)
        provider_status: dict[str, Any] = {}
        if binance_spot_result is not None:
            provider_status["binance_spot"] = {
                "status": binance_spot_result.get("status"),
                "product_id": binance_spot_result.get("product_id"),
                "market_type": binance_spot_result.get("market_type"),
                "base_asset": binance_spot_result.get("base_asset"),
                "quote_asset": binance_spot_result.get("quote_asset"),
                "product_status": binance_spot_result.get("product_status"),
                "is_spot_trading_allowed": binance_spot_result.get("is_spot_trading_allowed"),
                "observed_at_utc": binance_spot_result.get("observed_at_utc"),
                "source_url": binance_spot_result.get("source_url"),
                "reason": binance_spot_result.get("reason"),
                "evidence_note": binance_spot_result.get("evidence_note"),
            }

        sec_config = parameters.get("sec_edgar")
        if sec_config is not None:
            if not isinstance(sec_config, dict) or set(sec_config) - {"cik", "issuer_name", "period", "resolve_ticker"}:
                raise ValueError("sec_edgar may contain only cik, issuer_name, period, and resolve_ticker")
            if instrument["asset_class"] not in {"listed_equity", "tokenized_equity"}:
                raise ValueError("SEC issuer fundamentals require an equity instrument identity")
            resolve_ticker = sec_config.get("resolve_ticker", False)
            if not isinstance(resolve_ticker, bool):
                raise ValueError("sec_edgar.resolve_ticker must be boolean")
            explicit_cik = sec_config.get("cik")
            if bool(explicit_cik) == resolve_ticker:
                raise ValueError("Supply either sec_edgar.cik or resolve_ticker=true, but not both")
            sec_client = SECEdgarCompanyFacts()
            ticker_resolution = None
            if resolve_ticker:
                if instrument["asset_class"] != "listed_equity":
                    raise ValueError("Automatic SEC ticker resolution is limited to listed_equity; tokenized equity requires an explicit CIK")
                ticker_resolution = sec_client.resolve_ticker(
                    ticker=instrument["symbol"],
                    exchange=instrument["exchange"],
                    issuer_name=instrument["issuer"],
                )
                if ticker_resolution.get("status") != "resolved":
                    raise ValueError(
                        "SEC ticker resolution did not produce one exact issuer match: "
                        + str(ticker_resolution.get("status"))
                    )
                cik = ticker_resolution["cik"]
                issuer_name = instrument["issuer"]
            else:
                cik = explicit_cik
                issuer_name = sec_config.get("issuer_name")
                if not isinstance(issuer_name, str) or not issuer_name.strip():
                    raise ValueError("sec_edgar.issuer_name is required when an explicit CIK is supplied")
            sec_result = sec_client.fetch_facts(
                cik=cik,
                instrument_key=instrument_key,
                issuer_name=issuer_name,
                period=sec_config.get("period", "annual"),
            )
            facts.extend(sec_result["facts"])
            provider_status["sec_edgar"] = {
                "status": "retrieved" if sec_result["facts"] else "partial",
                "cik": sec_result["cik"],
                "entity_name": sec_result["provider_entity_name"],
                "fact_count": len(sec_result["facts"]),
                "missing_dimensions": sec_result["missing_dimensions"],
                "source_url": sec_result["source_url"],
                "ticker_resolution": ({
                    "status": ticker_resolution["status"],
                    "ticker": ticker_resolution["ticker"],
                    "exchange": ticker_resolution["exchange"],
                    "issuer_name": ticker_resolution["issuer_name"],
                    "source_url": ticker_resolution["source_url"],
                    "retrieved_at_utc": ticker_resolution["retrieved_at_utc"],
                    "limitations": ticker_resolution["limitations"],
                } if ticker_resolution else None),
            }

        clinical_config = parameters.get("clinical_trials", [])
        if not isinstance(clinical_config, list) or len(clinical_config) > 10:
            raise ValueError("clinical_trials must be a list containing at most 10 NCT records")
        if clinical_config and instrument["asset_class"] not in {"listed_equity", "tokenized_equity"}:
            raise ValueError("ClinicalTrials.gov issuer diligence requires an equity instrument identity")
        clinical_status = []
        seen_nct: set[str] = set()
        clinical_client = ClinicalTrialsGov() if clinical_config else None
        for item in clinical_config:
            if not isinstance(item, dict) or set(item) != {"nct_id", "attribution_basis"}:
                raise ValueError("Each clinical_trials item must contain nct_id and attribution_basis")
            nct_id = item["nct_id"]
            if not isinstance(nct_id, str) or nct_id.upper() in seen_nct:
                raise ValueError("clinical_trials NCT identifiers must be unique strings")
            seen_nct.add(nct_id.upper())
            trial = clinical_client.fetch_study(
                nct_id=nct_id,
                instrument_key=instrument_key,
                attribution_basis=item["attribution_basis"],
            )
            facts.extend(trial["facts"])
            clinical_status.append({
                "nct_id": trial["nct_id"],
                "study_title": trial["study_title"],
                "overall_status": trial["overall_status"],
                "fact_count": len(trial["facts"]),
                "attribution_status": trial["issuer_trial_attribution"]["status"],
                "source_url": trial["source_url"],
            })
        if clinical_config:
            provider_status["clinical_trials"] = {
                "status": "retrieved" if clinical_status else "unavailable",
                "studies": clinical_status,
            }

        defi_config = parameters.get("defillama")
        if defi_config is not None:
            if not isinstance(defi_config, dict) or set(defi_config) != {"protocol_slug", "attribution_basis"}:
                raise ValueError("defillama must contain protocol_slug and attribution_basis")
            if instrument["asset_class"] != "crypto":
                raise ValueError("DeFiLlama protocol research requires a crypto instrument identity")
            defi_result = DeFiLlamaProtocolResearch().fetch_protocol_research(
                protocol_slug=defi_config["protocol_slug"],
                instrument_key=instrument_key,
                attribution_basis=defi_config["attribution_basis"],
            )
            facts.extend(defi_result["facts"])
            provider_status["defillama"] = {
                "status": defi_result["data_quality_status"],
                "protocol_slug": defi_result["protocol_slug"],
                "protocol_name": defi_result["protocol_name"],
                "fact_count": len(defi_result["facts"]),
                "missing_metrics": defi_result["missing_metrics"],
                "source_url": defi_result["source_url"],
                "attribution_status": defi_result["protocol_instrument_attribution"]["status"],
            }

        generated_at = datetime.now(timezone.utc)
        freshness_limits = parameters.get("freshness_limits_hours", {})
        if not isinstance(freshness_limits, dict):
            raise ValueError("freshness_limits_hours must be an object")
        packet = build_research_packet(
            instrument_key, facts, now=generated_at,
            freshness_limits_hours=freshness_limits,
        )
        fundamental_metrics = (
            calculate_financial_ratios(packet["facts"], instrument_key=instrument_key)
            if instrument["asset_class"] in {"listed_equity", "tokenized_equity"}
            else None
        )

        scenarios = parameters.get("scenario_inputs")
        if scenarios is not None:
            if not isinstance(scenarios, dict) or scenarios.get("instrument_key") != instrument_key:
                raise ValueError("scenario_inputs must include the exact normalized instrument_key")
            scenarios = calculate_long_scenarios(**scenarios)

        sizing = parameters.get("position_sizing_inputs")
        if sizing is not None:
            if not isinstance(sizing, dict) or sizing.get("instrument_key") != instrument_key:
                raise ValueError("position_sizing_inputs must include the exact normalized instrument_key")
            sizing = calculate_cash_position_size(**sizing)

        report = {
            "generated_at_utc": generated_at.isoformat().replace("+00:00", "Z"),
            "instrument": instrument,
            "research_packet": packet,
            "fundamental_metrics": fundamental_metrics,
            "conclusion": parameters.get("conclusion", "insufficient_evidence"),
            "executive_summary": parameters.get("executive_summary", []),
            "scenarios": scenarios,
            "position_sizing": sizing,
            "risks": parameters.get("risks", []),
            "thesis_invalidation": parameters.get("thesis_invalidation", []),
            "unresolved_questions": parameters.get("unresolved_questions", []),
            "provider_status": provider_status or {"status": "No external provider adapter requested"},
            "methodology_notes": parameters.get("methodology_notes", []),
            "freshness_limits_hours": freshness_limits,
        }
        output_directory = self.manager.workspace.directory("reports/opportunities")
        artifact = build_opportunity_report_pdf(report, output_directory)
        resolved = artifact.resolve(strict=True)
        if not resolved.is_relative_to(output_directory):
            raise ValueError("Generated opportunity report escaped reports/opportunities")
        payload = resolved.read_bytes()
        if (not resolved.is_file() or resolved.suffix.lower() != ".pdf"
                or len(payload) < 16 or not payload.startswith(b"%PDF-")
                or b"%%EOF" not in payload[-1024:]):
            raise ValueError("Opportunity report failed PDF integrity checks")
        manifest_directory = self.manager.workspace.directory("data/manifests/opportunities")
        manifest_path = write_opportunity_manifest(report, resolved, manifest_directory)
        manifest_payload = manifest_path.read_bytes()
        return {
            "report_type": "investment.opportunity_report",
            "format": "pdf",
            "artifact_path": resolved.relative_to(self.manager.workspace.root).as_posix(),
            "manifest_path": manifest_path.relative_to(self.manager.workspace.root).as_posix(),
            "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
            "filename": resolved.name,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "instrument_key": instrument_key,
            "conclusion": report["conclusion"],
            "fact_count": packet["fact_count"],
            "data_quality_status": packet["data_quality"]["status"],
            "venue_verification_status": (instrument.get("venue_verification") or {}).get("status", "not_verified"),
            "provider_status": provider_status,
            "read_only": True,
            "hypothetical_only": True,
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
            account_export_directory=self.manager.workspace.directory("data/account_exports"),
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
