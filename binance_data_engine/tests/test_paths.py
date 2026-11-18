from pathlib import Path

from binance_data_engine.paths import default_snapshot_output


def test_windows_snapshot_uses_persistent_user_data():
    result = default_snapshot_output({"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"}, platform="nt")
    assert result == Path(
        r"C:\Users\Example\AppData\Local\MASTER-ARSENAL\workspace\data\snapshots\snapshot.json"
    )


def test_windows_snapshot_has_home_fallback():
    result = default_snapshot_output({}, platform="nt")
    assert result.parts[-6:] == (
        "AppData", "Local", "MASTER-ARSENAL", "workspace", "data", "snapshots", "snapshot.json"
    )[-6:]


def test_non_windows_snapshot_keeps_relative_default():
    assert default_snapshot_output({}, platform="posix") == Path("snapshot.json")
