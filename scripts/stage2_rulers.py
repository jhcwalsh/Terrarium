"""D-SP-11's SEALED judging code -- the new seam/texture bar and the re-founded A1.

Charter: ``governance/decision-register.md`` **D-SP-11** (owner ruling
2026-08-18, "all three"). This module is to the D-SP-11 seal what
``scripts/stage2_report.py`` is to the stage-2 seal: **the code that judges**, so
it is hashed together with the thresholds it reads, before any measurement is
taken. Nothing here writes a file, samples an ensemble or draws a random number
at import time.

**Two new constructs, and what each is for.**

* ``S1`` -- the **seam/texture bar**. R2 measures two things at once: how *often*
  the compiler splices, and how *big* a splice is. D-SP-10's record shows the
  cost of that -- reach is bought with joins, the seam share went 7.5% -> 19.5%,
  and R2's p95 half flipped to FAIL while the contiguous months it is taken over
  got *calmer*. ``S1`` separates the two questions. It judges **shape, not
  frequency**: how many seams a world has is R2's business and this bar cannot
  see it.
* ``A1R`` -- ``A1``, **re-founded on a batch size computed from the engine's own
  measured margin**. The sealed ``A1`` is read on one batch of fifty decades, and
  the six-seed disclosure says that reading swings by +/-5 pp between adjacent
  seeds against a bar that asks only for a sign. ``A1R`` keeps ``A1``'s
  statistic and its containment band exactly, and replaces "is the sign
  positive on this draw" with "is the sign positive, at a batch size powered to
  tell the engine's own margin from zero".

**Neither construct re-grades anything.** ``A1``'s sealed verdict is a fact of
the record and is reported beside ``A1R`` forever; ``R2``'s two halves keep
being read exactly as they were. These are new rulers, and rulers change only
forward.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

from stage2_anchors import PRIMARY_BLOCK_MONTHS  # noqa: E402

_REPO_ROOT = _SCRIPTS_DIR.parent
_SPECS = _REPO_ROOT / "docs" / "superpowers" / "specs"
SEALED_PATH = _SPECS / "stage2-prereg-2.json"
V2_ANCHORS_PATH = _SPECS / "spine-v2-anchors.json"
REACH_RESULTS_PATH = _SPECS / "stage2-reach-results.json"


# =========================================================================== #
# RULER 1 -- the seam/texture bar
# =========================================================================== #
#
# THE QUESTION, in one line: **can you find the seams?**
#
# A compiled world is real months of history spliced end to end. Two things can
# be wrong with the splicing and they are different things:
#
#   (i)  the months INSIDE a block can stop looking like history's own months --
#        the "texture" failure. History's own month-to-month distribution is the
#        anchor for this and it stands: it is the same object R2's
#        ``panel_p95_adjacent_yoy_pp`` was cut from, and this bar does not move
#        it.
#   (ii) the joins BETWEEN blocks can be visible -- the "seam" failure. This is
#        the half R2 cannot isolate, because a world with twice as many seams
#        of exactly the same size moves R2's pooled p95 without any seam having
#        got worse.
#
# THE SEAM CRITERION IS ANCHORED, NOT INVENTED. The principle: *a seam should be
# statistically indistinguishable from an ordinary historical month-transition.*
# Made concrete: the seam-pair jump distribution must sit inside the distribution
# of history's own adjacent-month jumps, at declared quantiles, allowing for the
# sampling uncertainty of a sample that size. Nothing about the generated world
# enters the derivation of the band -- the band is a function of the PANEL and of
# a sample size, and that is the whole content of the word "anchored" here.
#
# WHY THIS IS THE RIGHT OPERATIONALISATION OF "CAN YOU FIND THEM". A detector
# that flags a month-transition as a seam whenever its inflation jump exceeds a
# threshold has an advantage over guessing of exactly |F_seam(t) - F_history(t)|
# at its threshold t. If the two distributions agree at the quantiles a detector
# would use, no such detector works. So the bar counts the seams a detector could
# find, and NOT the seams the compiler cut.

#: The declared quantiles the two distributions are compared at.
#:
#: **The median** is the bar's "ordinary month" anchor -- a detector tuned to
#: "this transition is bigger than a typical month" lives here. **The 95th
#: percentile** is its tail anchor, and it is *not a new number*: it is the
#: quantile R2's own sealed bound is cut at, so the two bars are read on the
#: same summary of the same series and a reader can hold them side by side.
#:
#: Deliberately NOT included: the 99th percentile (the panel has 800 adjacent
#: pairs, so a p99 rests on eight order statistics and its band is wider than
#: any effect worth barring), and the mean (|dYoY| is strongly right-skewed, so
#: its mean is a re-statement of the tail and would double-count the p95).
SEAM_QUANTILES: tuple[float, ...] = (0.50, 0.95)

#: The band's confidence level. 95%, the campaign's own -- P2's sealed band is a
#: 95% block-bootstrap interval at 2000 draws and this reuses both numbers
#: rather than introducing a third convention.
BAND_LEVEL = 0.95
#: Bootstrap draws. The campaign's own count (anchors section M4).
BAND_DRAWS = 2000
#: Moving-block length, in months. ``stage2_anchors.PRIMARY_BLOCK_MONTHS`` -- the
#: campaign's primary block length, imported rather than retyped.
#:
#: **Why blocks at all.** Trailing 12-month YoY is a 12-month moving construct,
#: so |dYoY| is strongly serially dependent; an iid bootstrap of it would report
#: a band far narrower than history's own resolution and the bar would reject
#: worlds that are indistinguishable from history. A moving-block bootstrap at
#: two years is the conservative choice, and conservative is the right direction
#: for a band that decides a FAIL.
BAND_BLOCK_MONTHS = PRIMARY_BLOCK_MONTHS
#: The bootstrap's seed. The campaign's own verification seed; the band is a
#: deterministic function of (panel, n, q) given it.
BAND_SEED = 20260821

#: A condition is JUDGED only when at least this many observations sit beyond the
#: quantile being judged -- the standard "expected count >= 5" rule. At the p95
#: that is 100 transitions; at the median, 10. Below it the sample quantile is a
#: function of one or two order statistics, the band swallows everything, and a
#: PASS would mean "too few seams to tell" rather than "the seams look like
#: history". Such a condition is reported and flagged, never counted.
MIN_TAIL_COUNT = 5

#: Judged on DISTINCT ordered panel-row pairs, and this is a house rule with a
#: reason. A fifty-decade batch has 5,950 adjacent pairs drawn from a panel with
#: 800 distinct transitions and about 640 distinct rows visited, so the same
#: historical transition is re-used dozens of times. Counting each re-use as
#: independent evidence would cut the band far below the panel's own resolution
#: and turn the bar into a test of how often the compiler repeats itself --
#: which is the frequency question R2 already answers. De-duplicating makes the
#: unit of evidence the compiler's VOCABULARY of transitions, which is what "does
#: a seam look like a historical transition" asks. The raw (non-deduplicated)
#: reading is computed and published beside every judged one.
DEDUPLICATE_TRANSITIONS = True


def panel_adjacent_jumps(yoy: np.ndarray) -> np.ndarray:
    """History's own month-to-month inflation moves -- **the anchor**.

    ``|dYoY|`` between consecutive panel rows, dropping the pairs the panel's own
    12-month warm-up leaves undefined. This is the identical object
    ``spine_pilot_report.judge_b2``'s sealed ``panel_p95_adjacent_yoy_pp`` was
    cut from: its 95th percentile is 0.74339119635..., which is that sealed
    number to every digit. The new bar therefore stands on the exam's own
    anchor and does not open a second one.
    """
    jumps = np.abs(np.diff(np.asarray(yoy, dtype=np.float64)))
    return jumps[~np.isnan(jumps)]


def anchor_digest(jumps: np.ndarray) -> str:
    """sha256 over the anchor series' float64 bytes.

    The band is a pure function of this series, so the seal records its digest:
    a panel that moves under the bar is then a loud failure rather than a quiet
    re-anchoring.
    """
    return hashlib.sha256(np.ascontiguousarray(jumps, dtype=np.float64).tobytes()).hexdigest()


def moving_block_band(
    jumps: np.ndarray,
    n: int,
    q: float,
    *,
    draws: int = BAND_DRAWS,
    block: int = BAND_BLOCK_MONTHS,
    seed: int = BAND_SEED,
    level: float = BAND_LEVEL,
) -> tuple[float, float]:
    """The band a sample of ``n`` historical transitions would put ``q`` in.

    The null this realises, stated plainly: *these ``n`` transitions are ordinary
    historical month-transitions.* Resample ``n`` values from the anchor by
    moving blocks of ``block`` months, take the quantile, repeat ``draws`` times,
    and report the central ``level`` of the resulting distribution. A world whose
    transitions sit outside that band is a world whose transitions history would
    not have produced -- which for a seam means a detector can find it.

    Deterministic in ``seed``: no wall clock, no global RNG.
    """
    anchor = np.asarray(jumps, dtype=np.float64)
    n = int(n)
    if n < 1:
        raise ValueError("a band needs at least one transition")
    if anchor.size < block:
        raise ValueError(f"the anchor has {anchor.size} jumps, fewer than the {block}-month block")
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, anchor.size - block + 1, size=(int(draws), n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(int(draws), -1)[:, :n]
    sampled = np.quantile(anchor[idx], float(q), axis=1)
    tail = (1.0 - float(level)) / 2.0
    lo, hi = np.percentile(sampled, [100.0 * tail, 100.0 * (1.0 - tail)])
    return float(lo), float(hi)


def transition_jumps(rows: np.ndarray, yoy: np.ndarray) -> dict[str, Any]:
    """A compiled batch's month-transitions, split into seam and contiguous.

    Returns both readings: ``distinct`` (the judged one -- each ordered
    ``(from_row, to_row)`` pair counted once) and ``raw`` (every adjacent month
    pair in the batch, the published disclosure). A pair is a **seam** exactly
    when the row drawn is not the panel's next row, which is the same test
    ``spine_pilot_report.judge_b2`` and ``stage2_weekc.r2_diagnostics`` apply.
    """
    rows = np.asarray(rows, dtype=np.int64)
    y = np.asarray(yoy, dtype=np.float64)
    a, b = rows[:, :-1].ravel(), rows[:, 1:].ravel()
    raw_jump = np.abs(y[b] - y[a])
    raw_seam = b != a + 1
    pairs = np.unique(np.stack([a, b], axis=1), axis=0)
    pa, pb = pairs[:, 0], pairs[:, 1]
    d_jump = np.abs(y[pb] - y[pa])
    d_seam = pb != pa + 1
    return {
        "raw": {"seam": raw_jump[raw_seam], "contiguous": raw_jump[~raw_seam]},
        "distinct": {"seam": d_jump[d_seam], "contiguous": d_jump[~d_seam]},
    }


def _condition(
    kind: str, q: float, values: np.ndarray, anchor: np.ndarray, sealed: Mapping[str, Any]
) -> dict[str, Any]:
    """One (kind, quantile) cell: the value, its band, whether it is judged."""
    params = sealed["parameters"]
    n = int(values.size)
    tail = n * (1.0 - float(q)) if q >= 0.5 else n * float(q)
    judged = bool(n >= 1 and tail >= float(params["min_tail_count"]))
    if n == 0:
        return {
            "kind": kind,
            "quantile": float(q),
            "n_transitions": 0,
            "judged": False,
            "why_not_judged": "the world has no transitions of this kind",
            "value": None,
            "band": None,
            "inside": None,
            "slack": None,
        }
    value = float(np.quantile(values, float(q)))
    lo, hi = moving_block_band(
        anchor,
        n,
        q,
        draws=int(params["band_draws"]),
        block=int(params["band_block_months"]),
        seed=int(params["band_seed"]),
        level=float(params["band_level"]),
    )
    width = hi - lo
    return {
        "kind": kind,
        "quantile": float(q),
        "n_transitions": n,
        "judged": judged,
        "why_not_judged": (
            None
            if judged
            else (
                f"only {tail:.1f} transitions sit beyond the q={q} quantile, under the declared "
                f"minimum of {params['min_tail_count']}: the sample quantile would rest on one "
                "or two order statistics and a PASS would mean 'too few to tell'"
            )
        ),
        "value": value,
        "band": [lo, hi],
        "inside": bool(lo <= value <= hi),
        # positive inside, negative outside, in units of the band's own width --
        # the quantity an anti-test sweep has to be monotone in
        "slack": float(min(value - lo, hi - value) / width) if width > 0 else 0.0,
    }


def judge_s1(rows: np.ndarray, yoy: np.ndarray, sealed: Mapping[str, Any]) -> dict[str, Any]:
    """``S1`` -- can you find the seams, and does the texture inside a block hold?

    Two halves, each judged at each declared quantile, **all four conditions
    two-sided**:

    * **texture** -- the world's contiguous month-transitions must sit inside
      history's own distribution. Two-sided because a world can fail this in both
      directions: too rough is a world whose months are not history's, and too
      calm is a world that has quietly stopped moving (and, worse, a world whose
      calm contiguous months make its seams *more* findable, not less).
    * **seams** -- the world's seam transitions must sit inside the same
      distribution. Two-sided for the same reason: a compiler that only ever
      joins rows with near-identical inflation has seams that are findable by
      being unnaturally smooth, and it has stopped conditioning as well.

    The bar PASSES when every judged condition holds. A half with too few
    transitions to resolve is reported, flagged, and excluded -- a world with no
    seams at all passes the seam half **vacuously**, which is correct: there is
    nothing to find.
    """
    anchor = panel_adjacent_jumps(yoy)
    split = transition_jumps(rows, yoy)
    key = "distinct" if bool(sealed["parameters"]["deduplicate_transitions"]) else "raw"
    quantiles = [float(q) for q in sealed["bars"]["S1_quantiles"]]

    conditions: list[dict[str, Any]] = []
    for kind in ("contiguous", "seam"):
        for q in quantiles:
            conditions.append(_condition(kind, q, split[key][kind], anchor, sealed))

    judged = [c for c in conditions if c["judged"]]
    passes = bool(judged) and all(c["inside"] for c in judged)
    seam_conditions = [c for c in conditions if c["kind"] == "seam"]
    texture_conditions = [c for c in conditions if c["kind"] == "contiguous"]

    raw_disclosure = {
        kind: {
            "n_transitions": int(split["raw"][kind].size),
            "quantiles": {
                str(q): (
                    float(np.quantile(split["raw"][kind], q)) if split["raw"][kind].size else None
                )
                for q in quantiles
            },
        }
        for kind in ("contiguous", "seam")
    }
    return {
        "bar": "S1",
        "pass": passes,
        # the binding margin: the smallest slack over the judged conditions,
        # positive on a PASS. This is the number a sweep is monotone in.
        "value": min((c["slack"] for c in judged), default=float("nan")),
        "value_note": (
            "the binding margin -- the smallest distance from a judged quantile to the nearer "
            "edge of its band, in units of the band's width. Positive on a PASS"
        ),
        "texture_pass": bool(all(c["inside"] for c in texture_conditions if c["judged"])),
        "seam_pass": bool(all(c["inside"] for c in seam_conditions if c["judged"])),
        "seams_vacuous": bool(not any(c["judged"] for c in seam_conditions)),
        "conditions": conditions,
        "n_conditions_judged": len(judged),
        "counted_on": key,
        "anchor": {
            "n_jumps": int(anchor.size),
            "quantiles": {str(q): float(np.quantile(anchor, q)) for q in quantiles},
            "digest": anchor_digest(anchor),
        },
        "raw_disclosure": raw_disclosure,
        "detectability_disclosure": seam_detectability(rows, yoy, sealed),
        "reading_note": (
            "S1 judges the SHAPE of a world's month-transitions and is blind to how many of "
            "them are seams -- that is R2's question and R2 keeps answering it. A seam FAIL "
            "says a jump-threshold detector can pick the splices out of the tape; it does not "
            "say the compiler splices too often"
        ),
    }


def seam_detectability(
    rows: np.ndarray, yoy: np.ndarray, sealed: Mapping[str, Any]
) -> dict[str, Any]:
    """How well the best jump-threshold detector separates seams from history.

    A **disclosure**, never judged. The Kolmogorov-Smirnov distance between the
    seam-jump distribution and history's own adjacent-jump distribution is
    exactly the maximum of (true positives - false positives) over all
    single-threshold detectors, so it reads directly as "a detector that flags
    big inflation jumps finds this fraction more seams than it flags ordinary
    months". Its own null band at the same sample size is reported beside it.

    It is not judged because a KS distance at n in the high hundreds resolves
    differences finer than the anchor's own quantile uncertainty, and the bar is
    already stated at declared quantiles. Publishing it stops the quantile
    statement from hiding a distribution that agrees at two points and nowhere
    else.
    """
    anchor = np.sort(panel_adjacent_jumps(yoy))
    split = transition_jumps(rows, yoy)
    key = "distinct" if bool(sealed["parameters"]["deduplicate_transitions"]) else "raw"
    out: dict[str, Any] = {"judged": False, "statistic": "kolmogorov_smirnov_vs_the_panel"}
    params = sealed["parameters"]
    for kind in ("contiguous", "seam"):
        sample = np.sort(np.asarray(split[key][kind], dtype=np.float64))
        if sample.size == 0:
            out[kind] = {"n": 0, "ks": None, "null_p95": None}
            continue
        grid = np.concatenate([anchor, sample])
        f_anchor = np.searchsorted(anchor, grid, side="right") / anchor.size
        f_sample = np.searchsorted(sample, grid, side="right") / sample.size
        ks = float(np.max(np.abs(f_sample - f_anchor)))
        rng = np.random.Generator(np.random.PCG64(int(params["band_seed"])))
        block = int(params["band_block_months"])
        n_blocks = int(np.ceil(sample.size / block))
        starts = rng.integers(
            0, anchor.size - block + 1, size=(int(params["band_draws"]), n_blocks)
        )
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(
            int(params["band_draws"]), -1
        )[:, : sample.size]
        draws = np.sort(anchor[idx], axis=1)
        f_draw = np.searchsorted(anchor, draws, side="right") / anchor.size
        ranks = (np.arange(1, sample.size + 1) / sample.size)[None, :]
        null = np.max(np.abs(ranks - f_draw), axis=1)
        out[kind] = {
            "n": int(sample.size),
            "ks": ks,
            "null_p95": float(np.percentile(null, 95.0)),
            "reading": (
                "the best jump-threshold detector's advantage over guessing, in probability points"
            ),
        }
    return out


def self_referential_seam_check(
    rows: np.ndarray, yoy: np.ndarray, sealed: Mapping[str, Any]
) -> dict[str, Any]:
    """The bar S1 deliberately is NOT: seams judged against the world's OWN months.

    Kept in the sealed module because the noise-inflation anti-test's whole point
    is the difference between the two. A bar that asked "do this world's seams
    look like this world's other months" is passed by any compiler that roughens
    its own texture until the seams blend in. S1 anchors on history instead, and
    this function is what makes that claim checkable rather than asserted.
    Never a verdict.
    """
    split = transition_jumps(rows, yoy)
    key = "distinct" if bool(sealed["parameters"]["deduplicate_transitions"]) else "raw"
    contiguous, seam = split[key]["contiguous"], split[key]["seam"]
    quantiles = [float(q) for q in sealed["bars"]["S1_quantiles"]]
    rows_out = []
    for q in quantiles:
        if seam.size == 0 or contiguous.size == 0:
            rows_out.append({"quantile": q, "inside": None})
            continue
        lo, hi = moving_block_band(
            contiguous,
            int(seam.size),
            q,
            draws=int(sealed["parameters"]["band_draws"]),
            block=int(sealed["parameters"]["band_block_months"]),
            seed=int(sealed["parameters"]["band_seed"]),
            level=float(sealed["parameters"]["band_level"]),
        )
        value = float(np.quantile(seam, q))
        rows_out.append(
            {"quantile": q, "value": value, "band": [lo, hi], "inside": bool(lo <= value <= hi)}
        )
    return {
        "judged": False,
        "conditions": rows_out,
        "pass_if_it_were_a_bar": bool(
            all(r["inside"] for r in rows_out if r["inside"] is not None)
        ),
        "note": (
            "seams judged against the WORLD's own contiguous months instead of history's. This "
            "is the bar S1 refuses to be, and the noise-inflation anti-test measures the gap"
        ),
    }


# =========================================================================== #
# RULER 2 -- the conditional era-crossing rule, checked on a compiled world
# =========================================================================== #


def era_crossing_audit(
    rows: np.ndarray,
    spine_seasons: np.ndarray,
    era_bucket: np.ndarray,
    *,
    n_panel_rows: int,
) -> dict[str, Any]:
    """Every bucket-changing seam, checked against the spine's own crossings.

    Ruler 2 says a seam may cross the inflation line only in a month where the
    spine's own inflation path crosses it, and only in the spine's direction.
    This function does not trust the engine's counters: it re-derives every
    crossing seam from the compiled row tape and the decade's season path, and
    classifies it.

    ``forced_reentry_exemptions`` is the one licensed escape and it is counted
    rather than waived: the panel-edge rule (owner ruling 2026-08-16) draws
    UNFILTERED when nothing matches, so a seam out of the panel's last row can
    change bucket with no licence. Every other crossing seam must be faithful.
    """
    rows = np.asarray(rows, dtype=np.int64)
    hot = np.asarray(spine_seasons, dtype=np.int64) & 1
    era = np.asarray(era_bucket, dtype=np.int64)
    a, b = rows[:, :-1], rows[:, 1:]
    seam = b != a + 1
    crossing = seam & (era[b] != era[a])
    story = hot[:, 1:] != hot[:, :-1]
    faithful = crossing & story & (era[b] == hot[:, 1:]) & (era[a] == hot[:, :-1])
    edge = crossing & (a + 1 >= int(n_panel_rows))
    unfaithful = crossing & ~faithful & ~edge
    return {
        "seams": int(seam.sum()),
        "crossing_seams": int(crossing.sum()),
        "crossing_seams_at_a_story_crossing_in_the_story_s_direction": int(faithful.sum()),
        "forced_reentry_exemptions": int(edge.sum()),
        "unlicensed_crossing_seams": int(unfaithful.sum()),
        "holds": bool(unfaithful.sum() == 0),
        "story_crossing_months": int(story.sum()),
        "rule": (
            "a seam may change era bucket only at a month where the spine's own era bit "
            "changes, and only to the bucket the spine changes INTO. Window: zero months -- the "
            "licence is read on the same two months the join connects"
        ),
    }


# =========================================================================== #
# RULER 3 -- A1, re-founded on a computed batch size
# =========================================================================== #

#: Two-sided significance level and target power. 0.05 / 0.90 are the charter's
#: own ("90% power") and the conventional level; neither is tuned.
A1R_ALPHA = 0.05
A1R_POWER = 0.90

#: The sub-batch seed stride. A NEW axis needs its own stride, coprime with the
#: platform's 7919 and with ``spine_v2_fit.SPINE2_ATTEMPT_STRIDE`` (the memory
#: this campaign already paid for once: reusing a stride collapsed twenty spines
#: to two). 15,485,863 is prime and larger than every layer offset in
#: ``ah.gen.spine.LAYER_OFFSETS`` and ``stage2_fit.STAGE2_LAYER_OFFSETS``, so
#: ``seed_i + offset_a == seed_j + offset_b`` is impossible for i != j. Sub-batch
#: 0 IS the sealed verification seed, so the old A1 reading is literally the
#: first rung of the new ladder.
A1R_SEED_STRIDE = 15485863

#: The computable ceiling on the batch, in sub-batches of fifty decades.
#: Measured runtime on this machine: **0.71 s** to compile one fifty-decade batch
#: with no institutional twin attached, so 600 sub-batches (30,000 decades) is
#: about 7 minutes of generation. The cap exists so the construct has a declared
#: ceiling even if the power calculation asks for more; if it ever binds, that
#: is reported as a shortfall in power rather than hidden.
A1R_CAP_SUB_BATCHES = 600
#: Decades per sub-batch -- the sealed batch size, carried unchanged, so each
#: sub-batch IS one ordinary A1 reading and the ladder is comparable to the old
#: one rung by rung.
A1R_DECADES_PER_SUB_BATCH = 50


def _z(p: float) -> float:
    """Standard-normal quantile, by bisection on ``math.erf``. No scipy."""
    from math import erf, sqrt

    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 0.5 * (1.0 + erf(mid / sqrt(2.0))) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _chi2_lower_quantile(df: int, p: float) -> float:
    """The ``p``-quantile of chi-square(df), by bisection on its CDF.

    Used for one thing only: the upper confidence bound on the pilot's standard
    deviation, which is what turns "the batch size at the point estimate" into
    "the batch size that survives the pilot having been six seeds".
    """
    from math import exp, lgamma, log

    def cdf(x: float) -> float:
        # regularised lower incomplete gamma P(df/2, x/2) by series expansion
        a, z = df / 2.0, x / 2.0
        if z <= 0.0:
            return 0.0
        term = 1.0 / a
        total = term
        for k in range(1, 2000):
            term *= z / (a + k)
            total += term
            if term < total * 1e-15:
                break
        return float(exp(-z + a * log(z) - lgamma(a)) * total)

    lo, hi = 1e-9, 1e4
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def a1r_power_plan(
    pilot_sd: float,
    margins: Mapping[str, float],
    *,
    alpha: float = A1R_ALPHA,
    power: float = A1R_POWER,
    pilot_n: int = 6,
    cap: int = A1R_CAP_SUB_BATCHES,
) -> dict[str, Any]:
    """How many fifty-decade sub-batches ``A1`` needs, at the ENGINE's own margin.

    The construct, stated so it can be checked. ``A1``'s difference read on one
    sub-batch of fifty decades has a standard deviation across seeds -- the
    six-seed disclosure measured it. Read on ``B`` independent sub-batches and
    pooled, its standard error is that divided by ``sqrt(B)``: the sub-batches
    are independent by construction (disjoint seeds, disjoint streams), so this
    needs no assumption about months inside a decade being independent, which
    they are not.

    For a two-sided test at ``alpha`` with power ``power`` against a margin
    ``delta``:

        B >= (z_(1-alpha/2) + z_power)^2 * sd^2 / delta^2

    Two margins are planned for and both are reported: the engine's own measured
    margin against **zero** (does the hedge pay at all?) and against **history's
    own +3.49** (is the engine's hedge history's?).

    **The pilot was six seeds and that is priced, not ignored.** ``B`` scales
    with ``sd^2``, and the sampling distribution of ``sd^2`` at six draws is
    wide: its upper 90% chi-square bound is about three times the point
    estimate. The plan therefore reports ``B`` at the point estimate AND at that
    upper bound, and adopts the larger of the two, capped. Adopting the point
    estimate alone would be planning a power calculation at the most flattering
    reading of its own input.
    """
    z_sum = _z(1.0 - alpha / 2.0) + _z(power)
    sd2 = float(pilot_sd) ** 2
    df = int(pilot_n) - 1
    sd2_upper = sd2 * df / _chi2_lower_quantile(df, 1.0 - 0.90)

    def required(variance: float, delta: float) -> int:
        return int(np.ceil(z_sum**2 * variance / float(delta) ** 2))

    per_margin: dict[str, Any] = {}
    for name, delta in margins.items():
        at_point = required(sd2, delta)
        at_upper = required(sd2_upper, delta)
        per_margin[name] = {
            "delta_pp": float(delta),
            "sub_batches_at_the_point_estimate": at_point,
            "sub_batches_at_the_upper_90pct_bound_on_sd": at_upper,
            "adopted_before_the_cap": max(at_point, at_upper),
            "capped": bool(max(at_point, at_upper) > cap),
        }
    binding = max(per_margin.values(), key=lambda r: r["adopted_before_the_cap"])
    adopted = min(int(binding["adopted_before_the_cap"]), int(cap))
    return {
        "alpha": float(alpha),
        "power": float(power),
        "z_sum": float(z_sum),
        "pilot_n_seeds": int(pilot_n),
        "pilot_sd_pp": float(pilot_sd),
        "pilot_sd_upper_90pct_bound_pp": float(np.sqrt(sd2_upper)),
        "per_margin": per_margin,
        "sub_batches_required": int(binding["adopted_before_the_cap"]),
        "cap_sub_batches": int(cap),
        "sub_batches_adopted": adopted,
        "decades_per_sub_batch": A1R_DECADES_PER_SUB_BATCH,
        "decades_adopted": adopted * A1R_DECADES_PER_SUB_BATCH,
        "cap_binds": bool(binding["adopted_before_the_cap"] > cap),
        "achieved_power_at_the_adopted_size": _achieved_power(
            adopted, sd2_upper, float(binding["delta_pp"]), alpha
        ),
    }


def _achieved_power(b: int, variance: float, delta: float, alpha: float) -> float:
    """Power actually bought at ``b`` sub-batches, at the conservative variance."""
    from math import erf, sqrt

    if b < 1:
        return 0.0
    se = np.sqrt(variance / b)
    lam = abs(float(delta)) / float(se)
    x = lam - _z(1.0 - alpha / 2.0)
    return float(0.5 * (1.0 + erf(x / sqrt(2.0))))


def a1r_seeds(n_sub_batches: int, base_seed: int) -> list[int]:
    """The declared sub-batch seeds: ``base + A1R_SEED_STRIDE * k``."""
    return [int(base_seed) + A1R_SEED_STRIDE * int(k) for k in range(int(n_sub_batches))]


def pool_a1_verdicts(verdicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The pooled ``A1`` reading, recovered exactly from the sealed judge's output.

    ``A1``'s spread is ``1200 * (sum of commodity returns - sum of bond returns)
    / (count of months)``, pooled over every decade in the batch. So the pooled
    spread over B sub-batches is the **count-weighted mean** of the sub-batches'
    own spreads -- an algebraic identity, not a re-implementation, and it lets a
    25,700-decade batch be pooled without ever holding 25,700 decades in memory.

    The identity is not asserted: ``tests/test_stage2_rulers.py::
    test_pooling_the_sealed_a1_verdicts_equals_judging_the_pooled_batch`` builds a
    batch both ways and demands agreement to 1e-12. If ``judge_a1`` ever stopped
    being a ratio of pooled sums, that test fails rather than this function
    quietly reporting a different statistic.
    """
    if not verdicts:
        raise ValueError("A1R needs at least one sub-batch verdict to pool")
    totals: dict[str, list[float]] = {"high": [0.0, 0.0], "low": [0.0, 0.0]}
    for verdict in verdicts:
        for key in ("high", "low"):
            n = float(verdict[f"months_{key}"])
            spread = float(verdict[f"spread_{key}_pp"])
            if n <= 0.0 or not np.isfinite(spread):
                continue
            totals[key][0] += n
            totals[key][1] += spread * n
    spreads = {
        key: (totals[key][1] / totals[key][0] if totals[key][0] else float("nan"))
        for key in ("high", "low")
    }
    containment = [float(x) for x in verdicts[0]["containment_pp"]]
    return {
        "spread_high_pp": spreads["high"],
        "spread_low_pp": spreads["low"],
        "difference_pp": spreads["high"] - spreads["low"],
        "months_high": int(totals["high"][0]),
        "months_low": int(totals["low"][0]),
        "containment_pp": containment,
        "containment_pass": bool(containment[0] <= spreads["high"] <= containment[1]),
        "n_sub_batches": len(verdicts),
    }


