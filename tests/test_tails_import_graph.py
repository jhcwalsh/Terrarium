"""WP2.1b Item 1 acceptance: tails.py/strategies.py have no portfolio/sleeve dependency.

D4 must be computable from an Ensemble alone (generated factors only), with no
dependency on Step-3 portfolio/sleeve machinery -- the sleeve taxonomy is not frozen
until Step 2R. This walks the AST of the two modules and asserts that no
import/from statement names a portfolio, sleeve, or institution module, matching the
approach of the existing import-graph proof in ``tests/test_leakage_guard.py``
(walk source, assert absence) but via ``ast`` rather than regex, per the WP2.1b
Task 2 brief.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = ("institution", "portfolio", "sleeve")
_TARGETS = (
    ROOT / "src" / "ah" / "eval" / "metrics" / "tails.py",
    ROOT / "src" / "ah" / "strategies.py",
)


def _imported_module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_tails_and_strategies_never_import_portfolio_or_sleeve_modules() -> None:
    offenders: list[str] = []
    for path in _TARGETS:
        assert path.exists(), f"expected target module missing: {path}"
        for module_name in _imported_module_names(path):
            if any(bad in module_name for bad in _FORBIDDEN):
                offenders.append(f"{path.relative_to(ROOT).as_posix()} imports '{module_name}'")
    assert not offenders, (
        f"D4 tail machinery must not depend on portfolio/sleeve modules: {offenders}"
    )
