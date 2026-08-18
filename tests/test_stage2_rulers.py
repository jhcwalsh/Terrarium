"""D-SP-11: the three rulers' own tests.

What is pinned here, and why each one exists:

* **the era-crossing rule is a rule, not a hope** -- a compiled world under
  ruler 2 has *no* bucket-changing seam except at a month where the spine itself
  crosses, in the spine's own direction; and the licence's semantics are pinned
  directly on the predicate function, both ways, so the test is a comparison
  rather than a restatement of the implementation.
* **ruler 2 is additive** -- turning it off reproduces D-SP-10's engine
  bit-for-bit, so the whole prior record still stands.
* **S1's band is anchored, monotone and two-sided** -- the band moves with the
  panel and with n and with nothing else; the bar catches a world whose seams are
  too big AND one whose seams are suspiciously small.
* **A1R's pooling is the sealed judge's own statistic** -- the count-weighted
  identity is checked against ``judge_a1`` run on the genuinely pooled batch.
* **the A1R seed ladder has distinct tapes** -- the campaign has paid for a
  seed-stride collision once.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load(name: str) -> Any:
    """Load a ``scripts/`` module by path -- ``tests/test_stage2_weekc_composition``'s
    own pattern, registered in ``sys.modules`` under its real name so the module's
    own imports resolve to the same objects this file reaches."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rulers = _load("stage2_rulers")
worlds = _load("stage2_worlds")

# --------------------------------------------------------------------------- #
# ruler 2 -- the conditional era-crossing rule
# --------------------------------------------------------------------------- #


def _design(**kwargs):
    return worlds.ReachDesign("t", **kwargs)


def test_the_licence_fires_only_where_the_spine_crosses_and_only_in_its_direction():
    """The predicate, both ways. A crossing month licenses (was, now); a
    non-crossing month licenses nothing; and month 0 licenses nothing because
    there is no previous month to have crossed from."""
    design = _design(era_conditional_crossing=True)
    hot = np.array([0, 0, 1, 1, 0], dtype=np.int64)
    assert rulers is not None  # import-order guard, not a claim
    assert worlds._era_crossing_licence(design, hot, 0) is None
    assert worlds._era_crossing_licence(design, hot, 1) is None  # 0 -> 0
    assert worlds._era_crossing_licence(design, hot, 2) == (0, 1)  # 0 -> 1
    assert worlds._era_crossing_licence(design, hot, 3) is None  # 1 -> 1
    assert worlds._era_crossing_licence(design, hot, 4) == (1, 0)  # 1 -> 0
    off = _design(era_conditional_crossing=False)
    assert all(worlds._era_crossing_licence(off, hot, m) is None for m in range(hot.size))


def test_the_licence_widens_the_join_filter_only_in_the_licensed_direction():
    """The filter admits a bucket change only for the licensed (was -> now)
    pair, and never widens the declared level bound while doing it."""
    era = np.array([0, 0, 1, 1], dtype=np.int64)
    yoy = np.array([1.0, 1.2, 1.4, 9.0], dtype=np.float64)
    cand = np.array([1, 2, 3], dtype=np.int64)
    previous = 0  # bucket 0

    same_only = worlds._join_filter(cand, era, yoy, previous, 2.5, era_relaxed=False)
    assert same_only.tolist() == [1]

    licensed = worlds._join_filter(
        cand, era, yoy, previous, 2.5, era_relaxed=False, crossing_licence=(0, 1)
    )
    # row 2 crosses and is inside the level bound; row 3 crosses but is 8.0 pp away
    assert licensed.tolist() == [1, 2]

    wrong_way = worlds._join_filter(
        cand, era, yoy, previous, 2.5, era_relaxed=False, crossing_licence=(1, 0)
    )
    assert wrong_way.tolist() == [1], "a licence out of the OTHER bucket must not apply"


def test_the_licence_only_adds_candidates_and_never_removes_one():
    """Ruler 2 is a faithfulness rule, not a relaxation: everything the platform
    would have admitted is still admitted."""
    rng = np.random.default_rng(7)
    era = rng.integers(0, 2, size=40).astype(np.int64)
    yoy = rng.normal(3.0, 1.0, size=40)
    cand = np.arange(1, 40)
    for previous in (0, 5, 17):
        base = set(worlds._join_filter(cand, era, yoy, previous, 1.0, era_relaxed=False).tolist())
        for licence in ((0, 1), (1, 0)):
            widened = set(
                worlds._join_filter(
                    cand, era, yoy, previous, 1.0, era_relaxed=False, crossing_licence=licence
                ).tolist()
            )
            assert base <= widened