def judge_a1_refounded(
    pooled: Mapping[str, Any],
    per_sub_batch: Sequence[float],
    sealed: Mapping[str, Any],
) -> dict[str, Any]:
    """``A1R`` -- ``A1``'s question, asked at a batch size that can answer it.

    ``pooled`` is the SEALED ``A1`` judge's own verdict, run once on the whole
    pooled batch: the statistic is ``A1``'s, unmodified and un-reimplemented, and
    the containment condition is ``A1``'s carried band. ``per_sub_batch`` is the
    same statistic read on each fifty-decade sub-batch separately, and supplies
    the standard error -- the sub-batches are independent, so their spread is the
    honest uncertainty of the pooled number.

    **The decision rule, declared before the measurement.**

    * ``directional`` -- the two-sided ``1 - alpha`` interval around the pooled
      difference lies **entirely above zero**. This is ``A1``'s own directional
      condition with the coin-flip taken out of it: at the sealed size the
      interval is five points wide and cannot exclude anything.
    * ``containment`` -- the pooled high-inflation spread sits inside ``A1``'s
      carried containment band. Byte-carried; the re-founding is about power, not
      about moving a threshold.
    * ``A1R`` passes when both hold.

    And two readings that are **not** the verdict but are the point of the
    exercise: whether the interval excludes zero **in either direction** (a
    precise negative verdict is a verdict), and whether it excludes **history's
    own +3.49**.
    """
    values = np.asarray(list(per_sub_batch), dtype=np.float64)
    b = int(values.size)
    if b < 2:
        raise ValueError("A1R needs at least two sub-batches to have a standard error")
    bars = sealed["bars"]
    alpha = float(sealed["parameters"]["a1r_alpha"])
    z = _z(1.0 - alpha / 2.0)
    point = float(pooled["difference_pp"])
    sd = float(values.std(ddof=1))
    se = sd / np.sqrt(b)
    ci = [point - z * se, point + z * se]

    history = float(bars["A1R_history_difference_pp"])
    excludes_zero = bool(ci[0] > 0.0 or ci[1] < 0.0)
    directional = bool(ci[0] > 0.0)
    containment = bool(pooled["containment_pass"])
    return {
        "bar": "A1R",
        "pass": bool(directional and containment),
        "value": point,
        "pooled_difference_pp": point,
        "pooled_spread_high_pp": float(pooled["spread_high_pp"]),
        "pooled_spread_low_pp": float(pooled["spread_low_pp"]),
        "n_sub_batches": b,
        "n_decades": b * int(sealed["parameters"]["a1r_decades_per_sub_batch"]),
        "sub_batch_mean_pp": float(values.mean()),
        "sub_batch_sd_pp": sd,
        "standard_error_pp": float(se),
        "confidence_interval": ci,
        "confidence_level": 1.0 - alpha,
        "directional_pass": directional,
        "containment_pass": containment,
        "excludes_zero": excludes_zero,
        "sign_if_it_excludes_zero": ("positive" if ci[0] > 0.0 else "negative")
        if excludes_zero
        else None,
        "history_difference_pp": history,
        "excludes_history": bool(ci[1] < history or ci[0] > history),
        "distance_from_history_in_standard_errors": float((point - history) / se) if se else None,
        "distance_from_zero_in_standard_errors": float(point / se) if se else None,
        "sub_batch_share_positive": float((values > 0).mean()),
        "reading_note": (
            "A1R is A1's statistic and A1's containment band, read on a batch sized by a power "
            "calculation at the engine's OWN measured margin. It replaces a coin flip with a "
            "verdict; it does not re-grade the sealed A1, which stands"
        ),
    }


