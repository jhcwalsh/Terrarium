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
from collections import Counter, defaultdict
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "ah" / "narration"

EXEMPT_MODULES = {"config.py", "params.py", "probe.py", "constants.py"}

#: Values allowed in ANY non-exempt module.
#:   0 / 1  — indexing, off-by-one, empty checks, identity, sign tests. Neither
#:            is a quantity: `x > 0` is "did it move", not "did it move enough".
#: Float 0.0/1.0 compare equal to the ints and need no separate entry.
UNIVERSAL = {0, 1, -1}

#: ``(module, value) -> (expected occurrences, why it is not a tunable)``.
#:
#: **The count is load-bearing.** Keying on ``(module, value)`` alone let one
#: justification silently cover every later use of the same number in the same
#: file — ``("build.py", 2)`` was written about a severity constant and would
#: have waved through any other 2 added to that module, and ``("events.py", 2)``
#: covered three unrelated sites. A count pins how many uses were inspected, so
#: adding a fourth 2 to ``events.py`` fails the test until someone says what it
#: is. Every justification below therefore enumerates its own sites.
JUSTIFIED: dict[tuple[str, float], tuple[int, str]] = {
    ("events.py", 2): (
        3,
        "three sites, all arity rather than quantity: `return 2` as the third "
        "severity band inside severity(); `if index < 2` guarding a consensus "
        "that reads month-1 and month-2; and `series[index - 2]` reading the "
        "second-previous month. The CUT-POINTS that decide what lands in band 2 "
        "are config",
    ),
    ("events.py", 3): (
        1,
        "one site: `return 3`, SEVERITY_MAX as the top band inside severity(). "
        "The function returns 0/1/2/3 by grammar; the cut-points are the tunable",
    ),
    ("build.py", 2): (
        2,
        "two sites, different classes and both inspected: _CREDIT_STRESS_SEVERITY "
        "(the severity at which E08 counts as credit stress for the Committee's "
        "financial-conditions sentence -- expressed in the severity grammar, so "
        "it moves with severity.cuts rather than independently of them); and "
        "`json.dumps(indent=2)`, which is file formatting",
    ),
    ("build.py", 3): (
        1,
        "one site: the severity-3 count in the manifest's summary block. The top "
        "of the grammar, reported, not a threshold applied to anything",
    ),
    ("cli.py", 2): (1, "one site: process exit code for an unresolved-parameter failure"),
    ("cli.py", 3): (1, "one site: process exit code for a missing-series failure"),
    ("diagnostics.py", 4): (
        1,
        "one site: _MI_VOCABULARY_BUDGET = DIAGNOSTIC_TOP_ROWS * 4, how many of "
        "the most frequent words the vocabulary panel scores for mutual "
        "information. A presentation budget on a measurement -- every word in it "
        "is reported and the ranking is by MI, so widening it adds rarer words "
        "with less data behind each estimate rather than changing a verdict. "
        "(An earlier version of this entry described a per-class histogram that "
        "does not use a literal 4 at all: the count now makes that kind of drift "
        "fail rather than pass.)",
    ),
    ("voices/fomc.py", 3): (
        1,
        "one site: SEVERITY_MAX in the deletion rule -- the Committee drops its "
        "commitment to target only on a top-band departure from its own rule. "
        "The band is the grammar; what lands in it is config",
    ),
    ("voices/__init__.py", 2): (
        1,
        "one site: indexing the previous-but-one month for a comparison",
    ),
}


def _literals() -> dict[str, Counter[float]]:
    """Every numeric literal in the package, per module, WITH occurrence counts."""
    found: dict[str, Counter[float]] = defaultdict(Counter)
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
                found[module][node.value] += 1
    return found


def test_no_unjustified_numeric_literal_in_the_package():
    unexplained: list[str] = []
    for module, counts in sorted(_literals().items()):
        for value in sorted(counts):
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


def test_every_justification_covers_exactly_the_sites_it_claims():
    """A justification must be stale-proof in both directions.

    Too few occurrences and the entry is documenting something that no longer
    exists; too many and a new, uninspected use of the number has crept in under
    a sentence written about a different one.
    """
    actual = _literals()
    problems: list[str] = []
    for (module, value), (expected, _) in sorted(JUSTIFIED.items()):
        seen = actual.get(module, Counter()).get(value, 0)
        if seen != expected:
            problems.append(f"{module}: {value!r} justified for {expected} site(s), found {seen}")
    assert not problems, (
        "JUSTIFIED entries that no longer match the code:\n  "
        + "\n  ".join(problems)
        + "\n\nA changed count means a use of this number was added or removed. "
        "Update the count AND the sentence, naming every site it now covers."
    )


def test_the_exempt_modules_are_the_ones_claimed():
    """The exemption list is small and named; it must not quietly grow."""
    assert {"config.py", "params.py", "probe.py", "constants.py"} == EXEMPT_MODULES
    for name in EXEMPT_MODULES:
        assert (PACKAGE / name).exists(), name
