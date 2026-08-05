"""The programme module is read-only BY CONSTRUCTION, not by promise.

Same pattern as tests/test_blocks_import_graph.py: an admin diagnostic that
claims to write nothing should not be able to, and the cheapest enforcement
is that it cannot import anything that writes.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "src" / "ah" / "programme.py"
FORBIDDEN = ("ah.store", "ah.serve", "sqlite3")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_programme_never_imports_a_writer():
    offenders = [
        module
        for module in _imported_modules(MODULE)
        for bad in FORBIDDEN
        if module == bad or module.startswith(bad + ".")
    ]
    assert not offenders, f"ah.programme must not import a writer: {offenders}"


def test_programme_is_not_in_the_preregistration_seal():
    lock = Path(__file__).resolve().parents[1] / "prereg" / "battery-lock.yaml"
    if not lock.exists():
        return  # the seal lives elsewhere; the CLAUDE.md list already excludes this file
    assert "programme.py" not in lock.read_text("utf-8")
