"""Spine v2, stage 1: measure the historical facts the rebuilt exam will grade against.

Writes ``docs/superpowers/specs/spine-v2-anchors.json``. Deterministic and
offline: the only data read is the local DuckDB/Parquet catalog through
``ah.gen.bootstrap.campaign_source`` (the same panel the spine pilot measured),
and every random draw comes from a ``numpy.random.Generator(PCG64(seed))`` whose
seed is one of the five literal constants below -- one per resampling section,
each generator consumed in a fixed order. No seed is derived from another by an
arithmetic stride (the platform's seed-stride collision lesson), and a module
level assertion holds them distinct. Re-running reproduces the JSON byte for
byte.

Sections A-D are the original stage-1 measurement. Sections E-H were added to
close the exam's four OPEN items
(``docs/superpowers/specs/2026-08-17-spine-v2-exam.md``, "Before sealing"):

- **E (OPEN-1)** the clockwise-ordering fraction recomputed on the CURRENT panel
  vintage, with a block-bootstrap interval -- the O1 bar is cut from its lower
  edge.
- **F (OPEN-2)** block-bootstrap intervals on the high-minus-low stock-bond
  correlation difference and on the difference in share-of-rolling-windows
  positive, both at the 4% line -- the A2 margin is cut from the former's lower
  edge.
- **G (OPEN-3)** bootstrap intervals on each season's completed-spell median
  dwell, resampling SPELLS rather than months.
- **H (OPEN-4)** a generated-side power calculation: how many generated decades
  a TRUE engine needs before it clears each bar with >= 90% probability.

Sections I and J were added on 2026-08-17 for the two owner-agreed
regime-identification obligations, and neither draws a random number -- both are
deterministic recomputations of anchors under a different labelling of the same
panel months, judged against the sampling intervals E and G already measured:

- **I (obligation A)** label stability: each of the two-dial classifier's dials
  is perturbed +-0.50 pp in its own units and every affected anchor is re-derived,
  then compared with its own sampling noise. The growth dial has no threshold of
  its own, so it is perturbed one layer down in ``regime_ruleset_v1`` and the
  months are re-labelled -- with an assertion that the unperturbed rebuild
  reproduces the panel's labels exactly.
- **J (obligation B)** a second classification of the SAME four seasons, built
  from five inputs rather than two (the two dials plus credit conditions, labor
  direction and market stress) by a transparent vote with a stated tie-break,
  with the disagreement map, the re-derived anchors, and the owner's
  pre-declared decision rule applied per anchor.

Nothing here is a new definition where the platform already has one. Every
concept this script needs is imported from the module that owns it:

- ``ah.gen.spine.panel_yoy``       -- trailing 12-month CPI inflation, in percent,
  computed in the panel's own source space (the ``cpi`` factor is a LEVEL).
- ``ah.gen.spine.panel_quadrant``  -- the four-quadrant investment clock.
- ``ah.gen.spine.fit_hazard``      -- the era threshold that splits "hot" from
  "cold", and the at-risk/event discipline the pilot's hazard table rests on.
- ``ah.gen.regimes.semimarkov.spells_from_labels`` -- run-length decomposition
  (the round-one seal used exactly this for its dwell medians).
- ``ah.strategies.load_derived_series`` + ``ah.eval.metrics.tails.
  derived_series_values`` -- the SEALED ``govt_tr_10y`` transform. The panel has
  no bond total-return factor, only the 10-year yield level; the platform's one
  sanctioned way to turn that level into a monthly return is this derived
  series (carry minus 8.5-year duration times the yield change), so that is what
  is used rather than a fresh formula written here.

The two downturn definitions this script reports side by side are the two the
spine-02 verdict-integrity review found had been mixed inside one comparison
(``docs/superpowers/specs/2026-08-16-spine02-results.md``, section "B6 v2"):
CRI-only onsets (the sealed panel anchor) and REC+CRI onsets (what the judge
actually counted on the spine side). Both are computed here, each
self-consistently on both sides of its own ratio.

Invocation (from the worktree root, no network needed):

    uv run python scripts/spine_v2_anchors.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from ah.data import derive
from ah.eval.metrics.tails import derived_series_values

# Sections I and J must rebuild the platform's OWN regime features (so a
# perturbed threshold re-labels exactly what an unperturbed one labels) and must
# read two series the factor panel does not carry. Both jobs are done with
# ``ah.gen.bootstrap``'s own helpers rather than with a second implementation
# written here -- which is why the private names are imported: a re-implementation
# that drifted from ``build_source`` by one line would make every perturbation
# result a measurement of the drift. ``section_i`` asserts the rebuild reproduces
# ``source.labels`` bit-identically before any threshold is moved.
from ah.gen.bootstrap import (
    CAMPAIGN_VINTAGE_ID,
    INDPRO_SERIES_ID,
    USREC_SERIES_ID,
    _catalog_access,
    _drawdown_fraction,
    _monthly,
    _read_series,
    _yoy_percent,
    campaign_source,
    load_manifest,
    read_factor_frames,
)
from ah.gen.regimes.semimarkov import spells_from_labels
from ah.gen.spine import CLOCKWISE, QUADRANTS, fit_hazard, panel_quadrant, panel_yoy
from ah.strategies import load_derived_series

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # running as a script puts it there already
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Section K's window rule and the sealed judge's window rule must be the SAME
# code, not two implementations that agree today: the whole point of the pooled
# re-derivation is that both sides of a D bar are measured identically. So the
# completed-spell decomposition is imported from the grader module the judges
# import, rather than written a second time here.
from spine_v2_grader import CONTRACTING_LABELS, INCUMBENT_CONTRACTING_LABELS  # noqa: E402
from spine_v2_grader import clockwise_counts as grader_clockwise_counts  # noqa: E402
from spine_v2_grader import completed_spells as grader_completed_spells  # noqa: E402
from spine_v2_grader import season_cells as grader_season_cells  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-anchors.json"
#: Round one's seal. Section E checks its clockwise anchor against this vintage
#: rather than restating the number, so a drift cannot hide behind a literal.
PILOT_PREREG_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-pilot-prereg.json"

#: The lookahead window for "a downturn began within K months of this month".
#: 12, matching the pilot's B6 (``spine_pilot_seal.K_MONTHS``) so the anchors
#: are directly comparable with the sealed round-one/round-two numbers.
K_MONTHS = 12

#: Section B's block bootstrap. One generator, used sequentially in a fixed
#: order (sorted block lengths), so no two configurations can share a tape and
#: no stride constant is reused on a new axis.
BOOTSTRAP_SEED = 20260816
N_BOOTSTRAP = 2000
BLOCK_LENGTHS_MONTHS = (12, 24, 36)
PRIMARY_BLOCK_MONTHS = 24
CI_PERCENTILES = (2.5, 97.5)

#: Section D's inflation-state split. 4% is the conventional "high inflation"
#: line; 3% and 5% are the sensitivity arms.
INFLATION_THRESHOLDS_PP = (3.0, 4.0, 5.0)
PRIMARY_INFLATION_THRESHOLD_PP = 4.0
ROLLING_CORR_WINDOW_MONTHS = 36

#: Section E (OPEN-1). Its own generator; the block machinery and the block
#: lengths are section B's, so the ordering interval and the transmission
#: interval are the same kind of object.
ORDERING_BOOTSTRAP_SEED = 20260817

#: Section F (OPEN-2). Its own generator, same machinery and block lengths.
CORRELATION_BOOTSTRAP_SEED = 20260818

#: Section G (OPEN-3). Resamples SPELLS, not months -- a spell is the
#: independent unit here (its months are one observation of one dwell, not many
#: observations), so the block machinery does not apply and an ordinary
#: i.i.d. resample of the completed-spell list is the right bootstrap. Spells
#: are cheap to resample, so this one runs more draws.
DWELL_BOOTSTRAP_SEED = 20260819
N_DWELL_BOOTSTRAP = 10000

#: Section H (OPEN-4). The generated-side power calculation.
POWER_SEED = 20260820
#: A generated decade is 120 months (the product's own decade length).
POWER_DECADE_MONTHS = 120
#: Months of a decade with no trailing 12-month inflation reading yet -- the
#: same warm-up the judge will apply on the generated side.
POWER_YOY_WARMUP_MONTHS = 12
POWER_N_ENSEMBLES = 2000
POWER_SEED_GRID = (5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 300, 400, 500)
#: The probability a TRUE engine must clear a bar with.
POWER_TARGET = 0.90
#: The ensemble size the prior rounds ran at, reported per bar for comparison.
POWER_PILOT_N_SEEDS = 20
#: The campaign's batch size, owner-ruled 2026-08-17: 50 decades per premise.
#: Every retained bar's power is reported at this size (section M).
SEALED_N_SEEDS = 50
assert SEALED_N_SEEDS in POWER_SEED_GRID, "the sealed batch size must be a grid point"

#: The exam's +-1 quarter dwell tolerance, in months. A policy choice (the
#: quarter is the game's smallest play unit), not an estimate -- section G
#: measures the sampling wobble beside it but does not set it.
DWELL_TOLERANCE_MONTHS = 3.0
#: A2(ii)'s two edges. Policy choices cut from the published 3%/4%/5% threshold
#: range, not from a sampling interval, so section F does not move them.
A2_SHARE_HIGH_FLOOR = 0.80
A2_SHARE_LOW_CEILING = 0.65

#: Section I (label stability). The size of the threshold perturbation applied
#: to EACH dial, in percentage points of that dial's own units -- 0.50 pp on the
#: inflation line (trailing CPI YoY) and 0.50 pp on the growth line
#: (``regime_ruleset_v1``'s ``growth_weak``, trailing INDPRO YoY). 50 basis
#: points is not an arbitrary round number here: it is the platform's own
#: ``ah.gen.spine.BACKDROP_MARGIN_PP``, the displacement the spine already
#: treats as the smallest meaningful move in an inflation state (it is inside
#: the era threshold itself and inside ``spine_quadrant``'s hot test), and it is
#: one conventional central-bank move. Applying the SAME 0.50 pp to the growth
#: dial keeps the two perturbations the same size in each dial's own units.
STABILITY_PERTURBATION_PP = 0.5

#: The nine arms: the baseline, each dial moved each way on its own, and the
#: four joint corners. ``(name, inflation_line_delta_pp, growth_line_delta_pp)``.
#: Sign convention, stated because it is easy to read backwards: a POSITIVE
#: inflation delta raises the hot line (fewer hot months); a POSITIVE growth
#: delta raises the contraction line (more months called weak, i.e. MORE
#: contracting months).
STABILITY_ARMS: tuple[tuple[str, float, float], ...] = (
    ("baseline", 0.0, 0.0),
    ("inflation_line_minus_50bp", -STABILITY_PERTURBATION_PP, 0.0),
    ("inflation_line_plus_50bp", +STABILITY_PERTURBATION_PP, 0.0),
    ("growth_line_minus_50bp", 0.0, -STABILITY_PERTURBATION_PP),
    ("growth_line_plus_50bp", 0.0, +STABILITY_PERTURBATION_PP),
    ("inflation_minus_growth_minus", -STABILITY_PERTURBATION_PP, -STABILITY_PERTURBATION_PP),
    ("inflation_minus_growth_plus", -STABILITY_PERTURBATION_PP, +STABILITY_PERTURBATION_PP),
    ("inflation_plus_growth_minus", +STABILITY_PERTURBATION_PP, -STABILITY_PERTURBATION_PP),
    ("inflation_plus_growth_plus", +STABILITY_PERTURBATION_PP, +STABILITY_PERTURBATION_PP),
)

#: Section J. The unemployment series the labor voter reads. Registered in
#: ``requirements.yaml`` (fred.UNRATE, monthly from 1948-01) and present in the
#: campaign vintage, so its 12-month lookback exists for every panel month.
UNRATE_SERIES_ID = "fred.UNRATE"
#: The panel factor the credit voter reads: Baa minus Aaa, in percentage points.
CREDIT_FACTOR = "ig_spread"
#: The labor voter's lookback, in months.
LABOR_CHANGE_MONTHS = 12
#: A run of this many or more consecutive disagreeing months is reported as a
#: CLUSTER with its dates, rather than being averaged into a percentage.
DISAGREEMENT_CLUSTER_MIN_MONTHS = 3

#: The pre-declared decision rule, owner-agreed 2026-08-17, quoted verbatim in
#: the exam document and carried in the JSON so the two cannot drift.
RICHER_DECISION_RULE = (
    "the richer classifier replaces the simple one ONLY IF the disagreement changes an "
    "anchor by more than that anchor's own sampling noise. Otherwise simplicity wins."
)

#: The bars section H's recommendation is taken over. ``A1_with_containment``
#: and the ``A2*`` components are diagnostics reported beside their headline
#: bar, not separate bars, and do not drive the recommended ensemble size.
HEADLINE_BARS = ("T1", "O1", "D1", "D2", "D3", "D4", "A1", "A2")

_SEEDS = (
    BOOTSTRAP_SEED,
    ORDERING_BOOTSTRAP_SEED,
    CORRELATION_BOOTSTRAP_SEED,
    DWELL_BOOTSTRAP_SEED,
    POWER_SEED,
)
assert len(set(_SEEDS)) == len(_SEEDS), "every section must draw from its own seed"

#: Named episodes, inclusive month bounds. The three high-inflation episodes the
#: stage-1 brief asks for, plus the calm/disinflation contrasts that set the
#: other end of the range. 2021-2022 is declared here on purpose even though the
#: panel cannot serve it -- an absent episode must be visible in the output, not
#: silently missing from a list.
NAMED_EPISODES: tuple[tuple[str, str, str, str, str], ...] = (
    ("early_calm_1953_1965", "1953-04", "1965-12", "low", "post-war calm, pre-Vietnam build-up"),
    ("oil_shock_1973_1975", "1973-01", "1975-12", "high", "first oil shock and the 1973-75 bust"),
    (
        "great_inflation_1977_1982",
        "1977-01",
        "1982-12",
        "high",
        "second inflation wave through the Volcker disinflation",
    ),
    (
        "great_disinflation_1983_1999",
        "1983-01",
        "1999-12",
        "low",
        "the long disinflation and the 1990s expansion",
    ),
    ("post_gfc_calm_2010_2019", "2010-01", "2019-12", "low", "post-GFC low-inflation decade"),
    (
        "pandemic_inflation_2021_2022",
        "2021-01",
        "2022-12",
        "high",
        "the 2021-22 inflation surge -- OUTSIDE the panel (see notes)",
    ),
)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _f(x: Any) -> float | None:
    """A float that survives JSON: NaN and infinities become null."""
    v = float(x)
    return v if np.isfinite(v) else None


def _month_labels(dates: pd.DatetimeIndex) -> list[str]:
    """``['1953-04', '1953-05', ...]`` -- the panel's months as plain strings."""
    return [str(label) for label in dates.strftime("%Y-%m")]


def _onset_flags(state: np.ndarray) -> np.ndarray:
    """The months at which ``state`` TURNS ON (row 0 counts if it opens inside).

    Identical in form to ``ah.gen.spine.fit_hazard``'s event construction and to
    ``scripts/spine_pilot_seal._b6_onset_rates``'s ``onset_at``; written once
    here so both downturn definitions get the same treatment.
    """
    out = np.zeros(state.size, dtype=bool)
    out[0] = bool(state[0])
    out[1:] = state[1:] & ~state[:-1]
    return out


def _episodes(state: np.ndarray, months: list[str]) -> list[dict[str, Any]]:
    """Contiguous runs of ``state``, dated, so an economist can eyeball them."""
    runs: list[dict[str, Any]] = []
    for value, start, length in spells_from_labels(state.astype(np.int8)):
        if value != 1:
            continue
        runs.append(
            {
                "start": months[start],
                "end": months[start + length - 1],
                "months": int(length),
            }
        )
    return runs


def _eligible_mask(yoy: np.ndarray, n_rows: int, k: int) -> np.ndarray:
    """The B6 population: a defined trailing YoY and a FULL k-month lookahead.

    Verbatim in effect from ``scripts/spine_pilot_seal._b6_onset_rates``: without
    the right-hand truncation the months near the panel's end can never record an
    onset they had no room to observe, which would bias every rate downward.
    """
    eligible = ~np.isnan(yoy)
    eligible[max(n_rows - k, 0) :] = False
    return eligible


def _followed_within(onset_at: np.ndarray, index: np.ndarray, k: int) -> np.ndarray:
    """Per eligible month: did an onset occur in the next ``k`` months?"""
    return np.array([bool(onset_at[t + 1 : t + 1 + k].any()) for t in index], dtype=bool)


def _quantiles(values: np.ndarray) -> dict[str, float | None]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"lo": None, "hi": None, "median": None}
    lo, hi = np.percentile(finite, CI_PERCENTILES)
    return {"lo": _f(lo), "hi": _f(hi), "median": _f(np.median(finite))}


# --------------------------------------------------------------------------- #
# A -- event chronology
# --------------------------------------------------------------------------- #


def section_a(source: Any, yoy: np.ndarray, cells: np.ndarray) -> dict[str, Any]:
    """Both downturn definitions: events, dated episodes, months at risk."""
    labels = np.asarray(source.labels)
    months = _month_labels(source.dates)
    n = source.n_rows
    eligible = _eligible_mask(yoy, n, K_MONTHS)

    out: dict[str, Any] = {
        "panel_months": int(n),
        "panel_span": [months[0], months[-1]],
        "k_months": K_MONTHS,
        "eligible_months_full_lookahead": int(eligible.sum()),
        "definitions": {},
    }
    for name, state in (
        ("cri_only", labels == "CRI"),
        ("rec_plus_cri", np.isin(labels, ["REC", "CRI"])),
    ):
        onset_at = _onset_flags(state)
        # at-risk, fit_hazard's own discipline: a defined quadrant, not already
        # inside the state, and never the final row (it has no t+1).
        at_risk = (cells >= 0) & ~state
        at_risk[-1] = False
        onsets = np.flatnonzero(onset_at)
        out["definitions"][name] = {
            "label_codes": ["CRI"] if name == "cri_only" else ["REC", "CRI"],
            "n_onsets_panel": int(onset_at.sum()),
            "onset_months": [months[i] for i in onsets],
            "state_months_total": int(state.sum()),
            "episodes": _episodes(state, months),
            "months_at_risk_hazard_denominator": int(at_risk.sum()),
            "months_at_risk_b6_population": int(eligible.sum()),
            "n_onsets_inside_lookahead_of_eligible": int(
                _followed_within(onset_at, np.flatnonzero(eligible), K_MONTHS).sum()
            ),
        }
    return out


