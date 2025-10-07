from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import CaptureMode, Direction, ImageFormat


@dataclass(frozen=True)
class CaptureRequest:
    monitor: int
    capture_mode: CaptureMode
    min_overlap: float


@dataclass(frozen=True)
class CaptureResult:
    image_bytes: bytes
    width: int
    height: int
    hash_value: str | None = None


class CaptureService(Protocol):
    def capture(self, request: CaptureRequest) -> CaptureResult:
        """Capture the configured window or monitor."""


class InputService(Protocol):
    def send_direction(self, direction: Direction) -> None:
        """Send the requested arrow key via the OS."""


class WaitService(Protocol):
    def wait_fixed(self, delay_seconds: float) -> None:
        """Sleep for a fixed amount of time."""

    def wait_for_change(self, previous_hash: str | None, timeout_seconds: float) -> bool:
        """Return True if a visual change is detected within timeout."""


class DuplicateDetector(Protocol):
    def is_duplicate(self, hash_value: str) -> bool:
        """Return True if the hash has been seen before in the session."""

    def remember(self, hash_value: str) -> None:
        """Record the hash as seen."""


class OutputWriter(Protocol):
    def write_capture(
        self,
        session_dir: Path,
        index: int,
        image_format: ImageFormat,
        image_bytes: bytes,
        jpeg_quality: int,
    ) -> Path:
        """Persist the capture bytes to disk and return the path."""
