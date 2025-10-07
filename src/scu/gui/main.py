"""Qt-based desktop application entry point for SCU."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from ..config import AppConfig, CaptureMode, ConfigRepository, Direction, WaitMode
from ..events import ErrorEvent, ProgressEvent, StateChangeEvent, WarningEvent
from ..output import FilesystemOutputWriter
from ..pipeline import Pipeline
from ..platform import Win32CaptureService, Win32InputService, Win32WaitService
from ..session import SessionController, SessionState


class SessionWorker(QObject):
    """Background worker that drives the session controller."""

    progress = Signal(int, object, object)
    warning = Signal(str)
    error = Signal(str)
    state_changed = Signal(str)
    finished = Signal()

    def __init__(self, config: AppConfig, session_name: Optional[str] = None) -> None:
        super().__init__()
        pipeline = Pipeline(
            capture_service=Win32CaptureService(),
            input_service=Win32InputService(),
            wait_service=Win32WaitService(),
            output_writer=FilesystemOutputWriter(),
        )
        self._controller = SessionController(
            config=config,
            pipeline=pipeline,
            event_callback=self._handle_event,
        )
        self._session_name = session_name
        self._stop_requested = False

    @property
    def controller(self) -> SessionController:
        return self._controller

    def _handle_event(self, event: ProgressEvent | WarningEvent | ErrorEvent | StateChangeEvent) -> None:
        if isinstance(event, ProgressEvent):
            image_path = str(event.image_path) if event.image_path else ""
            self.progress.emit(event.step_index, event.total_steps, image_path)
        elif isinstance(event, WarningEvent):
            self.warning.emit(event.message)
        elif isinstance(event, ErrorEvent):
            self.error.emit(event.message)
        elif isinstance(event, StateChangeEvent):
            self.state_changed.emit(event.state)

    @Slot()
    def run(self) -> None:
        try:
            self._controller.start(session_name=self._session_name)
            while True:
                state = self._controller.state
                if state == SessionState.RUNNING:
                    if self._stop_requested:
                        self._controller.request_stop()
                        self._stop_requested = False
                    self._controller.step()
                elif state == SessionState.PAUSED:
                    QThread.msleep(100)
                else:
                    break
        except Exception as exc:  # noqa: BLE001 - propagate domain failures
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

    @Slot()
    def pause(self) -> None:
        self._controller.pause()

    @Slot()
    def resume(self) -> None:
        self._controller.resume()

    @Slot()
    def stop(self) -> None:
        self._stop_requested = True
        if self._controller.state == SessionState.PAUSED:
            self._controller.stop()


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SCU Capture Utility")
        self.resize(720, 520)

        self._config_repo = ConfigRepository()
        self._current_config = self._config_repo.load_recent()
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[SessionWorker] = None

        self._build_ui()
        self._apply_config(self._current_config)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self.monitor_spin = QSpinBox()
        self.monitor_spin.setMinimum(1)
        self.monitor_spin.setMaximum(16)
        form_layout.addRow("Monitor", self.monitor_spin)

        self.capture_mode_combo = QComboBox()
        self.capture_mode_combo.addItem("Active window", CaptureMode.ACTIVE_WINDOW)
        self.capture_mode_combo.addItem("Full monitor", CaptureMode.FULL_MONITOR)
        form_layout.addRow("Capture mode", self.capture_mode_combo)

        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Right (→)", Direction.RIGHT)
        self.direction_combo.addItem("Left (←)", Direction.LEFT)
        form_layout.addRow("Direction", self.direction_combo)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 10_000)
        form_layout.addRow("Capture count", self.count_spin)

        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 60.0)
        self.delay_spin.setDecimals(2)
        self.delay_spin.setSingleStep(0.1)
        form_layout.addRow("Delay (s)", self.delay_spin)

        self.wait_mode_combo = QComboBox()
        self.wait_mode_combo.addItem("Fixed delay", WaitMode.FIXED)
        self.wait_mode_combo.addItem("Wait for change", WaitMode.CHANGE_DETECTION)
        self.wait_mode_combo.currentIndexChanged.connect(self._on_wait_mode_changed)
        form_layout.addRow("Wait mode", self.wait_mode_combo)

        self.wait_timeout_spin = QDoubleSpinBox()
        self.wait_timeout_spin.setRange(0.1, 600.0)
        self.wait_timeout_spin.setDecimals(2)
        self.wait_timeout_spin.setSingleStep(0.5)
        form_layout.addRow("Wait timeout (s)", self.wait_timeout_spin)

        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse_output)
        output_layout.addWidget(browse_button)
        form_layout.addRow("Output directory", output_layout)

        control_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_session)
        control_layout.addWidget(self.start_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_session)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button)

        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume_session)
        self.resume_button.setEnabled(False)
        control_layout.addWidget(self.resume_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_session)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        layout.addLayout(control_layout)

        self.status_label = QLabel("Idle")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_list = QListWidget()
        layout.addWidget(self.log_list, stretch=1)

        self.setCentralWidget(central)

    def _apply_config(self, config: AppConfig) -> None:
        self.monitor_spin.setValue(config.monitor)
        self.capture_mode_combo.setCurrentIndex(0 if config.capture_mode is CaptureMode.ACTIVE_WINDOW else 1)
        self.direction_combo.setCurrentIndex(0 if config.direction is Direction.RIGHT else 1)
        self.count_spin.setValue(config.count)
        self.delay_spin.setValue(config.delay)
        self.wait_mode_combo.setCurrentIndex(0 if config.wait_mode is WaitMode.FIXED else 1)
        if config.wait_timeout is not None:
            self.wait_timeout_spin.setValue(config.wait_timeout)
        self.wait_timeout_spin.setEnabled(config.wait_mode is WaitMode.CHANGE_DETECTION)
        self.output_edit.setText(str(config.output_dir))

    def _build_config(self) -> AppConfig:
        capture_mode = self.capture_mode_combo.currentData()
        if not isinstance(capture_mode, CaptureMode):
            capture_mode = CaptureMode.ACTIVE_WINDOW
        direction = self.direction_combo.currentData()
        if not isinstance(direction, Direction):
            direction = Direction.RIGHT
        wait_mode = self.wait_mode_combo.currentData()
        if not isinstance(wait_mode, WaitMode):
            wait_mode = WaitMode.FIXED
        wait_timeout: Optional[float]
        if wait_mode is WaitMode.CHANGE_DETECTION:
            wait_timeout = float(self.wait_timeout_spin.value())
        else:
            wait_timeout = None
        output_dir = Path(self.output_edit.text()).expanduser()
        return replace(
            self._current_config,
            monitor=int(self.monitor_spin.value()),
            capture_mode=capture_mode,
            direction=direction,
            count=int(self.count_spin.value()),
            delay=float(self.delay_spin.value()),
            wait_mode=wait_mode,
            wait_timeout=wait_timeout,
            output_dir=output_dir,
        )

    def _ensure_worker(self) -> bool:
        return self._worker_thread is None

    def start_session(self) -> None:
        if sys.platform != "win32":
            QMessageBox.critical(self, "Unsupported platform", "The GUI is only available on Windows.")
            return
        if not self._ensure_worker():
            return
        try:
            config = self._build_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid configuration", str(exc))
            return
        self._current_config = config
        self._config_repo.save_recent(config)

        self.log_list.clear()
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting…")

        try:
            worker = SessionWorker(config)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Unavailable", str(exc))
            self._reset_controls()
            return
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.progress.connect(self._on_progress)
        worker.warning.connect(self._on_warning)
        worker.error.connect(self._on_error)
        worker.state_changed.connect(self._on_state_change)
        thread.finished.connect(self._on_worker_finished)

        self._worker = worker
        self._worker_thread = thread
        thread.start()

        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def pause_session(self) -> None:
        if self._worker is None:
            return
        QMetaObject.invokeMethod(self._worker, "pause", Qt.QueuedConnection)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(True)

    def resume_session(self) -> None:
        if self._worker is None:
            return
        QMetaObject.invokeMethod(self._worker, "resume", Qt.QueuedConnection)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

    def stop_session(self) -> None:
        if self._worker is None:
            return
        QMetaObject.invokeMethod(self._worker, "stop", Qt.QueuedConnection)

    def _on_browse_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select output directory", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def _on_wait_mode_changed(self, index: int) -> None:
        mode = self.wait_mode_combo.itemData(index)
        self.wait_timeout_spin.setEnabled(mode is WaitMode.CHANGE_DETECTION)

    def _on_progress(self, step_index: int, total_steps: object, image_path: object) -> None:
        if isinstance(total_steps, int) and total_steps > 0:
            self.progress_bar.setMaximum(total_steps)
            self.progress_bar.setValue(step_index)
        else:
            self.progress_bar.setMaximum(0)
        if isinstance(image_path, str) and image_path:
            self.log_list.addItem(f"Saved: {image_path}")
        else:
            self.log_list.addItem(f"Completed step {step_index}")
        self.log_list.scrollToBottom()

    def _on_warning(self, message: str) -> None:
        self.log_list.addItem(f"Warning: {message}")
        self.log_list.scrollToBottom()

    def _on_error(self, message: str) -> None:
        self.log_list.addItem(f"Error: {message}")
        self.log_list.scrollToBottom()
        QMessageBox.critical(self, "Session error", message)
        self._reset_controls()

    def _on_state_change(self, state: str) -> None:
        self.status_label.setText(state.capitalize())
        if state == SessionState.RUNNING.value:
            self.pause_button.setEnabled(True)
            self.resume_button.setEnabled(False)
        elif state == SessionState.PAUSED.value:
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
        elif state in {SessionState.STOPPED.value, SessionState.ERROR.value, SessionState.IDLE.value}:
            self._reset_controls(state.capitalize())

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._worker_thread = None
        self._reset_controls()

    def _reset_controls(self, status: Optional[str] = None) -> None:
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setMaximum(1)
        self.status_label.setText(status or "Idle")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker is not None and self._worker_thread is not None:
            QMetaObject.invokeMethod(self._worker, "stop", Qt.QueuedConnection)
            self._worker_thread.quit()
            self._worker_thread.wait(2000)
        super().closeEvent(event)


def main() -> None:
    """Launch the GUI application."""

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["main", "MainWindow", "SessionWorker"]
