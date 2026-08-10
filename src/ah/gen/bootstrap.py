"""``bootstrap-v1`` -- the frozen benchmark generator (STEP2 Sec.WP2.4).

**This module implements a specification it does not own.** Every parameter below --
the stationary form and its draw rule, the mean block length, the draw span, the factor
set, the stratification scheme, the criterion ensemble size -- is sealed in
``pre-registration.yaml``'s ``bootstrap_v1`` block, hashed into
``pre-registration.lock``, and frozen *before this module existed*, deliberately, so the
benchmark could not be shaped to fit the battery that judges it. Where the sealed
document and this code disagree, the document wins and the code is the defect;
``tests/test_bootstrap.py`` asserts every constant here against the sealed YAML so the
two cannot drift.

What the benchmark is
---------------------
A Politis-Romano **stationary block bootstrap** over the real historical panel,
stratified by the Step-1 regime label of each block's start month. The sealed
``form_statement``, verbatim:

    Draw a uniform start index in [0, T); at each subsequent month, with probability
    p = 1/mean_block_months draw a fresh uniform start, otherwise advance the current
    index by one, WRAPPING CIRCULARLY (index T maps to 0). Block lengths are therefore
    Geometric(p) with mean mean_block_months, which is what makes the resampled series
    stationary -- a fixed-length block bootstrap is not. The circular wrap is part of
    the definition, not an implementation convenience: without it, late-sample rows are
    under-sampled.

Stratification replaces "a uniform start index in [0, T)" with "a uniform start index
among the rows whose regime label is the one drawn for this month". Under *unconditional*
sampling the regime is itself drawn at its historical frequency over the draw span, so
the composition ``P(regime) x Uniform(rows of that regime)`` is exactly uniform over
``[0, T)`` again -- the stratified unconditional draw and the plain uniform draw are the
same distribution, which is why the sealed ``block_length_derivation``'s measurements
(taken on an unstratified prototype) transfer without qualification. Under *conditioned*
sampling a WorldSpec regime sequence replaces the frequency draw and the composition is
no longer uniform: that is the whole point of the stratification machinery.

Multivariate blocks, never per-factor resampling
------------------------------------------------
A block is a contiguous window across **all** factors at once: one shared row index into
a ``(T, n_factors)`` source matrix. This is the single most important structural property
of the benchmark. A per-factor resample would leave every marginal statistic looking
identical while destroying exactly what the cross-block correlation, crisis-co-movement
and lead-lag statistics measure -- so ``tests/test_bootstrap.py`` checks it exactly (on a
source whose every column is an injective function of the row index) rather than
statistically.

What it deliberately cannot do
-------------------------------
- **No ``factor_conditions`` mechanism, ever.** The sealed ``conditioning_statement``
  says so: bootstrap-v1 honours a WorldSpec's regime sequence (via stratification) and
  nothing else. Its conditional-tier failure is expected and is measured evidence, not a
  defect to fix.
- **The span reaches 1953-04** (AM-2026-08-09-002, the span-53 ratification; as sealed
  at G2 it was 1990-01, bound by equity_vol, and the severe test was NOT posable).
  The extended ``block_draw_span`` is 1953-04..2020-12, bound by ``ust_2y``'s GS1/GS3
  donor floor; a multivariate block can only be drawn where the whole panel exists, and
  serving that panel is campaign-3's read-path flip -- until its seal, draws over the
  extension cannot run (spec now, wiring at campaign-3). WP2.11's severe test is now
  **posable for both sides**; :data:`SEVERE_TEST_POSABLE` states that in code.

Layering
--------
``ah.gen`` may never import ``ah.eval`` (``CLAUDE.md``'s leakage guard; the enforced
half is the ``ah.eval.g2`` import-graph test, the stated rule is the whole package).
:func:`read_factor_frames` is therefore a second implementation of the factor-id ->
Step-1-series resolution that ``ah.eval.panel.read_factor_frames`` already performs, and
that duplication is a real risk: two independent definitions of one mapping is the defect
class this repository keeps finding. ``ah.eval.panel`` is a *sealed* judged source and
cannot be refactored into a shared home without an amendment, so the duplication is
closed by a machine check instead --
``tests/test_bootstrap.py::test_local_factor_resolution_matches_ah_eval_panel`` asserts
the two resolvers return identical frames for the real manifest, and a test module may
import both layers where a generator module may not.

Data surface
------------
Real data is read only through :class:`ah.splits.DataAccess`, whose ``train_val`` is the
sanctioned reference surface; the holdout is unreachable from here (this module never
constructs or imports a :class:`~ah.splits.FinalEvaluationToken`). The campaign vintage
is pinned to :data:`CAMPAIGN_VINTAGE_ID`.

Determinism
-----------
All randomness flows from one integer seed through
``numpy.random.Generator(PCG64(seed))``; ensemble seeds are ``base_seed + 7919*k``
(:data:`SEED_STRIDE`). No global RNG, no clock reads. The same seed against the same
source gives a bit-identical ensemble.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ah.core.numericworld import NumericWorld
from ah.data import derive
from ah.factors import FactorManifest, FactorSource, load_manifest
from ah.gen import registry
from ah.gen.base import AbsentLayer, Ensemble, EnsembleMeta, RegimeRecord
from ah.splits import DataAccess

__all__ = [
    "BLOCK_DRAW_SPAN_BINDING_FACTOR",
    "BLOCK_DRAW_SPAN_END",
    "BLOCK_DRAW_SPAN_MONTHS",
    "BLOCK_DRAW_SPAN_START",
    "BLOCK_LENGTH_DISTRIBUTION",
    "CAMPAIGN_VINTAGE_ID",
    "CRITERION_MONTHS",
    "CRITERION_N_PATHS",
    "FACTOR_SET",
    "FORM",
    "GENERATOR_ID",
    "MEAN_BLOCK_MONTHS",
    "REGIME_LABELS",
    "SEED_STRIDE",
    "SEVERE_TEST_POSABLE",
    "STRATIFICATION",
    "WORLDSPEC_REGIME_TO_LABEL",
    "BootstrapError",
    "BootstrapSource",
    "BootstrapV1",
    "bootstrap_v1_factory",
    "build_source",
    "campaign_source",
    "read_factor_frames",
    "validated_active_blocks",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]

# --------------------------------------------------------------------------- #
# THE SEALED SPEC. Every constant below is `pre-registration.yaml`'s `bootstrap_v1`
# block (or, for the ensemble size, its `ensemble_size:` block), restated in code and
# asserted equal to the sealed document by tests/test_bootstrap.py. Changing one of
# these numbers is a change to a sealed value: it needs a dated amendment in
# governance/amendment-log.yaml and a re-seal, not an edit here.
# --------------------------------------------------------------------------- #

GENERATOR_ID = "bootstrap-v1"
FORM = "stationary_block_bootstrap"
BLOCK_LENGTH_DISTRIBUTION = "geometric"

#: Sealed mean block length. Bounded BELOW by `dependence_band_exceedance_fraction`
#: (short blocks destroy serial dependence; L=3 fails outright, L=4 sits exactly on the
#: bound in its worst seed) and ABOVE by the memorization surface (a stationary bootstrap
#: emits a verbatim 24-month window with probability (1-1/L)**23, and `nn_distance_p05`
#: collapses to 0.0 once that rate passes 5%). The sealed window at twelve factors is
#: roughly 5 <= L <= 9; 6 sits inside it, ONE STEP from the lower edge.
MEAN_BLOCK_MONTHS = 6

# AM-2026-08-09-002 (span-53 ratification): 1990-01/372/equity_vol -> the
# extended span. Spec now, wiring at campaign-3 -- draws over the extension
# require the campaign-3 read-path flip and its re-derived references.
BLOCK_DRAW_SPAN_START = "1953-04-01"
BLOCK_DRAW_SPAN_END = "2020-12-01"  # inclusive -- 813 months of 1953-04..2020-12
BLOCK_DRAW_SPAN_MONTHS = 813
BLOCK_DRAW_SPAN_BINDING_FACTOR = "ust_2y"

#: Every active factor with train+validation data on the sealed campaign vintage.
#: Campaign-2 (2026-08-02, owner-ratified): hy_spread revived via the pinned
#: hy_oas_pre1996 splice at the read surface; fx_usd and cape_v added by the fx
#: and valuation block_addition amendments. commodities stays declared-unavailable.
FACTOR_SET: tuple[str, ...] = (
    "cape_v",
    "cpi",
    "equity_mkt",
    "equity_vol",
    "funding_spread",
    "fx_usd",
    "hml",
    "hqm_curve",
    "hy_spread",
    "ig_spread",
    "mom",
    "policy_rate",
    "smb",
    "ust_10y",
    "ust_2y",
)

STRATIFICATION = "regime_ruleset_v1"
#: Campaign-2 vintage (S2-CAMPAIGN-VINTAGE-2): four iterations recorded in the
#: retrofit register (RFR-91/92); the RFR-61 discipline applies -- pre-existing
#: factors' bands are re-derived on this vintage and any movement is disclosed.
CAMPAIGN_VINTAGE_ID = "2026-08-02.4"

#: The sealed criterion ensemble size. A run at any other size -- or against any vintage
#: other than `CAMPAIGN_VINTAGE_ID` -- is diagnostic only;
#: `ah.eval.battery.BatteryReport.criterion_bearing` records which it was.
CRITERION_N_PATHS = 1024
CRITERION_MONTHS = 120

#: See the module docstring. False from the G2 seal until AM-2026-08-09-002 extended
#: the span past the excluded decade; the constant exists so a caller (and the
#: evidence documents) can assert it rather than recall it.
SEVERE_TEST_POSABLE = True

SEED_STRIDE = 7919  # CLAUDE.md's ensemble seed rule: base_seed + 7919*k

#: The six Step-1 ruleset labels, taken from `ah.data.derive` rather than restated.
REGIME_LABELS: tuple[str, ...] = tuple(derive.REGIME_LABELS)

# --------------------------------------------------------------------------- #
# The two regime features that no factor supplies.
#
# `ah.data.derive.label_regime` classifies a month from five inputs. THREE come from
# factors already in the sealed FACTOR_SET (`cpi` -> cpi_yoy, `equity_mkt` -> drawdown,
# and `hy_spread` -> hy_oas, which is absent -- see below). The other two,
# `usrec` (NBER recession) and `growth_yoy` (industrial production), have no
# `factors.yaml` mapping at all and are read directly from their registered
# requirements.yaml series ids, through the same train+validation surface.
#
# This is a stratification input, not a generated factor: neither series is emitted in
# any ensemble, and neither enters the factor set the battery judges.
# --------------------------------------------------------------------------- #
USREC_SERIES_ID = "fred.USREC"
INDPRO_SERIES_ID = "fred.INDPRO"

# --------------------------------------------------------------------------- #
# WorldSpec regime name -> Step-1 ruleset label.
#
# NOT SUPPLIED BY THE SEAL, and recorded here as the choice it is. The sealed
# `stratification_statement` says a conditioned WorldSpec "pins the stratification path:
# the start regime of each block is the requested regime for that month", and names the
# six ruleset labels -- but the WorldSpec schema's `RegimeName` enumerates EIGHT names,
# so two of them have no label of their own and the mapping had to be chosen. It is
# stated here, tested for exhaustiveness (an unmapped name would silently fall back to an
# unconditional draw), and reported in WP2.4's write-up:
#
#   recovery       -> EXP  a recovery is a post-recession expansion; the ruleset's EXP
#                          branch ("not in recession, growth >= growth_slow, inflation
#                          below cpi_high") is exactly where a recovery month lands.
#   deflation_boom -> EXP  strong growth with low inflation is, under regime_ruleset_v1,
#                          an EXP month: the ruleset has no deflation branch at all.
#
# Both collapses are lossy and both are visible in the ensemble metadata's
# `requested_regimes`, so a reader can see that a world asking for `deflation_boom` was
# served EXP months rather than something the label set can actually distinguish.
# --------------------------------------------------------------------------- #
WORLDSPEC_REGIME_TO_LABEL: Mapping[str, str] = {
    "expansion": "EXP",
    "slowdown": "SLOW",
    "recession": "REC",
    "crisis": "CRI",
    "recovery": "EXP",
    "stagflation": "STAG",
    "reflation": "REF",
    "deflation_boom": "EXP",
}


class BootstrapError(RuntimeError):
    """Raised for a source that cannot honestly be built, or a malformed sample request."""


# --------------------------------------------------------------------------- #
# active_blocks -- RFR-4's missing producer
# --------------------------------------------------------------------------- #


def validated_active_blocks(
    manifest: FactorManifest, declared: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """``manifest.active_blocks``, checked rather than trusted (RFR-4).

    ``EnsembleMeta.active_blocks`` has existed since WP2.1b with a default of ``()`` and
    no producer at all; ``bootstrap-v1`` is the first generator, so it is the first
    producer, and the retrofit row asks for the field to be *validated against the
    manifest* rather than copied on faith. ``declared`` is the value a caller believes
    the ensemble was generated over; passing ``None`` simply adopts the manifest's.

    Raises :class:`BootstrapError` when the two disagree -- an ensemble labelled with
    blocks it was not generated over is worse than one labelled with nothing.
    """
    live = tuple(manifest.active_blocks)
    if declared is not None and tuple(declared) != live:
        raise BootstrapError(
            f"active_blocks mismatch: ensemble declares {tuple(declared)}, the live "
            f"factor manifest declares {live}"
        )
    return live


# --------------------------------------------------------------------------- #
# the factor-id -> Step-1-series resolver (see the module docstring's "Layering")
# --------------------------------------------------------------------------- #

# Each `kind: derived` expr's ah.data.derive helper and the exact positional arity it
# expects. Mirrors ah.eval.panel._DERIVED_EXPRS; the equivalence test is what keeps the
# two tables identical.
_DERIVED_EXPRS: dict[str, tuple[int, Any]] = {
    "add": (2, lambda frames: derive.add(frames[0], frames[1])),
    "difference": (2, lambda frames: derive.difference(frames[0], frames[1])),
    "funding_stress": (1, lambda frames: derive.funding_stress(frames[0])),
    # campaign-2 seal additions -- mirrored from ah.eval.panel._DERIVED_EXPRS,
    # kept identical by the equivalence test.
    "hy_oas_spliced": (3, lambda frames: derive.hy_oas_spliced(frames[0], frames[1], frames[2])),
    "fx_usd_spliced": (2, lambda frames: derive.fx_usd_spliced(frames[0], frames[1])),
    "demeaned_log_cape": (1, lambda frames: derive.demeaned_log_cape(frames[0])),
}

#: Mirrors ah.eval.panel's DerivedExpr.optional_inputs for the one pinned-splice
#: case: fred.HY_OAS's train+validation read is empty by construction and the
#: transform handles it. The equivalence test pins this to panel's declaration.
_OPTIONAL_INPUTS: dict[str, tuple[int, ...]] = {"hy_oas_spliced": (0,)}


def _read_series(access: DataAccess, series_id: str) -> pd.DataFrame | None:
    """``access.train_val(series_id)``, or ``None`` for an unknown/empty series."""
    try:
        frame = access.train_val(series_id)
    except KeyError:
        return None
    if frame.empty:
        return None
    if not {"date", "value"} <= set(frame.columns):
        raise BootstrapError(
            f"series '{series_id}': train_val frame lacks the canonical date/value columns"
        )
    return frame


def _resolve_derived(source: FactorSource, factor: str, frames: list[pd.DataFrame]) -> pd.DataFrame:
    assert source.expr is not None
    spec = _DERIVED_EXPRS.get(source.expr)
    if spec is None:
        raise BootstrapError(
            f"factor '{factor}': unknown derived expr '{source.expr}'; "
            f"known: {sorted(_DERIVED_EXPRS)}"
        )
    arity, fn = spec
    if len(frames) != arity:
        raise BootstrapError(
            f"factor '{factor}': derived expr '{source.expr}' expects {arity} input(s), "
            f"got {len(frames)}"
        )
    return fn(frames)


def read_factor_frames(access: DataAccess, manifest: FactorManifest) -> dict[str, pd.DataFrame]:
    """Every **available** active factor's train+validation ``(date, value)`` frame.

    A factor with no data (``kind: unavailable``, or a declared source that returned
    nothing) is simply absent from the result -- a data gap is a fact about the world,
    not an error. Deliberately identical in behaviour to
    ``ah.eval.panel.read_factor_frames``'s ``frames`` mapping; see the module docstring's
    "Layering" for why it exists twice and what stops the two drifting.
    """
    frames: dict[str, pd.DataFrame] = {}
    for factor in manifest.active_factors():
        source = manifest.sources[factor]
        if source.kind == "unavailable":
            continue
        if source.kind == "series":
            assert source.series_id is not None
            raw = _read_series(access, source.series_id)
            if raw is not None:
                frames[factor] = raw
            continue
        if source.kind == "derived":
            optional = _OPTIONAL_INPUTS.get(source.expr or "", ())
            inputs: list[pd.DataFrame] = []
            any_missing = False
            for position, series_id in enumerate(source.inputs):
                raw = _read_series(access, series_id)
                if raw is None:
                    if position in optional:
                        raw = pd.DataFrame(
                            {"date": pd.Series([], dtype="datetime64[ns]"), "value": []}
                        )
                    else:
                        any_missing = True
                        break
                inputs.append(raw)
            if any_missing:
                continue
            derived_frame = _resolve_derived(source, factor, inputs)
            if not derived_frame.empty:
                frames[factor] = derived_frame
            continue
        raise BootstrapError(f"factor '{factor}': unknown source kind '{source.kind}'")
    return frames


# --------------------------------------------------------------------------- #
# the fitted source: a panel, its regime labels, and the strata they induce
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BootstrapSource:
    """The block-draw span: what the benchmark resamples, and how it is stratified.

    ``values`` is ``(T, n_factors)`` in ``factor_names`` order, over the ``T`` months of
    ``dates`` -- one shared row index across every factor, which is what makes a block
    multivariate. ``labels[i]`` is month ``i``'s ``regime_ruleset_v1`` label.

    ``strata`` and ``label_frequencies`` are derived in ``__post_init__`` and are the
    only things the sampler consults: the row indices available under each label, and
    each label's historical frequency over this span.
    """

    factor_names: tuple[str, ...]
    dates: pd.DatetimeIndex
    values: np.ndarray
    labels: tuple[str, ...]
    ruleset_version: str
    vintage_id: str
    active_blocks: tuple[str, ...]
    strata: Mapping[str, np.ndarray] = field(init=False, repr=False)
    label_frequencies: Mapping[str, float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=np.float64)
        if values.ndim != 2:
            raise BootstrapError(f"source values must be (T, n_factors); got {values.shape}")
        if values.shape[1] != len(self.factor_names):
            raise BootstrapError("source values' last dim must match len(factor_names)")
        if values.shape[0] != len(self.labels) or values.shape[0] != len(self.dates):
            raise BootstrapError("source values, dates and labels must all have T rows")
        if values.shape[0] == 0:
            raise BootstrapError("source is empty; a bootstrap needs rows to draw from")
        if not bool(np.all(np.isfinite(values))):
            raise BootstrapError(
                "source carries non-finite values; the draw span must be a complete panel"
            )
        unknown = sorted(set(self.labels) - set(REGIME_LABELS))
        if unknown:
            raise BootstrapError(
                f"source carries labels {unknown} that regime_ruleset_v1 does not define; "
                f"known: {list(REGIME_LABELS)}"
            )
        labels = np.asarray(self.labels)
        strata = {
            label: np.flatnonzero(labels == label)
            for label in REGIME_LABELS
            if np.any(labels == label)
        }
        frequencies = {label: float(idx.size) / labels.size for label, idx in strata.items()}
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "strata", strata)
        object.__setattr__(self, "label_frequencies", frequencies)

    @property
    def n_rows(self) -> int:
        return int(self.values.shape[0])

    @property
    def n_factors(self) -> int:
        return int(self.values.shape[1])

    def check_active_blocks(self, live: tuple[str, ...]) -> None:
        """Raise unless this source's ``active_blocks`` equals ``live`` (RFR-4)."""
        if tuple(self.active_blocks) != tuple(live):
            raise BootstrapError(
                f"active_blocks mismatch: source declares {tuple(self.active_blocks)}, "
                f"the live factor manifest declares {tuple(live)}"
            )


