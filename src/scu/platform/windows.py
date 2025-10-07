"""Windows-specific service implementations."""

from __future__ import annotations

import ctypes
import hashlib
import io
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Sequence

from ..config import CaptureMode, Direction
from ..interfaces import CaptureRequest, CaptureResult, CaptureService, InputService, WaitService

try:  # pragma: no cover - optional dependency used only on Windows at runtime
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - pillow is optional
    Image = None  # type: ignore


@dataclass(frozen=True)
class Rect:
    """Simple rectangle utility."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    @property
    def area(self) -> int:
        return self.width * self.height

    def intersect(self, other: "Rect") -> "Rect":
        return Rect(
            left=max(self.left, other.left),
            top=max(self.top, other.top),
            right=min(self.right, other.right),
            bottom=min(self.bottom, other.bottom),
        )

    def clamp_within(self, bounds: "Rect") -> "Rect":
        return Rect(
            left=max(self.left, bounds.left),
            top=max(self.top, bounds.top),
            right=min(self.right, bounds.right),
            bottom=min(self.bottom, bounds.bottom),
        )

    def overlap_ratio(self, other: "Rect") -> float:
        if self.area == 0:
            return 0.0
        intersection = self.intersect(other)
        return intersection.area / self.area


class Win32API(Protocol):
    """Protocol for Win32 API access used by the services."""

    def list_monitors(self) -> Sequence[Rect]:
        ...

    def get_foreground_window_rect(self) -> Rect | None:
        ...

    def capture_rect(self, rect: Rect) -> bytes:
        ...

    def send_key(self, vk_code: int) -> None:
        ...


class Win32CaptureService(CaptureService):
    """Capture service backed by Win32 APIs."""

    def __init__(self, api: Optional[Win32API] = None) -> None:
        if api is None and sys.platform != "win32":  # pragma: no cover - requires Windows
            raise RuntimeError("Win32CaptureService can only be used on Windows")
        self.api = api or RealWin32API()  # type: ignore[arg-type]

    def capture(self, request: CaptureRequest) -> CaptureResult:
        monitors = list(self.api.list_monitors())
        if request.monitor < 1 or request.monitor > len(monitors):
            raise ValueError(f"Monitor {request.monitor} is not available")
        monitor_rect = monitors[request.monitor - 1]

        if request.capture_mode is CaptureMode.FULL_MONITOR:
            target_rect = monitor_rect
        else:
            window_rect = self.api.get_foreground_window_rect()
            if window_rect is None:
                raise RuntimeError("No active window detected")
            if window_rect.overlap_ratio(monitor_rect) < request.min_overlap:
                raise RuntimeError("Active window does not meet the minimum overlap requirement")
            target_rect = window_rect.clamp_within(monitor_rect)

        if target_rect.area == 0:
            raise RuntimeError("Target capture area is empty")

        image_bytes = self.api.capture_rect(target_rect)
        hash_value = hashlib.sha1(image_bytes).hexdigest() if image_bytes else None
        return CaptureResult(
            image_bytes=image_bytes,
            width=target_rect.width,
            height=target_rect.height,
            hash_value=hash_value,
        )


class Win32InputService(InputService):
    """Input service that sends arrow keys using Win32 SendInput."""

    VK_LEFT = 0x25
    VK_RIGHT = 0x27

    def __init__(self, api: Optional[Win32API] = None) -> None:
        if api is None and sys.platform != "win32":  # pragma: no cover - requires Windows
            raise RuntimeError("Win32InputService can only be used on Windows")
        self.api = api or RealWin32API()  # type: ignore[arg-type]

    def send_direction(self, direction: Direction) -> None:
        vk_code = self.VK_LEFT if direction is Direction.LEFT else self.VK_RIGHT
        self.api.send_key(vk_code)


class Win32WaitService(WaitService):
    """Wait service supporting both fixed delay and change detection polling."""

    def __init__(
        self,
        change_detector: Optional[Callable[[], str | None]] = None,
        poll_interval: float = 0.1,
        sleep_fn: Callable[[float], None] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
    ) -> None:
        self._change_detector = change_detector
        self._poll_interval = max(0.01, poll_interval)
        self._sleep = sleep_fn or time.sleep
        self._monotonic = monotonic_fn or time.monotonic

    def wait_fixed(self, delay_seconds: float) -> None:
        if delay_seconds > 0:
            self._sleep(delay_seconds)

    def wait_for_change(self, previous_hash: str | None, timeout_seconds: float) -> bool:
        if timeout_seconds <= 0:
            return True
        if self._change_detector is None:
            self._sleep(timeout_seconds)
            return True
        deadline = self._monotonic() + timeout_seconds
        while self._monotonic() < deadline:
            current_hash = self._change_detector()
            if current_hash is None:
                self._sleep(self._poll_interval)
                continue
            if previous_hash is None or current_hash != previous_hash:
                return True
            remaining = max(0.0, deadline - self._monotonic())
            self._sleep(min(self._poll_interval, remaining))
        return False


class Win32Error(RuntimeError):
    """Raised when a Win32 API call fails."""


if sys.platform == "win32":  # pragma: no cover - real API only exercised on Windows
    from ctypes import wintypes

    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0
    BI_RGB = 0
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 1),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.ULONG_PTR),
        ]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(_RECT),
        wintypes.LPARAM,
    )

    class RealWin32API:
        def __init__(self) -> None:
            self.user32 = ctypes.windll.user32
            self.gdi32 = ctypes.windll.gdi32
            self.user32.SetProcessDPIAware()

        def list_monitors(self) -> Sequence[Rect]:
            monitors: list[Rect] = []

            def _callback(hmonitor: wintypes.HMONITOR, hdc: wintypes.HDC, rect_ptr: ctypes.POINTER(_RECT), lparam: wintypes.LPARAM) -> wintypes.BOOL:
                rect = rect_ptr.contents
                monitors.append(Rect(rect.left, rect.top, rect.right, rect.bottom))
                return True

            if not self.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(_callback), 0):
                raise Win32Error("EnumDisplayMonitors failed")
            if not monitors:
                raise Win32Error("No monitors detected")
            return monitors

        def get_foreground_window_rect(self) -> Rect | None:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return None
            rect = _RECT()
            if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                raise Win32Error("GetWindowRect failed")
            return Rect(rect.left, rect.top, rect.right, rect.bottom)

        def capture_rect(self, rect: Rect) -> bytes:
            width, height = rect.width, rect.height
            if width == 0 or height == 0:
                return b""

            hdc_screen = self.user32.GetDC(0)
            if not hdc_screen:
                raise Win32Error("GetDC failed")
            hdc_mem = self.gdi32.CreateCompatibleDC(hdc_screen)
            if not hdc_mem:
                self.user32.ReleaseDC(0, hdc_screen)
                raise Win32Error("CreateCompatibleDC failed")
            bitmap = self.gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            if not bitmap:
                self.gdi32.DeleteDC(hdc_mem)
                self.user32.ReleaseDC(0, hdc_screen)
                raise Win32Error("CreateCompatibleBitmap failed")
            try:
                if not self.gdi32.SelectObject(hdc_mem, bitmap):
                    raise Win32Error("SelectObject failed")
                if not self.gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, rect.left, rect.top, SRCCOPY):
                    raise Win32Error("BitBlt failed")

                bmi = BITMAPINFO()
                ctypes.memset(ctypes.byref(bmi), 0, ctypes.sizeof(bmi))
                bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.bmiHeader.biWidth = width
                bmi.bmiHeader.biHeight = -height  # top-down bitmap
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = BI_RGB

                buffer_size = width * height * 4
                buffer = (ctypes.c_ubyte * buffer_size)()
                if not self.gdi32.GetDIBits(
                    hdc_mem,
                    bitmap,
                    0,
                    height,
                    ctypes.byref(buffer),
                    ctypes.byref(bmi),
                    DIB_RGB_COLORS,
                ):
                    raise Win32Error("GetDIBits failed")
                raw_bytes = bytes(buffer)
                if Image is None:
                    return raw_bytes
                image = Image.frombuffer("RGBA", (width, height), raw_bytes, "raw", "BGRA", 0, 1)
                with io.BytesIO() as stream:
                    image.save(stream, format="PNG")
                    return stream.getvalue()
            finally:
                self.gdi32.DeleteObject(bitmap)
                self.gdi32.DeleteDC(hdc_mem)
                self.user32.ReleaseDC(0, hdc_screen)

        def send_key(self, vk_code: int) -> None:
            inputs = (INPUT * 2)()
            inputs[0].type = INPUT_KEYBOARD
            inputs[0].union.ki = KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=0, time=0, dwExtraInfo=0)
            inputs[1].type = INPUT_KEYBOARD
            inputs[1].union.ki = KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
            sent = self.user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
            if sent != 2:
                raise Win32Error("SendInput failed")

else:  # pragma: no cover - placeholder for non-Windows environments

    class RealWin32API:  # type: ignore[override]
        def __init__(self) -> None:
            raise RuntimeError("RealWin32API is only available on Windows")

        def list_monitors(self) -> Sequence[Rect]:
            raise RuntimeError("RealWin32API is only available on Windows")

        def get_foreground_window_rect(self) -> Rect | None:
            raise RuntimeError("RealWin32API is only available on Windows")

        def capture_rect(self, rect: Rect) -> bytes:
            raise RuntimeError("RealWin32API is only available on Windows")

        def send_key(self, vk_code: int) -> None:
            raise RuntimeError("RealWin32API is only available on Windows")
