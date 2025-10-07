from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List

from scu.config import AppConfig, SessionMode
from scu.events import ErrorEvent, ProgressEvent, StateChangeEvent
from scu.pipeline import SessionContext, StepOutcome
from scu.session import SessionController, SessionState


class StubPipeline:
    def __init__(self, outcomes: List[StepOutcome] | None = None, *, raise_on_step: bool = False) -> None:
        self.outcomes = outcomes or []
        self.raise_on_step = raise_on_step

    def execute_step(self, context: SessionContext, index: int) -> StepOutcome:
        if self.raise_on_step:
            raise RuntimeError("capture failed")
        if self.outcomes:
            return self.outcomes.pop(0)
        return StepOutcome(index=index, image_path=None, hash_value=None, warnings=[])


def collect_events(event_list: List) -> Callable:
    def _collector(event) -> None:
        event_list.append(event)

    return _collector


def test_session_progress_and_completion(tmp_path: Path) -> None:
    config = AppConfig(output_dir=tmp_path, session_mode=SessionMode.FIXED_COUNT, count=2)
    events: List = []
    pipeline = StubPipeline()
    controller = SessionController(config=config, pipeline=pipeline, event_callback=collect_events(events))  # type: ignore[arg-type]

    controller.start(now=datetime(2024, 1, 1, 0, 0, 0), session_name="test")
    assert controller.state == SessionState.RUNNING
    controller.step()
    controller.step()
    assert controller.state == SessionState.STOPPED

    progress_events = [e for e in events if isinstance(e, ProgressEvent)]
    assert len(progress_events) == 2
    state_events = [e for e in events if isinstance(e, StateChangeEvent)]
    assert state_events[-1].state == SessionState.STOPPED.value


def test_session_handles_errors(tmp_path: Path) -> None:
    config = AppConfig(output_dir=tmp_path)
    events: List = []
    pipeline = StubPipeline(raise_on_step=True)
    controller = SessionController(config=config, pipeline=pipeline, event_callback=collect_events(events))  # type: ignore[arg-type]
    controller.start(session_name="err")

    try:
        controller.step()
    except RuntimeError:
        pass

    assert controller.state == SessionState.ERROR
    assert any(isinstance(e, ErrorEvent) for e in events)


def test_time_limit_stops_automatically(tmp_path: Path) -> None:
    config = AppConfig(output_dir=tmp_path, session_mode=SessionMode.TIME_LIMIT, time_limit_seconds=1)
    events: List = []
    pipeline = StubPipeline()
    controller = SessionController(config=config, pipeline=pipeline, event_callback=collect_events(events))  # type: ignore[arg-type]
    start_time = datetime.now() - timedelta(seconds=2)
    controller.start(now=start_time, session_name="time")

    controller.step()
    assert controller.state == SessionState.STOPPED
