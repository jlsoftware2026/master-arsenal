import tempfile
import unittest
from pathlib import Path

from local_engine.protocol import JobValidationError, new_job, validate_job
from local_engine.runtime import JobManager, JobRunner, Workspace


class LocalEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = JobManager(Workspace(Path(self.temp.name) / "workspace"))

    def tearDown(self):
        self.temp.cleanup()

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
        job = new_job("engine.health_check")
        self.manager.submit(job)
        self.manager.validate_pending(job["job_id"])
        self.manager.approve(job["job_id"])
        result = JobRunner(self.manager).run(job["job_id"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue(self.manager.get(job["job_id"])["result"]["read_only"])

    def test_unsupported_handler_fails_explicitly(self):
        job = new_job("market.opening_report")
        self.manager.submit(job)
        self.manager.validate_pending(job["job_id"])
        self.manager.approve(job["job_id"])
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


if __name__ == "__main__":
    unittest.main()