# --------------------------------------------------------------------------- #
# B -- transmission lift
# --------------------------------------------------------------------------- #


def _tight_definitions(source: Any, yoy: np.ndarray) -> dict[str, dict[str, Any]]:
    """Candidate "tight-policy month" indicators, per panel row.

    ``defined`` marks rows where the indicator can be evaluated at all; a row
    where it cannot is dropped from THAT indicator's population only (and the
    population size is reported alongside its numbers).
    """
    names = list(source.factor_names)
    values = np.asarray(source.values)
    n = source.n_rows
    ust10 = values[:, names.index("ust_10y")]
    ust2 = values[:, names.index("ust_2y")]
    policy = values[:, names.index("policy_rate")]

    all_defined = np.ones(n, dtype=bool)

    trailing_mean = np.full(n, np.nan)
    for t in range(36, n):
        trailing_mean[t] = policy[t - 36 : t].mean()

    return {
        "curve_inversion_10y_2y": {
            "score": ust2 - ust10,  # positive = inverted = tighter
            "defined": all_defined,
            "description": (
                "the 10-year Treasury yield sits below the 2-year yield "
                "(an inverted yield curve); tightness score = 2y minus 10y. THE "
                "PRIMARY DEFINITION: it is the panel-side conditioning the spine "
                "pilot sealed in round one "
                "(scripts/spine_pilot_seal._b6_onset_rates) and the one round "
                "two's matched comparison used."
            ),
        },
        "real_policy_rate_positive": {
            "score": policy - yoy,
            "defined": ~np.isnan(yoy),
            "description": (
                "the effective fed funds rate exceeds trailing 12-month CPI "
                "inflation (a positive real policy rate); tightness score = the "
                "real rate itself. Sensitivity only."
            ),
        },
        "policy_rate_above_trailing_36m": {
            "score": policy - trailing_mean,
            "defined": ~np.isnan(trailing_mean),
            "description": (
                "the policy rate sits above its own average over the previous "
                "36 months (policy tighter than its recent norm); tightness "
                "score = rate minus that average. Sensitivity only; the first 36 "
                "panel months cannot evaluate it."
            ),
        },
    }


def _stationary_bootstrap_indices(
    rng: np.random.Generator, n: int, mean_block: int, n_draws: int
) -> np.ndarray:
    """``(n_draws, n)`` Politis-Romano stationary-bootstrap row indices.

    Geometric block lengths with mean ``mean_block`` (restart probability
    ``1/mean_block``) and wrap-around continuation, so the resampled series is
    stationary and blocks of consecutive months travel together. Vectorised, but
    the two RNG calls happen in a fixed order, so the tape is deterministic.
    """
    restart = rng.random((n_draws, n)) < (1.0 / float(mean_block))
    restart[:, 0] = True
    starts = rng.integers(0, n, size=(n_draws, n))
    positions = np.arange(n)[None, :]
    segment_start = np.maximum.accumulate(np.where(restart, positions, 0), axis=1)
    chosen = np.take_along_axis(starts, segment_start, axis=1)
    return (chosen + (positions - segment_start)) % n


def _lift(tight: np.ndarray, outcome: np.ndarray) -> tuple[float, float, float]:
    """(conditional rate, unconditional rate, lift) on one sample of months."""
    n_tight = int(tight.sum())
    unconditional = float(outcome.mean()) if outcome.size else float("nan")
    if n_tight == 0 or unconditional == 0.0:
        return float("nan"), unconditional, float("nan")
    conditional = float(outcome[tight].mean())
    return conditional, unconditional, conditional / unconditional


def section_b(source: Any, yoy: np.ndarray) -> dict[str, Any]:
    labels = np.asarray(source.labels)
    n = source.n_rows
    base_eligible = _eligible_mask(yoy, n, K_MONTHS)
    tight_defs = _tight_definitions(source, yoy)
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))

    states = {
        "cri_only": labels == "CRI",
        "rec_plus_cri": np.isin(labels, ["REC", "CRI"]),
    }
    outcomes: dict[str, np.ndarray] = {}
    for name, state in states.items():
        onset_at = _onset_flags(state)
        outcomes[name] = _followed_within(onset_at, np.flatnonzero(base_eligible), K_MONTHS)

    tight_primary = (
        cast(np.ndarray, tight_defs["curve_inversion_10y_2y"]["score"])[base_eligible] > 0.0
    )
    #: The share of eligible months the primary definition calls tight. Every
    #: alternative below is ALSO evaluated at this same share, because a lift is
    #: mechanically diluted by calling more months tight -- comparing a 19%-of-
    #: months indicator with a 70%-of-months indicator measures the cut-off, not
    #: the indicator.
    primary_base_rate = float(tight_primary.mean())

    # ---- point estimates, primary tightness definition, both downturn defs ----
    point: dict[str, Any] = {}
    for name, outcome in outcomes.items():
        conditional, unconditional, lift = _lift(tight_primary, outcome)
        point[name] = {
            "conditional_rate": _f(conditional),
            "unconditional_rate": _f(unconditional),
            "lift": _f(lift),
            "tight_months": int(tight_primary.sum()),
            "eligible_months": int(outcome.size),
            "tight_months_followed_by_onset": int(outcome[tight_primary].sum()),
            "eligible_months_followed_by_onset": int(outcome.sum()),
        }

    # ---- block bootstrap: one index tape per block length, shared by both defs
    bootstrap: dict[str, Any] = {}
    for block in sorted(BLOCK_LENGTHS_MONTHS):
        index = _stationary_bootstrap_indices(rng, int(tight_primary.size), block, N_BOOTSTRAP)
        tight_draws = tight_primary[index]
        per_def: dict[str, Any] = {}
        for name, outcome in outcomes.items():
            draws_outcome = outcome[index]
            lifts = np.full(N_BOOTSTRAP, np.nan)
            conds = np.full(N_BOOTSTRAP, np.nan)
            uncs = np.full(N_BOOTSTRAP, np.nan)
            for b in range(N_BOOTSTRAP):
                conds[b], uncs[b], lifts[b] = _lift(tight_draws[b], draws_outcome[b])
            per_def[name] = {
                "lift_ci95": _quantiles(lifts),
                "conditional_rate_ci95": _quantiles(conds),
                "unconditional_rate_ci95": _quantiles(uncs),
                "draws_used": int(np.isfinite(lifts).sum()),
                "draws_dropped_no_tight_month": int(N_BOOTSTRAP - np.isfinite(lifts).sum()),
            }
        bootstrap[f"block_{block}m"] = per_def

    # ---- sensitivity to the tight-policy definition (point estimates only) ----
    tight_sensitivity: dict[str, Any] = {}
    for tname, spec in tight_defs.items():
        defined = cast(np.ndarray, spec["defined"])
        mask = base_eligible & defined
        sub = mask[base_eligible]  # position of the kept months inside the base population
        score = cast(np.ndarray, spec["score"])[mask]
        threshold = float(np.quantile(score, 1.0 - primary_base_rate))
        arms = {
            "native_cut": score > 0.0,
            "base_rate_matched": score > threshold,
        }
        entry: dict[str, Any] = {
            "description": spec["description"],
            "eligible_months": int(mask.sum()),
            "base_rate_matched_score_threshold": _f(threshold),
            "arms": {},
        }
        for arm_name, flag in arms.items():
            per_def: dict[str, Any] = {}
            for name, outcome in outcomes.items():
                conditional, unconditional, lift = _lift(flag, outcome[sub])
                per_def[name] = {
                    "conditional_rate": _f(conditional),
                    "unconditional_rate": _f(unconditional),
                    "lift": _f(lift),
                }
            entry["arms"][arm_name] = {
                "tight_months": int(flag.sum()),
                "tight_share": _f(float(flag.mean())),
                "definitions": per_def,
            }
        tight_sensitivity[tname] = entry

    return {
        "k_months": K_MONTHS,
        "primary_tight_definition": "curve_inversion_10y_2y",
        "primary_tight_base_rate": _f(primary_base_rate),
        "primary_block_months": PRIMARY_BLOCK_MONTHS,
        "n_bootstrap": N_BOOTSTRAP,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_method": (
            "stationary (Politis-Romano) block bootstrap over the eligible months' "
            "(tight, downturn-within-12m) pairs; geometric block lengths with the "
            "stated mean, wrap-around, 2.5/97.5 percentile interval"
        ),
        "point_estimates": point,
        "bootstrap_ci95": bootstrap,
        "tight_definition_sensitivity": tight_sensitivity,
    }


# --------------------------------------------------------------------------- #
# C -- regime durations
# --------------------------------------------------------------------------- #


def section_c(source: Any, cells: np.ndarray, era_threshold_pp: float) -> dict[str, Any]:
    """Completed dwell lengths per quadrant, with censored spells split out."""
    spells = spells_from_labels(cells)
    n_spells = len(spells)
    completed: dict[int, list[int]] = {i: [] for i in range(len(QUADRANTS))}
    censored: dict[int, list[dict[str, Any]]] = {i: [] for i in range(len(QUADRANTS))}
    months = _month_labels(source.dates)

    for position, (state, start, length) in enumerate(spells):
        if state < 0:
            continue
        # Left-censored: the spell opens the panel, or opens straight out of a
        # run of rows with no defined quadrant (the first 12 months, where the
        # trailing YoY does not exist yet) -- we cannot see when it really began.
        # Right-censored: the spell is still running at the panel's last row.
        left = position == 0 or spells[position - 1][0] < 0
        right = position == n_spells - 1
        record = {
            "start": months[start],
            "end": months[start + length - 1],
            "months": int(length),
            "left_censored": bool(left),
            "right_censored": bool(right),
        }
        if left or right:
            censored[state].append(record)
        else:
            completed[state].append(int(length))

    # The pilot's own B4 anchor kept EVERY spell, censored ones included
    # (scripts/spine_pilot_seal._b4_dwell_medians). Reproduced here so the
    # completed-only figures below can be read against the sealed number rather
    # than mistaken for a restatement of it.
    all_spells: dict[int, list[int]] = {i: [] for i in range(len(QUADRANTS))}
    for state, _start, length in spells:
        if state >= 0:
            all_spells[state].append(int(length))

    per_quadrant: dict[str, Any] = {}
    for i, quadrant in enumerate(QUADRANTS):
        months = np.array(sorted(completed[i]), dtype=np.float64)
        quarters = months / 3.0
        if months.size:
            q25_m, q50_m, q75_m = (float(x) for x in np.percentile(months, [25, 50, 75]))
        else:
            q25_m = q50_m = q75_m = float("nan")
        per_quadrant[quadrant] = {
            "n_completed_spells": int(months.size),
            "n_censored_spells": len(censored[i]),
            "censored_spells": censored[i],
            "median_months": _f(q50_m),
            "iqr_months": [_f(q25_m), _f(q75_m)],
            "median_quarters": _f(q50_m / 3.0),
            "iqr_quarters": [_f(q25_m / 3.0), _f(q75_m / 3.0)],
            "sorted_spells_months": [int(x) for x in months],
            "sorted_spells_quarters": [_f(x) for x in quarters],
            "sparse": bool(months.size < 20),
            "all_spells_including_censored": {
                "n_spells": len(all_spells[i]),
                "median_months": _f(float(np.median(all_spells[i]))) if all_spells[i] else None,
                "sorted_spells_months": sorted(all_spells[i]),
            },
        }

    return {
        "era_threshold_pp": _f(era_threshold_pp),
        "quadrant_legend": list(QUADRANTS),
        "undefined_quadrant_months": int((cells < 0).sum()),
        "unit_note": (
            "months is the unit the spine pilot's own B4 anchor is stated in "
            "(panel_dwell_medians = [5, 4, 9, 6] MONTHS, "
            "docs/superpowers/specs/spine-pilot-prereg.json); quarters = months / 3"
        ),
        "pilot_b4_panel_dwell_medians_months": [5.0, 4.0, 9.0, 6.0],
        "per_quadrant": per_quadrant,
    }


# --------------------------------------------------------------------------- #
# D -- allocation episode facts
# --------------------------------------------------------------------------- #


class _OneRowEnsemble:
    """Adapter so the sealed derived-series transform can run on one panel column.

    ``ah.eval.metrics.tails.derived_series_values`` asks its argument for
    ``factor(name)`` and expects a ``(n_paths, months)`` slab. The historical
    panel is one path, so this hands it a ``(1, T)`` view of the requested
    column. Nothing about the sealed transform is reimplemented here.
    """

    def __init__(self, columns: dict[str, np.ndarray]) -> None:
        self._columns = columns

    def factor(self, name: str) -> np.ndarray:
        return self._columns[name].reshape(1, -1)


def _asset_returns(source: Any) -> dict[str, np.ndarray | None]:
    """The monthly total-return series section D conditions on, in decimals."""
    names = list(source.factor_names)
    values = np.asarray(source.values)
    ust10 = values[:, names.index("ust_10y")]
    bond = derived_series_values(
        cast(Any, _OneRowEnsemble({"ust_10y": ust10})),
        load_derived_series()["govt_tr_10y"],
    )[0]
    return {
        "equities": values[:, names.index("equity_mkt")],
        "bonds": bond,
        "commodities": values[:, names.index("commodities")],
        "real_assets": None,
    }