# =========================================================================== #
# the threshold block: one assembly path, from the measurements
# =========================================================================== #


def sealed_from_sources(
    v2_anchors_path: Path | None = None, reach_results_path: Path | None = None
) -> dict[str, Any]:
    """Assemble D-SP-11's threshold block from its two sources.

    Exactly one assembly path, ``scripts/stage2_report.sealed_from_anchors``'s
    rule carried forward: the seal script writes what this builds and the
    anti-test sweeps judge with what this builds, so a sweep can never be run
    against numbers that differ from the sealed ones.

    * ``S1`` seals **rules, not a number**, and deliberately. Its band is a
      function of the panel and of the sample size the world happens to present,
      so a fixed number would be a band cut at one arbitrary n. The precedent is
      the campaign's own ruling SQ9 -- seal the selection rule when the value is
      not pinned. What IS pinned and hashed: the quantiles, the level, the draw
      count, the block length, the bootstrap seed, the minimum tail count, the
      de-duplication rule, the anchor's digest, and a reference table of bands
      over a declared grid of sample sizes so a reader can check any arm by hand.
    * ``A1R`` seals the power calculation's inputs and its answer: the pilot's
      six-seed standard deviation (read out of the D-SP-10 artifact, not
      retyped), history's own A1 difference (read out of the v2 anchors, not
      retyped), alpha, power, the seed rule, the cap, and the adopted batch size.
    """
    anchors = json.loads((v2_anchors_path or V2_ANCHORS_PATH).read_text(encoding="utf-8"))
    reach = json.loads((reach_results_path or REACH_RESULTS_PATH).read_text(encoding="utf-8"))

    states = anchors["d_allocation_episode_facts"]["inflation_states"]["cpi_yoy_ge_4pct"]
    history_high = float(
        states["high_inflation"]["spreads_ann_arith_pp"]["commodities_minus_bonds"]
    )
    history_low = float(states["low_inflation"]["spreads_ann_arith_pp"]["commodities_minus_bonds"])
    history_difference = history_high - history_low

    pilot = reach["seed_dispersion_disclosure"]["after"]
    pilot_sd = float(pilot["A1_difference_pp_sd"])
    pilot_mean = float(pilot["A1_difference_pp_mean"])
    pilot_n = len(pilot["seeds"])

    plan = a1r_power_plan(
        pilot_sd,
        {"vs_zero": abs(pilot_mean), "vs_history": abs(pilot_mean - history_difference)},
        pilot_n=pilot_n,
    )
    return {
        "bars": {
            "S1_quantiles": list(SEAM_QUANTILES),
            "S1_band_level": BAND_LEVEL,
            "S1_conditions": [
                f"{kind}_q{q:g}" for kind in ("contiguous", "seam") for q in SEAM_QUANTILES
            ],
            "S1_both_halves_required": True,
            "A1R_alpha": A1R_ALPHA,
            "A1R_power": A1R_POWER,
            "A1R_history_difference_pp": history_difference,
            "A1R_history_spread_high_pp": history_high,
            "A1R_history_spread_low_pp": history_low,
            "A1R_pilot_mean_pp": pilot_mean,
            "A1R_pilot_sd_pp": pilot_sd,
            "A1R_pilot_n_seeds": pilot_n,
            "A1R_sub_batches": plan["sub_batches_adopted"],
            "A1R_decades": plan["decades_adopted"],
            "A1R_seed_stride": A1R_SEED_STRIDE,
        },
        "parameters": {
            "band_level": BAND_LEVEL,
            "band_draws": BAND_DRAWS,
            "band_block_months": BAND_BLOCK_MONTHS,
            "band_seed": BAND_SEED,
            "min_tail_count": MIN_TAIL_COUNT,
            "deduplicate_transitions": DEDUPLICATE_TRANSITIONS,
            "a1r_alpha": A1R_ALPHA,
            "a1r_decades_per_sub_batch": A1R_DECADES_PER_SUB_BATCH,
            "era_crossing_window_months": 0,
        },
        "a1r_power_plan": plan,
    }


def band_reference_table(jumps: np.ndarray, sealed: Mapping[str, Any]) -> dict[str, Any]:
    """S1's bands over a declared grid of sample sizes -- for the seal to carry.

    The judge computes the band at the world's own n; this table exists so a
    reader with the seal in front of them can check any arm's condition without
    re-running a bootstrap, and so a band that ever moved would be visible in a
    diff of the seal rather than only in a re-run.
    """
    params = sealed["parameters"]
    grid = (100, 200, 400, 600, 800, 1200, 2000, 4000, 6000)
    return {
        str(n): {
            f"q{q:g}": list(
                moving_block_band(
                    jumps,
                    n,
                    q,
                    draws=int(params["band_draws"]),
                    block=int(params["band_block_months"]),
                    seed=int(params["band_seed"]),
                    level=float(params["band_level"]),
                )
            )
            for q in sealed["bars"]["S1_quantiles"]
        }
        for n in grid
    }


def load_sealed(path: Path | None = None) -> dict[str, Any]:
    """The D-SP-11 pre-registration. Read-only; nothing here ever writes it."""
    return json.loads((path or SEALED_PATH).read_text(encoding="utf-8"))
