from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import AppConfig, ProcessOrder, WaitMode
from .events import WarningEvent
from .interfaces import (
    CaptureRequest,
    CaptureService,
    CaptureResult,
    DuplicateDetector,
    InputService,
    OutputWriter,
    WaitService,
)
from .output import SessionPathManager


@dataclass
class StepOutcome:
    index: int
    image_path: Optional[Path]
    hash_value: Optional[str]
    warnings: List[WarningEvent]


@dataclass
class SessionContext:
    config: AppConfig
    path_manager: SessionPathManager
    duplicate_detector: DuplicateDetector
    last_hash: Optional[str] = None


class Pipeline:
    """Coordinates capture, input, and wait operations for each step."""

    def __init__(
        self,
        capture_service: CaptureService,
        input_service: InputService,
        wait_service: WaitService,
        output_writer: OutputWriter,
    ) -> None:
        self.capture_service = capture_service
        self.input_service = input_service
        self.wait_service = wait_service
        self.output_writer = output_writer

    def execute_step(self, context: SessionContext, index: int) -> StepOutcome:
        config = context.config
        warnings: List[WarningEvent] = []

        if config.process_order == ProcessOrder.KEY_FIRST:
            self.input_service.send_direction(config.direction)

        capture_result = self._perform_capture(context)
        image_path_obj: Optional[Path] = None
        hash_value = capture_result.hash_value

        if capture_result.image_bytes:
            if hash_value is None:
                hash_value = context.path_manager.hash_bytes(capture_result.image_bytes)
            image_path = self.output_writer.write_capture(
                session_dir=context.path_manager.session_dir or context.path_manager.prepare_session_dir(),
                index=index,
                image_format=config.image_format,
                image_bytes=capture_result.image_bytes,
                jpeg_quality=config.jpeg_quality,
            )
            image_path_obj = image_path

            if hash_value:
                if context.duplicate_detector.is_duplicate(hash_value):
                    warnings.append(
                        WarningEvent(
                            timestamp=datetime.now(),
                            message="Duplicate frame detected",
                        )
                    )
                context.duplicate_detector.remember(hash_value)
                context.last_hash = hash_value

        if config.process_order == ProcessOrder.SHOT_FIRST:
            self.input_service.send_direction(config.direction)

        if config.wait_mode == WaitMode.FIXED:
            self.wait_service.wait_fixed(config.delay)
        else:
            changed = self.wait_service.wait_for_change(context.last_hash, config.wait_timeout or 0.0)
            if not changed:
                warnings.append(
                    WarningEvent(
                        timestamp=datetime.now(),
                        message="No visual change detected before timeout",
                    )
                )

        return StepOutcome(index=index, image_path=image_path_obj, hash_value=hash_value, warnings=warnings)

    def _perform_capture(self, context: SessionContext) -> CaptureResult:
        request = CaptureRequest(
            monitor=context.config.monitor,
            capture_mode=context.config.capture_mode,
            min_overlap=context.config.min_overlap,
        )
        return self.capture_service.capture(request)
