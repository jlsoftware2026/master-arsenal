import unittest
from pathlib import Path

from local_engine.paths import default_workspace


class DefaultWorkspacePathTests(unittest.TestCase):
    def test_windows_workspace_uses_local_app_data(self):
        result = default_workspace(
            {"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"}, platform="nt"
        )
        self.assertEqual(
            result, Path(r"C:\Users\Example\AppData\Local\MASTER-ARSENAL\workspace")
        )

    def test_windows_workspace_has_home_fallback(self):
        result = default_workspace({}, platform="nt")
        self.assertEqual(
            result.parts[-4:], ("AppData", "Local", "MASTER-ARSENAL", "workspace")
        )

    def test_non_windows_workspace_keeps_relative_default(self):
        self.assertEqual(default_workspace({}, platform="posix"), Path("MASTER-ARSENAL-LOCAL"))


if __name__ == "__main__":
    unittest.main()
