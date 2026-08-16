"""The narration package is a DISPLAY surface, and the dependency runs one way.

DN-9 §1: "nothing on the wire moves a price. Narration is strictly downstream of
the numeric path." The repo's own invariant says the same thing from the other
side — the engine consumes a projection that structurally omits narrative.

``ah.narration`` may read anything. Nothing in ``ah.core``, ``ah.gen``,
``ah.eval`` or ``ah.port`` may import from it. An import-graph test is the only
way that stays true: a single convenience import in the wrong direction would
make the numeric path depend on the copy, and no unit test elsewhere would
notice.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "ah"
NUMERIC_PACKAGES = ("core", "gen", "eval", "port")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_numeric_package_imports_the_narration_layer():
    offenders: list[str] = []
    for package in NUMERIC_PACKAGES:
        for path in sorted((SRC / package).rglob("*.py")):
            for name in _imports(path):
                if name == "ah.narration" or name.startswith("ah.narration."):
                    offenders.append(f"{path.relative_to(SRC)} imports {name}")
    assert not offenders, (
        "the numeric path must not depend on the display layer:\n  " + "\n  ".join(offenders)
    )


def test_the_narration_layer_does_not_import_the_toy_engine_or_the_institution():
    """Narration renders a *generated* path. It never runs one.

    Reading ``ah.gen`` (the ensemble contract) and ``ah.core.loader`` (to compile
    a preset) is legitimate and expected. Importing ``ah.core.engine`` or
    ``ah.core.institution`` would mean the workbench had started simulating
    something, which is a different layer's job.
    """
    banned = {"ah.core.engine", "ah.core.institution"}
    offenders: list[str] = []
    for path in sorted((SRC / "narration").rglob("*.py")):
        for name in _imports(path):
            if name in banned:
                offenders.append(f"{path.relative_to(SRC)} imports {name}")
    assert not offenders, "\n  ".join(offenders)
