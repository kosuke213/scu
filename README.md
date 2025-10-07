# SCU Core Library

This repository contains the core domain logic and planning documents for the "Multi-monitor screenshot & arrow key automation utility" described in `requirements.md`. The focus of this iteration is to establish a testable Python package that encapsulates the orchestration logic, configuration persistence, session state management, and output organization that will back a Windows-native GUI layer.

## Repository layout

- `requirements.md` — Original Japanese requirement specification.
- `docs/` — Architecture and implementation planning documents.
- `src/scu/` — Python package implementing the core domain logic.
- `tests/` — Automated unit tests for the domain logic.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

The core coordination logic remains platform agnostic. Windows-specific integrations (Win32 capture, SendInput) are exposed via the new GUI layer described below.

## Launching the Windows GUI

The desktop application depends on Qt via PySide6 and currently targets Windows. Install the GUI extras and invoke the launcher:

```bash
pip install -e .[gui]
scu-gui
```

Alternatively, you can run the module directly with `python -m scu.gui.main`. The application persists the most recent configuration using the existing `ConfigRepository` and allows you to start, pause, resume, and stop capture sessions from a single window.

## Building a standalone executable

To distribute the tool as a single `.exe`, install the build extras and run the packaging helper (PyInstaller must be executed on Windows for a functional binary):

```bash
pip install -e .[build]
scu-build-exe --dist dist --name scu-capture
```

The command produces an executable in the chosen `dist` directory. Use `--onedir` to emit a folder-based distribution or `--no-clean` for quicker iterative builds.
