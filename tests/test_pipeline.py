from dataclasses import dataclass
from pathlib import Path
from typing import List

from scu.config import AppConfig, ProcessOrder, WaitMode
from scu.duplicates import SimpleDuplicateDetector
from scu.interfaces import CaptureRequest, CaptureResult, CaptureService, InputService, OutputWriter, WaitService
from scu.output import SessionPathManager
from scu.pipeline import Pipeline, SessionContext


@dataclass
class RecordedCall:
    name: str


class FakeCaptureService(CaptureService):
    def __init__(self) -> None:
        self.count = 0

    def capture(self, request: CaptureRequest) -> CaptureResult:  # type: ignore[override]
        self.count += 1
        data = f"frame-{self.count}".encode()
        return CaptureResult(image_bytes=data, width=100, height=100, hash_value=None)


class RecordingInputService(InputService):
    def __init__(self, calls: List[RecordedCall]) -> None:
        self.calls = calls

    def send_direction(self, direction) -> None:  # type: ignore[override]
        self.calls.append(RecordedCall(f"send-{direction.value}"))


class RecordingWaitService(WaitService):
    def __init__(self, calls: List[RecordedCall], change_result: bool = True) -> None:
        self.calls = calls
        self.change_result = change_result

    def wait_fixed(self, delay_seconds: float) -> None:  # type: ignore[override]
        self.calls.append(RecordedCall(f"wait-fixed-{delay_seconds}"))

    def wait_for_change(self, previous_hash, timeout_seconds: float) -> bool:  # type: ignore[override]
        self.calls.append(RecordedCall(f"wait-change-{timeout_seconds}"))
        return self.change_result


class FilesystemOutputWriter(OutputWriter):
    def __init__(self, base: Path) -> None:
        self.base = base

    def write_capture(self, session_dir, index, image_format, image_bytes, jpeg_quality):  # type: ignore[override]
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"page_{index:04d}{image_format.extension}"
        path.write_bytes(image_bytes)
        return path


def test_pipeline_observes_key_first_order(tmp_path: Path) -> None:
    calls: List[RecordedCall] = []
    config = AppConfig(output_dir=tmp_path, process_order=ProcessOrder.KEY_FIRST)
    pipeline = Pipeline(
        capture_service=FakeCaptureService(),
        input_service=RecordingInputService(calls),
        wait_service=RecordingWaitService(calls),
        output_writer=FilesystemOutputWriter(tmp_path / "session"),
    )

    manager = SessionPathManager(config)
    manager.prepare_session_dir(session_name="sess")
    context = SessionContext(config=config, path_manager=manager, duplicate_detector=SimpleDuplicateDetector())

    outcome = pipeline.execute_step(context, index=1)

    assert calls[0].name.startswith("send-")
    assert any(call.name.startswith("wait-fixed") for call in calls)
    assert outcome.image_path is not None


def test_pipeline_change_detection_warning(tmp_path: Path) -> None:
    calls: List[RecordedCall] = []
    config = AppConfig(output_dir=tmp_path, wait_mode=WaitMode.CHANGE_DETECTION, wait_timeout=1.0)
    pipeline = Pipeline(
        capture_service=FakeCaptureService(),
        input_service=RecordingInputService(calls),
        wait_service=RecordingWaitService(calls, change_result=False),
        output_writer=FilesystemOutputWriter(tmp_path / "session"),
    )
    manager = SessionPathManager(config)
    manager.prepare_session_dir(session_name="sess")
    context = SessionContext(config=config, path_manager=manager, duplicate_detector=SimpleDuplicateDetector())

    outcome = pipeline.execute_step(context, index=1)
    assert len(outcome.warnings) == 1
    assert "No visual change" in outcome.warnings[0].message