def _monthly(frame: pd.DataFrame) -> pd.Series:
    """A ``(date, value)`` frame as a date-indexed, sorted, float series."""
    series = frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")["value"]
    return series.astype(np.float64).sort_index()


def _yoy_percent(level: pd.Series) -> pd.Series:
    """Trailing 12-month percent change of a level series."""
    return (level / level.shift(12) - 1.0) * 100.0


def _drawdown_fraction(returns: pd.Series) -> pd.Series:
    """Peak-to-current drawdown of a cumulative total-return index, as a fraction <= 0.

    Computed over the factor's OWN full train+validation history rather than over the
    draw span: the running maximum at 1990-01 must know about the 1926-1989 peaks, or
    every early-span month reads as a fresh high.
    """
    clean = returns.dropna()
    index = (1.0 + clean).cumprod()
    return index / index.cummax() - 1.0


def regime_labels_for(
    dates: pd.DatetimeIndex,
    *,
    cpi_level: pd.Series,
    equity_returns: pd.Series,
    usrec: pd.Series,
    indpro: pd.Series,
) -> tuple[str, ...]:
    """``regime_ruleset_v1`` labels for ``dates``, via :func:`ah.data.derive.label_regime`.

    The five inputs ``label_regime`` needs, and where each comes from:

    - ``cpi_yoy``     -- trailing 12m percent change of the ``cpi`` factor (a level).
    - ``growth_yoy``  -- trailing 12m percent change of ``fred.INDPRO``.
    - ``drawdown``    -- peak-to-current drawdown of the ``equity_mkt`` cumulative index.
    - ``usrec``       -- ``fred.USREC``, the NBER recession indicator.
    - ``hy_oas``      -- **NaN, always.** ``hy_spread``'s entire licensed history falls
      inside the holdout, so it is in the sealed ``reference_run.missing_factors`` and no
      train+validation value exists. ``NaN >= hy_crisis`` is ``False``, so the CRI
      branch's high-yield disjunct is simply dead and CRI rests on the drawdown disjunct
      alone -- exactly the "KNOWN GAP IN THE LABELS THEMSELVES" the sealed
      ``stratification_statement`` records, made explicit here rather than rediscovered.

    Raises :class:`BootstrapError` if any of the four observable features is missing for
    any requested month: a silently-defaulted feature changes labels, and a label change
    changes what every conditioned draw resamples.
    """
    features = pd.DataFrame(index=dates)
    features["cpi_yoy"] = _yoy_percent(cpi_level).reindex(dates)
    features["growth_yoy"] = _yoy_percent(indpro).reindex(dates)
    features["drawdown"] = _drawdown_fraction(equity_returns).reindex(dates)
    features["usrec"] = usrec.reindex(dates)

    missing = features.columns[features.isna().any()].tolist()
    if missing:
        first_bad = features.index[features.isna().any(axis=1)][0]
        raise BootstrapError(
            f"regime features {sorted(missing)} are incomplete over the draw span "
            f"(first gap at {first_bad.date()}); a defaulted feature would silently "
            f"change the stratification"
        )

    thresholds = derive.regime_thresholds()
    return tuple(
        derive.label_regime(
            usrec=float(row.usrec),
            cpi_yoy=float(row.cpi_yoy),
            growth_yoy=float(row.growth_yoy),
            drawdown=float(row.drawdown),
            hy_oas=float("nan"),  # see the docstring: no train+validation hy_spread exists
            thr=thresholds,
        )
        for row in features.itertuples()
    )


