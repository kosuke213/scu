"""Utilities for creating a distributable Windows executable."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


def build_executable(
    dist_path: Path | None = None,
    *,
    onefile: bool = True,
    clean: bool = True,
    name: str = "scu-gui",
) -> None:
    """Invoke PyInstaller to bundle the GUI into an executable."""

    try:
        import PyInstaller.__main__ as pyinstaller_main
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in tests via stubs
        raise RuntimeError(
            "PyInstaller is required to build the executable. Install the 'build' extra first."
        ) from exc

    entry_point = Path(__file__).resolve().parents[1] / "gui" / "main.py"

    args = ["--noconfirm", "--windowed", f"--name={name}"]
    if clean:
        args.append("--clean")
    if onefile:
        args.append("--onefile")
    if dist_path is not None:
        args.append(f"--distpath={Path(dist_path).resolve()}")
    args.append(str(entry_point))

    pyinstaller_main.run(args)


def main(argv: Sequence[str] | None = None) -> None:
    """Command line interface for :func:`build_executable`."""

    parser = argparse.ArgumentParser(description="Bundle the SCU GUI into a Windows executable.")
    parser.add_argument(
        "--dist",
        type=Path,
        default=None,
        help="Directory where the executable should be written (defaults to PyInstaller's dist path)",
    )
    parser.add_argument(
        "--name",
        default="scu-gui",
        help="Name of the generated executable.",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Create a folder-based distribution instead of a single file.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip PyInstaller's clean step to speed up repeated builds.",
    )

    args = parser.parse_args(argv)
    build_executable(
        dist_path=args.dist,
        onefile=not args.onedir,
        clean=not args.no_clean,
        name=args.name,
    )


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    main()


__all__ = ["build_executable", "main"]
