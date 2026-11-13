import json
import multiprocessing
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance_data_engine.client import PaginationMetadata
from binance_data_engine.models import Candle

from local_engine.protocol import JobValidationError, new_job, validate_job
from local_engine.runtime import JobManager, JobRunner, Workspace


def _process_submit(root, job, queue):
    try:
        JobManager(Workspace(root)).submit(job)
        queue.put("submitted")
    except JobValidationError:
        queue.put("duplicate")


def _process_claim(root, job_id, queue):
    try:
        JobManager(Workspace(root)).claim(job_id)
        queue.put("claimed")
    except JobValidationError:
        queue.put("unavailable")


class FakeBinanceClient:
    def __init__(self):
        self.cutoff = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)
        self.last_response_metadata = {
            "http_status": 200,
            "retrieved_at_utc": "2026-11-13T03:01:00Z",
        }

    def get_server_time(self, market):
        return self.cutoff + timedelta(minutes=1)

    def get_historical_klines(self, symbol, interval, start, end, market="spot"):
        rows = []
        for index in range(3):
            opened = start + timedelta(hours=index)
            price = Decimal("100") + index
            rows.append(Candle(
                symbol=symbol, interval=interval, open_time=opened,
                close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
                open=price, high=price + 1, low=price - 1, close=price,
                volume=Decimal("10"),
            ))
        return rows, PaginationMetadata(
            pages=1, returned=len(rows), requested_start=start.isoformat(),
            requested_end=end.isoformat(), complete=True,
        )

    def get_24h_ticker(self, symbol, market):
        return {"symbol": symbol, "priceChangePercent": "1.0"}


class LocalEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "workspace"
        self.manager = JobManager(Workspace(root))
        self.second_manager = JobManager(Workspace(root))

    def tearDown(self):
        self.temp.cleanup()

    def _approved_job(self, job_type="engine.health_check", parameters=None):
        job = new_job(job_type, parameters)
        self.manager.submit(job)
        self.manager.validate_pending(job["job_id"])
        self.manager.approve(job["job_id"])
        return job

    def test_new_job_requires_explicit_approval(self):
        job = new_job("engine.health_check")
        self.assertEqual(validate_job(job), job)
        self.assertTrue(job["approval"]["required"])
        self.assertFalse(job["approval"]["granted"])

    def test_rejects_unknown_fields_and_job_types(self):
        job = new_job("engine.health_check")
        job["command"] = "whoami"
        with self.assertRaises(JobValidationError):
            validate_job(job)
        job = new_job("engine.health_check")
        job["job_type"] = "arbitrary.execute"
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_rejects_non_string_enum_values(self):
        job = new_job("engine.health_check")
        job["requested_by"] = {}
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_rejects_path_traversal(self):
        job = new_job("engine.health_check")
        job["output"]["directory"] = "..\\..\\outside"
        with self.assertRaises(JobValidationError):
            validate_job(job)

    def test_rejects_job_id_path_traversal(self):
        with self.assertRaises(ValueError):
            self.manager.workspace.job_path("inbox", "../../outside")

    def test_job_requires_validation_and_approval(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        self.assertEqual(self.manager.validate_pending(job["job_id"]), "awaiting_approval")
        with self.assertRaises(JobValidationError):
            self.manager.claim(job["job_id"])
        self.manager.approve(job["job_id"])
        self.assertEqual(self.manager.get(job["job_id"])["status"], "validated")

    def test_health_check_completes(self):
        job = self._approved_job()
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(self.manager.get(job["job_id"])["result"]["read_only"])

    def test_intraday_job_defaults_to_pdf_output(self):
        job = new_job("market.intraday_snapshot")
        self.assertEqual(job["output"], {
            "format": "pdf", "directory": "reports/intraday"
        })

    def test_intraday_snapshot_job_generates_pdf(self):
        job = self._approved_job(
            "market.intraday_snapshot",
            {"cutoff_utc": "2026-11-13T03:00:00Z", "interval": "1h", "market": "spot"},
        )
        with patch("local_engine.runtime.BinancePublicClient", return_value=FakeBinanceClient()):
            result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed")
        artifact = result["result"]["artifact_path"]
        self.assertTrue(artifact.startswith("reports/intraday/"))
        path = self.manager.workspace.directory(artifact)
        self.assertTrue(path.is_file())
        self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
        record = self.manager.get(job["job_id"])
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["format"], "pdf")

    def test_intraday_snapshot_job_requires_cutoff(self):
        job = self._approved_job("market.intraday_snapshot")
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("cutoff_utc is required", result["error"])

    def test_intraday_snapshot_job_rejects_non_pdf_output(self):
        job = new_job("market.intraday_snapshot", {
            "cutoff_utc": "2026-11-13T03:00:00Z"
        })
        job["output"]["format"] = "json"
        self.manager.submit(job)
        self.manager.validate_pending(job["job_id"])
        self.manager.approve(job["job_id"])
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("requires output.format='pdf'", result["error"])

    def test_unsupported_handler_fails_explicitly(self):
        job = self._approved_job("market.opening_report")
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("not implemented by this runtime", result["error"])

    def test_submitted_job_is_valid_json_with_real_newline(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        path = self.manager.workspace.job_path("inbox", job["job_id"])
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(json.loads(raw.decode("utf-8"))["job_id"], job["job_id"])

    def test_duplicate_job_id_is_rejected(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        with self.assertRaises(JobValidationError):
            self.manager.submit(job)

    def test_workspace_rejects_symlink_escape_before_creating_children(self):
        root = Path(self.temp.name) / "symlink-workspace"
        outside = Path(self.temp.name) / "outside"
        root.mkdir()
        outside.mkdir()
        try:
            (root / "jobs").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Directory symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "escapes root"):
            Workspace(root).initialize()
        self.assertFalse((outside / "inbox").exists())

    def test_workspace_rejects_escape(self):
        with self.assertRaises(ValueError):
            self.manager.workspace.directory("../outside")

    def test_interrupted_transition_leaves_one_valid_state(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        source = self.manager.workspace.job_path("inbox", job["job_id"])
        target = self.manager.workspace.job_path("awaiting_approval", job["job_id"])
        with patch("local_engine.runtime.os.replace", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                self.manager.validate_pending(job["job_id"])
        self.assertTrue(source.is_file())
        self.assertFalse(target.exists())
        self.assertEqual(self.manager.get(job["job_id"])["status"], "inbox")

    def test_interruption_after_record_update_keeps_source_state_authoritative(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        source = self.manager.workspace.job_path("inbox", job["job_id"])
        target = self.manager.workspace.job_path("awaiting_approval", job["job_id"])
        real_replace = __import__("os").replace
        calls = 0

        def interrupt_before_rename(src, dst):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_replace(src, dst)
            raise OSError("simulated crash before state rename")

        with patch("local_engine.runtime.os.replace", side_effect=interrupt_before_rename):
            with self.assertRaises(OSError):
                self.manager.validate_pending(job["job_id"])
        self.assertTrue(source.is_file())
        self.assertFalse(target.exists())
        self.assertEqual(self.manager.get(job["job_id"])["status"], "inbox")

    def test_legacy_duplicate_states_are_reported_not_silently_selected(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        source = self.manager.workspace.job_path("inbox", job["job_id"])
        duplicate = self.manager.workspace.job_path("validated", job["job_id"])
        shutil.copyfile(source, duplicate)
        with self.assertRaisesRegex(JobValidationError, "multiple lifecycle states"):
            self.manager.get(job["job_id"])

    def test_concurrent_duplicate_submissions_allow_only_one(self):
        job = new_job("engine.health_check")
        barrier = threading.Barrier(2)
        outcomes = []

        def submit(manager):
            barrier.wait()
            try:
                manager.submit(job)
                outcomes.append("submitted")
            except JobValidationError:
                outcomes.append("duplicate")

        threads = [
            threading.Thread(target=submit, args=(self.manager,)),
            threading.Thread(target=submit, args=(self.second_manager,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertCountEqual(outcomes, ["submitted", "duplicate"])
        self.assertTrue(all(not thread.is_alive() for thread in threads))

    def test_multiprocess_duplicate_submissions_allow_only_one(self):
        job = new_job("engine.health_check")
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(target=_process_submit, args=(str(self.manager.workspace.root), job, queue))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        outcomes = [queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
        self.assertTrue(all(process.exitcode == 0 for process in processes))
        self.assertCountEqual(outcomes, ["submitted", "duplicate"])

    def test_multiprocess_claims_allow_only_one_worker(self):
        job = self._approved_job()
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(target=_process_claim, args=(str(self.manager.workspace.root), job["job_id"], queue))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        outcomes = [queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
        self.assertTrue(all(process.exitcode == 0 for process in processes))
        self.assertCountEqual(outcomes, ["claimed", "unavailable"])

    def test_concurrent_claims_allow_only_one_worker(self):
        job = self._approved_job()
        barrier = threading.Barrier(2)
        outcomes = []

        def claim(manager):
            barrier.wait()
            try:
                manager.claim(job["job_id"])
                outcomes.append("claimed")
            except JobValidationError:
                outcomes.append("unavailable")

        threads = [
            threading.Thread(target=claim, args=(self.manager,)),
            threading.Thread(target=claim, args=(self.second_manager,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertCountEqual(outcomes, ["claimed", "unavailable"])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(self.manager.get(job["job_id"])["status"], "running")


if __name__ == "__main__":
    unittest.main()