def build_source(
    access: DataAccess,
    manifest: FactorManifest,
    *,
    vintage_id: str = CAMPAIGN_VINTAGE_ID,
    enforce_sealed_span: bool = True,
) -> BootstrapSource:
    """Assemble the sealed draw span, its factor matrix and its regime labels.

    The span is derived, never asserted: every available active factor's frame is joined
    on date and the rows where **all** of them are simultaneously observed are kept --
    which is the sealed ``block_draw_span_rule`` verbatim, and which is why the result is
    checked against the sealed ``block_draw_span`` rather than trusted to match it.
    ``enforce_sealed_span=False`` exists only for a caller deliberately measuring a
    different vintage (a provenance script); a production fit leaves it on.

    Raises :class:`BootstrapError` if the derived factor set or span disagrees with the
    seal -- a benchmark quietly resampling a different window, or a different set of
    factors, than the one every sealed band was reasoned about is exactly the failure the
    seal exists to make impossible.
    """
    active_blocks = validated_active_blocks(manifest)
    frames = read_factor_frames(access, manifest)

    factors = tuple(sorted(frames))
    if enforce_sealed_span and factors != FACTOR_SET:
        raise BootstrapError(
            f"resolved factor set {factors} != the sealed bootstrap_v1.factor_set "
            f"{FACTOR_SET}; the benchmark must emit exactly the sealed set"
        )

    panel = derive.assemble_panel({name: frames[name] for name in factors})
    panel = panel.assign(date=pd.to_datetime(panel["date"])).set_index("date").sort_index()
    span = panel[list(factors)].dropna()
    if span.empty:
        raise BootstrapError(
            "no month has every factor simultaneously observed; the multivariate draw span is empty"
        )

    dates = pd.DatetimeIndex(span.index)
    if enforce_sealed_span:
        want_start = pd.Timestamp(BLOCK_DRAW_SPAN_START)
        want_end = pd.Timestamp(BLOCK_DRAW_SPAN_END)
        if dates[0] != want_start or dates[-1] != want_end or len(dates) != BLOCK_DRAW_SPAN_MONTHS:
            raise BootstrapError(
                f"derived draw span {dates[0].date()}..{dates[-1].date()} "
                f"({len(dates)} months) != the sealed block_draw_span "
                f"{BLOCK_DRAW_SPAN_START}..{BLOCK_DRAW_SPAN_END} "
                f"({BLOCK_DRAW_SPAN_MONTHS} months)"
            )

    usrec_frame = _read_series(access, USREC_SERIES_ID)
    indpro_frame = _read_series(access, INDPRO_SERIES_ID)
    if usrec_frame is None or indpro_frame is None:
        raise BootstrapError(
            f"the stratification needs {USREC_SERIES_ID} and {INDPRO_SERIES_ID}; "
            f"one or both produced no train+validation data"
        )

    labels = regime_labels_for(
        dates,
        cpi_level=_monthly(frames["cpi"]),
        equity_returns=_monthly(frames["equity_mkt"]),
        usrec=_monthly(usrec_frame),
        indpro=_monthly(indpro_frame),
    )

    return BootstrapSource(
        factor_names=factors,
        dates=dates,
        values=span.to_numpy(dtype=np.float64),
        labels=labels,
        ruleset_version=str(derive.regime_thresholds()["version"]),
        vintage_id=vintage_id,
        active_blocks=active_blocks,
    )


