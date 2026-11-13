import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from local_engine.protocol import JobValidationError, new_job, validate_job
from local_engine.runtime import JobManager, JobRunner, Workspace


class LocalEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "workspace"
        self.manager = JobManager(Workspace(root))
        self.second_manager = JobManager(Workspace(root))

    def tearDown(self):
        self.temp.cleanup()

    def _approved_job(self, job_type="engine.health_check"):
        job = new_job(job_type)
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

    def test_unsupported_handler_fails_explicitly(self):
        job = self._approved_job("market.opening_report")
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("not implemented in Phase 2", result["error"])

    def test_duplicate_job_id_is_rejected(self):
        job = new_job("engine.health_check")
        self.manager.submit(job)
        with self.assertRaises(JobValidationError):
            self.manager.submit(job)

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
