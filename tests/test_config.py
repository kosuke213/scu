from pathlib import Path

from scu.config import AppConfig, CaptureMode, ConfigRepository, Direction, ProcessOrder, TemplateStore, WaitMode


def test_config_repository_roundtrip(tmp_path: Path) -> None:
    repo_path = tmp_path / "config.json"
    repo = ConfigRepository(path=repo_path)

    config = AppConfig(
        monitor=2,
        capture_mode=CaptureMode.FULL_MONITOR,
        direction=Direction.LEFT,
        count=25,
        delay=0.8,
        process_order=ProcessOrder.KEY_FIRST,
        wait_mode=WaitMode.CHANGE_DETECTION,
        wait_timeout=4.0,
        min_overlap=0.75,
        output_dir=tmp_path / "out",
        auto_session_subdir=False,
    )

    store = TemplateStore(recent=config)
    store.register_template("batch", config)
    repo.save(store)

    loaded = repo.load()
    assert loaded.recent == config
    assert "batch" in loaded.templates
    assert loaded.templates["batch"].direction == Direction.LEFT


def test_save_recent_overwrites(tmp_path: Path) -> None:
    repo = ConfigRepository(path=tmp_path / "cfg.json")
    repo.save_recent(AppConfig(monitor=1))
    repo.save_recent(AppConfig(monitor=3))

    loaded = repo.load_recent()
    assert loaded.monitor == 3