# --------------------------------------------------------------------------- #
# the generator
# --------------------------------------------------------------------------- #


def _regime_path(world: NumericWorld, months: int) -> tuple[str, ...] | None:
    """The requested ruleset label for each month, or ``None`` for unconditional draws.

    The sealed ``stratification_statement``: "CONDITIONED sampling (a WorldSpec naming a
    regime sequence) pins the stratification path: the start regime of each block is the
    requested regime for that month." A ``sequence`` mode world with segments in quarters
    is expanded to one label per month (``quarter = month // 3``); a month no segment
    covers is left unpinned (``""``) and falls back to the unconditional frequency draw.

    ``transition_matrix`` mode is deliberately NOT honoured: the sealed statement names
    exactly two behaviours, unconditional and sequence, and inventing a Markov path here
    would be a conditioning mechanism the seal does not grant this generator.
    """
    if world.regimes.mode != "sequence" or not world.regimes.sequence:
        return None
    path = [""] * months
    for segment in world.regimes.sequence:
        label = WORLDSPEC_REGIME_TO_LABEL.get(segment.regime, "")
        for quarter in range(int(segment.from_quarter), int(segment.to_quarter) + 1):
            for month in range(quarter * 3, min(quarter * 3 + 3, months)):
                path[month] = label
    return tuple(path)


