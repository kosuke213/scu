from __future__ import annotations

import hashlib
import sys

import pytest

from scu.config import CaptureMode, Direction
from scu.interfaces import CaptureRequest
from scu.platform.windows import Rect, Win32CaptureService, Win32InputService, Win32WaitService


class FakeWin32API:
    def __init__(self) -> None:
        self.monitors = [Rect(0, 0, 1920, 1080)]
        self.foreground: Rect | None = Rect(100, 100, 400, 300)
        self.captured_rects: list[Rect] = []
        self.sent_keys: list[int] = []

    def list_monitors(self) -> list[Rect]:
        return self.monitors

    def get_foreground_window_rect(self) -> Rect | None:
        return self.foreground

    def capture_rect(self, rect: Rect) -> bytes:
        self.captured_rects.append(rect)
        return f"capture:{rect.left},{rect.top},{rect.right},{rect.bottom}".encode()

    def send_key(self, vk_code: int) -> None:
        self.sent_keys.append(vk_code)


class FakeTimer:
    def __init__(self) -> None:
        self.current = 0.0
        self.slept: list[float] = []

    def sleep(self, delay: float) -> None:
        self.slept.append(delay)
        self.current += max(0.0, delay)

    def monotonic(self) -> float:
        return self.current


def test_capture_full_monitor_uses_monitor_bounds() -> None:
    api = FakeWin32API()
    service = Win32CaptureService(api=api)
    request = CaptureRequest(monitor=1, capture_mode=CaptureMode.FULL_MONITOR, min_overlap=0.5)

    result = service.capture(request)

    assert result.width == 1920
    assert result.height == 1080
    assert api.captured_rects[-1] == api.monitors[0]
    assert result.hash_value == hashlib.sha1(b"capture:0,0,1920,1080").hexdigest()


def test_services_require_windows_when_no_api() -> None:
    if sys.platform == "win32":
        pytest.skip("platform check only relevant for non-Windows CI")

    with pytest.raises(RuntimeError):
        Win32CaptureService()

    with pytest.raises(RuntimeError):
        Win32InputService()


def test_capture_active_window_clamps_to_monitor() -> None:
    api = FakeWin32API()
    api.foreground = Rect(-50, 10, 150, 110)  # partially outside the monitor
    service = Win32CaptureService(api=api)
    request = CaptureRequest(monitor=1, capture_mode=CaptureMode.ACTIVE_WINDOW, min_overlap=0.1)

    result = service.capture(request)

    assert api.captured_rects[-1] == Rect(0, 10, 150, 110)
    assert result.width == 150
    assert result.height == 100


def test_capture_active_window_overlap_validation() -> None:
    api = FakeWin32API()
    api.foreground = Rect(1910, 0, 2100, 200)
    service = Win32CaptureService(api=api)
    request = CaptureRequest(monitor=1, capture_mode=CaptureMode.ACTIVE_WINDOW, min_overlap=0.8)

    with pytest.raises(RuntimeError):
        service.capture(request)


def test_capture_invalid_monitor_raises() -> None:
    api = FakeWin32API()
    service = Win32CaptureService(api=api)
    request = CaptureRequest(monitor=2, capture_mode=CaptureMode.FULL_MONITOR, min_overlap=0.5)

    with pytest.raises(ValueError):
        service.capture(request)


def test_input_service_sends_correct_key() -> None:
    api = FakeWin32API()
    input_service = Win32InputService(api=api)

    input_service.send_direction(Direction.LEFT)
    input_service.send_direction(Direction.RIGHT)

    assert api.sent_keys == [Win32InputService.VK_LEFT, Win32InputService.VK_RIGHT]


def test_wait_service_detects_change_before_timeout() -> None:
    timer = FakeTimer()
    hashes = iter(["abc", "abc", "def"])
    service = Win32WaitService(
        change_detector=lambda: next(hashes, "def"),
        poll_interval=0.2,
        sleep_fn=timer.sleep,
        monotonic_fn=timer.monotonic,
    )

    assert service.wait_for_change("abc", 1.0) is True
    # slept at least twice (one poll + exit)
    assert timer.current >= 0.2


def test_wait_service_times_out_when_no_change() -> None:
    timer = FakeTimer()
    service = Win32WaitService(
        change_detector=lambda: "same",
        poll_interval=0.2,
        sleep_fn=timer.sleep,
        monotonic_fn=timer.monotonic,
    )

    assert service.wait_for_change("same", 0.5) is False
    assert timer.current == pytest.approx(0.5, rel=1e-6)


def test_wait_fixed_uses_sleep() -> None:
    timer = FakeTimer()
    service = Win32WaitService(sleep_fn=timer.sleep, monotonic_fn=timer.monotonic)

    service.wait_fixed(0.3)

    assert timer.current == pytest.approx(0.3, rel=1e-6)
