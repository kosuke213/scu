from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import AppConfig, ImageFormat
from .interfaces import OutputWriter


class SessionPathManager:
    """Handles directory preparation and file naming for captures."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session_dir: Optional[Path] = None

    def prepare_session_dir(self, now: Optional[datetime] = None, session_name: Optional[str] = None) -> Path:
        timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
        base_dir = self.config.output_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        if self.config.auto_session_subdir:
            prefix = session_name or f"{self.config.session_name_prefix}_{timestamp}"
            session_dir = base_dir / prefix
        else:
            session_dir = base_dir
        session_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir = session_dir
        return session_dir

    def capture_path(self, index: int, image_format: ImageFormat) -> Path:
        if self.session_dir is None:
            raise RuntimeError("Session directory not prepared")
        return self.session_dir / f"page_{index:04d}{image_format.extension}"

    def write_capture(self, index: int, image_format: ImageFormat, image_bytes: bytes, jpeg_quality: int = 90) -> Path:
        path = self.capture_path(index, image_format)
        path.write_bytes(image_bytes)
        return path

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha1(data).hexdigest()


class FilesystemOutputWriter(OutputWriter):
    """Persist captures to disk within the prepared session directory."""

    def write_capture(
        self,
        session_dir: Path,
        index: int,
        image_format: ImageFormat,
        image_bytes: bytes,
        jpeg_quality: int,
    ) -> Path:
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"page_{index:04d}{image_format.extension}"
        path.write_bytes(image_bytes)
        return path