class BootstrapV1:
    """The sealed benchmark. Implements :class:`ah.gen.base.Generator`."""

    generator_id = GENERATOR_ID

    def __init__(self, source: BootstrapSource | None = None) -> None:
        self._source = source

    # -- Generator protocol -------------------------------------------------- #

    def fit(self, data: Any) -> None:
        """Adopt a prepared :class:`BootstrapSource`. There is nothing to estimate.

        A block bootstrap has no parameters: the "fit" is the assembly of the draw span
        and its regime labels, which :func:`build_source` performs against a
        :class:`~ah.splits.DataAccess`. This method deliberately does NOT accept a
        ``DataAccess`` and refit from one -- keeping the data read in one named function
        is what makes "which vintage did this ensemble come from" answerable.
        """
        if not isinstance(data, BootstrapSource):
            raise BootstrapError(
                f"bootstrap-v1.fit expects a BootstrapSource (see build_source); "
                f"got {type(data).__name__}"
            )
        self._source = data

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        """Sample ``world``'s horizon. **``factor_conditions`` are ignored, by design.**

        The sealed ``conditioning_statement``: bootstrap-v1 honours a WorldSpec's regime
        sequence (via stratification) and nothing else; it has no mechanism for an
        inflation average, a rate endpoint or a crisis severity and will not acquire one.
        Its conditional-tier error is expected and is the measurement, not a defect.
        """
        months = int(world.horizon.quarters) * 3
        return self.sample_months(months, n_paths, seed, world=world)

    # -- the sampler ---------------------------------------------------------- #

    @staticmethod
    def ensemble_seed(base_seed: int, k: int) -> int:
        """``base_seed + 7919*k`` -- CLAUDE.md's platform-wide ensemble seed rule."""
        return int(base_seed) + SEED_STRIDE * int(k)

    def sample_months(
        self,
        months: int,
        n_paths: int,
        seed: int,
        *,
        world: NumericWorld | None = None,
    ) -> Ensemble:
        """``months``/``n_paths`` given directly, for a caller with no WorldSpec."""
        source = self._source
        if source is None:
            raise BootstrapError("bootstrap-v1 is not fitted; call fit(build_source(...)) first")
        months = int(months)
        n_paths = int(n_paths)
        if months < 1 or n_paths < 1:
            raise BootstrapError(
                f"bootstrap-v1: months and n_paths must both be >= 1, "
                f"got months={months}, n_paths={n_paths}"
            )

        requested = None if world is None else _regime_path(world, months)
        index, unsatisfiable = self._draw_indices(source, months, n_paths, seed, requested)
        paths = source.values[index]

        # WP2R.4: the realized regime path — the regime_ruleset_v1 label of the
        # historical row each month was actually drawn from. This is a record of
        # what the stratified draw did, not a conditioning mechanism: no RNG is
        # consumed, and under a WorldSpec sequence the realized label equals the
        # requested one wherever the stratum was satisfiable.
        label_codes = {label: i for i, label in enumerate(REGIME_LABELS)}
        source_codes = np.array([label_codes[label] for label in source.labels], dtype=np.int64)
        realized = source_codes[index]

        conditioning: dict[str, Any] = {
            "mode": "unconditional" if world is None else world.regimes.mode,
            "regime_path_source": (
                "worldspec_sequence" if requested is not None else "historical_frequency"
            ),
            "stratification": STRATIFICATION,
            "ruleset_version": source.ruleset_version,
            "mean_block_months": MEAN_BLOCK_MONTHS,
            "block_draw_span": {
                "start": str(source.dates[0].date()),
                "end": str(source.dates[-1].date()),
                "months": source.n_rows,
            },
            # Stated on every ensemble, not only in prose: this generator honours no
            # factor_conditions at all (the sealed conditioning_statement).
            "factor_conditions_honoured": False,
            "requested_regimes": sorted({label for label in (requested or ()) if label}),
            "unsatisfiable_regimes": unsatisfiable,
        }

        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id=source.vintage_id,
            seed=int(seed),
            n_paths=n_paths,
            months=months,
            checkpoint_hash=None,
            config_hash=None,
            conditioning=conditioning,
            active_blocks=tuple(source.active_blocks),
        )
        return Ensemble(
            paths=paths,
            factor_names=list(source.factor_names),
            meta=meta,
            regimes=RegimeRecord(
                labels=realized,
                legend=REGIME_LABELS,
                mode=(
                    "realized-historical-frequency"
                    if requested is None
                    else "realized-worldspec-sequence"
                ),
                ruleset_version=source.ruleset_version,
            ),
            slow_states=AbsentLayer(
                "bootstrap-v1 has no slow-state layer; blocks are drawn "
                "directly from the historical panel"
            ),
        )

    # -- the Politis-Romano draw, stratified by start-month regime ------------- #

    def _draw_indices(
        self,
        source: BootstrapSource,
        months: int,
        n_paths: int,
        seed: int,
        requested: Sequence[str] | None,
    ) -> tuple[np.ndarray, list[str]]:
        """``(n_paths, months)`` source row indices, plus any regime that could not be drawn.

        The sealed form, exactly: a fresh start at month 0 and thereafter with
        probability ``p = 1/MEAN_BLOCK_MONTHS``, otherwise ``(previous + 1) mod T`` --
        the circular wrap is part of the definition. The only departure from a plain
        uniform start is *which rows a fresh start may land on*: the stratum of the
        month's regime, drawn from the WorldSpec sequence when one pins it and from the
        span's own historical label frequencies otherwise.
        """
        rng = np.random.Generator(np.random.PCG64(int(seed)))
        n_rows = source.n_rows
        p = 1.0 / float(MEAN_BLOCK_MONTHS)

        restart = rng.random((n_paths, months)) < p
        restart[:, 0] = True

        labels = list(source.label_frequencies)
        weights = np.array([source.label_frequencies[label] for label in labels], dtype=np.float64)

        unsatisfiable: list[str] = []
        starts = np.empty((n_paths, months), dtype=np.int64)
        for t in range(months):
            wanted = "" if requested is None else requested[t]
            stratum = source.strata.get(wanted) if wanted else None
            if wanted and stratum is None and wanted not in unsatisfiable:
                # A requested regime with no month in the draw span cannot be honoured.
                # Falling back to the unconditional draw keeps the generator sampling
                # (a raise would abort a whole battery); recording it keeps the
                # substitution visible on the ensemble rather than silent.
                unsatisfiable.append(wanted)
            if stratum is not None:
                starts[:, t] = stratum[rng.integers(0, stratum.size, size=n_paths)]
            else:
                # Unconditional: draw the label at its historical frequency, then a
                # uniform row within it. Composed, that is exactly Uniform([0, T)) --
                # see the module docstring.
                drawn = rng.choice(len(labels), size=n_paths, p=weights)
                picked = np.empty(n_paths, dtype=np.int64)
                for j, label in enumerate(labels):
                    mask = drawn == j
                    count = int(np.count_nonzero(mask))
                    if count:
                        rows = source.strata[label]
                        picked[mask] = rows[rng.integers(0, rows.size, size=count)]
                starts[:, t] = picked

        index = np.empty((n_paths, months), dtype=np.int64)
        index[:, 0] = starts[:, 0]
        for t in range(1, months):
            advanced = (index[:, t - 1] + 1) % n_rows
            index[:, t] = np.where(restart[:, t], starts[:, t], advanced)
        return index, unsatisfiable


