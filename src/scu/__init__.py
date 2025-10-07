"""SCU core domain library."""

from .config import AppConfig, CaptureMode, Direction, ProcessOrder, WaitMode, SessionMode, ImageFormat
from .session import SessionController, SessionState
from .pipeline import Pipeline
from .output import SessionPathManager
from .duplicates import SimpleDuplicateDetector

__all__ = [
    "AppConfig",
    "CaptureMode",
    "Direction",
    "ProcessOrder",
    "WaitMode",
    "SessionMode",
    "ImageFormat",
    "SessionController",
    "SessionState",
    "Pipeline",
    "SessionPathManager",
    "SimpleDuplicateDetector",
]
