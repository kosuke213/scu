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

The current code is platform agnostic and focuses on core coordination logic. Windows-specific integrations (Win32 capture, SendInput) are abstracted behind service interfaces and can be implemented in future iterations with native bindings.
