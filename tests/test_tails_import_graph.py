"""WP2.1b Item 1 acceptance: tails.py/strategies.py have no portfolio/sleeve dependency.

D4 must be computable from an Ensemble alone (generated factors only), with no
dependency on Step-3 portfolio/sleeve machinery -- the sleeve taxonomy is not frozen
until Step 2R. This walks the AST of the two modules and asserts that no
import/from statement names a portfolio, sleeve, or institution module, matching the
approach of the existing import-graph proof in ``tests/test_leakage_guard.py``
(walk source, assert absence) but via ``ast`` rather than regex, per the WP2.1b
Task 2 brief.

The checker must see the *bound* name as well as the module, because
``from ah.core import institution`` names the forbidden module in ``node.names``, not
in ``node.module`` -- and ``ah/core/institution.py`` really exists and really holds
``SLEEVES``, so that is the natural way the dependency would creep back in.
``test_checker_catches_every_import_form`` pins all five forms by parsing them from
strings, so the checker is proven to protect rather than merely to pass.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = ("institution", "portfolio", "sleeve")
_TARGETS = (
    ROOT / "src" / "ah" / "eval" / "metrics" / "tails.py",
    ROOT / "src" / "ah" / "strategies.py",
)


def _imported_names(source: str, filename: str) -> list[str]:
    """Every module path an import statement could bind, dotted where meaningful.

    ``import a.b`` -> ``a.b``. ``from a.b import c`` -> ``a.b`` and ``a.b.c`` (``c``
    may itself be a submodule). ``from . import c`` has ``node.module is None``, so
    the alias name alone is emitted.
    """
    tree = ast.parse(source, filename=filename)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
                names.extend(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                names.extend(alias.name for alias in node.names)
    return names


def _offenders(source: str, filename: str) -> list[str]:
    return [
        name for name in _imported_names(source, filename) if any(bad in name for bad in _FORBIDDEN)
    ]


def test_tails_and_strategies_never_import_portfolio_or_sleeve_modules() -> None:
    offenders: list[str] = []
    for path in _TARGETS:
        assert path.exists(), f"expected target module missing: {path}"
        source = path.read_text(encoding="utf-8")
        for name in _offenders(source, str(path)):
            offenders.append(f"{path.relative_to(ROOT).as_posix()} imports '{name}'")
    assert not offenders, (
        f"D4 tail machinery must not depend on portfolio/sleeve modules: {offenders}"
    )


@pytest.mark.parametrize(
    "statement",
    [
        "from ah.core.institution import SLEEVES",
        "import ah.core.institution",
        "from ah.core import institution",
        "from ah.core import institution as inst",
        "from . import institution",
        "import ah.core.institution as inst",
        "from ah.eval import portfolio",
        "from ah.step3 import sleeve_map",
    ],
)
def test_checker_catches_every_import_form(statement: str) -> None:
    """The checker itself must catch each idiomatic way to name a forbidden module.

    Parsed from strings, deliberately: proving the checker protects must not require
    adding a real forbidden import to a real module.
    """
    assert _offenders(statement, "<synthetic>"), f"checker missed: {statement}"


@pytest.mark.parametrize(
    "statement",
    [
        "from ah.gen.base import Ensemble",
        "import numpy as np",
        "from ah.strategies import load_d4_strategies",
        "from . import base",
    ],
)
def test_checker_does_not_flag_permitted_imports(statement: str) -> None:
    assert not _offenders(statement, "<synthetic>")


def test_real_institution_module_exists() -> None:
    """The forbidden import above is real, not hypothetical -- so the guard is load-bearing."""
    institution = ROOT / "src" / "ah" / "core" / "institution.py"
    assert institution.exists()
    assert "SLEEVES" in institution.read_text(encoding="utf-8")