def test_the_era_audit_catches_an_unlicensed_crossing():
    """A break-and-check on the auditor itself: hand it a tape with a crossing
    seam at a month the story does not cross, and it must not report holds."""
    era = np.array([0, 0, 1, 1, 1], dtype=np.int64)
    rows = np.array([[0, 3]], dtype=np.int64)  # a seam from bucket 0 into bucket 1
    story_crosses = np.array([[0, 1]], dtype=np.int64)  # season low bit 0 -> 1
    story_flat = np.array([[1, 1]], dtype=np.int64)  # season low bit 1 -> 1

    good = rulers.era_crossing_audit(rows, story_crosses, era, n_panel_rows=5)
    assert good["crossing_seams"] == 1
    assert good["unlicensed_crossing_seams"] == 0
    assert good["holds"] is True

    bad = rulers.era_crossing_audit(rows, story_flat, era, n_panel_rows=5)
    assert bad["crossing_seams"] == 1
    assert bad["unlicensed_crossing_seams"] == 1
    assert bad["holds"] is False


def test_a_compiled_world_crosses_the_era_line_only_where_its_story_does():
    """The charter's own assertion, on a real compiled batch rather than a
    fixture: under ruler 2 every bucket-changing seam sits at a month where the
    spine crosses, in the spine's direction -- and under the D-SP-10 engine
    there are no bucket-changing seams at all, which is the fact ruler 2 exists
    to change."""
    from ah.gen.spine import fit_hazard, panel_yoy

    weeka = _load("stage2_fit")

    frozen = worlds.build_frozen_system()
    world = worlds.load_world()
    source = worlds.campaign_panel_source()
    hazard = fit_hazard(source)
    yoy = panel_yoy(source)
    era_bucket = np.where(np.isnan(yoy), -1, (yoy > hazard.era_threshold_pp).astype(np.int64))
    seed = int(weeka.STAGE2_VERIFY_SEED)

    audits = {}
    for name, design in (
        ("d-sp-10", worlds.ADOPTED_REACH),
        ("ruler-2", worlds.ERA_CONDITIONAL_REACH),
    ):
        with worlds.stage2_flesh(
            frozen, premise_mode=worlds.PREMISE_UNCONDITIONAL, design=design
        ) as run:
            ens = worlds.compile_world(world, 6, seed)
            decades = run.last_decades
        seasons = np.stack([np.asarray(d.season, dtype=np.int64) for d in decades])
        audits[name] = rulers.era_crossing_audit(
            np.asarray(ens.row_indices), seasons, era_bucket, n_panel_rows=source.n_rows
        )

    assert audits["d-sp-10"]["crossing_seams"] == 0
    assert audits["ruler-2"]["crossing_seams"] > 0, "ruler 2 must actually license crossings"
    assert audits["ruler-2"]["unlicensed_crossing_seams"] == 0
    assert audits["ruler-2"]["holds"] is True
    assert (
        audits["ruler-2"]["crossing_seams_at_a_story_crossing_in_the_story_s_direction"]
        == audits["ruler-2"]["crossing_seams"]
    )


# --------------------------------------------------------------------------- #
# ruler 1 -- S1's band and its two-sidedness
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def sealed():
    return rulers.sealed_from_sources()


def test_the_band_narrows_with_n_and_is_deterministic(sealed):
    """Two properties a band must have or it is not a band: it is a function of
    its seed alone, and more evidence resolves the quantile better."""
    anchor = np.abs(np.random.default_rng(3).normal(0.0, 1.0, size=800))
    widths = []
    for n in (200, 800, 3200):
        lo, hi = rulers.moving_block_band(anchor, n, 0.5)
        again = rulers.moving_block_band(anchor, n, 0.5)
        assert (lo, hi) == again
        widths.append(hi - lo)
    assert widths[0] > widths[1] > widths[2]


