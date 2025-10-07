from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class CaptureMode(str, Enum):
    ACTIVE_WINDOW = "active-window"
    FULL_MONITOR = "full-monitor"


class Direction(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class ProcessOrder(str, Enum):
    SHOT_FIRST = "shot-first"
    KEY_FIRST = "key-first"


class WaitMode(str, Enum):
    FIXED = "fixed"
    CHANGE_DETECTION = "wait-change"


class SessionMode(str, Enum):
    FIXED_COUNT = "fixed-count"
    TIME_LIMIT = "time-limit"
    MANUAL = "manual"


class ImageFormat(str, Enum):
    PNG = "png"
    JPG = "jpg"

    @property
    def extension(self) -> str:
        return ".jpg" if self is ImageFormat.JPG else ".png"


@dataclass
class HotkeyConfig:
    pause: str = "Ctrl+Alt+P"
    stop: str = "Ctrl+Alt+S"

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "HotkeyConfig":
        return cls(
            pause=str(data.get("pause", "Ctrl+Alt+P")),
            stop=str(data.get("stop", "Ctrl+Alt+S")),
        )


@dataclass
class AppConfig:
    monitor: int = 1
    capture_mode: CaptureMode = CaptureMode.ACTIVE_WINDOW
    direction: Direction = Direction.RIGHT
    count: int = 100
    delay: float = 0.5
    process_order: ProcessOrder = ProcessOrder.SHOT_FIRST
    wait_mode: WaitMode = WaitMode.FIXED
    wait_timeout: Optional[float] = 5.0
    min_overlap: float = 0.7
    output_dir: Path = field(default_factory=lambda: Path.home() / "Pictures" / "SCU")
    image_format: ImageFormat = ImageFormat.PNG
    jpeg_quality: int = 90
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    session_mode: SessionMode = SessionMode.FIXED_COUNT
    time_limit_seconds: Optional[int] = None
    auto_session_subdir: bool = True
    session_name_prefix: str = "session"

    def __post_init__(self) -> None:
        if self.monitor < 1:
            raise ValueError("monitor must be >= 1")
        if not 1 <= self.count <= 10_000:
            raise ValueError("count must be between 1 and 10,000")
        if self.delay < 0:
            raise ValueError("delay must be >= 0")
        if not 0 <= self.min_overlap <= 1:
            raise ValueError("min_overlap must be between 0 and 1")
        if self.image_format is ImageFormat.JPG and not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be 1..100")
        if self.wait_mode == WaitMode.CHANGE_DETECTION and self.wait_timeout is None:
            raise ValueError("wait_timeout is required for change detection mode")
        if self.session_mode == SessionMode.TIME_LIMIT and self.time_limit_seconds is None:
            raise ValueError("time_limit_seconds required for time-limit mode")
        self.output_dir = Path(self.output_dir).expanduser()

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["capture_mode"] = self.capture_mode.value
        data["direction"] = self.direction.value
        data["process_order"] = self.process_order.value
        data["wait_mode"] = self.wait_mode.value
        data["image_format"] = self.image_format.value
        data["session_mode"] = self.session_mode.value
        data["output_dir"] = str(self.output_dir)
        data["hotkeys"] = asdict(self.hotkeys)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "AppConfig":
        return cls(
            monitor=int(data.get("monitor", 1)),
            capture_mode=CaptureMode(data.get("capture_mode", CaptureMode.ACTIVE_WINDOW.value)),
            direction=Direction(data.get("direction", Direction.RIGHT.value)),
            count=int(data.get("count", 100)),
            delay=float(data.get("delay", 0.5)),
            process_order=ProcessOrder(data.get("process_order", ProcessOrder.SHOT_FIRST.value)),
            wait_mode=WaitMode(data.get("wait_mode", WaitMode.FIXED.value)),
            wait_timeout=float(data["wait_timeout"]) if data.get("wait_timeout") is not None else None,
            min_overlap=float(data.get("min_overlap", 0.7)),
            output_dir=Path(data.get("output_dir", Path.home() / "Pictures" / "SCU")),
            image_format=ImageFormat(data.get("image_format", ImageFormat.PNG.value)),
            jpeg_quality=int(data.get("jpeg_quality", 90)),
            hotkeys=HotkeyConfig.from_dict(data.get("hotkeys", {})),
            session_mode=SessionMode(data.get("session_mode", SessionMode.FIXED_COUNT.value)),
            time_limit_seconds=int(data["time_limit_seconds"]) if data.get("time_limit_seconds") is not None else None,
            auto_session_subdir=bool(data.get("auto_session_subdir", True)),
            session_name_prefix=str(data.get("session_name_prefix", "session")),
        )


@dataclass
class TemplateStore:
    recent: AppConfig = field(default_factory=AppConfig)
    templates: Dict[str, AppConfig] = field(default_factory=dict)

    def register_template(self, name: str, config: AppConfig) -> None:
        self.templates[name] = config

    def remove_template(self, name: str) -> None:
        self.templates.pop(name, None)

    def to_dict(self) -> Dict[str, object]:
        return {
            "recent": self.recent.to_dict(),
            "templates": {name: cfg.to_dict() for name, cfg in self.templates.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "TemplateStore":
        recent_data = data.get("recent", {})
        templates_data = data.get("templates", {})
        recent_cfg = AppConfig.from_dict(recent_data)
        templates_cfg = {name: AppConfig.from_dict(cfg) for name, cfg in templates_data.items()}
        return cls(recent=recent_cfg, templates=templates_cfg)


class ConfigRepository:
    """Persists configuration and templates to the filesystem."""

    def __init__(self, path: Optional[Path] = None) -> None:
        default_path = Path.home() / ".config" / "scu" / "config.json"
        self.path = path or default_path

    def load(self) -> TemplateStore:
        if not self.path.exists():
            return TemplateStore()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return TemplateStore.from_dict(data)

    def save(self, store: TemplateStore) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(store.to_dict(), indent=2)
        self.path.write_text(payload, encoding="utf-8")

    def load_recent(self) -> AppConfig:
        return self.load().recent

    def save_recent(self, config: AppConfig) -> None:
        store = self.load()
        store.recent = config
        self.save(store)

    def save_template(self, name: str, config: AppConfig) -> None:
        store = self.load()
        store.register_template(name, config)
        self.save(store)

    def delete_template(self, name: str) -> None:
        store = self.load()
        store.remove_template(name)
        self.save(store)

    def list_templates(self) -> Dict[str, AppConfig]:
        return self.load().templates
