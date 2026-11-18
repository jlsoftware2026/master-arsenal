from pathlib import Path

from local_engine.paths import default_workspace


def test_windows_workspace_uses_local_app_data():
    result = default_workspace({"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"}, platform="nt")
    assert result == Path(r"C:\Users\Example\AppData\Local\MASTER-ARSENAL\workspace")


def test_windows_workspace_has_home_fallback():
    result = default_workspace({}, platform="nt")
    assert result.parts[-4:] == ("AppData", "Local", "MASTER-ARSENAL", "workspace")


def test_non_windows_workspace_keeps_relative_default():
    assert default_workspace({}, platform="posix") == Path("MASTER-ARSENAL-LOCAL")
