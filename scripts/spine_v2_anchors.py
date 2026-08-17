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
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from ah.eval.metrics.tails import derived_series_values
from ah.gen.bootstrap import campaign_source
from ah.gen.regimes.semimarkov import spells_from_labels
from ah.gen.spine import CLOCKWISE, QUADRANTS, fit_hazard, panel_quadrant, panel_yoy
from ah.strategies import load_derived_series

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

#: The exam's +-1 quarter dwell tolerance, in months. A policy choice (the
#: quarter is the game's smallest play unit), not an estimate -- section G
#: measures the sampling wobble beside it but does not set it.
DWELL_TOLERANCE_MONTHS = 3.0
#: A2(ii)'s two edges. Policy choices cut from the published 3%/4%/5% threshold
#: range, not from a sampling interval, so section F does not move them.
A2_SHARE_HIGH_FLOOR = 0.80
A2_SHARE_LOW_CEILING = 0.65

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
    bars = exam_bars(transmission, regime_durations, allocation, ordering, correlation_intervals)
    power = section_h(source, yoy, cells, bars)

    anchors: dict[str, Any] = {
        "schema": "spine-v2-anchors-2",
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
        "exam_bars": bars,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(anchors, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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


if __name__ == "__main__":
    main()
