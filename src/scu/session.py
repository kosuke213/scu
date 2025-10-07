from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .config import AppConfig, SessionMode
from .duplicates import SimpleDuplicateDetector
from .events import ErrorEvent, ProgressEvent, StateChangeEvent, WarningEvent
from .output import SessionPathManager
from .pipeline import Pipeline, SessionContext


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class SessionRuntime:
    start_time: datetime
    completed_steps: int = 0
    total_steps: Optional[int] = None
    stop_requested: bool = False


class SessionController:
    """State machine that executes the pipeline and emits events."""

    def __init__(
        self,
        config: AppConfig,
        pipeline: Pipeline,
        event_callback: Callable[[ProgressEvent | WarningEvent | ErrorEvent | StateChangeEvent], None],
    ) -> None:
        self.config = config
        self.pipeline = pipeline
        self.event_callback = event_callback
        self.state = SessionState.IDLE
        self.path_manager = SessionPathManager(config)
        self.runtime: Optional[SessionRuntime] = None
        self.duplicate_detector = SimpleDuplicateDetector()
        self.time_limit_deadline: Optional[datetime] = None

    def start(self, now: Optional[datetime] = None, session_name: Optional[str] = None) -> None:
        if self.state not in {SessionState.IDLE, SessionState.STOPPED}:
            raise RuntimeError("Session already started")
        start_time = now or datetime.now()
        self.path_manager.prepare_session_dir(now=start_time, session_name=session_name)
        total_steps = self.config.count if self.config.session_mode == SessionMode.FIXED_COUNT else None
        self.runtime = SessionRuntime(start_time=start_time, total_steps=total_steps)
        self.state = SessionState.RUNNING
        if self.config.session_mode == SessionMode.TIME_LIMIT and self.config.time_limit_seconds:
            self.time_limit_deadline = start_time + timedelta(seconds=self.config.time_limit_seconds)
        else:
            self.time_limit_deadline = None
        self._emit_state_change()

    def pause(self) -> None:
        if self.state != SessionState.RUNNING:
            return
        self.state = SessionState.PAUSED
        self._emit_state_change()

    def resume(self) -> None:
        if self.state != SessionState.PAUSED:
            return
        self.state = SessionState.RUNNING
        self._emit_state_change()

    def stop(self) -> None:
        if self.state in {SessionState.STOPPED, SessionState.ERROR}:
            return
        self.state = SessionState.STOPPED
        self._emit_state_change()

    def request_stop(self) -> None:
        if not self.runtime:
            return
        self.runtime.stop_requested = True

    def step(self) -> None:
        if self.state != SessionState.RUNNING:
            raise RuntimeError("Session is not running")
        if not self.runtime:
            raise RuntimeError("Session not initialised")

        if self.runtime.stop_requested:
            self.stop()
            return

        if self.time_limit_deadline and datetime.now() >= self.time_limit_deadline:
            self.stop()
            return

        index = self.runtime.completed_steps + 1
        context = SessionContext(
            config=self.config,
            path_manager=self.path_manager,
            duplicate_detector=self.duplicate_detector,
        )
        try:
            outcome = self.pipeline.execute_step(context, index=index)
        except Exception as exc:  # noqa: BLE001 - propagate domain errors
            self.state = SessionState.ERROR
            self._emit_state_change()
            self.event_callback(
                ErrorEvent(
                    timestamp=datetime.now(),
                    message=str(exc),
                    recoverable=False,
                )
            )
            raise

        self.runtime.completed_steps += 1
        self._emit_progress(outcome.image_path)
        for warning in outcome.warnings:
            self.event_callback(warning)

        if self.runtime.total_steps and self.runtime.completed_steps >= self.runtime.total_steps:
            self.stop()

    def _emit_progress(self, image_path: Optional[Path]) -> None:
        if not self.runtime:
            return
        self.event_callback(
            ProgressEvent(
                timestamp=datetime.now(),
                step_index=self.runtime.completed_steps,
                total_steps=self.runtime.total_steps,
                image_path=image_path,
            )
        )

    def _emit_state_change(self) -> None:
        self.event_callback(
            StateChangeEvent(
                timestamp=datetime.now(),
                state=self.state.value,
            )
        )