# --------------------------------------------------------------------------- #
# the registered factory
# --------------------------------------------------------------------------- #


def _catalog_access(catalog_root: Path, vintage_id: str) -> tuple[Any, DataAccess]:
    """A :class:`DataAccess` pinned to one campaign vintage of the local catalog.

    A series absent from the vintage reads as an EMPTY frame rather than raising: a data
    gap is a fact about the world (``hy_spread`` is one), and ``build_source`` decides
    what to do about it.
    """
    from ah.data.catalog import Catalog  # local: keeps duckdb off the import path

    catalog = Catalog(catalog_root)

    def reader(series_id: str) -> pd.DataFrame:
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return catalog, DataAccess(reader)


@lru_cache(maxsize=4)
def campaign_source(
    catalog_root: str | None = None, vintage_id: str = CAMPAIGN_VINTAGE_ID
) -> BootstrapSource:
    """The fitted source for one campaign vintage, read from the local catalog.

    Memoized: ``ah.eval.metrics.conditional`` re-resolves the generator once per
    regenerated world (hundreds of times in one battery run), and rebuilding a 372x12
    panel and its regime labels each time would dominate the run for no change in result.
    The source is a pure function of ``(catalog_root, vintage_id)`` and is immutable, so
    sharing one instance across generators is safe.

    Raises whatever the catalog read raises when ``data/`` is absent -- which is the
    correct behaviour for the registered factory: ``ah.eval.metrics.conditional`` already
    guards factory construction and reports an unresolvable generator as NaN rather than
    crashing a battery run that has no catalog.
    """
    root = _REPO_ROOT / "data" if catalog_root is None else Path(catalog_root)
    catalog, access = _catalog_access(root, vintage_id)
    try:
        return build_source(access, load_manifest(), vintage_id=vintage_id)
    finally:
        catalog.close()


