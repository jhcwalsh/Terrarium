"""ER-14 close-out (Task S1, er14-04b): AT-7, AT-14 and the stream-corruption
guards.

The single highest-risk line in the whole release (R-1 in the plan's risk
table, design 2.7.2): adding ``e_infra`` to ``run_path``'s up-front draw
block anywhere except the END silently re-rolls every subsequent stream
(``e_pe``/``e_pc``/``e_re``) and, through the common-factor construction,
the public assets too -- in every world, with no test naming the cause.
AT-14 is quoted verbatim from the ratified design in the docstring below.

DEVIATION (matching tests/test_er14_inflation.py's own recorded deviation,
Task M1 / er14-02 report): ``src/ah/presets/`` holds five generated-plane
presets that ``run_path`` structurally rejects; every preset loop here is
filtered to the toy-v0 subset the same way.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import numpy as np

from ah.core import engine
from ah.core.engine import run_path
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric
from ah.core.worldspec import Structural, WeightsOnTruth

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
NO_INFRA_BASELINE_NPZ = ROOT / "tests" / "fixtures" / "er14" / "no-infra-baseline.npz"
SEED = 12345


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_toy(path: Path) -> bool:
    return _load(path).get("engine_defaults", {}).get("generator_id") == "toy-v0"


TOY_PRESETS: list[Path] = [p for p in sorted(PRESETS.glob("*.json")) if _is_toy(p)]


def test_at14_the_draw_order_guard():
    """AT-14 (D-ER14-2, mandated verbatim from the ratified design's §6):

    | AT-14 | Sleeve addition, if A14 is granted: the draw-order guard. With
    ``infra`` added to ``ASSETS``, the five public assets and ``pe``/``pc``/
    ``re`` must remain bit-identical to the no-infra build on every preset |
    exact equality | §2.7.2: appending the new Student-t draw at the end of
    the block preserves every existing stream; inserting it anywhere else
    silently corrupts every world. This test is the only thing standing
    between a one-line mistake and an undetectable one |

    And the hard constraint it enforces, also verbatim, from design §2.7.2:
    "Hard constraint for the implementation plan: the new draw is appended
    at the end of the existing draw block, never inserted. Appended, every
    existing stream is bit-identical and AT-6b/AT-7 hold. This is the single
    highest-risk line in the whole sleeve addition and it is one line."
    """
    ref = np.load(NO_INFRA_BASELINE_NPZ)
    for path in TOY_PRESETS:
        paths = run_path(project_numeric(load_worldspec(_load(path))), SEED)
        for asset in ("equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re"):
            np.testing.assert_array_equal(
                paths.returns[asset], ref[f"{path.stem}/{asset}"], err_msg=f"{path.stem}/{asset}"
            )


def test_at7_the_draw_block_order_is_the_declared_one():
    """AT-7. The draw order in run_path is unchanged and e_infra is LAST.
    Read as source, because the ordering - not any value - is the
    invariant."""
    src = inspect.getsource(engine.run_path)
    block = src.split("crisis = _crisis_mask")[0]
    drawn = re.findall(r"^\s*(\w+) = (?:rng\.standard_normal|_t_draws)\(", block, re.M)
    assert drawn == [
        "z_rate",
        "z_spread",
        "z_infl",
        "z_m",
        "e_eq",
        "e_hy",
        "e_com",
        "e_b",
        "e_reit",
        "e_pe",
        "e_pc",
        "e_re",
        "e_infra",  # appended, never inserted (design 2.7.2)
    ]


def _redraw_streams(seed: int, nm: int) -> dict[str, np.ndarray]:
    """Re-draw run_path's up-front block, in the DECLARED order, from a
    fresh generator - the only honest way to inspect the streams without
    exporting them from production code."""
    rng = np.random.Generator(np.random.PCG64(seed))
    out = {name: rng.standard_normal(nm) for name in ("z_rate", "z_spread", "z_infl")}
    for name in (
        "z_m",
        "e_eq",
        "e_hy",
        "e_com",
        "e_b",
        "e_reit",
        "e_pe",
        "e_pc",
        "e_re",
        "e_infra",
    ):
        out[name] = engine._t_draws(rng, nm)
    return out


def test_e_infra_is_its_own_tape_not_a_copy_of_another_stream():
    """Distinct-tape guard (the seed-stride lesson: reusing the platform
    stride on a new axis collapsed 20 spines to 2). e_infra must correlate
    with no existing innovation stream, and must not equal one."""
    streams = _redraw_streams(seed=12345, nm=120)
    for name, other in streams.items():
        if name == "e_infra":
            continue
        assert not np.array_equal(streams["e_infra"], other), name
        assert abs(np.corrcoef(streams["e_infra"], other)[0, 1]) < 0.25, name


def test_the_contract_already_anticipated_this_class():
    """schemas/ is read-only vendored truth and does NOT block the sleeve
    (design 2.7.0): no schema enumerates the asset or sleeve set, and both
    infrastructure fields plus the smoothing weight are already declared.

    DEVIATION from the plan's literal file-line pointer: the smoothing
    weight field lives on ``WeightsOnTruth.infrastructure``
    (``structural.smoothing.weights_on_truth.infrastructure``), not directly
    on ``Smoothing`` -- ``Smoothing`` only carries ``weights_on_truth`` as a
    submodel. Same claim (the field is already declared), correct class."""
    schema = json.loads((ROOT / "schemas" / "worldspec-v1.3.schema.json").read_text())
    infra = schema["properties"]["structural"]["properties"]["infrastructure"]["properties"]
    assert set(infra) == {"discount_rate_shift_bps", "inflation_linkage"}
    assert "infrastructure" in WeightsOnTruth.model_fields
    assert "infrastructure" in Structural.model_fields
