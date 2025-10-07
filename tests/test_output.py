from datetime import datetime
from pathlib import Path

from scu.config import AppConfig, ImageFormat
from scu.output import SessionPathManager


def test_prepare_session_dir_creates_subdir(tmp_path: Path) -> None:
    config = AppConfig(output_dir=tmp_path, auto_session_subdir=True, session_name_prefix="session")
    manager = SessionPathManager(config)
    now = datetime(2024, 1, 2, 3, 4, 5)
    session_dir = manager.prepare_session_dir(now=now)

    assert session_dir.exists()
    assert session_dir.parent == tmp_path
    assert session_dir.name.startswith("session_20240102_030405")


def test_capture_path_uses_zero_padding(tmp_path: Path) -> None:
    config = AppConfig(output_dir=tmp_path, auto_session_subdir=False)
    manager = SessionPathManager(config)
    manager.prepare_session_dir(session_name="manual")
    path = manager.capture_path(7, ImageFormat.PNG)
    assert path.name == "page_0007.png"
