import unittest
from pathlib import Path

from binance_data_engine.paths import default_snapshot_output


class DefaultSnapshotPathTests(unittest.TestCase):
    def test_windows_snapshot_uses_persistent_user_data(self):
        result = default_snapshot_output(
            {"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"}, platform="nt"
        )
        self.assertEqual(
            str(result).replace("/", "\\"),
            r"C:\Users\Example\AppData\Local\MASTER-ARSENAL\workspace\data\snapshots\snapshot.json",
        )

    def test_windows_snapshot_has_home_fallback(self):
        result = default_snapshot_output({}, platform="nt")
        self.assertEqual(
            result.parts[-7:],
            ("AppData", "Local", "MASTER-ARSENAL", "workspace", "data", "snapshots", "snapshot.json"),
        )

    def test_non_windows_snapshot_keeps_relative_default(self):
        self.assertEqual(default_snapshot_output({}, platform="posix"), Path("snapshot.json"))


if __name__ == "__main__":
    unittest.main()
