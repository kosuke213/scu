"""Platform-specific service implementations."""

from .windows import (
    Rect,
    Win32CaptureService,
    Win32InputService,
    Win32WaitService,
)

__all__ = [
    "Rect",
    "Win32CaptureService",
    "Win32InputService",
    "Win32WaitService",
]
