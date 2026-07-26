"""The negative-control suite: five deliberately broken generators (WP2.2b Task 7).

STEP2-GENERATOR-PLAN Sec.WP2.2b, verbatim: "``negative_controls.py`` registers
deliberately broken generators: **NC1** iid Gaussian with matched means/covariance
(kills tails/clustering -- monthly tier must fail it); **NC2** temporally shuffled real
data (kills dynamics -- ACF/horizon tiers must fail it); **NC3** mean/vol-shifted
bootstrap (drifted marginals -- bands must fail it); **NC4** memorizer replaying
training decades with noise (memorization tier must fail it); **NC5** condition-ignoring
generator (conditional tier must fail it). A test asserts each control fails at least
its designated tier at enforce level. This suite is the battery's own validation record
and is cited in ``G2-EVIDENCE.md``."

Why this module exists
-----------------------
WP2.2 built eight metric suites computing ~120 registered metrics. Every one of them was
tested against data constructed to exercise its own formula; **none had been run against
a generator that is wrong in the way the suite was meant to catch.** That distinction is
not academic here: review of those suites found nine separate metrics that scored
*better* when the generator produced less, every one of which passed its own tests,
because each guard test held fixed exactly the axis the gaming vector lived on. This
module is the first independent check on whether the battery detects badness at all.

Consequently: **a control that passes a tier it should fail is a finding about the
battery, not a bug in the control.** Nothing here may be weakened, and no threshold may
be tuned, to make a designated tier fire. Where a designated tier did not fire, the gap
is recorded on the report itself (:attr:`ControlOutcome.designated_substantive_failures`
is empty and the markdown renders ``MISS``) and pinned by a named test in
``tests/test_negative_controls.py``.

Two rejection surfaces, reported separately -- and why that is not a new judging rule
--------------------------------------------------------------------------------------
:class:`ah.eval.battery.BatteryReport` decides ``passed`` from ONE surface: a metric's
value against a ``pre-registration.yaml`` :class:`~ah.eval.prereg.Threshold`, blocking
only at ``severity: enforce``. But DN-1.1 Sec.II.6 states the monthly and 1-5yr tiers'
acceptance criterion as *"within block-bootstrap 90% bands of history"* -- the
:class:`~ah.eval.reference.StatBand` the battery computes, attaches to every
:class:`~ah.eval.battery.MetricResult`, renders in its report, and **never judges
against**. The two are different questions, and WP2.2b's NC3 is aimed squarely at the
second one ("a band that admits a mean/volatility-shifted generator is not a band").

This module therefore reports both, side by side, and never merges them:

- ``enforce_failures`` / ``report_failures`` -- the battery's own threshold verdict,
  split by severity. Copied from :class:`~ah.eval.battery.MetricResult`, computed
  nowhere here.
- ``band_failures`` -- the metric's value outside its own ``[lo, hi]``. This is the
  DN-1.1 criterion made explicit for the report table; it changes no verdict, gates
  nothing, and :func:`ah.eval.battery.run_battery` is untouched by it. WP2.3 is the work
  package that turns bands into sealed thresholds; until it does, band membership is
  *evidence*, presented as such.

Substantive vs. NaN-driven rejection
--------------------------------------
THE ONE NaN RULE (:func:`ah.eval.battery._passed`) means an uncomputable metric fails,
which is right for a verdict and useless as evidence: "NC1 was rejected" is worth
nothing if the rejection came from a metric that is NaN for *every* generator (the
structural-gap metrics, an absent factor, a D4 leg the ensemble does not emit). Every
failure set here is therefore split into a **substantive** half (the metric produced a
finite value and that value failed) and a **NaN** half, and only the substantive half
counts as a tier "catching" a control. Without this split the acceptance test would pass
vacuously for all five controls on the strength of ``money_pump_violations`` alone.

Where the controls' data comes from
-------------------------------------
Every real-data input flows through :attr:`ah.eval.reference.ReferenceStats.historical_series`
-- the same sanctioned train+validation surface :mod:`ah.eval.metrics.tails`,
:mod:`~ah.eval.metrics.utility` and :mod:`~ah.eval.metrics.memorization` read through --
never a fresh catalog read. This module holds no
:class:`~ah.splits.FinalEvaluationToken`, never imports :mod:`ah.eval.g2` (AST-guarded in
``tests/test_negative_controls.py``), and no control object retains a
:class:`~ah.splits.DataAccess`. NC4 additionally needs TRAIN alone (replaying a
*training* decade is the whole point), recovered by re-partitioning the already-fetched
combined series on the sealed :data:`ah.splits.TRAIN` boundary -- exactly the technique
and the justification :func:`ah.eval.metrics.memorization._train_validation_series`
already documents.

The fitted panel is the **inner join** across every available active factor
(:class:`HistoricalPanel`): NC1 needs a joint covariance and NC2/NC3/NC5 must resample
co-dated rows, so a shared date axis is unavoidable here in a way it deliberately is not
in :func:`ah.eval.reference.compute_reference` (whose statistics are scoped per factor
precisely so a short-history factor cannot truncate a long one). The consequence is
stated rather than hidden: with real Step-1 series the join is bounded below by the
latest-starting factor (``hy_spread``, 1996 before splicing), so the controls are fitted
on a shorter window than the bands they are judged against. That biases the controls
*toward* looking historical, i.e. toward NOT being caught -- the conservative direction
for a negative control. :attr:`HistoricalPanel.n_obs` and its date span are recorded on
the report so the window is auditable.

Determinism
------------
Every control draws exclusively from ``numpy.random.Generator(PCG64(seed))`` with the
seed it was handed by :meth:`sample` -- no global RNG, no ``random``, no clock. Two
consequences that are asserted rather than assumed: the same seed gives a bit-identical
ensemble, and (because :mod:`ah.eval.metrics.conditional` re-invokes the generator under
test through :func:`ah.gen.registry.resolve`) the whole battery verdict for a control is
bit-reproducible.

The five controls
------------------
Each is stated precisely enough to be reconstructed from this docstring alone, because
the table this module emits is cited as evidence in ``G2-EVIDENCE.md``.

``nc1-iid-gaussian`` -- fits the per-factor mean vector ``mu`` and the full sample
covariance ``Sigma`` of the joint panel, then emits ``n_paths * months`` independent
draws from ``N(mu, Sigma)`` via a symmetric-eigendecomposition square root
(:func:`_psd_sqrt`; negative eigenvalues clipped to zero, so a rank-deficient panel
degrades to a degenerate-but-valid Gaussian instead of raising). Preserved exactly in
expectation: every factor's mean, standard deviation, and every contemporaneous
cross-factor correlation. Destroyed: excess kurtosis (-> 0), the Hill tail indices (->
the Gaussian value), every autocorrelation of returns and of ``|deviation|`` (-> 0),
``acf_abs_decay``, the leverage effect, and every crisis-conditional co-movement lift.
Designated: the ``monthly`` tier.

``nc2-shuffled`` -- for each path, draws ONE permutation of the historical panel's row
indices and takes its first ``months`` rows. The permutation is **common across
factors**, deliberately: an independent per-factor shuffle would destroy the
contemporaneous cross-correlation structure too, and NC2 would then be rejected for a
reason that has nothing to do with dynamics. As built, every factor's marginal
distribution is an exact uniform subsample of its own history and every contemporaneous
cross-factor relationship is exactly preserved; only the time ordering is destroyed.
Designated: the ``monthly`` tier's ACF family and the ``1_5yr``/``10yr`` horizon tiers.

``nc3-shifted-bootstrap`` -- a moving-block bootstrap of the panel's rows (block length
:data:`NC3_BLOCK_MONTHS`, blocks drawn with replacement, common across factors so
within-block serial structure and cross-factor structure both survive), followed by a
stated affine distortion of each factor ``f`` independently::

    x' = mu_f + NC3_VOL_MULTIPLIER * (x - mu_f) + NC3_MEAN_SHIFT_SDS * sigma_f

with ``mu_f``/``sigma_f`` that factor's own historical mean and standard deviation.
Both constants are stated up front and derived from band geometry, never tuned -- see
:data:`NC3_MEAN_SHIFT_SDS` and :data:`NC3_VOL_MULTIPLIER`. Designated: the reference
**bands**, not a threshold.

``nc4-memorizer`` -- for each path, draws a uniformly random contiguous start index into
the **TRAIN** portion of the panel and replays the next ``months`` rows verbatim (a
literal training decade, every factor co-dated), then adds iid Gaussian noise of
standard deviation ``NC4_NOISE_FRACTION * sigma_f`` per factor. See
:data:`NC4_NOISE_FRACTION` for the derivation of the level. Designated: the
``memorization`` suite.

``nc5-condition-ignoring`` -- **exactly** ``nc3-shifted-bootstrap``'s construction with
the distortion switched off (``mean shift 0``, ``vol multiplier 1``), i.e. a plain
moving-block bootstrap of real history: statistically the most defensible of the five,
and the closest thing this module has to a competent generator. Its ``sample(world, ...)``
ignores ``world.factor_conditions`` entirely -- **but every other control's ``sample``
does too** (see :meth:`_Control.sample`'s docstring: none of the five has any
conditioning mechanism at all), so a ``conditional``-suite rejection of NC5 is **NOT**
attributable to condition-ignoring specifically. Measured: NC1 (the iid Gaussian, whose
designated defect is unrelated to conditioning) fires 12 of NC5's 14 designated
conditional metrics and is roughly an order of magnitude WORSE than NC5 on
``condition_adherence_error_inflation`` (220.7 vs 23.3). This suite has no construction
whose *only* defect is condition-ignoring while everything else about it is competent
(that needs a control that DOES read ``factor_conditions``, which none of the five
attempt), so the conditional tier's *specificity* -- would it also pass a generator that
gets everything else right and only mishandles conditioning -- is untested. See Finding
5.

Cost, and why the reference is computed once
----------------------------------------------
:func:`run_negative_controls` computes ONE :class:`~ah.eval.reference.ReferenceStats` at
the shared ensemble path length and registers the reference-dependent suites once, then
calls :func:`ah.eval.battery.run_battery` per control. That is exactly what five
:func:`~ah.eval.battery.run_full_battery` calls would do -- all five ensembles have the
same ``months``, so all five would compute the identical reference -- at a fifth of the
cost. :func:`control_reference` is the same call, exposed so a caller (and the tests)
can fit the controls without running the battery.

What the first run of this suite found (WP2.2b Task 7)
--------------------------------------------------------
Recorded here rather than only in a report, because this module is the evidence artifact
``G2-EVIDENCE.md`` cites and a reader of the table needs to know how to read it. Each
finding is pinned by a named ``test_finding_*`` in ``tests/test_negative_controls.py``;
when WP2.3 closes one, that test fails loudly and is deleted in the same commit.

**Every number below is exactly what this module's own synthetic-fixture run produces**
(``tests/test_negative_controls.py``'s ``_SEED``/``_N_PATHS``/``_MONTHS``/
``_N_RESAMPLES``) -- restated here for a reader of this docstring, not a separate,
unverifiable production run.

1. **No metric suite emits a** ``<factor>.mean``, ``<factor>.std`` **or**
   ``<factorA>~<factorB>.correlation`` **metric at all**, although
   :data:`ah.eval.reference.SINGLE_FACTOR_STATS` and
   :data:`~ah.eval.reference.CROSS_BLOCK_STATS` register all three and
   :func:`~ah.eval.reference.compute_reference` computes a real length-matched band for
   each. NC3 exists to break exactly that axis and is invisible to it: its
   ``equity_mkt`` pooled mean and standard deviation both sit well outside their own
   train+validation bands, and in its own designated cell NC3's band-failure SET is
   IDENTICAL to ``nc5-condition-ignoring``'s -- the identical construction with the
   distortion switched off -- when the two are sampled at the same seed (see
   ``tests/test_negative_controls.py::
   test_finding_the_monthly_tier_cannot_separate_nc3_from_the_undistorted_bootstrap``
   for the exact, paired comparison this claim now rests on).
2. **The battery's blocking surface is currently blind to all five controls.** Only four
   ``enforce``-severity thresholds exist; three fired for nobody, and the fourth
   (``floor_violations``) fired identically for all five, including for controls that
   replay real historical values verbatim -- see :attr:`NegativeControlReport.
   shared_enforce_failures`, which exists so that gate cannot be misread as a detection.
   Every substantive catch came from a reference band the battery does not judge against
   or from a ``report``-severity threshold that does not block.
3. **A plain moving-block bootstrap scores WORSE on** ``near_duplicate_fraction`` **than
   the deliberate memorizer** (0.2394 vs 0.0654; ``nn_distance_p05`` 0.0687 vs 0.6491).
   WP2.4's G2 benchmark generator is a block bootstrap, so it will trip the same metric
   -- **but the metric's real defect is larger than that comparison alone suggests.**
   Varying ONLY NC4's start-index distribution (holding its noise level fixed) shows
   ``near_duplicate_fraction`` is dominated by block-PHASE alignment, not by copying:
   snapping the replay start to the suite's own 24-month block grid drives it to 0.8875
   (every "copy" now lands on a grid boundary the memorization suite also chops on),
   while a ZERO-noise, literal verbatim copy at a random (non-grid) offset scores 0.2423
   -- statistically indistinguishable from the plain block bootstrap's own 0.2394 above,
   even though a verbatim copy is about as memorized as a block can get. The suite's own
   windowing (non-overlapping 24-month blocks anchored at index 0 on both the generated
   and TRAIN sides) is the confound. **Consequence for the remedy Finding 3 previously
   implied**: a *relative* bound against a block-bootstrap baseline inherits this same
   phase blindness and would not fix it; the suite would need to compare against ALL
   offsets (sliding windows) rather than a fixed grid on either side. Not fixed here
   (``ah.eval.metrics.memorization`` is untouched by this WP) -- see
   ``governance/retrofit-register.md``.
4. **The 10yr tier caught nothing.** 16 of its 22 metrics -- 14 ``<factor>.ergodicity_gap``
   (one per active factor) plus ``ten_year_return_vs_valuation_{r2,slope}`` -- carry
   ``status=structurally_unavailable`` and are NaN for every generator (73%, not the 59%
   a naive read of the report's own NaN-bucket columns suggests: 3 of the 16 -- one
   ``ergodicity_gap`` with no reference band at all, plus both
   ``ten_year_return_vs_valuation_*`` names -- have ``band=None`` and so never land in
   :attr:`CellOutcome.band_nan_metrics`/:attr:`~CellOutcome.enforce_nan_failures`, which
   is where "13" comes from if counted off those buckets alone). NC2 -- designated to
   this tier -- is not caught by it. (``regime_duration_{mean,p50,p90}`` is registered at
   the ``1_5yr`` tier, not ``10yr`` -- named here only to head off the natural but wrong
   assumption that it is one of this tier's NaN metrics.)
5. **A ``conditional``-suite rejection is not specific to condition-ignoring.** All five
   controls ignore ``factor_conditions`` (none has any conditioning mechanism), and the
   tier fires substantively for all five -- NC1 (iid Gaussian, whose designated defect is
   unrelated to conditioning) fires 12 of NC5's 14 designated conditional metrics and is
   ~10x worse than NC5 on ``condition_adherence_error_inflation`` (220.7 vs 23.3). The
   suite has no control that honours conditions while being otherwise competent, so the
   conditional tier's specificity -- would it let a condition-honouring generator pass
   while still catching a condition-ignoring one -- is untested. See
   ``governance/retrofit-register.md`` for the missing condition-honouring control.
6. **The battery-verdict instability recorded on
   ``test_battery_verdict_is_bit_identical_for_the_same_seed`` has a structural, not a
   numerical-noise, cause.** 148 of 3035 finite (value, band) comparisons across all five
   controls sit at *exactly* zero distance from their own band edge -- passing today only
   because a closed interval includes its own boundary -- and are therefore one ULP of
   perturbation away from flipping sides. 33 of those 148 rest on a fully degenerate
   ``[0.0, 0.0]`` band (7 distinct metric names, all ``tail_dependence_{lower,upper}``
   pairs whose historical block-bootstrap replicates never once produced a joint
   exceedance; e.g. ``hy_spread~ust_2y.tail_dependence_upper``: value ``0.0``, band
   ``[0.0, 0.0]``). Any nonzero perturbation of any size is structurally guaranteed to
   flip a knife-edge comparison, which is sufficient on its own to explain an
   occasional bit-level verdict change and requires no BLAS thread-count hypothesis.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd

from ah.core.numericworld import NumericWorld
from ah.eval import battery as battery_mod
from ah.eval import prereg as prereg_mod
from ah.eval.battery import (
    BATTERY_VERSION,
    TIERS,
    BatteryReport,
    MetricResult,
    register_reference_dependent_suites,
    run_battery,
)
from ah.eval.prereg import PreRegistration
from ah.eval.reference import DEFAULT_BLOCK_LENGTH, ReferenceStats, compute_reference
from ah.factors import FactorManifest
from ah.gen import registry as gen_registry
from ah.gen.base import Ensemble, EnsembleMeta
from ah.splits import TRAIN, DataAccess

__all__ = [
    "DESIGNATIONS",
    "NC1_IID_GAUSSIAN",
    "NC2_SHUFFLED",
    "NC3_BLOCK_MONTHS",
    "NC3_MEAN_SHIFT_SDS",
    "NC3_SHIFTED_BOOTSTRAP",
    "NC3_VOL_MULTIPLIER",
    "NC4_MEMORIZER",
    "NC4_NOISE_FRACTION",
    "NC5_CONDITION_IGNORING",
    "NEGATIVE_CONTROL_IDS",
    "CellOutcome",
    "ControlOutcome",
    "Designation",
    "HistoricalPanel",
    "NegativeControlError",
    "NegativeControlReport",
    "build_negative_controls",
    "control_reference",
    "fit_historical_panel",
    "negative_control_registry",
    "run_negative_controls",
]


class NegativeControlError(RuntimeError):
    """Raised when a control cannot honestly be fitted or run."""


# --------------------------------------------------------------------------- #
# ids, stated constants, designations
# --------------------------------------------------------------------------- #

NC1_IID_GAUSSIAN = "nc1-iid-gaussian"
NC2_SHUFFLED = "nc2-shuffled"
NC3_SHIFTED_BOOTSTRAP = "nc3-shifted-bootstrap"
NC4_MEMORIZER = "nc4-memorizer"
NC5_CONDITION_IGNORING = "nc5-condition-ignoring"

NEGATIVE_CONTROL_IDS: tuple[str, ...] = (
    NC1_IID_GAUSSIAN,
    NC2_SHUFFLED,
    NC3_SHIFTED_BOOTSTRAP,
    NC4_MEMORIZER,
    NC5_CONDITION_IGNORING,
)

# NC3's moving-block length, in months. Two years: long enough that within-block serial
# dependence (the ACF family, the variance ratios at 12m) survives the resample, so NC3
# is NOT accidentally a second copy of NC2 -- its defect must be drifted marginals and
# nothing else. Deliberately NOT `ah.eval.reference.DEFAULT_BLOCK_LENGTH` (120): at the
# production reference block length a 120-month resample is one contiguous historical
# block, which would make NC3 a memorizer as well as a drifter and confound two controls.
NC3_BLOCK_MONTHS = 24

# NC3's mean shift, in units of each factor's own historical standard deviation.
#
# Derived from band geometry, not tuned. `ah.eval.battery.run_full_battery` draws every
# reference replicate at the judged ensemble's own path length n (120 months at DN-1.1's
# decade horizon), so the 90% band on `mean` has half-width ~= 1.645 * sigma / sqrt(n)
# ~= 0.15 * sigma for a weakly dependent series -- wider under real serial dependence,
# but that inflation is bounded by the block bootstrap's own effective sample size. A
# shift of 0.5 sigma is therefore ~3 band half-widths outside: unambiguously rejectable
# by a band that works, while remaining a shift a plausibly-miscalibrated real generator
# could exhibit (half a monthly standard deviation of drift), not a cartoon.
NC3_MEAN_SHIFT_SDS = 0.5

# NC3's volatility multiplier. Same derivation on the other moment: the 90% band on a
# standard deviation has relative half-width ~= 1.645 / sqrt(2n) ~= 11% at n = 120, so a
# 50% inflation sits ~4.5 half-widths out. Stated, not tuned.
NC3_VOL_MULTIPLIER = 1.5

# NC4's additive noise, as a fraction of each factor's own historical standard deviation.
#
# **Load-bearing, and derived from first principles rather than tuned until a test
# passed.** `ah.eval.metrics.memorization` compares 24-month blocks standardized by that
# factor's own TRAIN mean/std under a Euclidean distance, and flags a generated block as
# a near-duplicate when its nearest-TRAIN-block distance falls below the 5th percentile
# of TRAIN's own leave-one-out nearest-neighbour distance. Two facts fix the scale:
#
# 1. Perturbing a copied 24-month standardized block by iid noise of relative size f puts
#    the copy at expected distance sqrt(24) * f ~= 4.9 f from its source.
# 2. Two *genuinely independent* standardized 24-month windows sit at expected distance
#    sqrt(2 * 24) ~= 6.9 from each other (E||u - v||^2 = 24 * (1 + 1) under unit
#    variance and independence). The epsilon the suite derives is the 5th percentile of
#    that distribution, i.e. materially below 6.9 but of that order.
#
# At f = 0.10 the copy sits ~0.49 from its source: an order of magnitude closer than the
# closest pair of distinct historical decades, so it is unambiguously a copy under any
# reasonable epsilon -- while still differing from the source in EVERY value, so NC4 is
# caught for reproducing a training trajectory's *shape*, not for emitting a literally
# equal array (which a byte comparison would catch and which would prove nothing about
# the metric). It also leaves 99% of the source variance intact, so NC4 remains a
# convincing generator to every OTHER suite: its marginals, ACF, tails and clustering are
# history's own. That is what makes it a clean test of the memorization tier specifically.
#
# Stated assumption, not closed here: this scale is applied as
# `0.10 * HistoricalPanel.std`, which is the panel's TRAIN+VALIDATION standard
# deviation (`fit_historical_panel` computes it over the whole joint panel), while
# `ah.eval.metrics.memorization` standardizes its own distances by that factor's TRAIN
# split ALONE (`_train_mean_std`). The two are close in practice (TRAIN is the large
# majority of the joint panel and standard deviation is a slowly-varying statistic), but
# they are not the identical number, so `NC4_NOISE_FRACTION`'s derivation above (which
# reasons in units of ONE shared sigma) is strictly correct only if TRAIN's and
# TRAIN+VALIDATION's sigmas coincide. Not tightened here -- see
# `governance/retrofit-register.md`.
NC4_NOISE_FRACTION = 0.10

# NC5 reuses NC3's block length; the two differ ONLY in the distortion applied after
# resampling (see the module docstring).
NC5_BLOCK_MONTHS = NC3_BLOCK_MONTHS

# Eigenvalues of the fitted covariance below this multiple of its largest eigenvalue are
# clipped to zero when forming NC1's square root -- a rank-deficient historical panel
# (two factors that are exact linear combinations of the same inputs) must degrade to a
# valid degenerate Gaussian, not raise out of a Cholesky factorization.
_EIGENVALUE_FLOOR_RATIO = 1e-12


@dataclass(frozen=True)
class Designation:
    """Which part of the battery a control is built to be rejected by.

    ``tiers`` are :data:`ah.eval.battery.TIERS` members; ``suites`` are
    :data:`ah.eval.battery.SUITES` keys. Both are needed because they are orthogonal
    axes: ``memorization`` and ``conditional`` both register at tier ``monthly``, so a
    tier alone cannot express "the memorization suite must catch this", and the horizon
    suite spans three tiers, so a suite alone cannot express "the 1_5yr statistics must
    catch this". A cell counts as designated when its tier is in ``tiers`` AND its suite
    is in ``suites``.

    ``criterion`` is the rejection surface the plan names for this control:
    ``"enforce"`` (a ``severity: enforce`` threshold must fail) or ``"band"`` (the value
    must fall outside its train+validation reference band). Both are always reported;
    this records which one the control was designed to exercise.
    """

    control_id: str
    tiers: tuple[str, ...]
    suites: tuple[str, ...]
    criterion: str
    construction: str


DESIGNATIONS: Mapping[str, Designation] = MappingProxyType(
    {
        NC1_IID_GAUSSIAN: Designation(
            control_id=NC1_IID_GAUSSIAN,
            tiers=("monthly",),
            suites=("monthly",),
            criterion="enforce",
            construction=(
                "iid draws from N(mu, Sigma) with mu/Sigma the joint train+validation "
                "panel's own mean vector and full sample covariance; means, standard "
                "deviations and contemporaneous correlations preserved, all tail "
                "behaviour, autocorrelation and volatility clustering destroyed"
            ),
        ),
        NC2_SHUFFLED: Designation(
            control_id=NC2_SHUFFLED,
            tiers=("monthly", "1_5yr", "10yr"),
            suites=("monthly", "horizon"),
            criterion="enforce",
            construction=(
                "real train+validation rows in a random order: one permutation per path, "
                "COMMON across factors, first `months` rows taken; every marginal is an "
                "exact uniform subsample of its own history and every contemporaneous "
                "cross-factor relationship is exact, only time ordering is destroyed"
            ),
        ),
        NC3_SHIFTED_BOOTSTRAP: Designation(
            control_id=NC3_SHIFTED_BOOTSTRAP,
            tiers=("monthly",),
            suites=("monthly",),
            criterion="band",
            construction=(
                f"moving-block bootstrap of real rows (block={NC3_BLOCK_MONTHS} months, "
                f"common across factors), then per factor "
                f"x' = mu + {NC3_VOL_MULTIPLIER} * (x - mu) + {NC3_MEAN_SHIFT_SDS} * sigma "
                f"with mu/sigma that factor's own historical mean and standard deviation"
            ),
        ),
        NC4_MEMORIZER: Designation(
            control_id=NC4_MEMORIZER,
            tiers=("monthly",),
            suites=("memorization",),
            criterion="enforce",
            construction=(
                f"verbatim replay of a uniformly-drawn contiguous TRAIN window of "
                f"`months` rows per path (every factor co-dated), plus iid Gaussian "
                f"noise of standard deviation {NC4_NOISE_FRACTION} * sigma_f per factor"
            ),
        ),
        NC5_CONDITION_IGNORING: Designation(
            control_id=NC5_CONDITION_IGNORING,
            tiers=("monthly",),
            suites=("conditional",),
            criterion="enforce",
            construction=(
                f"plain moving-block bootstrap of real rows (block={NC5_BLOCK_MONTHS} "
                f"months, common across factors) with NO distortion -- identical to "
                f"nc3-shifted-bootstrap with the shift switched off -- whose sample() "
                f"ignores world.factor_conditions entirely"
            ),
        ),
    }
)


# --------------------------------------------------------------------------- #
# the fitted historical panel
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class HistoricalPanel:
    """The joint, co-dated train+validation panel every control is fitted from.

    ``values`` is ``(n_obs, n_factors)`` in ``factor_names`` order; ``dates`` is the
    shared monthly index the inner join produced. ``train_rows`` is how many leading
    rows fall inside :data:`ah.splits.TRAIN` -- NC4 replays only from those. ``mean``
    and ``std`` are per factor, computed once here so no control invents its own
    convention (``std`` uses ``ddof=1``, matching
    :func:`ah.eval.reference._std`; a zero-variance factor's ``std`` is floored at 1.0
    so a distortion or a noise level defined as a multiple of it stays finite).
    """

    factor_names: tuple[str, ...]
    dates: pd.DatetimeIndex
    values: np.ndarray
    train_rows: int
    mean: np.ndarray
    std: np.ndarray

    @property
    def n_obs(self) -> int:
        return int(self.values.shape[0])

    @property
    def n_factors(self) -> int:
        return int(self.values.shape[1])


def fit_historical_panel(reference: ReferenceStats) -> HistoricalPanel:
    """Inner-join :attr:`~ah.eval.reference.ReferenceStats.historical_series` into one panel.

    The ONLY real-data read in this module, and it reads an already-computed
    train+validation object rather than a catalog. Factors are taken in sorted order so
    the panel's column order is a function of the data, not of mapping insertion order.

    Raises :class:`NegativeControlError` if the reference carries no historical series at
    all, or if the inner join is empty -- a control fitted on nothing is not a control,
    and silently returning a degenerate panel would let all five "pass" for no reason.
    """
    series = reference.historical_series
    if not series:
        raise NegativeControlError(
            "reference carries no historical_series; the negative controls cannot be "
            "fitted (compute_reference must have been run against a live DataAccess)"
        )
    names = tuple(sorted(series))
    frame = pd.concat({name: series[name] for name in names}, axis=1, join="inner")
    frame = frame.sort_index()
    if frame.empty:
        raise NegativeControlError(
            f"the inner join across {len(names)} historical factor series is empty; "
            f"the negative controls need a shared date axis (see the module docstring's "
            f"'The fitted panel is the inner join')"
        )
    dates = pd.DatetimeIndex(frame.index)
    values = frame.to_numpy(dtype=np.float64)
    train_rows = int(np.count_nonzero(dates < pd.Timestamp(TRAIN.end)))
    mean = values.mean(axis=0)
    std = values.std(axis=0, ddof=1)
    std = np.where(std > 0.0, std, 1.0)
    return HistoricalPanel(
        factor_names=names,
        dates=dates,
        values=values,
        train_rows=train_rows,
        mean=mean,
        std=std,
    )


def _psd_sqrt(cov: np.ndarray) -> np.ndarray:
    """A square root ``L`` of a symmetric PSD ``cov`` with ``L @ L.T == cov``.

    Symmetric eigendecomposition with negative / numerically-zero eigenvalues clipped, not
    a Cholesky factorization: the historical panel can be rank deficient (two factors
    derived from overlapping inputs), and a rank-deficient panel must produce a valid
    degenerate Gaussian rather than raise out of the control's constructor. Deterministic
    -- ``numpy.linalg.eigh`` takes no RNG.
    """
    cov = np.asarray(cov, dtype=np.float64)
    symmetric = 0.5 * (cov + cov.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    largest = float(np.max(eigenvalues)) if eigenvalues.size else 0.0
    floor = _EIGENVALUE_FLOOR_RATIO * largest if largest > 0.0 else 0.0
    clipped = np.where(eigenvalues > floor, eigenvalues, 0.0)
    return eigenvectors * np.sqrt(clipped)


# --------------------------------------------------------------------------- #
# the controls
# --------------------------------------------------------------------------- #


class _Control:
    """Shared plumbing: identity, the fitted panel, and the ``Generator`` protocol.

    Every subclass implements :meth:`_draw` only -- ``(months, n_paths, rng) ->
    (n_paths, months, n_factors)`` -- so the seeding discipline (one
    ``numpy.random.Generator(PCG64(seed))`` per :meth:`sample_months` call, nothing else)
    is written once and cannot drift between controls.
    """

    generator_id: str = ""

    def __init__(self, panel: HistoricalPanel, vintage_id: str, active_blocks: tuple[str, ...]):
        self._panel = panel
        self._vintage_id = vintage_id
        self._active_blocks = active_blocks

    # -- Generator protocol ------------------------------------------------- #

    def fit(self, data: Any) -> None:
        """No-op: a control is fully specified by the panel it was constructed with.

        Present for :class:`ah.gen.base.Generator` protocol conformance -- the battery
        must not be able to tell a control apart from a real generator by its interface.
        Deliberately does NOT accept a :class:`~ah.splits.DataAccess` or refit from one:
        the only sanctioned data surface is the already-computed reference this object
        was built from.
        """
        del data

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        """Sample ``world``'s horizon. **Every control ignores ``factor_conditions``.**

        NC5 is the one whose *designation* is that failure; the other four ignore
        conditions too, simply because none of them has any conditioning mechanism at
        all. That is stated here rather than left implicit, because
        :mod:`ah.eval.metrics.conditional` re-invokes whichever generator is under test
        and will therefore report a real adherence error for all five.
        """
        return self.sample_months(world.horizon.quarters * 3, n_paths, seed)

    # -- the actual sampler -------------------------------------------------- #

    def sample_months(self, months: int, n_paths: int, seed: int) -> Ensemble:
        """``months``/``n_paths`` given directly, for a caller with no WorldSpec."""
        if months < 1 or n_paths < 1:
            raise NegativeControlError(
                f"{self.generator_id}: months and n_paths must both be >= 1, "
                f"got months={months}, n_paths={n_paths}"
            )
        rng = np.random.Generator(np.random.PCG64(seed))
        paths = self._draw(months, n_paths, rng)
        meta = EnsembleMeta(
            generator_id=self.generator_id,
            vintage_id=self._vintage_id,
            seed=seed,
            n_paths=n_paths,
            months=months,
            config_hash=None,
            checkpoint_hash=None,
            active_blocks=self._active_blocks,
        )
        return Ensemble(paths=paths, factor_names=list(self._panel.factor_names), meta=meta)

    def _draw(self, months: int, n_paths: int, rng: np.random.Generator) -> np.ndarray:
        raise NotImplementedError  # pragma: no cover - abstract


class IidGaussianControl(_Control):
    """NC1 -- iid ``N(mu, Sigma)`` matched to the panel's mean vector and covariance.

    See the module docstring's "The five controls" for exactly what this preserves
    (means, standard deviations, contemporaneous correlations) and what it destroys
    (every tail, autocorrelation and volatility-clustering statistic). The covariance is
    the ``ddof=1`` sample covariance of the joint panel; the square root is
    :func:`_psd_sqrt`.
    """

    generator_id = NC1_IID_GAUSSIAN

    def __init__(self, panel: HistoricalPanel, vintage_id: str, active_blocks: tuple[str, ...]):
        super().__init__(panel, vintage_id, active_blocks)
        self._sqrt = _psd_sqrt(np.cov(panel.values, rowvar=False, ddof=1))

    def _draw(self, months: int, n_paths: int, rng: np.random.Generator) -> np.ndarray:
        z = rng.standard_normal((n_paths, months, self._panel.n_factors))
        return self._panel.mean + z @ self._sqrt.T


class ShuffledControl(_Control):
    """NC2 -- real rows in a random order; one permutation per path, common across factors.

    See the module docstring for why the permutation is shared across factors rather than
    drawn per factor (an independent per-factor shuffle would also destroy the
    contemporaneous cross-factor structure, and NC2 would then be rejected for the wrong
    reason). Sampling is without replacement within a path, so each path's marginals are
    an exact uniform subsample of the factor's own history.
    """

    generator_id = NC2_SHUFFLED

    def _draw(self, months: int, n_paths: int, rng: np.random.Generator) -> np.ndarray:
        n_obs = self._panel.n_obs
        take = min(months, n_obs)
        out = np.empty((n_paths, months, self._panel.n_factors), dtype=np.float64)
        for p in range(n_paths):
            order = rng.permutation(n_obs)
            if months <= n_obs:
                out[p] = self._panel.values[order[:months]]
            else:
                # A horizon longer than history: tile independent permutations rather
                # than sample with replacement, so the marginals stay exact.
                filled = 0
                while filled < months:
                    chunk = min(take, months - filled)
                    out[p, filled : filled + chunk] = self._panel.values[order[:chunk]]
                    filled += chunk
                    order = rng.permutation(n_obs)
        return out


def _moving_block_indices(
    n_obs: int, months: int, block: int, n_paths: int, rng: np.random.Generator
) -> np.ndarray:
    """``(n_paths, months)`` row indices from a moving-block bootstrap of ``n_obs`` rows.

    Blocks are drawn with replacement from every valid contiguous start, concatenated,
    and truncated to ``months``. The identical scheme
    :func:`ah.eval.reference._draw_moving_block_indices` uses for the reference bands, so
    NC3 and NC5 resample history the same way the bands do. That shared scheme is what
    makes the NC3-minus-NC5 difference interpretable: the two controls differ ONLY by the
    distortion, so any metric NC3 fires and NC5 does not is attributable to the drift and
    nothing else. (Finding 1 in this module's docstring is exactly that difference, and it
    is empty of location/scale metrics.)
    """
    effective_block = max(1, min(block, n_obs))
    n_blocks = int(np.ceil(months / effective_block))
    max_start = n_obs - effective_block + 1
    starts = rng.integers(0, max_start, size=(n_paths, n_blocks))
    offsets = np.arange(effective_block)
    stitched = (starts[:, :, None] + offsets[None, None, :]).reshape(n_paths, -1)
    return stitched[:, :months]


class ShiftedBootstrapControl(_Control):
    """NC3 -- a moving-block bootstrap of real rows with a stated mean/volatility shift.

    ``mean_shift_sds`` and ``vol_multiplier`` default to :data:`NC3_MEAN_SHIFT_SDS` /
    :data:`NC3_VOL_MULTIPLIER`; both are derived from band geometry at those constants'
    definitions and are not tuned. With both at their neutral values (0.0, 1.0) this IS
    :class:`ConditionIgnoringControl`, which is exactly how NC5 is defined.
    """

    generator_id = NC3_SHIFTED_BOOTSTRAP

    def __init__(
        self,
        panel: HistoricalPanel,
        vintage_id: str,
        active_blocks: tuple[str, ...],
        *,
        mean_shift_sds: float = NC3_MEAN_SHIFT_SDS,
        vol_multiplier: float = NC3_VOL_MULTIPLIER,
        block_months: int = NC3_BLOCK_MONTHS,
    ):
        super().__init__(panel, vintage_id, active_blocks)
        self._mean_shift_sds = float(mean_shift_sds)
        self._vol_multiplier = float(vol_multiplier)
        self._block_months = int(block_months)

    def _draw(self, months: int, n_paths: int, rng: np.random.Generator) -> np.ndarray:
        idx = _moving_block_indices(self._panel.n_obs, months, self._block_months, n_paths, rng)
        raw = self._panel.values[idx]
        mu = self._panel.mean
        sigma = self._panel.std
        return mu + self._vol_multiplier * (raw - mu) + self._mean_shift_sds * sigma


class MemorizerControl(_Control):
    """NC4 -- verbatim replay of a contiguous TRAIN window per path, plus small noise.

    The window start is uniform over every valid contiguous ``months``-length run inside
    the panel's TRAIN rows, and is drawn ONCE per path with every factor co-dated: the
    control replays a *decade of history*, not a per-factor collage, which is what makes
    it a memorizer in the sense ``ah.eval.metrics.memorization`` measures. The noise
    level is :data:`NC4_NOISE_FRACTION` -- see that constant for the derivation.

    If TRAIN carries fewer than ``months`` rows the replay window is clamped to what
    exists and the remainder wraps; that is a degenerate configuration (a horizon longer
    than the training history) and is stated rather than silently producing a shorter
    ensemble.
    """

    generator_id = NC4_MEMORIZER

    def __init__(
        self,
        panel: HistoricalPanel,
        vintage_id: str,
        active_blocks: tuple[str, ...],
        *,
        noise_fraction: float = NC4_NOISE_FRACTION,
    ):
        super().__init__(panel, vintage_id, active_blocks)
        self._noise_fraction = float(noise_fraction)
        if panel.train_rows < 2:
            raise NegativeControlError(
                f"{self.generator_id}: the fitted panel has {panel.train_rows} TRAIN "
                f"row(s); a memorizer needs a training sample to replay"
            )

    def _draw(self, months: int, n_paths: int, rng: np.random.Generator) -> np.ndarray:
        train = self._panel.values[: self._panel.train_rows]
        n_train = train.shape[0]
        max_start = max(1, n_train - months + 1)
        starts = rng.integers(0, max_start, size=n_paths)
        offsets = np.arange(months) % n_train
        idx = (starts[:, None] + offsets[None, :]) % n_train
        replay = train[idx]
        noise = rng.standard_normal(replay.shape) * (self._noise_fraction * self._panel.std)
        return replay + noise


class ConditionIgnoringControl(ShiftedBootstrapControl):
    """NC5 -- NC3's construction with the distortion switched off, ignoring conditions.

    Subclassing :class:`ShiftedBootstrapControl` with neutral parameters is deliberate
    and is the whole design of this control: NC5 must differ from a competent generator
    in exactly ONE respect (it does not read ``world.factor_conditions``), so that a
    ``conditional``-suite rejection cannot be attributed to anything else. Writing it as
    a second, independently-authored bootstrap would leave open the possibility that the
    two resamplers differ somewhere subtle.
    """

    generator_id = NC5_CONDITION_IGNORING

    def __init__(
        self,
        panel: HistoricalPanel,
        vintage_id: str,
        active_blocks: tuple[str, ...],
        *,
        block_months: int = NC5_BLOCK_MONTHS,
    ):
        super().__init__(
            panel,
            vintage_id,
            active_blocks,
            mean_shift_sds=0.0,
            vol_multiplier=1.0,
            block_months=block_months,
        )

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble:
        """Ignores every field of ``world`` except its horizon length.

        ``world.factor_conditions`` -- the inflation average, the policy-rate endpoints,
        the crisis window's timing and severity -- is read nowhere. That is the defect
        this control was DESIGNED to be caught for -- but note it is not the only
        control with that defect: every other control ignores ``factor_conditions`` too
        (see :meth:`_Control.sample` and the module docstring's Finding 5), so a
        ``conditional``-suite rejection here cannot, by itself, be attributed to
        condition-ignoring specifically.
        """
        return self.sample_months(world.horizon.quarters * 3, n_paths, seed)


_CONTROL_CLASSES: Mapping[str, type[_Control]] = MappingProxyType(
    {
        NC1_IID_GAUSSIAN: IidGaussianControl,
        NC2_SHUFFLED: ShuffledControl,
        NC3_SHIFTED_BOOTSTRAP: ShiftedBootstrapControl,
        NC4_MEMORIZER: MemorizerControl,
        NC5_CONDITION_IGNORING: ConditionIgnoringControl,
    }
)


def build_negative_controls(reference: ReferenceStats) -> dict[str, _Control]:
    """All five controls, fitted against ``reference``'s train+validation panel."""
    panel = fit_historical_panel(reference)
    return {
        control_id: cls(panel, reference.vintage_id, reference.active_blocks)
        for control_id, cls in _CONTROL_CLASSES.items()
    }


@contextmanager
def negative_control_registry(reference: ReferenceStats) -> Iterator[tuple[str, ...]]:
    """Register all five controls in :mod:`ah.gen.registry`, then restore it.

    Registration is required, not cosmetic: :mod:`ah.eval.metrics.conditional` resolves
    the ensemble's own ``generator_id`` through :func:`ah.gen.registry.resolve` and
    re-invokes it against the authored conditional worlds, so a control that is not
    registered would report NaN for the entire conditional tier and NC5 could not be
    evaluated at all.

    The registry is process-global; restoring it on exit keeps a battery run over the
    controls from leaking five broken generators into every later ``resolve`` in the
    same process. Each factory returns the SAME fitted instance (the controls are
    immutable after construction and hold no per-sample state), so a resolve inside the
    conditional suite gets the object this function fitted, not a re-fit.
    """
    controls = build_negative_controls(reference)
    saved = gen_registry.snapshot()
    try:
        for control_id, control in controls.items():
            gen_registry.register(control_id, lambda c=control: c)
        yield NEGATIVE_CONTROL_IDS
    finally:
        gen_registry.restore(saved)


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #


def _is_finite(value: float) -> bool:
    return bool(np.isfinite(value))


def _outside_band(result: MetricResult) -> bool:
    """``value`` outside ``[band.lo, band.hi]``, for a metric that HAS a usable band.

    ``False`` when there is no band, when the band's bounds are not both finite (a band
    resting on zero valid resamples says nothing -- see
    :attr:`ah.eval.reference.StatBand.n_valid_resamples`), or when the value is not
    finite (a NaN value is accounted for separately; see the module docstring's
    "Substantive vs. NaN-driven rejection"). This function judges nothing: it is the
    DN-1.1 Sec.II.6 band criterion rendered for the report table, and no battery verdict
    reads it.
    """
    band = result.band
    if band is None:
        return False
    if not (_is_finite(band.lo) and _is_finite(band.hi)):
        return False
    if not _is_finite(result.value):
        return False
    return not (band.lo <= result.value <= band.hi)


@dataclass(frozen=True)
class CellOutcome:
    """One ``(tier, suite)`` cell of the report table, for one control.

    Every list names metrics, never counts. ``*_nan_*`` variants carry the failures whose
    metric value was NaN, kept apart from the substantive ones for the reason the module
    docstring gives.
    """

    tier: str
    suite: str
    enforce_failures: tuple[str, ...]
    enforce_nan_failures: tuple[str, ...]
    report_failures: tuple[str, ...]
    report_nan_failures: tuple[str, ...]
    band_failures: tuple[str, ...]
    band_nan_metrics: tuple[str, ...]
    n_metrics: int

    @property
    def substantive_failures(self) -> tuple[str, ...]:
        """Every finite-valued failure in this cell, on either surface, sorted."""
        return tuple(
            sorted(set(self.enforce_failures) | set(self.band_failures) | set(self.report_failures))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "suite": self.suite,
            "n_metrics": self.n_metrics,
            "enforce_failures": list(self.enforce_failures),
            "enforce_nan_failures": list(self.enforce_nan_failures),
            "report_failures": list(self.report_failures),
            "report_nan_failures": list(self.report_nan_failures),
            "band_failures": list(self.band_failures),
            "band_nan_metrics": list(self.band_nan_metrics),
        }


@dataclass(frozen=True)
class ControlOutcome:
    """One control's full result: its designation, its cells, and its verdict."""

    control_id: str
    designation: Designation
    battery_passed: bool
    cells: tuple[CellOutcome, ...]
    values: Mapping[str, float]
    # metric name -> the suite that produced it. Needed because `values` is keyed by
    # metric name alone (the key convention `ah.eval.reference`/`prereg` share) and the
    # same name never appears in two suites, but a caller asking "what did the
    # memorization suite report for this control" has no other way to select them.
    suite_of: Mapping[str, str]

    def cell(self, tier: str, suite: str) -> CellOutcome | None:
        for c in self.cells:
            if c.tier == tier and c.suite == suite:
                return c
        return None

    def suite_metrics(self, suite: str) -> dict[str, float]:
        """Every metric value this control produced in ``suite``, by metric name."""
        return {
            name: value for name, value in self.values.items() if self.suite_of.get(name) == suite
        }

    @property
    def designated_cells(self) -> tuple[CellOutcome, ...]:
        return tuple(
            c
            for c in self.cells
            if c.tier in self.designation.tiers and c.suite in self.designation.suites
        )

    @property
    def designated_substantive_failures(self) -> tuple[str, ...]:
        """Finite-valued failures inside the designated cells -- the acceptance signal."""
        out: set[str] = set()
        for c in self.designated_cells:
            out |= set(c.substantive_failures)
        return tuple(sorted(out))

    @property
    def substantive_failures(self) -> tuple[str, ...]:
        out: set[str] = set()
        for c in self.cells:
            out |= set(c.substantive_failures)
        return tuple(sorted(out))

    @property
    def enforce_failures(self) -> tuple[str, ...]:
        out: set[str] = set()
        for c in self.cells:
            out |= set(c.enforce_failures)
        return tuple(sorted(out))

    @property
    def band_failures(self) -> tuple[str, ...]:
        out: set[str] = set()
        for c in self.cells:
            out |= set(c.band_failures)
        return tuple(sorted(out))

    @property
    def caught(self) -> bool:
        """Caught by ANY rejection surface (enforce, report, or band) in a designated
        cell. This is a weaker claim than :attr:`caught_at_criterion` and must not be
        read as "caught via the mechanism this control was designed to exercise" -- see
        that property's docstring for why the distinction matters."""
        return bool(self.designated_substantive_failures)

    @property
    def caught_at_criterion(self) -> bool:
        """Caught specifically via :attr:`Designation.criterion` -- the rejection
        surface the plan actually names for this control (``"enforce"`` or ``"band"``).

        Exists because the report table prints ``criterion`` and ``caught`` side by
        side, and a reader can misread ``criterion: enforce`` next to ``caught: yes`` as
        "this control was caught AT enforce level" -- which, per the module docstring's
        Finding 2, is false for every control except via the one shared, non-
        discriminating ``floor_violations`` gate. This property answers the narrower
        question the table invites but does not itself answer: did THIS SPECIFIC surface
        fire, substantively, in a designated cell.
        """
        out: set[str] = set()
        for c in self.designated_cells:
            surface = (
                c.band_failures if self.designation.criterion == "band" else c.enforce_failures
            )
            out |= set(surface)
        return bool(out)

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "designation": {
                "tiers": list(self.designation.tiers),
                "suites": list(self.designation.suites),
                "criterion": self.designation.criterion,
            },
            "construction": self.designation.construction,
            "battery_passed": self.battery_passed,
            "caught_by_designated_tier": self.caught,
            "caught_at_criterion": self.caught_at_criterion,
            "designated_substantive_failures": list(self.designated_substantive_failures),
            "substantive_failures": list(self.substantive_failures),
            "enforce_failures": list(self.enforce_failures),
            "band_failures": list(self.band_failures),
            "cells": [c.to_dict() for c in self.cells],
        }


