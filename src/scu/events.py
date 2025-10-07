from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProgressEvent:
    timestamp: datetime
    step_index: int
    total_steps: Optional[int]
    image_path: Optional[Path]
    message: str = ""


@dataclass(frozen=True)
class WarningEvent:
    timestamp: datetime
    message: str


@dataclass(frozen=True)
class ErrorEvent:
    timestamp: datetime
    message: str
    recoverable: bool = False


@dataclass(frozen=True)
class StateChangeEvent:
    timestamp: datetime
    state: str


Event = ProgressEvent | WarningEvent | ErrorEvent | StateChangeEvent
