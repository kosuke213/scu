from types import ModuleType
from pathlib import Path
import sys

from scu.tools import build_exe


def test_build_executable_constructs_expected_arguments(monkeypatch, tmp_path: Path) -> None:
    recorded: dict[str, list[str]] = {}

    stub_parent = ModuleType("PyInstaller")
    stub_main = ModuleType("PyInstaller.__main__")

    def fake_run(args: list[str]) -> None:
        recorded["args"] = list(args)

    stub_main.run = fake_run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "PyInstaller", stub_parent)
    monkeypatch.setitem(sys.modules, "PyInstaller.__main__", stub_main)

    build_exe.build_executable(dist_path=tmp_path, onefile=False, clean=False, name="custom")

    args = recorded["args"]
    assert "--onefile" not in args
    assert "--clean" not in args
    assert "--windowed" in args
    assert "--noconfirm" in args
    assert "--name=custom" in args
    assert f"--distpath={tmp_path.resolve()}" in args
    assert args[-1].endswith("scu/gui/main.py")


def test_main_parses_cli_arguments(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_builder(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "PyInstaller", ModuleType("PyInstaller"))
    monkeypatch.setitem(sys.modules, "PyInstaller.__main__", ModuleType("PyInstaller.__main__"))
    monkeypatch.setattr(build_exe, "build_executable", lambda **kwargs: fake_builder(**kwargs))

    build_exe.main(["--dist", str(tmp_path), "--onedir", "--no-clean", "--name", "demo"])

    assert captured["dist_path"] == tmp_path
    assert captured["onefile"] is False
    assert captured["clean"] is False
    assert captured["name"] == "demo"