@dataclass(frozen=True)
class NegativeControlReport:
    """The acceptance artifact: a row per control, a column per tier.

    JSON and markdown follow :class:`ah.eval.battery.BatteryReport`'s conventions (same
    header fields, same ``to_dict``/``to_json``/``to_markdown`` trio, ASCII only). The
    detail section under the table names every metric that fired, per control and per
    suite, so a reviewer can see *why* a control was rejected rather than only *that*
    it was.
    """

    battery_version: str
    prereg_digest: str
    vintage_id: str
    active_blocks: tuple[str, ...]
    seed: int
    n_paths: int
    months: int
    n_resamples: int
    block_length: int
    level: float
    panel_factors: tuple[str, ...]
    panel_n_obs: int
    panel_first_date: str
    panel_last_date: str
    outcomes: tuple[ControlOutcome, ...]

    def outcome(self, control_id: str) -> ControlOutcome:
        for o in self.outcomes:
            if o.control_id == control_id:
                return o
        raise NegativeControlError(f"no outcome for control '{control_id}'")

    @property
    def shared_enforce_failures(self) -> tuple[str, ...]:
        """Enforce failures that fired for EVERY control -- i.e. that discriminate nothing.

        A negative-control suite's whole claim is "the battery told these apart from a
        good generator". A gate that rejects all five identically has not told anything
        apart: at best it says something about the *data*, at worst it makes
        :attr:`ControlOutcome.battery_passed` false for a reason unrelated to any
        control's defect and lets a reader conclude the battery works when it did not.
        Reported explicitly so that conclusion cannot be drawn by accident.
        """
        if not self.outcomes:  # pragma: no cover - never empty in practice
            return ()
        shared = set(self.outcomes[0].enforce_failures)
        for o in self.outcomes[1:]:
            shared &= set(o.enforce_failures)
        return tuple(sorted(shared))

    @property
    def discriminating_enforce_failures(self) -> Mapping[str, tuple[str, ...]]:
        """Per control, the enforce failures that are NOT in :attr:`shared_enforce_failures`."""
        shared = set(self.shared_enforce_failures)
        return MappingProxyType(
            {
                o.control_id: tuple(n for n in o.enforce_failures if n not in shared)
                for o in self.outcomes
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "battery_version": self.battery_version,
            "prereg_digest": self.prereg_digest,
            "vintage_id": self.vintage_id,
            "active_blocks": list(self.active_blocks),
            "seed": self.seed,
            "n_paths": self.n_paths,
            "months": self.months,
            "n_resamples": self.n_resamples,
            "block_length": self.block_length,
            "level": self.level,
            "fitted_panel": {
                "factors": list(self.panel_factors),
                "n_obs": self.panel_n_obs,
                "first_date": self.panel_first_date,
                "last_date": self.panel_last_date,
            },
            "all_caught": all(o.caught for o in self.outcomes),
            "shared_enforce_failures": list(self.shared_enforce_failures),
            "discriminating_enforce_failures": {
                k: list(v) for k, v in self.discriminating_enforce_failures.items()
            },
            "controls": [o.to_dict() for o in self.outcomes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = [
            f"# Negative-control suite ({self.battery_version})",
            "",
            f"- vintage: {self.vintage_id}",
            f"- active blocks: {', '.join(self.active_blocks)}",
            f"- seed: {self.seed}; paths: {self.n_paths}; months: {self.months}",
            f"- reference: n_resamples={self.n_resamples}, block_length={self.block_length}, "
            f"level={self.level}",
            f"- fitted panel: {self.panel_n_obs} obs, {self.panel_first_date} .. "
            f"{self.panel_last_date}, {len(self.panel_factors)} factors",
            f"- prereg digest: {self.prereg_digest}",
            f"- enforce failures shared by ALL five (discriminate nothing): "
            f"{', '.join(self.shared_enforce_failures) or 'none'}",
            "",
            "Cells show `E<n>` enforce-threshold / `R<n>` report-threshold / `B<n>` "
            "reference-band failures, counting only metrics with a FINITE value. `*` "
            "marks a designated cell; `MISS` marks a designated cell that did not fire.",
            "",
            "`caught_on_any_surface`: caught by SOME designated-cell rejection surface "
            "(enforce, report, or band). `caught_at_criterion`: caught specifically via "
            "the `criterion` column -- the surface this control was designed to "
            "exercise. The two differ whenever a control was caught only by a surface "
            "other than its own designated one (see the module docstring's Finding 2): "
            "read `criterion: enforce` next to `caught_on_any_surface: yes` as NOT "
            "implying an enforce-level catch unless `caught_at_criterion` also says yes.",
            "",
        ]

        header = (
            "| control | criterion | "
            + " | ".join(TIERS)
            + " | caught_on_any_surface | caught_at_criterion |"
        )
        lines.append(header)
        lines.append("| --- | --- | " + " | ".join("---" for _ in TIERS) + " | --- | --- |")
        for o in self.outcomes:
            cells: list[str] = []
            for tier in TIERS:
                tier_cells = [c for c in o.cells if c.tier == tier]
                enforce = sum(len(c.enforce_failures) for c in tier_cells)
                report_sev = sum(len(c.report_failures) for c in tier_cells)
                band = sum(len(c.band_failures) for c in tier_cells)
                designated = any(
                    c.tier in o.designation.tiers and c.suite in o.designation.suites
                    for c in tier_cells
                )
                text = f"E{enforce}/R{report_sev}/B{band}" if tier_cells else "-"
                if designated:
                    fired = any(
                        c.substantive_failures
                        for c in tier_cells
                        if c.suite in o.designation.suites
                    )
                    text = f"*{text}" if fired else f"*{text} MISS"
                cells.append(text)
            verdict = "yes" if o.caught else "**NO**"
            at_criterion = "yes" if o.caught_at_criterion else "**NO**"
            lines.append(
                f"| {o.control_id} | {o.designation.criterion} | "
                + " | ".join(cells)
                + f" | {verdict} | {at_criterion} |"
            )
        lines.append("")

        for o in self.outcomes:
            lines.append(f"## {o.control_id}")
            lines.append("")
            lines.append(f"- construction: {o.designation.construction}")
            lines.append(
                f"- designated: tier(s) {', '.join(o.designation.tiers)}; "
                f"suite(s) {', '.join(o.designation.suites)}; criterion "
                f"{o.designation.criterion}"
            )
            lines.append(f"- battery verdict: {'PASS' if o.battery_passed else 'FAIL'}")
            lines.append(
                f"- caught on any surface: {'yes' if o.caught else 'NO -- see the report'}"
            )
            lines.append(
                f"- caught at its designated criterion ({o.designation.criterion}): "
                f"{'yes' if o.caught_at_criterion else 'NO -- caught, if at all, by a different surface'}"
            )
            lines.append("")
            lines.append(
                "| tier | suite | metrics | enforce fired | report fired | band fired | NaN-only |"
            )
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for c in o.cells:
                marker = (
                    "*" if c.tier in o.designation.tiers and c.suite in o.designation.suites else ""
                )
                lines.append(
                    f"| {marker}{c.tier} | {c.suite} | {c.n_metrics} | "
                    f"{', '.join(c.enforce_failures) or '-'} | "
                    f"{', '.join(c.report_failures) or '-'} | "
                    f"{', '.join(c.band_failures) or '-'} | "
                    f"{len(c.enforce_nan_failures) + len(c.report_nan_failures) + len(c.band_nan_metrics)} |"
                )
            lines.append("")
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# running the suite
# --------------------------------------------------------------------------- #


def control_reference(
    access: DataAccess,
    manifest: FactorManifest,
    *,
    n_resamples: int = 1000,
    months: int = 120,
    level: float = 0.9,
    block_length: int = DEFAULT_BLOCK_LENGTH,
    seed: int = 0,
    vintage_id: str = "negative-controls",
) -> ReferenceStats:
    """The one train+validation reference the controls are fitted from AND judged against.

    Exactly :func:`ah.eval.reference.compute_reference` with
    ``resample_length=months`` -- the same length-matching
    :func:`ah.eval.battery.run_full_battery` applies -- exposed as a named function so a
    caller can fit the controls without running the battery, and so
    :func:`run_negative_controls` computes it once rather than five identical times.
    """
    return compute_reference(
        access,
        manifest,
        vintage_id=vintage_id,
        seed=seed,
        n_resamples=n_resamples,
        level=level,
        block_length=block_length,
        resample_length=months,
    )


def _build_outcome(
    control_id: str, report: BatteryReport, results: Sequence[MetricResult]
) -> ControlOutcome:
    by_cell: dict[tuple[str, str], list[MetricResult]] = {}
    for r in results:
        by_cell.setdefault((r.tier, r.suite), []).append(r)

    cells: list[CellOutcome] = []
    suite_of: dict[str, str] = {}
    values: dict[str, float] = {}
    for (tier, suite), group in sorted(by_cell.items()):
        enforce: list[str] = []
        enforce_nan: list[str] = []
        report_sev: list[str] = []
        report_nan: list[str] = []
        band: list[str] = []
        band_nan: list[str] = []
        for r in group:
            values[r.name] = r.value
            suite_of[r.name] = suite
            finite = _is_finite(r.value)
            if r.passed is False:
                if r.severity == "enforce":
                    (enforce if finite else enforce_nan).append(r.name)
                else:
                    (report_sev if finite else report_nan).append(r.name)
            if _outside_band(r):
                band.append(r.name)
            elif r.band is not None and not finite:
                band_nan.append(r.name)
        cells.append(
            CellOutcome(
                tier=tier,
                suite=suite,
                enforce_failures=tuple(sorted(enforce)),
                enforce_nan_failures=tuple(sorted(enforce_nan)),
                report_failures=tuple(sorted(report_sev)),
                report_nan_failures=tuple(sorted(report_nan)),
                band_failures=tuple(sorted(band)),
                band_nan_metrics=tuple(sorted(band_nan)),
                n_metrics=len(group),
            )
        )

    return ControlOutcome(
        control_id=control_id,
        designation=DESIGNATIONS[control_id],
        battery_passed=report.passed,
        cells=tuple(cells),
        values=MappingProxyType(values),
        suite_of=MappingProxyType(suite_of),
    )


def run_negative_controls(
    *,
    access: DataAccess,
    manifest: FactorManifest,
    prereg: PreRegistration,
    seed: int,
    n_paths: int = 32,
    months: int = 120,
    n_resamples: int = 1000,
    level: float = 0.9,
    block_length: int = DEFAULT_BLOCK_LENGTH,
    reference_seed: int | None = None,
) -> NegativeControlReport:
    """Run the full validation battery over all five controls; return the report table.

    One reference, computed once at ``months`` (see :func:`control_reference` and the
    module docstring's "Cost"); the reference-dependent suites registered once against
    it; then :func:`ah.eval.battery.run_battery` per control, inside a
    :func:`negative_control_registry` context so the ``conditional`` suite can re-invoke
    each control by ``generator_id``.

    Determinism: ``seed`` drives every control's own sampling (control ``k`` in
    :data:`NEGATIVE_CONTROL_IDS` order uses ``seed + 7919 * k``, ``CLAUDE.md``'s
    platform-wide ensemble-seed stride) and the battery's Monte-Carlo subsampling;
    ``reference_seed`` (defaulting to ``seed``) drives the bootstrap bands. The same
    inputs give a bit-identical report.

    ``ah.eval.battery.SUITES`` is process-global, exactly like
    :mod:`ah.gen.registry`'s ``_REGISTRY`` that :func:`negative_control_registry`
    already snapshots and restores: this function calls
    :func:`~ah.eval.battery.register_reference_dependent_suites`, which mutates
    ``SUITES`` in place, so it snapshots ``SUITES`` first and restores it in a
    ``finally`` -- symmetric with the generator-registry handling, so a CLI caller (with
    no test fixture to compensate) does not leak this call's reference-dependent suites
    into a later, unrelated battery run in the same process.
    """
    reference = control_reference(
        access,
        manifest,
        n_resamples=n_resamples,
        months=months,
        level=level,
        block_length=block_length,
        seed=seed if reference_seed is None else reference_seed,
    )
    panel = fit_historical_panel(reference)

    outcomes: list[ControlOutcome] = []
    digest = ""
    saved_suites = dict(battery_mod.SUITES)
    try:
        register_reference_dependent_suites(manifest, reference)
        with negative_control_registry(reference):
            for k, control_id in enumerate(NEGATIVE_CONTROL_IDS):
                control = gen_registry.resolve(control_id)
                ensemble = control.sample_months(months, n_paths, seed + 7919 * k)
                report = run_battery(
                    ensemble,
                    reference=reference,
                    prereg=prereg,
                    manifest=manifest,
                    seed=seed,
                )
                digest = report.prereg_digest
                outcomes.append(_build_outcome(control_id, report, report.results))
    finally:
        battery_mod.SUITES.clear()
        battery_mod.SUITES.update(saved_suites)

    if not digest:  # pragma: no cover - NEGATIVE_CONTROL_IDS is never empty
        digest = prereg_mod.seal(prereg.source_path, sealed_at="n/a", dry_run=True)

    return NegativeControlReport(
        battery_version=BATTERY_VERSION,
        prereg_digest=digest,
        vintage_id=reference.vintage_id,
        active_blocks=manifest.active_blocks,
        seed=seed,
        n_paths=n_paths,
        months=months,
        n_resamples=n_resamples,
        block_length=block_length,
        level=level,
        panel_factors=panel.factor_names,
        panel_n_obs=panel.n_obs,
        panel_first_date=str(panel.dates.min().date()),
        panel_last_date=str(panel.dates.max().date()),
        outcomes=tuple(outcomes),
    )
