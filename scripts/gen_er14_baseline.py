"""Capture engine return baselines for the ER-14 release (AT-6b, AT-14).

Two references are needed and neither can be reconstructed after the fact:
  * the toy-v0.6 PUBLIC-asset streams, proving the release moves nothing it
    should not (AT-6b);
  * the post-mechanism, PRE-SLEEVE streams for all eight assets, proving the
    appended e_infra draw shifts nothing (AT-14, design 2.7.2).

Presets are stored as raw float64 arrays (exact comparison); the 51 compiler
fixtures are stored as sha256_of_arrays digests (the repo's own 12-decimal
platform-determinism convention) to keep the fixture small.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ah.core.digest import sha256_of_arrays
from ah.core.engine import run_path
from ah.core.loader import load_worldspec
from ah.core.numericworld import project_numeric

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"
FIXTURES = ROOT / "fixtures" / "compiler"
SEED = 12345


def _paths(doc: dict) -> object:
    return run_path(project_numeric(load_worldspec(doc)), SEED)


def _toy_preset_paths() -> list[Path]:
    """The toy-v0 subset of ``PRESETS`` (world-fence 511-515, per the plan's
    Global Constraints table). ``src/ah/presets/`` also holds five
    generated-plane presets (603, 701, 703, 801, 802 -- hier-flow-v1 /
    bootstrap-v1 / bootstrap-stratified) that ``ah.core.engine.run_path``
    structurally rejects (UnsupportedGeneratorError); this release's engine
    mechanism work is toy-plane only, so those are out of scope here and are
    filtered rather than left to crash the loop."""
    out = []
    for path in sorted(PRESETS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("engine_defaults", {}).get("generator_id") == "toy-v0":
            out.append(path)
    return out


def build(out_stem: str, assets: tuple[str, ...]) -> None:
    arrays: dict[str, np.ndarray] = {}
    for path in _toy_preset_paths():
        doc = json.loads(path.read_text(encoding="utf-8"))
        paths = _paths(doc)
        for asset in assets:
            arrays[f"{path.stem}/{asset}"] = np.asarray(paths.returns[asset], dtype=np.float64)
    np.savez_compressed(ROOT / f"{out_stem}.npz", **arrays)

    digests: dict[str, str] = {}
    skipped: list[str] = []
    for path in sorted(FIXTURES.glob("*.json")):
        if path.name == "_manifest.json":
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        try:
            paths = _paths(doc)
        except Exception as exc:  # a fixture the validator/engine rejects by design
            skipped.append(f"{path.stem}: {type(exc).__name__}")
            continue
        for asset in assets:
            digests[f"{path.stem}/{asset}"] = sha256_of_arrays([paths.returns[asset]])
    (ROOT / f"{out_stem}.json").write_text(
        json.dumps({"digests": digests, "skipped": skipped, "seed": SEED}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"{out_stem}: {len(arrays)} arrays, {len(digests)} digests, {len(skipped)} skipped")


def build_anchor_baseline() -> None:
    """The AT-6a reference.

    DEVIATION (Task M3, extended in Task M5 -- see tests/test_er14_inflation.py's
    test_at6a_the_inflation_channel_is_inert_at_the_anchor docstring for the
    full account): setting only the DECLARED inflation.average_pct to the
    anchor does not make the REALIZED trailing-mean inflation_excess exactly
    zero -- _inflation_path is a stochastic mean-REVERTING process, so the
    realized path wanders around the anchor. inflation_excess is forced to an
    exact zero array here (mirroring the test's monkeypatch) so the new
    lambda*x / D*gamma*d_x terms vanish algebraically rather than
    approximately -- the reference is then "every OTHER (non-inflation) term
    in the current formula, on the current preset content", which is exactly
    what the test's own monkeypatched run reduces to. This also makes the
    fixture immune to preset-content edits (Task M5 zeroed
    entry_multiple_drift_annual_pct on the two live presets) -- it is a
    formula-structure guard, not a frozen numeric snapshot."""
    import ah.core.engine as _engine

    original = _engine.inflation_excess
    _engine.inflation_excess = lambda infl, **_: np.zeros_like(infl, dtype=np.float64)
    try:
        arrays: dict[str, np.ndarray] = {}
        for path in _toy_preset_paths():
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["factor_conditions"]["inflation"]["average_pct"] = 2.0
            doc["factor_conditions"]["crisis_windows"] = []
            paths = _paths(doc)
            for asset in ("pe", "pc", "re"):
                arrays[f"{path.stem}/{asset}"] = np.asarray(paths.returns[asset], dtype=np.float64)
    finally:
        _engine.inflation_excess = original
    np.savez_compressed(ROOT / "tests/fixtures/er14/anchor-baseline-toy-v0.6.npz", **arrays)
    print("anchor-baseline-toy-v0.6: written")


if __name__ == "__main__":
    build(
        "tests/fixtures/er14/public-baseline-toy-v0.6",
        ("equity", "bonds", "hy", "commodities", "reits"),
    )
    build_anchor_baseline()
    # ER-14 close-out (Task S1, er14-04b): the AT-14 reference -- the tree AS
    # IT STANDS RIGHT NOW (mechanisms complete, no infra sleeve wired in yet).
    # Captured before engine.py gains ASSETS+"infra" and the appended e_infra
    # draw, so AT-14 has something pre-sleeve to compare against.
    build(
        "tests/fixtures/er14/no-infra-baseline",
        ("equity", "bonds", "hy", "commodities", "reits", "pe", "pc", "re"),
    )
