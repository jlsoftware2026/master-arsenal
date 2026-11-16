"""Integrity checks for the exact user-supplied original Claude skill packages."""
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_engine.runtime import verify_original_skill_packages


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class OriginalSkillIntegrityTests(unittest.TestCase):
    def test_all_four_original_archives_and_adaptations_verify(self):
        result = verify_original_skill_packages(REPOSITORY_ROOT)
        self.assertEqual(result["status"], "passed", result["findings"])
        self.assertEqual(len(result["packages"]), 4)
        self.assertTrue(all(item["status"] == "passed" for item in result["packages"]))
        self.assertEqual(len(result["manifest_sha256"]), 64)

    def test_tampered_original_archive_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(REPOSITORY_ROOT / "docs" / "original-skills-source",
                            root / "docs" / "original-skills-source")
            shutil.copytree(REPOSITORY_ROOT / "skills", root / "skills")
            archive = root / "docs" / "original-skills-source" / "binance-apertura-mercado.skill.b64"
            archive.write_text(archive.read_text(encoding="ascii") + "x", encoding="ascii")
            result = verify_original_skill_packages(root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("SHA-256 mismatch" in item for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
