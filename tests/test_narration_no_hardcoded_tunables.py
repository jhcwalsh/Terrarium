"""Acceptance 6: no tunable value is hardcoded anywhere in the package.

The task's rule is that every tunable lives in ``voices.yaml`` or becomes an
``UNRESOLVED.md`` entry. A grep is the only way to check that mechanically, so
this test walks the AST of every module in ``ah.narration`` and collects every
numeric literal.

**Four modules are exempt entirely**, for reasons that are structural rather
than convenient:

* ``config.py`` — the config loader. Values arrive here by definition.
* ``params.py`` — the open-parameter registry. Its literals *are* the candidate
  values, and every one of them is in ``UNRESOLVED.md`` by construction.
* ``probe.py`` — generates the unratified probe config from that registry.
* ``constants.py`` — calendar arithmetic and unit conversions, each with a
  docstring saying why it is not a tunable.

Everywhere else, every surviving literal is listed below **with its
justification**. Adding a literal to a non-exempt module fails this test until
someone writes down why it is not a decision — which is the point.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "ah" / "narration"

EXEMPT_MODULES = {"config.py", "params.py", "probe.py", "constants.py"}

#: Values allowed in ANY non-exempt module.
#:   0 / 1  — indexing, off-by-one, empty checks, identity, sign tests. Neither
#:            is a quantity: `x > 0` is "did it move", not "did it move enough".
#: Float 0.0/1.0 compare equal to the ints and need no separate entry.
UNIVERSAL = {0, 1, -1}

#: (module, value) -> why this specific literal is not a tunable.
JUSTIFIED: dict[tuple[str, float], str] = {
    ("events.py", 2): (
        "unpacking the two-element (mean, sd) window statistic, and indexing the "
        "second-previous month in the persistence-weighted consensus; both are "
        "the arity of an expression, not a quantity"
    ),
    ("events.py", 3): (
        "SEVERITY_MAX as the top band inside severity(): the function returns "
        "0/1/2/3 by grammar, and the CUT-POINTS that map onto them are the "
        "tunable and come from config"
    ),
    ("build.py", 2): (
        "_CREDIT_STRESS_SEVERITY: the severity at which E08 counts as credit "
        "stress for the Committee's financial-conditions sentence. Expressed in "
        "the severity grammar rather than in basis points, so it moves with "
        "severity.cuts rather than independently of them"
    ),
    ("build.py", 3): (
        "the severity-3 count in the manifest's summary block - the top of the "
        "grammar, reported, not a threshold applied to anything"
    ),
    ("cli.py", 2): "process exit code for an unresolved-parameter failure",
    ("cli.py", 3): "process exit code for a missing-series failure",
    ("diagnostics.py", 4): (
        "the four severity levels (0..3) enumerated as columns of the per-class "
        "histogram; the grammar, one row wider"
    ),
    ("voices/fomc.py", 3): (
        "SEVERITY_MAX in the deletion rule: the Committee drops its commitment "
        "to target only on a top-band departure from its own rule. The band is "
        "the grammar; what lands in it is config"
    ),
    ("voices/__init__.py", 2): "indexing the previous-but-one month for a comparison",
}


def _literals() -> dict[str, set[float]]:
    found: dict[str, set[float]] = defaultdict(set)
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in EXEMPT_MODULES:
            continue
        module = str(path.relative_to(PACKAGE)).replace("\\", "/")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool)
            ):
                found[module].add(node.value)
    return found


def test_no_unjustified_numeric_literal_in_the_package():
    unexplained: list[str] = []
    for module, values in sorted(_literals().items()):
        for value in sorted(values):
            if value in UNIVERSAL:
                continue
            if (module, value) in JUSTIFIED:
                continue
            unexplained.append(f"{module}: {value!r}")
    assert not unexplained, (
        "numeric literals with no justification:\n  "
        + "\n  ".join(unexplained)
        + "\n\nEither move the value into voices.yaml (and add it to "
        "ah.narration.params, which regenerates UNRESOLVED.md), or add it to "
        "JUSTIFIED above with a sentence saying why it is not a decision."
    )


def test_every_justification_is_still_load_bearing():
    """A justification for a literal that no longer exists is stale documentation."""
    actual = _literals()
    stale = [
        f"{module}: {value!r}"
        for (module, value) in JUSTIFIED
        if value not in actual.get(module, set())
    ]
    assert not stale, "JUSTIFIED entries for literals that no longer exist:\n  " + "\n  ".join(
        stale
    )


def test_the_exempt_modules_are_the_ones_claimed():
    """The exemption list is small and named; it must not quietly grow."""
    assert {"config.py", "params.py", "probe.py", "constants.py"} == EXEMPT_MODULES
    for name in EXEMPT_MODULES:
        assert (PACKAGE / name).exists(), name
