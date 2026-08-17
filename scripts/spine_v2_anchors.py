"""Spine v2, stage 1: measure the historical facts the rebuilt exam will grade against.

Writes ``docs/superpowers/specs/spine-v2-anchors.json``. Deterministic and
offline: the only data read is the local DuckDB/Parquet catalog through
``ah.gen.bootstrap.campaign_source`` (the same panel the spine pilot measured),
and the only randomness is the block bootstrap in section B, drawn from a single
``numpy.random.Generator(PCG64(BOOTSTRAP_SEED))`` with ``BOOTSTRAP_SEED`` a
literal constant below. Re-running reproduces the JSON byte for byte.

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
from ah.gen.spine import QUADRANTS, fit_hazard, panel_quadrant, panel_yoy
from ah.strategies import load_derived_series

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-v2-anchors.json"

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


def main() -> None:
    source = campaign_source()
    yoy = panel_yoy(source)
    hazard = fit_hazard(source)
    cells = panel_quadrant(source, yoy, hazard.era_threshold_pp)
    panel_months = _month_labels(source.dates)

    anchors: dict[str, Any] = {
        "schema": "spine-v2-anchors-1",
        "purpose": (
            "Historical anchors measured BEFORE the decade generator's economic engine "
            "is rebuilt (spine v2, stage 1). Every number is reproducible by re-running "
            "scripts/spine_v2_anchors.py; no number here is a threshold yet."
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
        "b_transmission_lift": section_b(source, yoy),
        "c_regime_durations": section_c(source, cells, hazard.era_threshold_pp),
        "d_allocation_episode_facts": section_d(source, yoy),
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


if __name__ == "__main__":
    main()