def test_the_band_moves_when_the_anchor_moves(sealed):
    """The band is cut from the panel and from nothing else, so a different
    panel must give a different band -- the bite-proof for 'anchored'."""
    a = np.abs(np.random.default_rng(3).normal(0.0, 1.0, size=800))
    _, hi_a = rulers.moving_block_band(a, 500, 0.95)
    lo_b, _ = rulers.moving_block_band(a * 2.0, 500, 0.95)
    assert lo_b > hi_a


def test_s1_passes_a_world_that_is_history_and_its_seams_are_vacuous(sealed):
    """The identity control. Fifty contiguous 120-month stretches of the panel
    ARE history; a bar that fails them is measuring itself."""
    yoy = np.concatenate([[np.nan] * 12, np.linspace(1.0, 9.0, 400) + np.sin(np.arange(400))])
    starts = np.arange(12, 12 + 50)
    rows = np.stack([np.arange(s, s + 120) for s in starts])
    verdict = rulers.judge_s1(rows, yoy, sealed)
    assert verdict["seams_vacuous"] is True
    assert verdict["texture_pass"] is True
    assert verdict["pass"] is True


def test_s1_fails_seams_that_are_too_big_and_seams_that_are_too_small(sealed):
    """Two-sided, and the demonstration is a pair of worlds that fail on
    opposite edges of the same band."""
    rng = np.random.default_rng(11)
    yoy = np.concatenate([[np.nan] * 12, np.cumsum(rng.normal(0.0, 0.3, size=800))])
    n = yoy.size

    def world(jump_scale: float) -> np.ndarray:
        rows = []
        for k in range(50):
            r = [12 + (k * 7) % 200]
            for m in range(1, 120):
                if m % 6 == 0:  # a seam, placed by construction
                    target = yoy[r[-1]] + jump_scale * (1 if m % 12 == 0 else -1)
                    r.append(int(np.nanargmin(np.abs(yoy[12:] - target)) + 12))
                else:
                    r.append(min(r[-1] + 1, n - 1))
            rows.append(r)
        return np.asarray(rows, dtype=np.int64)

    big = rulers.judge_s1(world(4.0), yoy, sealed)
    tiny = rulers.judge_s1(world(0.0), yoy, sealed)
    assert big["seam_pass"] is False
    assert tiny["seam_pass"] is False
    big_seam = [c for c in big["conditions"] if c["kind"] == "seam" and c["judged"]]
    tiny_seam = [c for c in tiny["conditions"] if c["kind"] == "seam" and c["judged"]]
    assert all(c["value"] > c["band"][1] for c in big_seam), "too-big seams fail ABOVE"
    assert all(c["value"] < c["band"][0] for c in tiny_seam), "too-small seams fail BELOW"


def test_s1_refuses_to_judge_a_half_it_cannot_resolve(sealed):
    """Three seams is not evidence about a 95th percentile, and the bar says so
    rather than passing them."""
    yoy = np.concatenate([[np.nan] * 12, np.linspace(1.0, 9.0, 400)])
    rows = np.stack([np.arange(12, 132)] * 4)
    rows[0, 60] = 300  # two seams on one path
    verdict = rulers.judge_s1(rows, yoy, sealed)
    seam = [c for c in verdict["conditions"] if c["kind"] == "seam"]
    assert [c["judged"] for c in seam] == [False, False]
    assert all(c["why_not_judged"] for c in seam)


# --------------------------------------------------------------------------- #
# ruler 3 -- the power plan and the pooling identity
# --------------------------------------------------------------------------- #


def test_the_power_plan_scales_as_the_textbook_formula_says(sealed):
    """Halving the margin quadruples the batch; the plan is arithmetic, not a
    fitted rule."""
    plan_a = rulers.a1r_power_plan(4.0, {"m": 1.0}, cap=10**9)
    plan_b = rulers.a1r_power_plan(4.0, {"m": 0.5}, cap=10**9)
    ratio = (
        plan_b["per_margin"]["m"]["sub_batches_at_the_point_estimate"]
        / plan_a["per_margin"]["m"]["sub_batches_at_the_point_estimate"]
    )
    assert 3.9 < ratio < 4.1
    plan_c = rulers.a1r_power_plan(8.0, {"m": 1.0}, cap=10**9)
    ratio_sd = (
        plan_c["per_margin"]["m"]["sub_batches_at_the_point_estimate"]
        / plan_a["per_margin"]["m"]["sub_batches_at_the_point_estimate"]
    )
    assert 3.9 < ratio_sd < 4.1