def bootstrap_v1_factory() -> BootstrapV1:
    """Construct a fitted ``bootstrap-v1`` against the sealed campaign vintage."""
    return BootstrapV1(campaign_source())


# The id an authored WorldSpec may name for this generator.
#
# `schemas/worldspec-v1.0.schema.json` restricts `engine_defaults.generator_id` to
# `[toy-v0, bootstrap-stratified, signature-mmd, conditional-diffusion]`. That enum
# predates STEP2-GENERATOR-PLAN Sec.WP2.4's instruction to "Register `bootstrap-v1`",
# so the plan's id and the schema's id for the same generator differ. `CLAUDE.md`
# resolves that directly: schemas/ is read-only vendored truth and "wins for field
# definitions" -- an enum's members are a field definition -- so the code is what
# moves, not the contract.
#
# Without this alias the break is live, not theoretical: every authored world in
# `fixtures/worlds/conditional/` names `bootstrap-stratified`, validates against the
# schema, and then fails `resolve_for_world` with UnknownGeneratorError. Both ids
# resolve to the SAME factory, so an ensemble is identical whichever name reached it.
#
# RECONCILED at WP2R.7 (the plan scoped this under §WP2R.7, the WorldSpec bump —
# an earlier revision of this comment said §WP2R.6, an off-by-one): WorldSpec v1.2's
# enum carries the resolved namespace (`bootstrap-v1` first-class, `hier-flow-v1`
# the promoted default) AND keeps `bootstrap-stratified` as a deprecated member,
# because the sealed 1.0.x fixture worlds carry it and may not be edited. This alias
# therefore stays: it is what makes those sealed worlds RUN, not merely validate.
# It needs no amendment: `ah/gen/registry.py` and this module are outside the
# pre-registration seal (no `gen/` file is a judged source -- `gen/base.py` is
# excluded by name as "the defendant whose output is judged, not the judge itself").
SCHEMA_GENERATOR_ID = "bootstrap-stratified"

registry.register(GENERATOR_ID, bootstrap_v1_factory)
registry.register(SCHEMA_GENERATOR_ID, bootstrap_v1_factory)