def _return_stats(returns: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    sample = returns[mask]
    if sample.size == 0:
        return {
            "months": 0,
            "ann_mean_arith_pct": None,
            "ann_mean_geom_pct": None,
            "mean_pct": None,
        }
    mean = float(sample.mean())
    return {
        "months": int(sample.size),
        "mean_pct": _f(mean * 100.0),
        "ann_mean_arith_pct": _f(mean * 12.0 * 100.0),
        "ann_mean_geom_pct": _f(((1.0 + mean) ** 12 - 1.0) * 100.0),
        "ann_vol_pct": _f(float(sample.std(ddof=1)) * np.sqrt(12.0) * 100.0)
        if sample.size > 1
        else None,
    }


def _block_of_returns(returns: dict[str, np.ndarray | None], mask: np.ndarray) -> dict[str, Any]:
    """Per-asset stats plus the two spreads, over the months in ``mask``."""
    stats: dict[str, Any] = {}
    for asset, series in returns.items():
        stats[asset] = None if series is None else _return_stats(series, mask)
    bonds = stats.get("bonds")
    spreads: dict[str, Any] = {}
    for asset, key in (
        ("commodities", "commodities_minus_bonds"),
        ("real_assets", "real_assets_minus_bonds"),
    ):
        arm = stats.get(asset)
        if arm is None or bonds is None or arm["ann_mean_arith_pct"] is None:
            spreads[key] = None
        else:
            spreads[key] = _f(arm["ann_mean_arith_pct"] - bonds["ann_mean_arith_pct"])
    stats["spreads_ann_arith_pp"] = spreads
    return stats


def _correlation(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float | None:
    if int(mask.sum()) < 3:
        return None
    return _f(float(np.corrcoef(a[mask], b[mask])[0, 1]))


def section_d(source: Any, yoy: np.ndarray) -> dict[str, Any]:
    returns = _asset_returns(source)
    month_labels = _month_labels(source.dates)
    n = source.n_rows
    defined = ~np.isnan(yoy)  # also excludes the bond series' warm-up month 0

    equities = cast(np.ndarray, returns["equities"])
    bonds = cast(np.ndarray, returns["bonds"])

    # ---- (i) inflation-state conditioning ------------------------------------
    by_threshold: dict[str, Any] = {}
    for threshold in INFLATION_THRESHOLDS_PP:
        high = defined & (yoy >= threshold)
        low = defined & (yoy < threshold)
        by_threshold[f"cpi_yoy_ge_{threshold:g}pct"] = {
            "threshold_pp": threshold,
            "is_primary": threshold == PRIMARY_INFLATION_THRESHOLD_PP,
            "high_inflation": _block_of_returns(returns, high),
            "low_inflation": _block_of_returns(returns, low),
            "stock_bond_correlation": {
                "high_inflation": _correlation(equities, bonds, high),
                "low_inflation": _correlation(equities, bonds, low),
            },
        }

    # ---- named episodes -------------------------------------------------------
    periods = pd.PeriodIndex(source.dates, freq="M")
    episodes: dict[str, Any] = {}
    for key, start, end, kind, note in NAMED_EPISODES:
        window = np.asarray(
            (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))
        )
        mask = window & defined
        covered = int(mask.sum())
        expected = (
            (pd.Period(end, freq="M") - pd.Period(start, freq="M")).n + 1  # type: ignore[attr-defined]
        )
        if covered == 0:
            episodes[key] = {
                "span": [start, end],
                "inflation_kind": kind,
                "note": note,
                "available": False,
                "months_in_panel": 0,
                "months_declared": int(expected),
                "unavailable_reason": (
                    "no month of this episode is inside the panel. The panel is the "
                    "campaign train+validation span (1953-04..2020-12); 2021-01 onward "
                    "is the sealed HOLDOUT split (ah.splits.HOLDOUT), which this script "
                    "does not and must not open."
                ),
                "returns": None,
                "stock_bond_correlation": None,
                "mean_cpi_yoy_pct": None,
            }
            continue
        episodes[key] = {
            "span": [start, end],
            "inflation_kind": kind,
            "note": note,
            "available": True,
            "months_in_panel": covered,
            "months_declared": int(expected),
            "unavailable_reason": None,
            "mean_cpi_yoy_pct": _f(float(yoy[mask].mean())),
            "returns": _block_of_returns(returns, mask),
            "stock_bond_correlation": _correlation(equities, bonds, mask),
        }

    # ---- (ii) rolling stock-bond correlation ---------------------------------
    window = ROLLING_CORR_WINDOW_MONTHS
    rolling = np.full(n, np.nan)
    for t in range(window - 1, n):
        lo = t - window + 1
        if not defined[lo : t + 1].all():
            continue
        rolling[t] = float(np.corrcoef(equities[lo : t + 1], bonds[lo : t + 1])[0, 1])
    rolling_defined = ~np.isnan(rolling)
    rolling_summary: dict[str, Any] = {
        "window_months": window,
        "classification": (
            "each window is assigned to the inflation state of its FINAL month -- "
            "the month the correlation is 'as of'"
        ),
        "windows_defined": int(rolling_defined.sum()),
        "first_window_end": month_labels[int(np.flatnonzero(rolling_defined)[0])]
        if rolling_defined.any()
        else None,
        "by_threshold": {},
    }
    for threshold in INFLATION_THRESHOLDS_PP:
        high = rolling_defined & (yoy >= threshold)
        low = rolling_defined & (yoy < threshold)
        rolling_summary["by_threshold"][f"cpi_yoy_ge_{threshold:g}pct"] = {
            "threshold_pp": threshold,
            "high_inflation": {
                "windows": int(high.sum()),
                "share_positive": _f(float((rolling[high] > 0).mean())) if high.any() else None,
                "mean_correlation": _f(float(rolling[high].mean())) if high.any() else None,
            },
            "low_inflation": {
                "windows": int(low.sum()),
                "share_positive": _f(float((rolling[low] > 0).mean())) if low.any() else None,
                "mean_correlation": _f(float(rolling[low].mean())) if low.any() else None,
            },
        }

    return {
        "population_note": (
            "every statistic below is taken over panel months with a defined trailing "
            "12-month CPI inflation reading, i.e. from the 13th panel month onward -- "
            "which also drops the bond series' warm-up month (the sealed govt_tr_10y "
            "transform sets r_0 = 0.0, a placeholder, not a return)"
        ),
        "asset_sources": {
            "equities": "panel factor 'equity_mkt' -- Fama-French Mkt-RF + RF, a total return",
            "bonds": (
                "sealed derived series 'govt_tr_10y' applied to the panel's ust_10y level: "
                "r_t = 0.01 * (y_{t-1}/12 - 8.5 * (y_t - y_{t-1})). The panel carries no "
                "bond total-return factor, only the yield level"
            ),
            "commodities": (
                "panel factor 'commodities' -- AQR equal-weight commodity excess return + "
                "the one-month bill, a total return"
            ),
            "real_assets": None,
        },
        "real_assets_note": (
            "NOT AVAILABLE. The catalog registers no monthly REIT or real-asset "
            "total-return series: an intake schema exists (ah/data/schemas/"
            "nareit_returns.py) but no nareit series is registered in the catalog, and "
            "the only real-asset history present (jst.usa_housing_tr) is ANNUAL. Every "
            "real-asset field in this file is null by construction, never substituted."
        ),
        "annualisation_note": (
            "ann_mean_arith_pct = 12 x the mean monthly return; ann_mean_geom_pct = "
            "(1 + mean monthly return)^12 - 1. Spreads are taken on the ARITHMETIC "
            "annualisation because only that one is additive across assets"
        ),
        "inflation_states": by_threshold,
        "named_episodes": episodes,
        "rolling_stock_bond_correlation": rolling_summary,
    }


# --------------------------------------------------------------------------- #
# E -- the clockwise-ordering fraction (OPEN-1)
# --------------------------------------------------------------------------- #

#: ``CLOCKWISE`` as a 4x4 lookup, so a whole bootstrap draw can be scored at
#: once. Built FROM the imported frozenset, never restated by hand.
_CLOCKWISE_MATRIX = np.zeros((len(QUADRANTS), len(QUADRANTS)), dtype=bool)
for _a, _b in CLOCKWISE:
    _CLOCKWISE_MATRIX[_a, _b] = True


def _clockwise_counts(prev: np.ndarray, nxt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(transitions, clockwise transitions) over aligned quadrant-pair arrays.

    The transition definition is the pilot's, verbatim in effect from
    ``scripts/spine_pilot_seal._b4_clockwise_fraction``: a pair counts when both
    quadrants are defined (``>= 0``) and DIFFER -- a month that stays put is not
    a transition and neither is a month with no defined quadrant. Clockwise
    membership is ``ah.gen.spine.CLOCKWISE`` (recovery -> expansion ->
    stagflation -> recession -> recovery), imported above.
    """
    valid = (prev >= 0) & (nxt >= 0) & (prev != nxt)
    safe_prev = np.where(valid, prev, 0)
    safe_nxt = np.where(valid, nxt, 0)
    clockwise = valid & _CLOCKWISE_MATRIX[safe_prev, safe_nxt]
    axis = prev.ndim - 1
    return valid.sum(axis=axis), clockwise.sum(axis=axis)


def section_e(cells: np.ndarray, pilot_sealed_fraction: float) -> dict[str, Any]:
    """OPEN-1: the clockwise fraction on THIS vintage, with an error bar.

    The point estimate reuses the pilot's own transition and quadrant
    definitions (``ah.gen.spine.panel_quadrant`` for the cells, which ``main``
    computes once, and ``ah.gen.spine.CLOCKWISE`` for the ordering), so the only
    thing that can move it relative to the round-one seal is the panel itself.

    The interval is the same stationary block bootstrap section B uses, run over
    the panel's month sequence: a draw pastes together randomly chosen runs of
    consecutive real months, and a pair of adjacent drawn months is scored ONLY
    when it is a genuine consecutive pair of the real panel
    (``index[j] == index[j-1] + 1``). Pairs that straddle a block join, and the
    wrap-around pair, are dropped rather than scored -- a join between two
    unrelated months would invent a transition that never happened and would
    corrupt exactly the statistic being measured. About one pair in
    ``mean_block`` is dropped this way, which is why each draw's transition
    count is slightly below the panel's own.
    """
    n = int(cells.size)
    n_trans, n_cw = _clockwise_counts(cells[:-1], cells[1:])
    total = int(n_trans)
    clockwise = int(n_cw)
    fraction = float(clockwise) / total if total else float("nan")
    # The binomial standard error the round-one seal disclosed (~0.059). It
    # treats the 68 transitions as independent, which the bootstrap below does
    # not; both are reported so the reader can see how much the clumping costs.
    binomial_se = float(np.sqrt(fraction * (1.0 - fraction) / total)) if total else float("nan")

    rng = np.random.Generator(np.random.PCG64(ORDERING_BOOTSTRAP_SEED))
    bootstrap: dict[str, Any] = {}
    for block in sorted(BLOCK_LENGTHS_MONTHS):
        index = _stationary_bootstrap_indices(rng, n, block, N_BOOTSTRAP)
        prev_idx, next_idx = index[:, :-1], index[:, 1:]
        genuine = next_idx == (prev_idx + 1)
        prev_cells = np.where(genuine, cells[prev_idx], -1)
        next_cells = np.where(genuine, cells[next_idx], -1)
        draw_total, draw_cw = _clockwise_counts(prev_cells, next_cells)
        fractions = np.where(draw_total > 0, draw_cw / np.maximum(draw_total, 1), np.nan)
        bootstrap[f"block_{block}m"] = {
            "clockwise_fraction_ci95": _quantiles(fractions),
            "mean_transitions_per_draw": _f(float(draw_total.mean())),
            "draws_used": int(np.isfinite(fractions).sum()),
            "draws_dropped_no_transition": int(N_BOOTSTRAP - np.isfinite(fractions).sum()),
        }

    # A comparison the reader needs, because the block interval comes back
    # NARROWER than the naive one -- the opposite of what clustering usually
    # does. The cause is measurable and reported beside it: the clockwise
    # indicator is NEGATIVELY autocorrelated from one transition to the next
    # (the clock backtracks and then returns), so a resample that keeps
    # consecutive transitions together carries more information per transition
    # than one that scrambles them, not less.
    transitions = np.flatnonzero((cells[:-1] >= 0) & (cells[1:] >= 0) & (cells[:-1] != cells[1:]))
    indicator = _CLOCKWISE_MATRIX[cells[transitions], cells[transitions + 1]].astype(np.float64)
    lag1 = (
        _f(float(np.corrcoef(indicator[:-1], indicator[1:])[0, 1])) if indicator.size > 2 else None
    )
    iid_draws = indicator[rng.integers(0, indicator.size, size=(N_BOOTSTRAP, indicator.size))]
    iid_ci = _quantiles(iid_draws.mean(axis=1))

    primary = bootstrap[f"block_{PRIMARY_BLOCK_MONTHS}m"]["clockwise_fraction_ci95"]
    return {
        "definition": (
            "over consecutive panel rows where both quadrants are defined and DIFFER, "
            "the share of (previous, next) pairs in ah.gen.spine.CLOCKWISE "
            "(recovery -> expansion -> stagflation -> recession -> recovery). Quadrants "
            "from ah.gen.spine.panel_quadrant, era threshold from ah.gen.spine.fit_hazard; "
            "the transition rule is scripts/spine_pilot_seal._b4_clockwise_fraction's"
        ),
        "clockwise_fraction": _f(fraction),
        "n_transitions": total,
        "n_clockwise_transitions": clockwise,
        "binomial_se": _f(binomial_se),
        "pilot_sealed_fraction": _f(pilot_sealed_fraction),
        "reproduces_pilot_seal_exactly": bool(fraction == pilot_sealed_fraction),
        "primary_block_months": PRIMARY_BLOCK_MONTHS,
        "n_bootstrap": N_BOOTSTRAP,
        "bootstrap_seed": ORDERING_BOOTSTRAP_SEED,
        "bootstrap_method": (
            "stationary (Politis-Romano) block bootstrap over the panel's month "
            "sequence; only genuine consecutive-month pairs are scored, so block joins "
            "cannot invent a transition; 2.5/97.5 percentile interval"
        ),
        "bootstrap_ci95": bootstrap,
        "ci95_lower_edge": primary["lo"],
        "ci95_upper_edge": primary["hi"],
        "one_se_below_point": _f(fraction - binomial_se) if total else None,
        "transition_lag1_autocorrelation": lag1,
        "iid_over_transitions_ci95": iid_ci,
        "width_note": (
            "the block interval is NARROWER than the i.i.d.-over-transitions one, which "
            "is unusual and has a measured cause: transition_lag1_autocorrelation is "
            "negative, i.e. a counter-clockwise move tends to be followed by a clockwise "
            "one (the clock backtracks and returns). Keeping consecutive transitions "
            "together therefore carries MORE information per transition than scrambling "
            "them. Both intervals are published; the bar is cut from the block one, on "
            "the same machinery as every other interval in this file"
        ),
        "bar_note": (
            "the O1 bar is cut from ci95_lower_edge: a generated clockwise fraction at "
            "or above it is CONSISTENT WITH history, which is what the bar can honestly "
            "demand. one_se_below_point is the tighter alternative the exam's drafter "
            "named (anchor minus one standard error); both are published so the owner "
            "can see the cost of each"
        ),
    }


# --------------------------------------------------------------------------- #
# F -- intervals on the stock-bond correlation gap (OPEN-2)
# --------------------------------------------------------------------------- #


def _corr_from_sums(
    count: np.ndarray,
    sum_x: np.ndarray,
    sum_y: np.ndarray,
    sum_xx: np.ndarray,
    sum_yy: np.ndarray,
    sum_xy: np.ndarray,
) -> np.ndarray:
    """Pearson correlation from sufficient statistics, NaN where undefined.

    Algebraically identical to ``numpy.corrcoef`` on the same sample (both use
    the population moments; the ddof cancels in the ratio). Computed from sums
    so a whole bootstrap draw, or a whole ensemble of generated decades, can be
    scored without materialising its months.
    """
    with np.errstate(invalid="ignore", divide="ignore"):
        n = np.where(count >= 3, count.astype(np.float64), np.nan)
        cov = sum_xy / n - (sum_x / n) * (sum_y / n)
        var_x = sum_xx / n - (sum_x / n) ** 2
        var_y = sum_yy / n - (sum_y / n) ** 2
        out = cov / np.sqrt(var_x * var_y)
    return np.where(np.isfinite(out), out, np.nan)


def _corr_over_mask(x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Correlation of ``x`` and ``y`` over ``mask``, along the last axis."""
    axis = x.ndim - 1
    m = mask.astype(np.float64)
    return _corr_from_sums(
        mask.sum(axis=axis),
        (x * m).sum(axis=axis),
        (y * m).sum(axis=axis),
        (x * x * m).sum(axis=axis),
        (y * y * m).sum(axis=axis),
        (x * y * m).sum(axis=axis),
    )


def section_f(source: Any, yoy: np.ndarray) -> dict[str, Any]:
    """OPEN-2: block-bootstrap intervals on the two A2 differences.

    (a) the high-minus-low stock-bond CORRELATION difference and (b) the
    high-minus-low difference in the SHARE OF 36-MONTH ROLLING WINDOWS with a
    positive correlation, both at the primary 4% line, both by the same
    stationary block bootstrap and the same 12/24/36-month block lengths as the
    transmission lift in section B.

    Two populations, because the two statistics live on different rows. (a) is
    taken over months with a defined trailing inflation reading, resampled in
    blocks. (b) is taken over ROLLING WINDOWS, one per month, each carrying its
    end month's inflation state -- so a block of consecutive months is a block
    of consecutive windows and the block lengths mean the same thing on both.
    """
    returns = _asset_returns(source)
    equities = cast(np.ndarray, returns["equities"])
    bonds = cast(np.ndarray, returns["bonds"])
    threshold = PRIMARY_INFLATION_THRESHOLD_PP
    defined = ~np.isnan(yoy)

    # ---- (a) the level population -------------------------------------------
    level_rows = np.flatnonzero(defined)
    lvl_e = equities[level_rows]
    lvl_b = bonds[level_rows]
    lvl_high = yoy[level_rows] >= threshold

    corr_high = float(_corr_over_mask(lvl_e, lvl_b, lvl_high))
    corr_low = float(_corr_over_mask(lvl_e, lvl_b, ~lvl_high))
    level_point = corr_high - corr_low

    # ---- (b) the rolling-window population ----------------------------------
    n = source.n_rows
    window = ROLLING_CORR_WINDOW_MONTHS
    rolling = np.full(n, np.nan)
    for t in range(window - 1, n):
        lo = t - window + 1
        if not defined[lo : t + 1].all():
            continue
        rolling[t] = float(np.corrcoef(equities[lo : t + 1], bonds[lo : t + 1])[0, 1])
    win_rows = np.flatnonzero(~np.isnan(rolling))
    win_positive = rolling[win_rows] > 0.0
    win_high = yoy[win_rows] >= threshold

    share_high = float(win_positive[win_high].mean())
    share_low = float(win_positive[~win_high].mean())
    share_point = share_high - share_low

    # ---- the bootstrap -------------------------------------------------------
    rng = np.random.Generator(np.random.PCG64(CORRELATION_BOOTSTRAP_SEED))
    bootstrap: dict[str, Any] = {}
    for block in sorted(BLOCK_LENGTHS_MONTHS):
        li = _stationary_bootstrap_indices(rng, int(level_rows.size), block, N_BOOTSTRAP)
        draw_high = lvl_high[li]
        d_corr_high = _corr_over_mask(lvl_e[li], lvl_b[li], draw_high)
        d_corr_low = _corr_over_mask(lvl_e[li], lvl_b[li], ~draw_high)
        level_draws = d_corr_high - d_corr_low

        wi = _stationary_bootstrap_indices(rng, int(win_rows.size), block, N_BOOTSTRAP)
        w_high = win_high[wi]
        w_pos = win_positive[wi]
        n_high = w_high.sum(axis=1)
        n_low = (~w_high).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            d_share_high = np.where(n_high > 0, (w_pos & w_high).sum(axis=1) / n_high, np.nan)
            d_share_low = np.where(n_low > 0, (w_pos & ~w_high).sum(axis=1) / n_low, np.nan)
        share_draws = d_share_high - d_share_low

        bootstrap[f"block_{block}m"] = {
            "correlation_difference_ci95": _quantiles(level_draws),
            "correlation_high_ci95": _quantiles(d_corr_high),
            "correlation_low_ci95": _quantiles(d_corr_low),
            "share_positive_difference_ci95": _quantiles(share_draws),
            "share_positive_high_ci95": _quantiles(d_share_high),
            "share_positive_low_ci95": _quantiles(d_share_low),
            "draws_used_correlation": int(np.isfinite(level_draws).sum()),
            "draws_used_share_positive": int(np.isfinite(share_draws).sum()),
        }

    primary = bootstrap[f"block_{PRIMARY_BLOCK_MONTHS}m"]
    return {
        "threshold_pp": threshold,
        "primary_block_months": PRIMARY_BLOCK_MONTHS,
        "n_bootstrap": N_BOOTSTRAP,
        "bootstrap_seed": CORRELATION_BOOTSTRAP_SEED,
        "bootstrap_method": (
            "stationary (Politis-Romano) block bootstrap, the same machinery and the "
            "same 12/24/36-month block lengths as b_transmission_lift; the level "
            "statistic is resampled over months, the rolling-window statistic over "
            "windows (one per month, each carrying its end month's inflation state); "
            "2.5/97.5 percentile interval"
        ),
        "correlation_level": {
            "high_inflation": _f(corr_high),
            "low_inflation": _f(corr_low),
            "difference": _f(level_point),
            "months_high": int(lvl_high.sum()),
            "months_low": int((~lvl_high).sum()),
            "ci95_lower_edge": primary["correlation_difference_ci95"]["lo"],
            "ci95_upper_edge": primary["correlation_difference_ci95"]["hi"],
        },
        "share_of_rolling_windows_positive": {
            "window_months": window,
            "high_inflation": _f(share_high),
            "low_inflation": _f(share_low),
            "difference": _f(share_point),
            "windows_high": int(win_high.sum()),
            "windows_low": int((~win_high).sum()),
            "ci95_lower_edge": primary["share_positive_difference_ci95"]["lo"],
            "ci95_upper_edge": primary["share_positive_difference_ci95"]["hi"],
        },
        "bootstrap_ci95": bootstrap,
        "bar_note": (
            "A2(i)'s margin is cut from correlation_level.ci95_lower_edge: the generated "
            "high-minus-low correlation difference must exceed the lower edge of the "
            "historical interval, i.e. must be CONSISTENT WITH history rather than exceed "
            "a point estimate that is itself noisy. The share-of-windows interval is "
            "published as the evidence behind A2(ii)'s 80%/65% edges, which are unchanged"
        ),
    }


# --------------------------------------------------------------------------- #
# G -- intervals on the per-season dwell medians (OPEN-3)
# --------------------------------------------------------------------------- #


def section_g(regime_durations: dict[str, Any]) -> dict[str, Any]:
    """OPEN-3: a bootstrap interval for each season's completed-spell median.

    **Spells are resampled, not months.** A spell is one observation of one
    dwell: its months are not independent of each other -- they are the same
    dwell, seen month by month -- so resampling months would treat a single
    16-month stagflation as sixteen facts and would produce an interval far too
    narrow. The completed spells, on the other hand, are the independent units
    the median is computed over, so an ordinary i.i.d. resample of each season's
    completed-spell list is the right bootstrap and no block structure is needed.

    Nothing here changes the +-1 quarter tolerance. The intervals exist so a
    reader can see, per season, whether that tolerance is wider than the
    anchor's own sampling wobble -- and where it is not, the JSON says so in
    ``tolerance_at_least_as_wide``.
    """
    rng = np.random.Generator(np.random.PCG64(DWELL_BOOTSTRAP_SEED))
    tolerance_months = DWELL_TOLERANCE_MONTHS  # +-1 quarter, the smallest play unit
    per_quadrant: dict[str, Any] = {}
    for quadrant in QUADRANTS:
        spells = np.asarray(
            regime_durations["per_quadrant"][quadrant]["sorted_spells_months"],
            dtype=np.float64,
        )
        n_spells = int(spells.size)
        if n_spells == 0:
            per_quadrant[quadrant] = {"n_completed_spells": 0, "median_months": None}
            continue
        draws = rng.integers(0, n_spells, size=(N_DWELL_BOOTSTRAP, n_spells))
        medians = np.median(spells[draws], axis=1)
        ci = _quantiles(medians)
        point = float(np.median(spells))
        lo = cast(float, ci["lo"])
        hi = cast(float, ci["hi"])
        half_width = max(point - lo, hi - point)
        per_quadrant[quadrant] = {
            "n_completed_spells": n_spells,
            "median_months": _f(point),
            "median_quarters": _f(point / 3.0),
            "ci95_months": [ci["lo"], ci["hi"]],
            "ci95_quarters": [_f(lo / 3.0), _f(hi / 3.0)],
            "ci95_half_width_months": _f(half_width),
            "ci95_half_width_quarters": _f(half_width / 3.0),
            "bootstrap_median_of_medians_months": ci["median"],
            "tolerance_months": tolerance_months,
            "tolerance_at_least_as_wide": bool(tolerance_months >= half_width),
            "tolerance_minus_half_width_months": _f(tolerance_months - half_width),
        }
    return {
        "n_bootstrap": N_DWELL_BOOTSTRAP,
        "bootstrap_seed": DWELL_BOOTSTRAP_SEED,
        "resampling_unit": "completed spells (i.i.d.), NOT months",
        "resampling_unit_note": (
            "a spell's months are one observation of one dwell, not many independent "
            "observations of it; resampling months would understate the interval. The "
            "completed spells are the units the median is taken over, so they are what "
            "is resampled -- with replacement, one draw of the same size as the "
            "observed list, 2.5/97.5 percentiles over the draws' medians"
        ),
        "tolerance_note": (
            "tolerance_months = 3.0 is the exam's +-1 quarter dwell tolerance, unchanged "
            "by this measurement (its justification is the game's smallest play unit, not "
            "sampling noise). tolerance_at_least_as_wide records, per season, whether the "
            "tolerance is at least as wide as the median's own 95% sampling wobble"
        ),
        "per_quadrant": per_quadrant,
    }


# --------------------------------------------------------------------------- #
# H -- generated-side power (OPEN-4)
# --------------------------------------------------------------------------- #


def _prefix(values: np.ndarray) -> np.ndarray:
    """``out[i] = values[:i].sum()`` -- one extra leading zero, so a closed
    interval's sum is ``out[hi + 1] - out[lo]`` with no special cases."""
    return np.concatenate([[0.0], np.cumsum(values.astype(np.float64))])


def _window_sums(values: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Sum of ``values`` over each closed row range ``[lo[i], hi[i]]``."""
    pre = _prefix(values)
    return pre[hi + 1] - pre[lo]


def _pooled_median_from_histogram(hist: np.ndarray) -> np.ndarray:
    """Median of the multiset a length-histogram describes, per row.

    ``hist[i, L]`` is how many spells of length ``L`` ensemble ``i`` pooled.
    Reproduces ``numpy.median`` exactly (the mean of the two middle values when
    the count is even, the middle value when it is odd) without materialising
    the pooled list.
    """
    cum = np.cumsum(hist, axis=1)
    total = cum[:, -1]
    lengths = np.arange(hist.shape[1], dtype=np.float64)
    lower_rank = np.where(total > 0, (total - 1) // 2, 0)
    upper_rank = np.where(total > 0, total // 2, 0)
    last = hist.shape[1] - 1
    lower_idx = np.minimum((cum <= lower_rank[:, None]).sum(axis=1), last)
    upper_idx = np.minimum((cum <= upper_rank[:, None]).sum(axis=1), last)
    median = 0.5 * (lengths[lower_idx] + lengths[upper_idx])
    return np.where(total > 0, median, np.nan)


def _decade_spell_histogram(cells: np.ndarray, lo: int, hi: int, max_len: int) -> np.ndarray:
    """``(4, max_len + 1)`` counts of COMPLETED spell lengths inside ``[lo, hi]``.

    The exam's completed-spell rule applied to one generated decade: a run that
    touches either edge of the decade's usable window has an unknown true length
    and is dropped, exactly as the two censored panel spells are dropped from
    the anchors.
    """
    out = np.zeros((len(QUADRANTS), max_len + 1), dtype=np.float64)
    segment = cells[lo : hi + 1]
    runs = spells_from_labels(segment.astype(np.int8))
    for position, (state, _start, length) in enumerate(runs):
        if state < 0 or position == 0 or position == len(runs) - 1:
            continue
        if runs[position - 1][0] < 0 or runs[position + 1][0] < 0:
            continue  # borders an undefined stretch: same censoring problem
        out[state, int(length)] += 1.0
    return out


def _min_n_seeds(grid: tuple[int, ...], probabilities: np.ndarray) -> int | None:
    for n, p in zip(grid, probabilities, strict=True):
        if p >= POWER_TARGET:
            return int(n)
    return None


def exam_bars(
    transmission: dict[str, Any],
    regime_durations: dict[str, Any],
    allocation: dict[str, Any],
    ordering: dict[str, Any],
    correlation_intervals: dict[str, Any],
) -> dict[str, Any]:
    """The ten bars' numeric thresholds, DERIVED from the sections above.

    Nothing here restates a number by hand: T1's band is section B's primary
    bootstrap interval, each dwell band is section C's median plus or minus the
    tolerance, A1's containment range is the min and max episode spread from
    section D, O1's bar is section E's interval's lower edge and A2's margin is
    section F's. That is what keeps the exam document, this JSON and the
    judges from ever disagreeing about a threshold.
    """
    lift_ci = transmission["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["rec_plus_cri"][
        "lift_ci95"
    ]
    dwell: dict[str, Any] = {}
    for quadrant in QUADRANTS:
        median = cast(float, regime_durations["per_quadrant"][quadrant]["median_months"])
        dwell[quadrant] = [
            max(0.0, median - DWELL_TOLERANCE_MONTHS),
            median + DWELL_TOLERANCE_MONTHS,
        ]
    spreads = [
        episode["returns"]["spreads_ann_arith_pp"]["commodities_minus_bonds"]
        for episode in allocation["named_episodes"].values()
        if episode["available"]
    ]
    return {
        "T1_lift_band": [lift_ci["lo"], lift_ci["hi"]],
        "O1_clockwise_min": ordering["ci95_lower_edge"],
        "D_median_bands_months": dwell,
        "D_tolerance_months": DWELL_TOLERANCE_MONTHS,
        "A1_containment_pp": [_f(min(spreads)), _f(max(spreads))],
        "A2_correlation_margin": correlation_intervals["correlation_level"]["ci95_lower_edge"],
        "A2_share_high_floor": A2_SHARE_HIGH_FLOOR,
        "A2_share_low_ceiling": A2_SHARE_LOW_CEILING,
        "derivation_note": (
            "T1_lift_band = b_transmission_lift's primary 24-month bootstrap interval for "
            "the recession-or-crisis lift; D_median_bands_months = each season's "
            "completed-spell median +- 1 quarter, floored at zero because no spell is "
            "shorter than a month; A1_containment_pp = the min and max "
            "commodities-minus-bonds spread across the five in-panel episodes; "
            "O1_clockwise_min = e_ordering's 95% interval's LOWER edge; "
            "A2_correlation_margin = f_correlation_intervals' 95% interval's LOWER edge "
            "for the high-minus-low correlation difference"
        ),
    }


def section_h(
    source: Any,
    yoy: np.ndarray,
    cells: np.ndarray,
    bars: dict[str, Any],
) -> dict[str, Any]:
    """OPEN-4: how many generated decades a TRUE engine needs to clear each bar.

    **What "a true engine" means here.** An engine actually at the historical
    point estimates is modelled as one that emits a uniformly-drawn contiguous
    120-month stretch of the panel as each decade. That model has history's own
    point estimates by construction AND history's own month-to-month dependence,
    which an i.i.d. binomial calculation would throw away; it is also close to
    what the selection-only compiler does in spirit. Each bar is then evaluated
    on ``n`` such decades exactly as the judge would evaluate it on ``n``
    generated ones, ``POWER_N_ENSEMBLES`` times, and the reported power is the
    share of ensembles that pass.

    **Eligibility inside a decade, matched to the judge.** A decade's own
    trailing 12-month inflation does not exist for its first 12 months, so every
    inflation-conditioned statistic starts at decade month 13 (108 usable
    months); T1 additionally needs a full 12-month lookahead, leaving the 96
    eligible months the exam states; A2(ii)'s 36-month rolling windows are
    computed INSIDE the decade and their first usable end month is decade month
    37, leaving 84 windows.

    **Two honest limits.** The decades overlap (694 distinct start positions),
    so this is a bootstrap and its large-``n`` limit is the panel's own value,
    not an independent truth; and history's between-decade heterogeneity (the
    1970s against the 1990s) is inherited in full, which is plausibly wider than
    a well-behaved engine's, so the recommended ``n`` is conservative.
    """
    t1_band = cast(list[float], bars["T1_lift_band"])
    o1_bar = cast(float, bars["O1_clockwise_min"])
    dwell_bands = cast(dict[str, list[float]], bars["D_median_bands_months"])
    a1_containment = cast(list[float], bars["A1_containment_pp"])
    a2_margin = cast(float, bars["A2_correlation_margin"])

    n = int(source.n_rows)
    names = list(source.factor_names)
    values = np.asarray(source.values)
    labels = np.asarray(source.labels)
    returns = _asset_returns(source)
    equities = cast(np.ndarray, returns["equities"])
    bonds = cast(np.ndarray, returns["bonds"])
    commodities = cast(np.ndarray, returns["commodities"])

    decade = POWER_DECADE_MONTHS
    warmup = POWER_YOY_WARMUP_MONTHS
    starts = np.arange(0, n - decade + 1)
    n_starts = int(starts.size)
    usable_lo = starts + warmup  # decade month 13
    usable_hi = starts + decade - 1  # decade month 120

    # ---- T1: tightness and the 12-month downturn lookahead --------------------
    tight = (values[:, names.index("ust_2y")] - values[:, names.index("ust_10y")]) > 0.0
    downturn = np.isin(labels, ["REC", "CRI"])
    onset_at = _onset_flags(downturn)
    followed = np.zeros(n, dtype=bool)
    for t in range(n - K_MONTHS):
        followed[t] = bool(onset_at[t + 1 : t + 1 + K_MONTHS].any())
    t1_lo = starts + warmup
    t1_hi = starts + decade - 1 - K_MONTHS  # decade month 108
    t1_stats = np.stack(
        [
            _window_sums(np.ones(n), t1_lo, t1_hi),
            _window_sums(tight, t1_lo, t1_hi),
            _window_sums(tight & followed, t1_lo, t1_hi),
            _window_sums(followed, t1_lo, t1_hi),
        ],
        axis=1,
    )

    # ---- O1: transitions inside the decade's usable window --------------------
    pair_trans = np.zeros(n, dtype=np.float64)
    pair_cw = np.zeros(n, dtype=np.float64)
    tr, cw = _clockwise_counts(cells[:-1].reshape(-1, 1), cells[1:].reshape(-1, 1))
    pair_trans[1:] = tr.astype(np.float64)
    pair_cw[1:] = cw.astype(np.float64)
    o1_stats = np.stack(
        [
            _window_sums(pair_trans, usable_lo + 1, usable_hi),
            _window_sums(pair_cw, usable_lo + 1, usable_hi),
        ],
        axis=1,
    )

    # ---- A1 and A2(i): inflation-state sums over decade months 13..120 --------
    high = (yoy >= PRIMARY_INFLATION_THRESHOLD_PP) & ~np.isnan(yoy)
    low = (yoy < PRIMARY_INFLATION_THRESHOLD_PP) & ~np.isnan(yoy)
    alloc_columns: list[np.ndarray] = []
    for state in (high, low):
        f = state.astype(np.float64)
        for series in (
            f,
            commodities * f,
            bonds * f,
            equities * f,
            equities * equities * f,
            bonds * bonds * f,
            equities * bonds * f,
        ):
            alloc_columns.append(_window_sums(series, usable_lo, usable_hi))
    alloc_stats = np.stack(alloc_columns, axis=1)

    # ---- A2(ii): rolling windows computed INSIDE the decade --------------------
    win = ROLLING_CORR_WINDOW_MONTHS
    rolling_returns_only = np.full(n, np.nan)
    for t in range(win, n):  # t - win + 1 >= 1: never spans the bond warm-up row
        lo = t - win + 1
        rolling_returns_only[t] = float(np.corrcoef(equities[lo : t + 1], bonds[lo : t + 1])[0, 1])
    roll_defined = ~np.isnan(rolling_returns_only)
    roll_positive = roll_defined & (rolling_returns_only > 0.0)
    roll_lo = starts + win  # decade month 37
    roll_hi = usable_hi
    roll_stats = np.stack(
        [
            _window_sums(roll_defined & high, roll_lo, roll_hi),
            _window_sums(roll_defined & high & roll_positive, roll_lo, roll_hi),
            _window_sums(roll_defined & low, roll_lo, roll_hi),
            _window_sums(roll_defined & low & roll_positive, roll_lo, roll_hi),
        ],
        axis=1,
    )

    # ---- D1-D4: completed spell-length histograms per decade -------------------
    max_len = decade - warmup
    spell_hist = np.zeros((n_starts, len(QUADRANTS), max_len + 1), dtype=np.float64)
    for i in range(n_starts):
        spell_hist[i] = _decade_spell_histogram(
            cells, int(usable_lo[i]), int(usable_hi[i]), max_len
        )
    spell_flat = spell_hist.reshape(n_starts, -1)

    def _verdicts(
        t1: np.ndarray,
        o1: np.ndarray,
        alloc: np.ndarray,
        roll: np.ndarray,
        spells: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        """Every bar's pass flag AND the statistic behind it, per ensemble."""
        with np.errstate(invalid="ignore", divide="ignore"):
            elig, n_tight, n_tight_hit, n_hit = (t1[:, i] for i in range(4))
            conditional = np.where(n_tight > 0, n_tight_hit / n_tight, np.nan)
            unconditional = np.where(elig > 0, n_hit / elig, np.nan)
            lift = np.where(unconditional > 0, conditional / unconditional, np.nan)

            n_trans, n_cw = o1[:, 0], o1[:, 1]
            clockwise = np.where(n_trans > 0, n_cw / n_trans, np.nan)

            hi_n, hi_c, hi_b, hi_e, hi_ee, hi_bb, hi_eb = (alloc[:, i] for i in range(7))
            lo_n, lo_c, lo_b, lo_e, lo_ee, lo_bb, lo_eb = (alloc[:, i] for i in range(7, 14))
            spread_high = 1200.0 * (hi_c / hi_n - hi_b / hi_n)
            spread_low = 1200.0 * (lo_c / lo_n - lo_b / lo_n)
            corr_high = _corr_from_sums(hi_n, hi_e, hi_b, hi_ee, hi_bb, hi_eb)
            corr_low = _corr_from_sums(lo_n, lo_e, lo_b, lo_ee, lo_bb, lo_eb)

            wh, whp, wl, wlp = (roll[:, i] for i in range(4))
            share_high = np.where(wh > 0, whp / wh, np.nan)
            share_low = np.where(wl > 0, wlp / wl, np.nan)

            medians = {
                quadrant: _pooled_median_from_histogram(
                    spells[:, i * (max_len + 1) : (i + 1) * (max_len + 1)]
                )
                for i, quadrant in enumerate(QUADRANTS)
            }

        out = {
            "T1": (lift >= t1_band[0]) & (lift <= t1_band[1]),
            "O1": clockwise >= o1_bar,
            "A1": spread_high > spread_low,
            "A1_with_containment": (spread_high > spread_low)
            & (spread_high >= a1_containment[0])
            & (spread_high <= a1_containment[1]),
            "A2": (corr_high > 0.0)
            & ((corr_high - corr_low) >= a2_margin)
            & (share_high >= A2_SHARE_HIGH_FLOOR)
            & (share_low <= A2_SHARE_LOW_CEILING),
            # A2's four conditions separately, so a low A2 power can be read
            # rather than guessed at. Diagnostics, not bars.
            "A2i_level_positive": corr_high > 0.0,
            "A2i_margin": (corr_high - corr_low) >= a2_margin,
            "A2ii_share_high_floor": share_high >= A2_SHARE_HIGH_FLOOR,
            "A2ii_share_low_ceiling": share_low <= A2_SHARE_LOW_CEILING,
        }
        statistics = {
            "T1_lift": lift,
            "O1_clockwise_fraction": clockwise,
            "A1_spread_high_pp": spread_high,
            "A1_spread_low_pp": spread_low,
            "A2_correlation_high": corr_high,
            "A2_correlation_low": corr_low,
            "A2_correlation_difference": corr_high - corr_low,
            "A2_share_positive_high": share_high,
            "A2_share_positive_low": share_low,
        }
        for code, quadrant in zip(("D1", "D2", "D3", "D4"), QUADRANTS, strict=True):
            band = dwell_bands[quadrant]
            out[code] = (medians[quadrant] >= band[0]) & (medians[quadrant] <= band[1])
            statistics[f"{code}_median_months_{quadrant}"] = medians[quadrant]
        return out, statistics

    # The n -> infinity reference: every decade drawn exactly once. This is what
    # a true engine converges to, and it need NOT equal the panel-wide anchor a
    # bar was cut from -- a 120-month decade truncates long spells and cannot
    # show a transition across its own edges, so a statistic measured on decades
    # can sit systematically away from the same statistic measured on the whole
    # panel. Where it does, that is a property of the BAR, not of the engine,
    # and no ensemble size can fix it.
    ones = np.ones((1, n_starts))
    limit_verdicts, limit_stats = _verdicts(
        ones @ t1_stats, ones @ o1_stats, ones @ alloc_stats, ones @ roll_stats, ones @ spell_flat
    )

    rng = np.random.Generator(np.random.PCG64(POWER_SEED))
    bar_names = list(limit_verdicts)
    power: dict[str, list[float | None]] = {name: [] for name in bar_names}
    for n_seeds in POWER_SEED_GRID:
        drawn = rng.integers(0, n_starts, size=(POWER_N_ENSEMBLES, n_seeds))
        flat = (np.arange(POWER_N_ENSEMBLES)[:, None] * n_starts + drawn).ravel()
        counts = np.bincount(flat, minlength=POWER_N_ENSEMBLES * n_starts).reshape(
            POWER_N_ENSEMBLES, n_starts
        )
        weights = counts.astype(np.float64)
        verdicts, _ = _verdicts(
            weights @ t1_stats,
            weights @ o1_stats,
            weights @ alloc_stats,
            weights @ roll_stats,
            weights @ spell_flat,
        )
        for name in bar_names:
            power[name].append(_f(float(verdicts[name].mean())))

    pilot_index = POWER_SEED_GRID.index(POWER_PILOT_N_SEEDS)
    per_bar: dict[str, Any] = {}
    for name in bar_names:
        probabilities = np.asarray([p if p is not None else 0.0 for p in power[name]])
        recommended = _min_n_seeds(POWER_SEED_GRID, probabilities)
        per_bar[name] = {
            "is_headline_bar": name in HEADLINE_BARS,
            "power_by_n_seeds": dict(
                zip([str(x) for x in POWER_SEED_GRID], power[name], strict=True)
            ),
            "power_at_pilot_n_seeds": power[name][pilot_index],
            "pilot_n_seeds_sufficient": bool(probabilities[pilot_index] >= POWER_TARGET),
            "min_n_seeds_for_target": recommended,
            "max_power_on_grid": _f(float(probabilities.max())),
            "true_engine_limit_passes": bool(limit_verdicts[name][0]),
        }

    achievable = [
        per_bar[name]["min_n_seeds_for_target"]
        for name in HEADLINE_BARS
        if per_bar[name]["min_n_seeds_for_target"] is not None
    ]
    unreachable = [
        name for name in HEADLINE_BARS if per_bar[name]["min_n_seeds_for_target"] is None
    ]
    return {
        "target_pass_probability": POWER_TARGET,
        "n_ensembles": POWER_N_ENSEMBLES,
        "seed_grid": list(POWER_SEED_GRID),
        "power_seed": POWER_SEED,
        "decade_months": decade,
        "distinct_decade_starts": n_starts,
        "pilot_n_seeds": POWER_PILOT_N_SEEDS,
        "true_engine_model": (
            "each generated decade is a uniformly-drawn contiguous 120-month stretch of "
            "the panel, so the engine sits at history's point estimates WITH history's "
            "own month-to-month dependence; bars are judged on the pooled statistic over "
            "n such decades, POWER_N_ENSEMBLES times"
        ),
        "eligibility_note": (
            "inflation-conditioned statistics start at decade month 13 (108 usable "
            "months, the decade's own trailing-inflation warm-up); T1 also needs a full "
            "12-month lookahead (96 eligible months); A2(ii)'s rolling windows are "
            "computed inside the decade and start at end month 37 (84 windows); D1-D4 "
            "drop spells touching either edge of the usable window, the same "
            "completed-spell rule the anchors use"
        ),
        "limits_note": (
            "three limits, all of which push the same way -- toward treating the "
            "recommended n as an upper bound. (1) The decades overlap (694 distinct "
            "starts), so this is a bootstrap whose large-n limit is the panel's own "
            "value rather than an independent truth. (2) It inherits history's full "
            "between-decade heterogeneity (the 1970s against the 1990s), plausibly wider "
            "than a well-behaved engine's. (3) Drawing decade STARTS uniformly weights "
            "panel months unevenly: an interior month enters up to 84 decades while the "
            "first and last few years of the panel enter far fewer, so a statistic whose "
            "extremes sit at the panel's ends shifts. That is why the decade-measured "
            "low-inflation share-of-windows-positive (0.62) sits above the panel-wide "
            "figure (0.54): the two most negatively-correlated low-inflation stretches, "
            "the 1950s-60s and the 2010s, are exactly the down-weighted ones"
        ),
        "bars_judged": bars,
        "headline_bars": list(HEADLINE_BARS),
        "true_engine_limit_statistics": {
            name: _f(float(values[0])) for name, values in limit_stats.items()
        },
        "true_engine_limit_note": (
            "each statistic as a true engine would produce it in the large-n limit -- "
            "every 120-month decade of the panel pooled once. Read each against "
            "bars_judged: where the limit sits outside a band, the bar cannot be cleared "
            "at ANY ensemble size, because the offset is between a panel-wide anchor and "
            "the same statistic measured on decades, not between history and an engine"
        ),
        "per_bar": per_bar,
        "recommended_n_seeds": max(achievable) if achievable else None,
        "bars_unreachable_on_grid": unreachable,
    }


# --------------------------------------------------------------------------- #
# I and J -- regime-identification robustness (owner-agreed 2026-08-17)
#
# Neither section draws a single random number. Every figure below is a
# deterministic recomputation of an anchor under a different labelling of the
# SAME panel months, compared against sampling intervals that sections E and G
# already measured. That is why no new seed constant appears above: there is no
# new tape to keep distinct.
# --------------------------------------------------------------------------- #


class _RelabelledSource:
    """The two fields ``ah.gen.spine.panel_quadrant`` reads, and nothing else.

    ``panel_quadrant`` is the classifier under test and must never be
    re-implemented here, but it takes its growth direction from
    ``source.labels``. Handing it this projection is how a perturbed label
    vector is classified by the REAL classifier rather than by a copy of it.
    """

    def __init__(self, source: Any, labels: tuple[str, ...]) -> None:
        self.labels = labels
        self.n_rows = int(source.n_rows)


def _completed_spells_by_quadrant(cells: np.ndarray) -> list[list[int]]:
    """Per-quadrant COMPLETED spell lengths, by section C's own censoring rule.

    A spell is censored if it opens the panel, opens straight out of a stretch
    with no defined quadrant, or is still running at the last row; censored
    spells are dropped. Written once here so every arm of section I and both
    classifiers of section J are measured identically; ``section_i`` asserts it
    reproduces section C's own completed-spell lists on the baseline cells.
    """
    spells = spells_from_labels(cells.astype(np.int8))
    n_spells = len(spells)
    out: list[list[int]] = [[] for _ in QUADRANTS]
    for position, (state, _start, length) in enumerate(spells):
        if state < 0:
            continue
        left = position == 0 or spells[position - 1][0] < 0
        right = position == n_spells - 1
        if left or right:
            continue
        out[state].append(int(length))
    return out


def _classification_anchors(cells: np.ndarray) -> dict[str, Any]:
    """The anchors a re-labelling can move: dwell medians, ordering, counts."""
    n_trans, n_cw = _clockwise_counts(cells[:-1], cells[1:])
    total = int(n_trans)
    clockwise = int(n_cw)
    completed = _completed_spells_by_quadrant(cells)
    per_quadrant: dict[str, Any] = {}
    for i, quadrant in enumerate(QUADRANTS):
        lengths = sorted(completed[i])
        per_quadrant[quadrant] = {
            "n_completed_spells": len(lengths),
            "median_months": _f(float(np.median(lengths))) if lengths else None,
            "months_in_quadrant": int((cells == i).sum()),
            "sorted_spells_months": lengths,
        }
    return {
        "clockwise_fraction": _f(float(clockwise) / total) if total else None,
        "n_transitions": total,
        "n_clockwise_transitions": clockwise,
        "defined_months": int((cells >= 0).sum()),
        "per_quadrant": per_quadrant,
    }


def _regime_features(source: Any, access: Any, frames: dict[str, Any]) -> pd.DataFrame:
    """The five-column feature frame ``ah.data.derive.label_regime`` classifies.

    Built by exactly the calls ``ah.gen.bootstrap.build_source`` makes -- the
    same helpers on the same frames -- so that re-labelling with an unperturbed
    threshold dict returns the panel's own labels character for character.
    ``hy_oas`` is absent by construction on this vintage (the licensed history
    is all inside the holdout), which ``regime_labels_for`` records as a known
    gap; it is passed as NaN here for the same reason.
    """
    dates = pd.DatetimeIndex(source.dates)
    usrec_frame = _read_series(access, USREC_SERIES_ID)
    indpro_frame = _read_series(access, INDPRO_SERIES_ID)
    if usrec_frame is None or indpro_frame is None:
        raise RuntimeError(f"the panel's labels need {USREC_SERIES_ID} and {INDPRO_SERIES_ID}")
    features = pd.DataFrame(index=dates)
    features["cpi_yoy"] = _yoy_percent(_monthly(frames["cpi"])).reindex(dates)
    features["growth_yoy"] = _yoy_percent(_monthly(indpro_frame)).reindex(dates)
    features["drawdown"] = _drawdown_fraction(_monthly(frames["equity_mkt"])).reindex(dates)
    features["usrec"] = _monthly(usrec_frame).reindex(dates)
    if bool(features.isna().to_numpy().any()):
        raise RuntimeError("a regime feature is missing over the panel span")
    return features


def _feature_columns(features: pd.DataFrame) -> dict[str, np.ndarray]:
    """The feature frame as plain float columns, in ``label_regime``'s own names."""
    return {
        name: features[name].to_numpy(dtype=np.float64)
        for name in ("usrec", "cpi_yoy", "growth_yoy", "drawdown")
    }


def _labels_at(columns: dict[str, np.ndarray], thresholds: dict[str, Any]) -> tuple[str, ...]:
    """``regime_ruleset_v1`` labels under a (possibly perturbed) threshold set."""
    return tuple(
        derive.label_regime(
            usrec=float(usrec),
            cpi_yoy=float(cpi_yoy),
            growth_yoy=float(growth_yoy),
            drawdown=float(drawdown),
            hy_oas=float("nan"),
            thr=thresholds,
        )
        for usrec, cpi_yoy, growth_yoy, drawdown in zip(
            columns["usrec"],
            columns["cpi_yoy"],
            columns["growth_yoy"],
            columns["drawdown"],
            strict=True,
        )
    )


def _t1_lift_for_labels(source: Any, yoy: np.ndarray, labels: tuple[str, ...]) -> dict[str, Any]:
    """T1's recession-or-crisis lift under one arm's labels, point estimate only.

    The growth dial's perturbation moves ``REC`` labels, and T1's downturn
    definition is the REC-or-CRI union, so a growth perturbation moves T1 as
    well as the quadrant anchors. Reported as a disclosure beside section I --
    the tight-policy side (the yield curve) is untouched by either dial.
    """
    n = int(source.n_rows)
    eligible = _eligible_mask(yoy, n, K_MONTHS)
    names = list(source.factor_names)
    values = np.asarray(source.values)
    tight = (values[:, names.index("ust_2y")] - values[:, names.index("ust_10y")]) > 0.0
    onset_at = _onset_flags(np.isin(np.asarray(labels), ["REC", "CRI"]))
    outcome = _followed_within(onset_at, np.flatnonzero(eligible), K_MONTHS)
    conditional, unconditional, lift = _lift(tight[eligible], outcome)
    return {
        "lift": _f(lift),
        "conditional_rate": _f(conditional),
        "unconditional_rate": _f(unconditional),
        "n_onsets_panel": int(onset_at.sum()),
    }


def _interval_verdict(values: list[float], lo: float, hi: float, point: float) -> dict[str, Any]:
    """STABLE/FRAGILE for one anchor, by the stated containment rule.

    STABLE means every arm's value lies inside the anchor's own 95% sampling
    interval -- i.e. no perturbation of that size moves the anchor further than
    resampling the same history already moves it. ``spread_vs_interval_width``
    is published beside the verdict as the continuous version of the same
    comparison, so a reader who prefers "is the spread smaller than the interval
    is wide?" can apply that reading instead without recomputing anything.
    """
    finite = [v for v in values if np.isfinite(v)]
    spread = (max(finite) - min(finite)) if finite else float("nan")
    width = hi - lo
    inside = all(lo <= v <= hi for v in finite)
    return {
        "arm_min": _f(min(finite)) if finite else None,
        "arm_max": _f(max(finite)) if finite else None,
        "perturbation_spread": _f(spread),
        "sampling_ci95": [_f(lo), _f(hi)],
        "sampling_ci95_width": _f(width),
        "sampling_ci95_half_width": _f(max(point - lo, hi - point)),
        "spread_vs_interval_width": _f(spread / width) if width > 0 else None,
        "all_arms_inside_ci95": bool(inside),
        "verdict": "STABLE" if inside else "FRAGILE",
    }


def section_i(
    source: Any,
    yoy: np.ndarray,
    cells: np.ndarray,
    era_threshold_pp: float,
    access: Any,
    frames: dict[str, Any],
    regime_durations: dict[str, Any],
    ordering: dict[str, Any],
    dwell_intervals: dict[str, Any],
    bars: dict[str, Any],
    sealed_bars: dict[str, Any],
    sealed_contracting_labels: tuple[str, ...],
) -> dict[str, Any]:
    """Obligation A: how far do the anchors move when the two dials are nudged?

    The investment clock has exactly two dials. The INFLATION dial is a
    threshold inside the classifier itself (``panel_quadrant``'s
    ``yoy > era_threshold_pp``), so it is perturbed directly. The GROWTH dial is
    not a threshold at the classifier level at all -- ``panel_quadrant`` reads a
    published label and asks whether it is ``REC`` or ``CRI`` -- so its boundary
    lives one layer down, in ``regime_ruleset_v1``'s ``growth_weak`` line on
    trailing INDPRO growth, and it is perturbed THERE and the months re-labelled.
    Both moves are +-0.50 pp in the dial's own units.
    """
    base_thresholds = dict(derive.regime_thresholds())
    columns = _feature_columns(_regime_features(source, access, frames))
    growth_yoy = columns["growth_yoy"]
    growth_line = float(base_thresholds["growth_weak"])
    rebuilt = _labels_at(columns, base_thresholds)
    if rebuilt != tuple(source.labels):
        raise RuntimeError(
            "the rebuilt regime labels do not reproduce the panel's own; every "
            "perturbation below would be measuring that drift instead of the dial"
        )
    baseline_anchors = _classification_anchors(cells)
    for quadrant in QUADRANTS:
        observed = baseline_anchors["per_quadrant"][quadrant]["sorted_spells_months"]
        expected = regime_durations["per_quadrant"][quadrant]["sorted_spells_months"]
        if observed != expected:
            raise RuntimeError(f"completed-spell rule disagrees with section C on {quadrant}")

    incumbent_contracting = np.isin(np.asarray(source.labels), ["REC", "CRI"])
    arms: dict[str, Any] = {}
    per_arm_cells: dict[str, np.ndarray] = {}
    per_arm_labels: dict[str, tuple[str, ...]] = {}
    for name, d_infl, d_growth in STABILITY_ARMS:
        thresholds = dict(base_thresholds)
        thresholds["growth_weak"] = growth_line + d_growth
        labels = tuple(source.labels) if d_growth == 0.0 else _labels_at(columns, thresholds)
        per_arm_labels[name] = labels
        arm_cells = panel_quadrant(
            _RelabelledSource(source, labels), yoy, era_threshold_pp + d_infl
        )
        per_arm_cells[name] = arm_cells
        contracting = np.isin(np.asarray(labels), ["REC", "CRI"])
        defined = cells >= 0
        moved = int((arm_cells[defined] != cells[defined]).sum())
        arms[name] = {
            "inflation_line_delta_pp": d_infl,
            "growth_line_delta_pp": d_growth,
            "inflation_line_pp": _f(era_threshold_pp + d_infl),
            "growth_weak_pp": _f(thresholds["growth_weak"]),
            "contracting_months": int(contracting.sum()),
            "contracting_months_change": int(contracting.sum() - incumbent_contracting.sum()),
            "months_reassigned_vs_baseline": moved,
            "months_reassigned_share": _f(float(moved) / float(defined.sum())),
            "anchors": _classification_anchors(arm_cells),
            "t1_disclosure": _t1_lift_for_labels(source, yoy, labels),
        }

    # ---- verdicts, one per anchor -------------------------------------------
    verdicts: dict[str, Any] = {}
    cw_ci = ordering["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["clockwise_fraction_ci95"]
    verdicts["clockwise_fraction"] = _interval_verdict(
        [cast(float, arms[name]["anchors"]["clockwise_fraction"]) for name, _, _ in STABILITY_ARMS],
        cast(float, cw_ci["lo"]),
        cast(float, cw_ci["hi"]),
        cast(float, ordering["clockwise_fraction"]),
    )
    for quadrant in QUADRANTS:
        row = dwell_intervals["per_quadrant"][quadrant]
        lo, hi = cast(list[float], row["ci95_months"])
        verdicts[f"dwell_median_{quadrant}"] = _interval_verdict(
            [
                cast(float, arms[name]["anchors"]["per_quadrant"][quadrant]["median_months"])
                for name, _, _ in STABILITY_ARMS
            ],
            lo,
            hi,
            cast(float, row["median_months"]),
        )

    transition_counts = {
        name: arms[name]["anchors"]["n_transitions"] for name, _, _ in STABILITY_ARMS
    }
    t1_lifts = [cast(float, arms[name]["t1_disclosure"]["lift"]) for name, _, _ in STABILITY_ARMS]

    # ---- the second reading the verdicts above do NOT give ------------------
    # "Inside the anchor's own sampling interval" is what the owner asked for
    # and it is what the verdicts report. But those intervals are very wide
    # (OPEN-3's finding), and the exam does not judge with them -- it judges
    # with the D bands and the O1 minimum. So the same arms are also checked
    # against the bars themselves. A season whose HISTORICAL anchor leaves its
    # own band when the dial moves 50 bp is a fact about the bar, and it is
    # computed here rather than left to be noticed later.
    band_check: dict[str, Any] = {}
    dwell_bands = cast(dict[str, list[float]], bars["D_median_bands_months"])
    o1_min = cast(float, bars["O1_clockwise_min"])
    o1_values = [
        cast(float, arms[name]["anchors"]["clockwise_fraction"]) for name, _, _ in STABILITY_ARMS
    ]
    band_check["O1_clockwise_fraction"] = {
        "bar_minimum": _f(o1_min),
        "arms_outside": [
            name
            for name, _, _ in STABILITY_ARMS
            if not (cast(float, arms[name]["anchors"]["clockwise_fraction"]) >= o1_min)
        ],
        "arm_min": _f(min(o1_values)),
        "headroom_at_worst_arm": _f(min(o1_values) - o1_min),
    }
    for code, quadrant in zip(("D1", "D2", "D3", "D4"), QUADRANTS, strict=True):
        band = dwell_bands[quadrant]
        values = [
            cast(float, arms[name]["anchors"]["per_quadrant"][quadrant]["median_months"])
            for name, _, _ in STABILITY_ARMS
        ]
        outside = [
            name
            for name, value in zip([n for n, _, _ in STABILITY_ARMS], values, strict=True)
            if not (band[0] <= value <= band[1])
        ]
        band_check[f"{code}_dwell_median_{quadrant}"] = {
            "bar": [_f(band[0]), _f(band[1])],
            "arm_min": _f(min(values)),
            "arm_max": _f(max(values)),
            "arms_outside": outside,
            "n_arms_outside": len(outside),
        }

    # ---- the same check, re-run on the SEALED construct ----------------------
    # ``band_check`` above compares each arm's PANEL-WIDE median against the
    # pre-ruling panel-wide band, which is what §11 measured and reported. The
    # owner's pooled-spells re-derivation changed both halves of that comparison
    # (decade-pooled statistic, decade-pooled anchor), so the disclosure has to
    # be re-taken on the construct that is actually being sealed -- otherwise
    # the exam would ship a threshold-sensitivity result about bars it no longer
    # has. Each arm's months are re-classified under the sealed grader's
    # contracting set and pooled over the panel's own 120-month windows, exactly
    # as the sealed judge pools a generated batch.
    sealed_dwell_bands = cast(dict[str, list[float]], sealed_bars["D_median_bands_months"])
    starts = _decade_starts(int(cells.size), POWER_DECADE_MONTHS)
    sealed_band_check: dict[str, Any] = {}
    pooled_by_arm: dict[str, list[float]] = {}
    clockwise_by_arm: dict[str, float] = {}
    for name, d_infl, _d_growth in STABILITY_ARMS:
        arm_labels = per_arm_labels[name]
        arm_cells = grader_season_cells(
            np.asarray(arm_labels),
            yoy,
            era_threshold_pp + d_infl,
            contracting_labels=sealed_contracting_labels,
        )
        pooled = _pooled_decade_spells(
            arm_cells, starts, POWER_DECADE_MONTHS, POWER_YOY_WARMUP_MONTHS
        )
        pooled_by_arm[name] = [
            float(np.median(pooled[i])) if pooled[i] else float("nan")
            for i in range(len(QUADRANTS))
        ]
        arm_total, arm_cw = grader_clockwise_counts(arm_cells)
        clockwise_by_arm[name] = float(arm_cw) / arm_total if arm_total else float("nan")
    o1_sealed_min = cast(float, sealed_bars["O1_clockwise_min"])
    o1_sealed_values = [clockwise_by_arm[name] for name, _, _ in STABILITY_ARMS]
    sealed_band_check["O1_clockwise_fraction"] = {
        "bar": o1_sealed_min,
        "baseline_clockwise_fraction": _f(o1_sealed_values[0]),
        "arm_min": _f(min(o1_sealed_values)),
        "arm_max": _f(max(o1_sealed_values)),
        "arms_outside": [
            name
            for name, value in zip([n for n, _, _ in STABILITY_ARMS], o1_sealed_values, strict=True)
            if not (value >= o1_sealed_min)
        ],
        "headroom_at_worst_arm": _f(min(o1_sealed_values) - o1_sealed_min),
    }
    for i, (code, quadrant) in enumerate(zip(("D1", "D2", "D3", "D4"), QUADRANTS, strict=True)):
        band = sealed_dwell_bands[quadrant]
        values = [pooled_by_arm[name][i] for name, _, _ in STABILITY_ARMS]
        outside = [
            name
            for name, value in zip([n for n, _, _ in STABILITY_ARMS], values, strict=True)
            if not (band[0] <= value <= band[1])
        ]
        sealed_band_check[f"{code}_pooled_dwell_median_{quadrant}"] = {
            "bar": [_f(band[0]), _f(band[1])],
            "baseline_pooled_median_months": _f(values[0]),
            "arm_min": _f(min(values)),
            "arm_max": _f(max(values)),
            "arms_outside": outside,
            "n_arms_outside": len(outside),
        }

    return {
        "obligation": (
            "owner-agreed 2026-08-17 (A): perturb each dial of the two-dial classifier and "
            "report each anchor's spread across the perturbations against its own sampling "
            "noise"
        ),
        "perturbation_pp": STABILITY_PERTURBATION_PP,
        "perturbation_rationale": (
            "0.50 pp on EACH dial, in that dial's own units. On the inflation dial that is "
            "the platform's own ah.gen.spine.BACKDROP_MARGIN_PP -- the displacement the "
            "spine already treats as the smallest meaningful move in an inflation state, "
            "since it sits inside both the era threshold itself and spine_quadrant's hot "
            "test -- and it is one conventional central-bank move. The growth dial takes "
            "the same 50 basis points on trailing INDPRO growth, so neither dial is nudged "
            "harder than the other"
        ),
        "dials": {
            "inflation": (
                "panel_quadrant's hot test, yoy > era_threshold_pp, where era_threshold_pp "
                "= median(panel trailing CPI YoY) + BACKDROP_MARGIN_PP = "
                f"{era_threshold_pp!r} pp. Perturbed directly"
            ),
            "growth": (
                "panel_quadrant's contracting test, 'the month's regime_ruleset_v1 label is "
                "REC or CRI'. This dial carries NO threshold of its own: its boundary is "
                "regime_ruleset_v1's growth_weak line on trailing INDPRO growth (0.0 %/yr), "
                "one layer below the classifier. It is perturbed there and the months are "
                "re-labelled through ah.data.derive.label_regime"
            ),
        },
        "relabelling_check": {
            "rebuilt_labels_reproduce_panel": True,
            "note": (
                "the features are rebuilt with ah.gen.bootstrap's own helpers on the same "
                "frames build_source uses, and the unperturbed rebuild is asserted equal to "
                "source.labels before any threshold moves -- so a difference below is the "
                "dial, never a second implementation drifting"
            ),
        },
        "stag_branch_note": (
            "one consequence of perturbing growth_weak that a reader should see: the same "
            "line gates the ruleset's STAG branch, and panel_quadrant treats STAG as "
            "EXPANDING (its contracting test is REC-or-CRI membership, nothing else). So a "
            "hot weak-growth month can move between 'recession' and an EXPANDING quadrant "
            "rather than into the 'stagflation' cell -- the six-label ruleset's stagflation "
            "and the investment clock's stagflation are not the same object"
        ),
        "verdict_rule": (
            "STABLE means every arm's value lies inside the anchor's own 95% sampling "
            "interval (section E's block bootstrap for the ordering fraction, section G's "
            "spell bootstrap for the dwell medians): a perturbation of this size moves the "
            "anchor no further than resampling the same history already moves it. FRAGILE "
            "means at least one arm lands outside. spread_vs_interval_width is published "
            "beside every verdict for the alternative reading"
        ),
        "dial_scale_disclosure": {
            "inflation_indicator_sd_pp": _f(float(np.nanstd(yoy, ddof=1))),
            "growth_indicator_sd_pp": _f(float(np.std(growth_yoy, ddof=1))),
            "inflation_months_within_50bp_of_line": int(
                np.nansum(np.abs(yoy - era_threshold_pp) <= STABILITY_PERTURBATION_PP)
            ),
            "growth_months_within_50bp_of_line": int(
                (np.abs(growth_yoy - growth_line) <= STABILITY_PERTURBATION_PP).sum()
            ),
            "note": (
                "the same 50 basis points is NOT the same fraction of each dial's own "
                "spread, and the reader should see that rather than infer symmetry from "
                "the number: trailing CPI inflation is a much tighter series than trailing "
                "industrial-production growth, so 0.50 pp is a larger move relative to the "
                "inflation dial's own scale, and the arms below duly relabel far more "
                "months on the inflation dial than on the growth dial. The two "
                "perturbations are equal in the units the dials are STATED in, which is "
                "what a threshold-sensitivity check can honestly hold fixed; equalising "
                "them in standard deviations instead would mean nudging the inflation line "
                "by an amount no practitioner would call a threshold choice"
            ),
        },
        "arms": arms,
        "verdicts": verdicts,
        "bar_band_check": band_check,
        "bar_band_check_under_sealed_bars": sealed_band_check,
        "bar_band_check_under_sealed_bars_note": (
            "bar_band_check compares each arm's PANEL-WIDE median against the pre-ruling "
            "panel-wide band -- the comparison section 11 reported and the record of it. "
            "This block re-takes the same disclosure on the construct actually sealed: "
            "each arm's months re-classified under the sealed grader's contracting set, "
            "its completed spells pooled over the panel's own 120-month windows (the "
            "sealed D statistic), against the sealed decade-pooled band. Read THIS one "
            "for what a 50 bp move of a dial does to the bars that were sealed"
        ),
        "bar_band_check_note": (
            "the verdicts above answer the question the owner asked -- is the perturbation "
            "spread inside the anchor's own SAMPLING noise. This block answers the "
            "different question the exam actually judges with: does the anchor stay inside "
            "its own BAR when the dial moves 50 bp. The two can disagree, and here they do, "
            "because OPEN-3 established that the dwell intervals are much wider than the "
            "+-1 quarter bands. An arm listed under arms_outside is a case where HISTORY "
            "ITSELF, re-measured with a 50 bp different line, would fail the bar cut from it"
        ),
        "transition_counts_by_arm": transition_counts,
        "transition_count_note": (
            "transition counts are reported as context and carry NO stable/fragile verdict: "
            "no sampling interval for a COUNT is measured anywhere in this file on the same "
            "footing (section E's block bootstrap drops about one pair in mean_block at "
            "block joins by design, so its per-draw transition count is deliberately below "
            "the panel's and is not an error bar on it). The O1 bar is cut from the "
            "FRACTION, which does carry a verdict above"
        ),
        "t1_disclosure_summary": {
            "lift_min": _f(min(t1_lifts)),
            "lift_max": _f(max(t1_lifts)),
            "note": (
                "the growth-dial perturbation moves REC labels, and T1's downturn definition "
                "is the REC-or-CRI union, so T1's lift moves with it; the tight-policy side "
                "(the 10y-below-2y curve test) is untouched by either dial. Point estimates "
                "only, per arm, under t1_disclosure -- this is a disclosure that the growth "
                "dial reaches beyond the quadrant anchors, not a second T1 measurement. The "
                "allocation bars A1 and A2 split months at the fixed 4% CPI line, not at the "
                "era threshold, so neither dial reaches them at all"
            ),
        },
    }


def section_j(
    source: Any,
    yoy: np.ndarray,
    cells: np.ndarray,
    era_threshold_pp: float,
    access: Any,
    ordering: dict[str, Any],
    dwell_intervals: dict[str, Any],
) -> dict[str, Any]:
    """Obligation B: the same four seasons, identified from five inputs not two.

    The taxonomy does not change -- recession, recovery, expansion, stagflation,
    read off the same two axes. What changes is how the GROWTH axis is decided:
    instead of one published label, four voters vote and a stated tie-break
    settles a tie. The inflation axis is unchanged, and the reason is a data
    fact rather than a preference (see ``inflation_axis_note``).
    """
    n = int(source.n_rows)
    names = list(source.factor_names)
    values = np.asarray(source.values)
    dates = pd.DatetimeIndex(source.dates)
    months = _month_labels(dates)
    defined = cells >= 0

    # ---- the three corroborating indicators ---------------------------------
    unrate_frame = _read_series(access, UNRATE_SERIES_ID)
    if unrate_frame is None:
        raise RuntimeError(f"{UNRATE_SERIES_ID} is not in the campaign vintage")
    unrate = _monthly(unrate_frame)
    lagged = unrate.shift(LABOR_CHANGE_MONTHS)
    labor_change = (unrate - lagged).reindex(dates).to_numpy(dtype=np.float64)
    credit = values[:, names.index(CREDIT_FACTOR)]
    frames_equity = pd.Series(values[:, names.index("equity_mkt")], index=dates, dtype=np.float64)
    # The platform's own drawdown feature, over the panel's own equity factor.
    drawdown = _drawdown_fraction(frames_equity).reindex(dates).to_numpy(dtype=np.float64)
    stress = -drawdown  # oriented so larger = more contraction-like, like the others

    indicators = {
        "labor": labor_change,
        "credit": credit,
        "stress": stress,
    }
    if any(bool(np.isnan(v[defined]).any()) for v in indicators.values()):
        raise RuntimeError("a corroborating indicator is undefined inside the panel's own months")

    # ---- calibration: every voter fires as often as the incumbent dial -------
    incumbent = np.isin(np.asarray(source.labels), ["REC", "CRI"])
    base_rate = float(incumbent[defined].mean())
    voters: dict[str, np.ndarray] = {"label": incumbent}
    voter_meta: dict[str, Any] = {}
    for key, series in indicators.items():
        threshold = float(np.quantile(series[defined], 1.0 - base_rate))
        vote = series > threshold
        voters[key] = vote
        voter_meta[key] = {
            "threshold": _f(threshold),
            "realized_fire_share": _f(float(vote[defined].mean())),
            "agreement_with_incumbent": _f(float((vote[defined] == incumbent[defined]).mean())),
        }
    voter_meta["label"] = {
        "threshold": None,
        "realized_fire_share": _f(base_rate),
        "agreement_with_incumbent": 1.0,
    }

    # ---- the combination rule ------------------------------------------------
    votes = np.zeros(n, dtype=np.int64)
    for vote in voters.values():
        votes = votes + vote.astype(np.int64)
    contracting_richer = (votes >= 3) | ((votes == 2) & incumbent)

    # ---- the richer cells, built through panel_quadrant's own encoding -------
    hot = (yoy > era_threshold_pp).astype(np.int8)
    ok = ~np.isnan(yoy)

    def _cells_from(contracting: np.ndarray) -> np.ndarray:
        out = np.full(n, -1, dtype=np.int8)
        expanding = (~contracting).astype(np.int8)
        out[ok] = (expanding[ok] << 1) | hot[ok]
        return out

    if not np.array_equal(_cells_from(incumbent), cells):
        raise RuntimeError(
            "the richer classifier's cell encoding does not reproduce panel_quadrant when "
            "its growth input is the incumbent dial; the comparison below would be invalid"
        )
    richer_cells = _cells_from(contracting_richer)

    # ---- the disagreement map -------------------------------------------------
    differs = defined & (richer_cells != cells)
    by_decade: dict[str, Any] = {}
    decades = np.array([(int(label[:4]) // 10) * 10 for label in months], dtype=np.int64)
    for decade in sorted({int(d) for d in decades}):
        mask = defined & (decades == decade)
        by_decade[f"{decade}s"] = {
            "defined_months": int(mask.sum()),
            "disagreeing_months": int((differs & mask).sum()),
            "share": _f(float((differs & mask).sum()) / float(mask.sum())) if mask.any() else None,
        }
    by_season: dict[str, Any] = {}
    confusion: dict[str, Any] = {}
    for i, quadrant in enumerate(QUADRANTS):
        mask = defined & (cells == i)
        by_season[quadrant] = {
            "months_under_simple": int(mask.sum()),
            "disagreeing_months": int((differs & mask).sum()),
            "share": _f(float((differs & mask).sum()) / float(mask.sum())) if mask.any() else None,
        }
        confusion[quadrant] = {
            QUADRANTS[j]: int((mask & (richer_cells == j)).sum()) for j in range(len(QUADRANTS))
        }

    clusters: list[dict[str, Any]] = []
    for value, start, length in spells_from_labels(differs.astype(np.int8)):
        if value != 1 or length < DISAGREEMENT_CLUSTER_MIN_MONTHS:
            continue
        end = start + length - 1
        clusters.append(
            {
                "start": months[start],
                "end": months[end],
                "months": int(length),
                "simple_seasons": sorted(
                    {QUADRANTS[int(c)] for c in cells[start : end + 1] if c >= 0}
                ),
                "richer_seasons": sorted(
                    {QUADRANTS[int(c)] for c in richer_cells[start : end + 1] if c >= 0}
                ),
            }
        )

    # ---- the anchors under each classifier, and the decision rule ------------
    simple_anchors = _classification_anchors(cells)
    richer_anchors = _classification_anchors(richer_cells)

    def _decide(
        name: str, simple: float | None, richer: float | None, lo: float, hi: float, point: float
    ) -> dict[str, Any]:
        if simple is None or richer is None:
            return {"anchor": name, "verdict": "NOT COMPARABLE"}
        change = abs(richer - simple)
        half_width = max(point - lo, hi - point)
        triggers = change > half_width
        return {
            "anchor": name,
            "simple": _f(simple),
            "richer": _f(richer),
            "change": _f(change),
            "sampling_ci95": [_f(lo), _f(hi)],
            "sampling_ci95_half_width": _f(half_width),
            "change_exceeds_half_width": bool(triggers),
            "richer_inside_sampling_ci95": bool(lo <= richer <= hi),
            "verdict": "RICHER REPLACES SIMPLE" if triggers else "SIMPLICITY WINS",
        }

    cw_ci = ordering["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["clockwise_fraction_ci95"]
    decisions: dict[str, Any] = {
        "clockwise_fraction": _decide(
            "clockwise_fraction",
            cast(float, simple_anchors["clockwise_fraction"]),
            cast(float, richer_anchors["clockwise_fraction"]),
            cast(float, cw_ci["lo"]),
            cast(float, cw_ci["hi"]),
            cast(float, ordering["clockwise_fraction"]),
        )
    }
    for quadrant in QUADRANTS:
        row = dwell_intervals["per_quadrant"][quadrant]
        lo, hi = cast(list[float], row["ci95_months"])
        decisions[f"dwell_median_{quadrant}"] = _decide(
            f"dwell_median_{quadrant}",
            cast(float, simple_anchors["per_quadrant"][quadrant]["median_months"]),
            cast(float, richer_anchors["per_quadrant"][quadrant]["median_months"]),
            lo,
            hi,
            cast(float, row["median_months"]),
        )
    any_triggers = any(d.get("verdict") == "RICHER REPLACES SIMPLE" for d in decisions.values())

    return {
        "obligation": (
            "owner-agreed 2026-08-17 (B): build a second classification of the SAME four "
            "seasons from more inputs, map where it disagrees, re-derive the affected "
            "anchors, and apply the pre-declared decision rule"
        ),
        "taxonomy": list(QUADRANTS),
        "combination_rule": (
            "GROWTH AXIS -- four voters, each firing on the months its own indicator calls "
            "most contraction-like: (1) the incumbent dial, the month's regime_ruleset_v1 "
            "label being REC or CRI; (2) LABOR, the 12-month change in the unemployment "
            "rate; (3) CREDIT, the Baa-minus-Aaa spread; (4) MARKET STRESS, the equity "
            "drawdown. Voters 2-4 are calibrated to fire on the same share of panel months "
            "as voter 1 does, so no voter is louder merely by calling more months bad. "
            "Let c be the number of contracting votes: c >= 3 is contracting, c <= 1 is "
            "expanding, and c == 2 is settled by voter 1, the incumbent dial. "
            "INFLATION AXIS -- unchanged: hot is trailing 12-month CPI inflation above the "
            "panel's era threshold. SEASON -- (expanding << 1) | hot, read through "
            "ah.gen.spine.QUADRANTS, the same encoding panel_quadrant uses (asserted)"
        ),
        "base_rate_calibration": {
            "incumbent_contracting_share": _f(base_rate),
            "note": (
                "the threshold for each corroborating voter is the (1 - base rate) quantile "
                "of its own indicator over the panel's defined months. This is the same move "
                "b_transmission_lift already makes in its base_rate_matched arms, and it is "
                "made for the same reason: an indicator that calls more months bad scores "
                "differently for reasons that have nothing to do with the indicator. No "
                "threshold here was chosen by looking at what it does to an anchor"
            ),
            "per_voter": voter_meta,
            "vote_count_distribution": {
                str(k): int((votes[defined] == k).sum()) for k in range(len(voters) + 1)
            },
        },
        "inputs_used": {
            "labor": (
                f"{UNRATE_SERIES_ID} (monthly, 1948-01 onward in this vintage), "
                f"{LABOR_CHANGE_MONTHS}-month change in the unemployment rate, in percentage "
                "points; rising unemployment is contraction-like. The series starts more "
                "than five years before the panel does, so the lookback exists for every "
                "panel month and no month is dropped"
            ),
            "credit": (
                f"the panel's own '{CREDIT_FACTOR}' factor -- Baa minus Aaa, in percentage "
                "points, monthly across the whole panel; a wider spread is contraction-like"
            ),
            "stress": (
                "the equity drawdown from the running peak of the panel's equity_mkt "
                "cumulative index, computed by ah.gen.bootstrap._drawdown_fraction -- the "
                "platform's OWN drawdown feature, the same one regime_ruleset_v1's crisis "
                "branch reads; a deeper drawdown is contraction-like"
            ),
        },
        "inputs_considered_and_rejected": {
            "bis.credit_gap_us": (
                "REJECTED as the credit input, and the reason is availability, not "
                "preference: the series is QUARTERLY and begins 1957-10, fifty-four months "
                "after the panel starts. Using it would mean forward-filling a quarterly "
                "series into a monthly classifier AND leaving a four-and-a-half-year hole at "
                "the panel's head. The monthly ig_spread carries the same dimension over the "
                "whole span, so it is used instead and this substitution is stated rather "
                "than made silently"
            ),
            "hy_spread": (
                "NOT used, because on this panel it carries no information ig_spread does "
                "not: fred.HY_OAS's licensed history begins 2023-08 and lies entirely inside "
                "the holdout, so every panel month of hy_spread is the spliced Baa-minus-Aaa "
                "proxy. ig_spread is the same quantity without the proxy flag"
            ),
            "second_inflation_input": (
                "NONE EXISTS over the whole panel. The only other monthly inflation series "
                "in the campaign vintage is fred.CPI_CORE, which begins 1957-01 -- forty-five "
                "months after the panel starts. A classifier whose rule changes part-way "
                "through the panel is worse than one with a single input, so the inflation "
                "axis keeps its single input and THIS IS THE DIMENSION THIS COMPARISON DOES "
                "NOT ENRICH. Nothing is substituted for it"
            ),
        },
        "inflation_axis_note": (
            "the three extra inputs the owner named -- credit conditions, labor direction and "
            "market stress -- are all cyclical or financial-conditions indicators; none of "
            "them is an inflation indicator, so all three enter the GROWTH axis. The richer "
            "classifier is therefore richer on one axis and identical on the other, and the "
            "disagreement map below is entirely a map of growth-direction disagreement"
        ),
        "disagreement": {
            "defined_months": int(defined.sum()),
            "disagreeing_months": int(differs.sum()),
            "fraction": _f(float(differs.sum()) / float(defined.sum())),
            "by_decade": by_decade,
            "by_simple_season": by_season,
            "confusion_simple_rows_richer_columns": confusion,
            "cluster_min_months": DISAGREEMENT_CLUSTER_MIN_MONTHS,
            "clusters": clusters,
            "n_clusters": len(clusters),
            "months_in_clusters": int(sum(c["months"] for c in clusters)),
        },
        "anchors_simple": simple_anchors,
        "anchors_richer": richer_anchors,
        "decision_rule": RICHER_DECISION_RULE,
        "decision_rule_operationalisation": (
            "'more than that anchor's own sampling noise' is read as: the absolute change "
            "between the two classifiers' values exceeds the anchor's 95% interval "
            "half-width (section G's for a dwell median, section E's for the ordering "
            "fraction) -- the same half-width g_dwell_intervals already publishes. The "
            "stricter alternative reading, 'the richer value leaves the interval "
            "altogether', is published beside every verdict as "
            "richer_inside_sampling_ci95, so the owner can apply either without recomputing"
        ),
        "decisions": decisions,
        "any_anchor_triggers": bool(any_triggers),
        "recommended_sealed_grader": (
            "the RICHER classifier" if any_triggers else "the SIMPLE two-dial classifier"
        ),
    }


# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# K -- the pooled-spells re-derivation of D1-D4 (owner ruling, 2026-08-17)
#
# The four season-length bars were drafted as "the generated worlds' median
# completed spell, against history's". Two things about that construct were
# left implicit, and OPEN-4 found both of them biting:
#
#   (1) WHOSE median. A single generated decade contributes only a handful of
#       completed spells per season (the panel's own decades average 1.3
#       completed recession spells and 2.4 recovery ones), so a median taken
#       decade by decade is dominated by sampling noise rather than by the
#       engine -- which is exactly why D2 needed 50 decades for 90% power and
#       why a marginal D verdict could not be read. Pooling every completed
#       spell in the batch into ONE distribution and taking its median is the
#       fix: 50 decades pool ~120 recovery spells instead of ~2.4, and the
#       statistic then measures the engine.
#
#   (2) MEASURED ON WHAT WINDOW. Pooling alone does not close the gap, and this
#       section is where that is made visible. The panel-wide anchor is measured
#       on one unbroken 68-year record; the judged statistic is measured on
#       120-month decades, each of which drops the spell it opens with and the
#       spell it closes with. Long spells are far likelier to touch an edge, so
#       the decade-measured distribution is systematically shorter -- recovery's
#       median falls from 9 months panel-wide to 5 months on decades, because
#       recovery's spell list runs 2,2,3,3,3,4,5,5,5,6,6,12,13,... and the
#       panel-wide median of 9 is the midpoint of a jump nothing observed sits
#       in. Judging a decade-measured statistic against a panel-measured anchor
#       is the same class of error the spine-02 verdict-integrity review found
#       in B6 (recession-or-crisis on one side, crisis-only on the other), and
#       the exam's own remedy for it (T1's identical-conditioning ruling) is
#       what is applied here: BOTH sides are measured on 120-month windows with
#       the same 12-month warm-up and the same completed-spell rule.
#
# So the anchor a D bar is cut from is the panel's own decade-pooled completed
# spell median, and the tolerance stays +-1 quarter (a product fact -- the
# game's smallest play unit -- which no measurement here touches). What a D bar
# asks becomes: "does a decade of the generated world show seasons the length a
# decade of history shows?" -- which is also the question the product poses,
# since a player is handed one decade and never sees 68 years.
# --------------------------------------------------------------------------- #


def _decade_starts(n_rows: int, decade: int) -> np.ndarray:
    """Every start row of a full ``decade``-month window inside ``n_rows``."""
    return np.arange(0, n_rows - decade + 1)


def _pooled_decade_spells(
    cells: np.ndarray, starts: np.ndarray, decade: int, warmup: int
) -> list[list[int]]:
    """Completed spells of every window in ``starts``, pooled per season.

    One window is one simulated decade's worth of months: rows
    ``[start + warmup, start + decade - 1]`` (the warm-up months are dropped
    because a generated decade has no trailing inflation for them either), and
    the completed-spell rule inside it is ``spine_v2_grader.completed_spells``
    -- the SAME function the sealed judge calls on a generated decade.
    """
    pooled: list[list[int]] = [[] for _ in QUADRANTS]
    for start in starts:
        window = cells[int(start) + warmup : int(start) + decade]
        for i, lengths in enumerate(grader_completed_spells(window)):
            pooled[i].extend(lengths)
    return pooled


def _spell_summary(lengths: list[int], n_windows: int) -> dict[str, Any]:
    arr = np.asarray(sorted(lengths), dtype=np.float64)
    if arr.size == 0:
        return {"n_spells": 0, "median_months": None}
    q25, q50, q75 = (float(x) for x in np.percentile(arr, [25, 50, 75]))
    return {
        "n_spells": int(arr.size),
        "spells_per_window": _f(float(arr.size) / n_windows) if n_windows else None,
        "median_months": _f(q50),
        "median_quarters": _f(q50 / 3.0),
        "iqr_months": [_f(q25), _f(q75)],
        "mean_months": _f(float(arr.mean())),
        "max_months": _f(float(arr.max())),
    }


def section_k(cells_by_grader: dict[str, np.ndarray]) -> dict[str, Any]:
    """The decade-pooled completed-spell distribution, per grader.

    Reported three ways so the choice of anchor is auditable rather than
    asserted: ``overlapping_windows`` (every 120-month window of the panel, one
    per start row -- the primary), ``disjoint_windows`` (the panel cut into
    non-overlapping decades, which uses each month once and is the sensitivity
    check on the overlapping version's uneven month weighting), and
    ``panel_wide_comparison`` (section C's own numbers beside them, so the size
    and direction of the windowing effect is visible per season).
    """
    decade = POWER_DECADE_MONTHS
    warmup = POWER_YOY_WARMUP_MONTHS
    per_grader: dict[str, Any] = {}
    for grader, cells in cells_by_grader.items():
        n_rows = int(cells.size)
        overlapping = _decade_starts(n_rows, decade)
        disjoint = np.arange(0, n_rows - decade + 1, decade)
        pooled_overlap = _pooled_decade_spells(cells, overlapping, decade, warmup)
        pooled_disjoint = _pooled_decade_spells(cells, disjoint, decade, warmup)
        panel_wide = _completed_spells_by_quadrant(cells)
        comparison: dict[str, Any] = {}
        for i, quadrant in enumerate(QUADRANTS):
            panel_median = float(np.median(panel_wide[i])) if panel_wide[i] else float("nan")
            pooled_median = (
                float(np.median(pooled_overlap[i])) if pooled_overlap[i] else float("nan")
            )
            comparison[quadrant] = {
                "panel_wide_median_months": _f(panel_median),
                "panel_wide_n_completed_spells": len(panel_wide[i]),
                "decade_pooled_median_months": _f(pooled_median),
                "decade_minus_panel_wide_months": _f(pooled_median - panel_median),
                "panel_wide_max_spell_months": (
                    _f(float(max(panel_wide[i]))) if panel_wide[i] else None
                ),
            }
        per_grader[grader] = {
            "overlapping_windows": {
                "n_windows": int(overlapping.size),
                "per_quadrant": {
                    quadrant: _spell_summary(pooled_overlap[i], int(overlapping.size))
                    for i, quadrant in enumerate(QUADRANTS)
                },
            },
            "disjoint_windows": {
                "n_windows": int(disjoint.size),
                "starts": [int(x) for x in disjoint],
                "per_quadrant": {
                    quadrant: _spell_summary(pooled_disjoint[i], int(disjoint.size))
                    for i, quadrant in enumerate(QUADRANTS)
                },
            },
            "panel_wide_comparison": comparison,
        }
    return {
        "decade_months": decade,
        "warmup_months": warmup,
        "usable_months_per_decade": decade - warmup,
        "primary": "overlapping_windows",
        "rule": (
            "pool the COMPLETED spells of every 120-month window (12-month trailing-"
            "inflation warm-up dropped, then a spell that opens or closes the window is "
            "dropped as censored) and take the median of the pooled multiset. The window "
            "rule, the warm-up and the censoring are identical to what the sealed judge "
            "applies to a generated decade -- that identity is the point of the section"
        ),
        "why_pooling": (
            "a single decade contributes ~1-3 completed spells per season, so a "
            "per-decade median measures sampling noise; pooling the whole batch into one "
            "distribution makes the median a statement about the engine. At the sealed "
            "50 decades per premise the pooled recovery count is ~120 spells"
        ),
        "why_the_same_window_on_both_sides": (
            "a 120-month window drops the spell it opens with and the spell it closes "
            "with, and long spells are likelier to touch an edge, so a decade-measured "
            "median is systematically shorter than the same season's panel-wide median. "
            "Judging the generated side's decade-measured statistic against a "
            "panel-measured anchor is a definition mismatch of the same class the "
            "spine-02 review found in B6; the exam's remedy there (identical "
            "conditioning on both sides, T1) is applied here"
        ),
        "weighting_disclosure": (
            "overlapping windows weight the panel's months unevenly -- an interior month "
            "falls inside up to 109 windows, the first and last few years inside far "
            "fewer. disjoint_windows is the sensitivity check that uses every month "
            "exactly once; it rests on a handful of decades, so it is a check and not "
            "the anchor"
        ),
        "per_grader": per_grader,
    }


# --------------------------------------------------------------------------- #
# L -- the grader_v2 mapping fix (owner ruling, 2026-08-17)
#
# The incumbent classifier puts a month on the growth axis by asking whether its
# regime_ruleset_v1 label is REC or CRI. The ruleset's OWN stagflation label,
# STAG, is neither, so a stagflation month has been counting as EXPANDING -- the
# quirk section 11.1 found and section 11.5 caught biting on the whole of
# 1975-04..1975-12. Owner ruling: for transition/ordering purposes a stagflation
# month sits on the non-expanding side, per the owner's own definition of the
# season (growth stalling while inflation is high). ``grader_v2`` is that one
# change and nothing else; it lives in scripts/spine_v2_grader.py because the
# pilot's module and its two frozen seals must stay untouched.
#
# This section re-derives every anchor the change can move and publishes the two
# side by side. What moves and what does not is a fact about the panel, not an
# assumption: every STAG month is hot (the ruleset fires STAG only at or above
# 4.0 pp trailing CPI, the era threshold is 3.3513 pp), so months move from the
# EXPANSION cell to the STAGFLATION cell and nowhere else -- which leaves the
# recession and recovery anchors bit-identical and moves stagflation, expansion
# and the ordering fraction.
# --------------------------------------------------------------------------- #


def section_l(
    cells_incumbent: np.ndarray,
    cells_v2: np.ndarray,
    labels: np.ndarray,
    ordering_incumbent: dict[str, Any],
    ordering_v2: dict[str, Any],
) -> dict[str, Any]:
    """The mapping fix's effect on every anchor it can reach, old beside new."""
    defined = cells_incumbent >= 0
    moved = np.flatnonzero(defined & (cells_incumbent != cells_v2))
    transfers: dict[str, int] = {}
    for row in moved:
        key = f"{QUADRANTS[int(cells_incumbent[row])]} -> {QUADRANTS[int(cells_v2[row])]}"
        transfers[key] = transfers.get(key, 0) + 1

    old = _classification_anchors(cells_incumbent)
    new = _classification_anchors(cells_v2)
    per_quadrant: dict[str, Any] = {}
    for quadrant in QUADRANTS:
        o = old["per_quadrant"][quadrant]
        n = new["per_quadrant"][quadrant]
        per_quadrant[quadrant] = {
            "old_panel_wide_median_months": o["median_months"],
            "new_panel_wide_median_months": n["median_months"],
            "old_n_completed_spells": o["n_completed_spells"],
            "new_n_completed_spells": n["n_completed_spells"],
            "old_months_in_quadrant": o["months_in_quadrant"],
            "new_months_in_quadrant": n["months_in_quadrant"],
            "unchanged": bool(o["median_months"] == n["median_months"]),
            "new_sorted_spells_months": n["sorted_spells_months"],
        }
    return {
        "ruling": (
            "owner, 2026-08-17: stagflation months sit on the NON-EXPANDING side for "
            "transition/ordering purposes, per the owner's own definition of the season "
            "-- growth stalling while inflation is high"
        ),
        "grader_module": "scripts/spine_v2_grader.py",
        "contracting_labels": list(CONTRACTING_LABELS),
        "incumbent_contracting_labels": list(INCUMBENT_CONTRACTING_LABELS),
        "stag_months_in_panel": int((labels == "STAG").sum()),
        "stag_months_classifiable": int(((labels == "STAG") & defined).sum()),
        "months_moved": int(moved.size),
        "months_moved_share": _f(float(moved.size) / float(defined.sum())),
        "transfers": transfers,
        "t1_note": (
            "T1 is NOT re-anchored. Its downturn definition is the REC-or-CRI union on "
            "both sides and its band was measured on that union; the ruling is about the "
            "clock's transition/ordering axis. A STAG month is therefore contracting for "
            "the clock and still not a downturn onset for T1. Declared as a limitation"
        ),
        "a1_a2_note": (
            "A1 and A2 are untouched: both split months at the fixed 4% trailing CPI "
            "line, not at the era threshold or the growth dial, so no classifier change "
            "can reach them"
        ),
        "panel_wide_anchors": per_quadrant,
        "ordering": {
            "old_clockwise_fraction": ordering_incumbent["clockwise_fraction"],
            "new_clockwise_fraction": ordering_v2["clockwise_fraction"],
            "old_n_transitions": ordering_incumbent["n_transitions"],
            "new_n_transitions": ordering_v2["n_transitions"],
            "old_n_clockwise": ordering_incumbent["n_clockwise_transitions"],
            "new_n_clockwise": ordering_v2["n_clockwise_transitions"],
            "old_ci95": [
                ordering_incumbent["ci95_lower_edge"],
                ordering_incumbent["ci95_upper_edge"],
            ],
            "new_ci95": [ordering_v2["ci95_lower_edge"], ordering_v2["ci95_upper_edge"]],
            "old_O1_bar": ordering_incumbent["ci95_lower_edge"],
            "new_O1_bar": ordering_v2["ci95_lower_edge"],
            "paired_bootstrap_note": (
                "the two intervals are drawn from the SAME resampling tape (the same seed "
                "and the same index draws, since the draws depend only on the panel's "
                "length): the identical fake histories are scored under the two "
                "labellings, so the OLD and NEW intervals are paired and their difference "
                "is the labelling, not two different sets of random draws"
            ),
        },
        "full_ordering_v2": ordering_v2,
    }


def exam_bars_sealed(
    transmission: dict[str, Any],
    pooled_dwells: dict[str, Any],
    allocation: dict[str, Any],
    ordering: dict[str, Any],
    correlation_intervals: dict[str, Any],
    *,
    grader: str,
) -> dict[str, Any]:
    """The SEALED bar block, derived -- never restated -- from the sections above.

    Same discipline as :func:`exam_bars`, which this supersedes: T1's band is
    section B's primary bootstrap interval, A1's containment range is section
    D's episode spreads, O1's minimum is the ordering interval's lower edge and
    A2's margin is section F's. What changed, both by owner ruling of
    2026-08-17: each D band is now cut from section K's **decade-pooled** median
    for ``grader`` rather than from section C's panel-wide one, and the
    ordering interval is the one measured under the same grader.
    """
    lift_ci = transmission["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"]["rec_plus_cri"][
        "lift_ci95"
    ]
    pooled = pooled_dwells["per_grader"][grader]["overlapping_windows"]["per_quadrant"]
    dwell: dict[str, Any] = {}
    for quadrant in QUADRANTS:
        median = cast(float, pooled[quadrant]["median_months"])
        dwell[quadrant] = [
            max(0.0, median - DWELL_TOLERANCE_MONTHS),
            median + DWELL_TOLERANCE_MONTHS,
        ]
    spreads = [
        episode["returns"]["spreads_ann_arith_pp"]["commodities_minus_bonds"]
        for episode in allocation["named_episodes"].values()
        if episode["available"]
    ]
    return {
        "grader": grader,
        "T1_lift_band": [lift_ci["lo"], lift_ci["hi"]],
        "O1_clockwise_min": ordering["ci95_lower_edge"],
        "D_median_bands_months": dwell,
        "D_anchor_medians_months": {
            quadrant: pooled[quadrant]["median_months"] for quadrant in QUADRANTS
        },
        "D_tolerance_months": DWELL_TOLERANCE_MONTHS,
        "D_statistic": "median of the completed spells POOLED over the whole batch",
        "A1_containment_pp": [_f(min(spreads)), _f(max(spreads))],
        "A2_correlation_margin": correlation_intervals["correlation_level"]["ci95_lower_edge"],
        "A2_share_high_floor": A2_SHARE_HIGH_FLOOR,
        "A2_share_low_ceiling": A2_SHARE_LOW_CEILING,
        "derivation_note": (
            "T1_lift_band = b_transmission_lift's primary 24-month bootstrap interval for "
            "the recession-or-crisis lift; D_median_bands_months = each season's "
            "DECADE-POOLED completed-spell median (k_pooled_decade_dwells, overlapping "
            "windows, this bar block's grader) +- 1 quarter, floored at zero because no "
            "spell is shorter than a month; A1_containment_pp = the min and max "
            "commodities-minus-bonds spread across the five in-panel episodes; "
            "O1_clockwise_min = the ordering interval's LOWER edge measured under this "
            "grader; A2_correlation_margin = f_correlation_intervals' 95% interval's "
            "LOWER edge for the high-minus-low correlation difference"
        ),
    }


def main() -> None:
    source = campaign_source()
    yoy = panel_yoy(source)
    hazard = fit_hazard(source)
    cells = panel_quadrant(source, yoy, hazard.era_threshold_pp)
    panel_months = _month_labels(source.dates)

    transmission = section_b(source, yoy)
    regime_durations = section_c(source, cells, hazard.era_threshold_pp)
    allocation = section_d(source, yoy)
    pilot_seal = json.loads(PILOT_PREREG_PATH.read_text(encoding="utf-8"))
    ordering = section_e(cells, float(pilot_seal["b4"]["panel_clockwise_fraction"]))
    correlation_intervals = section_f(source, yoy)
    dwell_intervals = section_g(regime_durations)
    # The pre-ruling derivation, kept because section H's OPEN-4 finding is a
    # record of what those bars did and must not move when the bars are
    # re-specified. Everything sealed comes from exam_bars_sealed below.
    bars_open4 = exam_bars(
        transmission, regime_durations, allocation, ordering, correlation_intervals
    )
    power = section_h(source, yoy, cells, bars_open4)

    # grader_v2: the owner's mapping fix. One line of difference from
    # panel_quadrant -- STAG joins REC/CRI on the contracting side -- and the
    # assertion below states what that must and must not do on this panel.
    labels = np.asarray(source.labels)
    cells_v2 = grader_season_cells(labels, yoy, hazard.era_threshold_pp)
    assert np.array_equal(
        cells_v2[(cells >= 0) & (labels != "STAG")], cells[(cells >= 0) & (labels != "STAG")]
    ), "grader_v2 must differ from the incumbent classifier on STAG months and nowhere else"
    ordering_v2 = section_e(cells_v2, float(pilot_seal["b4"]["panel_clockwise_fraction"]))
    grader_v2 = section_l(cells, cells_v2, labels, ordering, ordering_v2)

    pooled_dwells = section_k({"incumbent": cells, "grader_v2": cells_v2})
    # Cross-check, not decoration: section K's decade-pooled medians are the same
    # object section H reports as its true-engine large-n limit, computed by a
    # different route (K pools spell lists window by window; H pools length
    # histograms through a matrix product). If the two ever disagree, one of them
    # is wrong and the D bars are being cut from a number nobody can reproduce.
    for code, quadrant in zip(("D1", "D2", "D3", "D4"), QUADRANTS, strict=True):
        pooled_median = pooled_dwells["per_grader"]["incumbent"]["overlapping_windows"][
            "per_quadrant"
        ][quadrant]["median_months"]
        limit_median = power["true_engine_limit_statistics"][f"{code}_median_months_{quadrant}"]
        assert pooled_median == limit_median, (
            f"{code}: section K's decade-pooled median {pooled_median} disagrees with "
            f"section H's true-engine limit {limit_median}"
        )

    bars = exam_bars_sealed(
        transmission,
        pooled_dwells,
        allocation,
        ordering_v2,
        correlation_intervals,
        grader="grader_v2",
    )
    power_sealed = section_h(source, yoy, cells_v2, bars)

    # Sections I and J read two series the factor panel does not carry
    # (fred.USREC and fred.INDPRO for the re-labelling, fred.UNRATE for the
    # labor voter) plus the untruncated factor frames, so they open the same
    # pinned campaign vintage campaign_source() reads. Read-only and offline.
    catalog, access = _catalog_access(_REPO_ROOT / "data", CAMPAIGN_VINTAGE_ID)
    try:
        frames = read_factor_frames(access, load_manifest())
        stability = section_i(
            source,
            yoy,
            cells,
            hazard.era_threshold_pp,
            access,
            frames,
            regime_durations,
            ordering,
            dwell_intervals,
            bars_open4,
            bars,
            CONTRACTING_LABELS,
        )
        richer = section_j(
            source, yoy, cells, hazard.era_threshold_pp, access, ordering, dwell_intervals
        )
    finally:
        catalog.close()

    anchors: dict[str, Any] = {
        "schema": "spine-v2-anchors-4",
        "purpose": (
            "Historical anchors measured BEFORE the decade generator's economic engine "
            "is rebuilt (spine v2, stage 1). Every number is reproducible by re-running "
            "scripts/spine_v2_anchors.py. Sections A-D are measurement only; sections "
            "E-H close the exam's four OPEN items and DO carry the two thresholds the "
            "exam cuts from them (O1's minimum and A2's margin), each stated as the "
            "lower edge of the historical interval beside it."
        ),
        "panel": {
            "vintage_id": source.vintage_id,
            "ruleset_version": source.ruleset_version,
            "months": int(source.n_rows),
            "span": [panel_months[0], panel_months[-1]],
            "factor_names": list(source.factor_names),
            "split_note": (
                "campaign train+validation only (ah.splits: train 1871-01..2010-12, "
                "validation 2011-01..2020-12). The holdout (2021-01 onward) is not read"
            ),
        },
        "source_module_sha256": {
            "src/ah/gen/spine.py": _sha256(_REPO_ROOT / "src" / "ah" / "gen" / "spine.py"),
            "src/ah/gen/bootstrap.py": _sha256(_REPO_ROOT / "src" / "ah" / "gen" / "bootstrap.py"),
            "src/ah/data/derive.py": _sha256(_REPO_ROOT / "src" / "ah" / "data" / "derive.py"),
        },
        "a_event_chronology": section_a(source, yoy, cells),
        "b_transmission_lift": transmission,
        "c_regime_durations": regime_durations,
        "d_allocation_episode_facts": allocation,
        "e_ordering": ordering,
        "f_correlation_intervals": correlation_intervals,
        "g_dwell_intervals": dwell_intervals,
        "h_generated_side_power": power,
        "i_label_stability": stability,
        "j_richer_identification": richer,
        "k_pooled_decade_dwells": pooled_dwells,
        "l_grader_v2": grader_v2,
        "m_power_under_sealed_bars": power_sealed,
        "exam_bars": bars,
        "exam_bars_superseded": {
            "open4_derivation": bars_open4,
            "note": (
                "the bar block as it stood when OPEN-4 measured power against it "
                "(h_generated_side_power). Superseded 2026-08-17 by the owner's pre-seal "
                "rulings; kept so the OPEN-4 finding stays readable against the bars it "
                "was actually measured on. exam_bars is what is sealed"
            ),
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": this file's own bytes are hashed into the v2 seal, and
    # Python's default text mode writes CRLF on Windows while git stores LF
    # (.gitattributes, eol=lf) -- so the sealed hash would otherwise depend on
    # which platform last ran the script. Writing LF explicitly makes the hash
    # the same everywhere and equal to what a fresh clone checks out.
    OUT_PATH.write_text(
        json.dumps(anchors, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"wrote {OUT_PATH}")
    for name in ("cri_only", "rec_plus_cri"):
        point = anchors["b_transmission_lift"]["point_estimates"][name]
        ci = anchors["b_transmission_lift"]["bootstrap_ci95"][f"block_{PRIMARY_BLOCK_MONTHS}m"][
            name
        ]["lift_ci95"]
        print(
            f"B {name:13s} lift = {point['lift']:.4f}  "
            f"[{ci['lo']:.4f}, {ci['hi']:.4f}] (block {PRIMARY_BLOCK_MONTHS}m)"
        )
    for quadrant in QUADRANTS:
        row = anchors["c_regime_durations"]["per_quadrant"][quadrant]
        print(
            f"C {quadrant:12s} n={row['n_completed_spells']:3d}  "
            f"median={row['median_months']} months ({row['median_quarters']:.3f} quarters)"
        )
    corr = anchors["d_allocation_episode_facts"]["inflation_states"]["cpi_yoy_ge_4pct"][
        "stock_bond_correlation"
    ]
    print(f"D stock-bond corr: high={corr['high_inflation']:.4f}  low={corr['low_inflation']:.4f}")
    print(
        f"E clockwise fraction = {ordering['clockwise_fraction']:.4f} on "
        f"{ordering['n_transitions']} transitions  "
        f"[{ordering['ci95_lower_edge']:.4f}, {ordering['ci95_upper_edge']:.4f}]  "
        f"reproduces pilot seal: {ordering['reproduces_pilot_seal_exactly']}"
    )
    level = correlation_intervals["correlation_level"]
    share = correlation_intervals["share_of_rolling_windows_positive"]
    print(
        f"F corr difference = {level['difference']:.4f}  "
        f"[{level['ci95_lower_edge']:.4f}, {level['ci95_upper_edge']:.4f}]"
    )
    print(
        f"F share-positive difference = {share['difference']:.4f}  "
        f"[{share['ci95_lower_edge']:.4f}, {share['ci95_upper_edge']:.4f}]"
    )
    for quadrant in QUADRANTS:
        row = dwell_intervals["per_quadrant"][quadrant]
        print(
            f"G {quadrant:12s} median={row['median_months']:.1f}m  "
            f"[{row['ci95_months'][0]:.1f}, {row['ci95_months'][1]:.1f}]  "
            f"tolerance wider: {row['tolerance_at_least_as_wide']}"
        )
    for name, row in power["per_bar"].items():
        print(
            f"H {name:20s} power at n={POWER_PILOT_N_SEEDS}: "
            f"{row['power_at_pilot_n_seeds']:.3f}  "
            f"min n for {POWER_TARGET:.0%}: {row['min_n_seeds_for_target']}"
        )
    for quadrant in QUADRANTS:
        row = pooled_dwells["per_grader"][bars["grader"]]["panel_wide_comparison"][quadrant]
        print(
            f"K {quadrant:12s} panel-wide {row['panel_wide_median_months']:.1f}m  "
            f"decade-pooled {row['decade_pooled_median_months']:.1f}m  "
            f"band {bars['D_median_bands_months'][quadrant]}"
        )
    for name, row in power_sealed["per_bar"].items():
        print(
            f"M {name:20s} power at n={SEALED_N_SEEDS}: "
            f"{row['power_by_n_seeds'][str(SEALED_N_SEEDS)]:.3f}  "
            f"min n for {POWER_TARGET:.0%}: {row['min_n_seeds_for_target']}"
        )
    for name, row in stability["verdicts"].items():
        print(
            f"I {name:26s} arms [{row['arm_min']:.4f}, {row['arm_max']:.4f}]  "
            f"ci95 [{row['sampling_ci95'][0]:.4f}, {row['sampling_ci95'][1]:.4f}]  "
            f"{row['verdict']}"
        )
    for name, row in stability["bar_band_check"].items():
        print(f"I bar-band {name:26s} arms outside its own bar: {row['arms_outside']}")
    dis = richer["disagreement"]
    print(
        f"J disagreement = {dis['disagreeing_months']}/{dis['defined_months']} months "
        f"({dis['fraction']:.4f}), {dis['n_clusters']} clusters of "
        f">= {dis['cluster_min_months']} months"
    )
    for name, row in richer["decisions"].items():
        print(
            f"J {name:26s} simple={row['simple']:.4f} richer={row['richer']:.4f}  "
            f"change={row['change']:.4f} vs half-width "
            f"{row['sampling_ci95_half_width']:.4f}  {row['verdict']}"
        )
    print(f"J recommended sealed grader: {richer['recommended_sealed_grader']}")


if __name__ == "__main__":
    main()
