"""WP2.8 import-graph — ah.gen.blocks never imports ah.eval (AST, whole package).

Same pattern as the WP2.7 joinery test: the losses/early-stopping/neighborhood
statistics are LOCAL implementations, and anything feeding a training decision
must stay outside the sealed judged modules (the WP2.7 teach-to-the-exam bar).
``tests/test_leakage_guard.py`` already proves no ``ah.gen`` module imports
``ah.eval.g2`` (the holdout mint); this test enforces the stricter stated rule
for the whole blocks package.
"""

from __future__ import annotations

import ast
from pathlib import Path

BLOCKS_DIR = Path(__file__).resolve().parents[1] / "src" / "ah" / "gen" / "blocks"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_blocks_package_never_imports_ah_eval():
    offenders: list[str] = []
    files = sorted(BLOCKS_DIR.glob("*.py"))
    assert files, "blocks package missing?"
    for path in files:
        for module in _imported_modules(path):
            if module == "ah.eval" or module.startswith("ah.eval."):
                offenders.append(f"{path.name}: {module}")
    assert not offenders, f"ah.gen.blocks must not import ah.eval: {offenders}"


def test_blocks_package_may_import_strategies_but_never_metrics():
    """ah.strategies (top-level, sealed) is the sanctioned door to the D4 set."""
    seen = set()
    for path in sorted(BLOCKS_DIR.glob("*.py")):
        seen |= _imported_modules(path)
    assert "ah.strategies" in seen
    assert not any(m.startswith("ah.eval.metrics") for m in seen)
