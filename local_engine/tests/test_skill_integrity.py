"""Integrity checks for original skill source hashes and ChatGPT adaptations."""
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_engine.runtime import verify_original_skill_packages


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class OriginalSkillIntegrityTests(unittest.TestCase):
    def test_all_four_adaptations_match_recorded_original_skill_identities(self):
        result = verify_original_skill_packages(REPOSITORY_ROOT)
        self.assertEqual(result["status"], "not_verified")
        self.assertEqual(len(result["packages"]), 4)
        self.assertTrue(all(item["status"] == "not_verified" for item in result["packages"]))
        self.assertEqual(len(result["manifest_sha256"]), 64)
        self.assertTrue(any("ZIP payloads are not embedded" in item for item in result["findings"]))

    def test_adaptation_identity_mismatch_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(REPOSITORY_ROOT / "docs" / "original-skills-source",
                            root / "docs" / "original-skills-source")
            shutil.copytree(REPOSITORY_ROOT / "skills", root / "skills")
            adapted = root / "skills" / "binance-apertura-mercado" / "SKILL.md"
            adapted.write_text("# wrong-skill-name\n", encoding="utf-8")
            result = verify_original_skill_packages(root)
            self.assertEqual(result["status"], "failed")
            self.assertTrue(any("heading does not match" in item for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