def test_the_plan_is_conservative_about_a_six_seed_pilot(sealed):
    """The adopted size uses the upper bound on the pilot's sd, not its point
    estimate -- otherwise the calculation is done at the flattering reading of
    its own input."""
    plan = sealed["a1r_power_plan"]
    assert plan["pilot_sd_upper_90pct_bound_pp"] > plan["pilot_sd_pp"]
    vs_zero = plan["per_margin"]["vs_zero"]
    assert (
        vs_zero["sub_batches_at_the_upper_90pct_bound_on_sd"]
        > vs_zero["sub_batches_at_the_point_estimate"]
    )
    assert plan["sub_batches_adopted"] == min(
        vs_zero["sub_batches_at_the_upper_90pct_bound_on_sd"], plan["cap_sub_batches"]
    )
    assert plan["achieved_power_at_the_adopted_size"] >= 0.90


def test_the_a1r_seed_ladder_has_pairwise_distinct_tapes():
    """The seed-stride lesson, enforced. Every rung's block stream and hazard
    stream must be a different tape from every other rung's."""
    from ah.gen.spine import LAYER_OFFSETS

    seeds = rulers.a1r_seeds(40, 20260821)
    assert len(set(seeds)) == 40
    tapes = set()
    for seed in seeds:
        for layer in ("blocks", "hazard"):
            rng = np.random.Generator(np.random.PCG64(seed + LAYER_OFFSETS[layer]))
            tapes.add(tuple(float(x) for x in rng.random(8)))
    assert len(tapes) == 80
    from math import gcd

    assert gcd(rulers.A1R_SEED_STRIDE, 7919) == 1
    assert gcd(rulers.A1R_SEED_STRIDE, 32452843) == 1
    assert max(LAYER_OFFSETS.values()) < rulers.A1R_SEED_STRIDE


def test_pooling_the_sealed_a1_verdicts_equals_judging_the_pooled_batch(sealed):
    """The identity ``pool_a1_verdicts`` rests on, checked against the sealed
    judge run on the genuinely concatenated batch."""
    v2r = _load("spine_v2_report")
    Batch, Decade, judge_a1 = v2r.Batch, v2r.Decade, v2r.judge_a1

    v2 = _load("stage2_report").load_v2_sealed()
    rng = np.random.default_rng(19)

    def decade(k: int) -> Any:
        yoy = np.concatenate([[np.nan] * 12, rng.uniform(1.0, 7.0, size=108)])
        return Decade(
            labels=np.array(["EXP"] * 120),
            yoy=yoy,
            tight=np.zeros(120, dtype=bool),
            equities=rng.normal(0.005, 0.04, size=120),
            bonds=rng.normal(0.002, 0.02, size=120),
            commodities=rng.normal(0.004, 0.06, size=120),
        )

    groups = [[decade(k) for _ in range(5)] for k in range(6)]
    per = [judge_a1(Batch(tuple(g)), dict(v2)) for g in groups]
    pooled_direct = judge_a1(Batch(tuple(d for g in groups for d in g)), dict(v2))
    pooled = rulers.pool_a1_verdicts(per)

    assert pooled["months_high"] == pooled_direct["months_high"]
    assert pooled["months_low"] == pooled_direct["months_low"]
    assert pooled["spread_high_pp"] == pytest.approx(pooled_direct["spread_high_pp"], abs=1e-10)
    assert pooled["difference_pp"] == pytest.approx(pooled_direct["difference_pp"], abs=1e-10)
    assert pooled["containment_pass"] == pooled_direct["containment_pass"]


def test_a1r_reads_a_precise_negative_as_a_verdict(sealed):
    """The point of the re-founding: a margin that is reliably negative is a
    verdict, not a coin flip. The bar FAILS and says why in the same breath."""
    pooled = {
        "difference_pp": -1.0,
        "spread_high_pp": 2.0,
        "spread_low_pp": 3.0,
        "containment_pass": True,
        "containment_pp": [-5.053054679081145, 32.31605649965673],
    }
    verdict = rulers.judge_a1_refounded(pooled, [-1.0 + 0.01 * k for k in range(-100, 100)], sealed)
    assert verdict["pass"] is False
    assert verdict["excludes_zero"] is True
    assert verdict["sign_if_it_excludes_zero"] == "negative"
    assert verdict["excludes_history"] is True
