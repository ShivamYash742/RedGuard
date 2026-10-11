"""The structure's rule, checked (docs/architecture.md): Scanner mode and Lab
mode never import each other, and core/ never imports a backend module."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODES = ("scanner_mode", "lab_mode")
BACKEND_MODULES = {"app", "database", "scanner_mode", "lab_mode"}


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module


def _files(top: str):
    return [p for p in (ROOT / top).rglob("*.py") if ".venv" not in p.parts]


@pytest.mark.parametrize("mode", MODES)
def test_modes_never_import_each_other(mode):
    other = MODES[1 - MODES.index(mode)]
    offenders = [
        f"{p.relative_to(ROOT)} imports {name}"
        for top in ("core", "backend") for p in _files(top) if mode in p.parts
        for name in _imports(p) if other in name.split(".")
    ]
    assert not offenders


def test_core_never_imports_backend():
    offenders = [
        f"{p.relative_to(ROOT)} imports {name}"
        for p in _files("core") for name in _imports(p)
        if name.split(".")[0] in BACKEND_MODULES
    ]
    assert not offenders
