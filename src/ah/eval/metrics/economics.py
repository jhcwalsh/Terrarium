"""The economic tier: implied Sharpe by regime, term premium, ERP, no-money-pump audit,
policy-anchor sanity (WP2.2 Task 5).

STEP2-GENERATOR-PLAN Sec.WP2.2's ``economics.py`` bullet, and DN-1.1 Sec.II.6's
"Economic" row, NORMATIVE for this suite's scope and judgement style:

    | Economic | Implied Sharpe ratios, term premium, ERP by regime; no-money-pump  |
    |          | audit; policy-anchor sanity | Defensible ranges, documented |       |
    |          | Literature ranges                                                  |

Every metric here is tier ``"economic"`` (:data:`~ah.eval.battery.TIERS`), and every
metric is judged against a **defensible absolute range**, never a train+validation
bootstrap band -- this is the one DN-1.1 tier whose own row says so explicitly
("Literature ranges", not "1926- panel, bootstrap CIs" the way the monthly/1-5yr/10yr
rows read). All six names are therefore registered in
:data:`~ah.eval.reference.PANEL_STATS` with no ``fn`` (the identical shape
``discriminative_score``/the memorization suite use): three of the six combine factors
from different blocks or a factor against a declared derived cash series, for which no
:data:`~ah.eval.reference.CROSS_BLOCK_STATS` entry exists (RFR-14 restricts cross-block
coverage to the pairs ``reference.py``'s own estimators compute), and the other three
are not two-factor comparisons at all.

The numeraire, stated once, reused rather than re-decided
------------------------------------------------------------
``pre-registration.yaml``'s ``conventions.numeraire_statement`` declares ONE numeraire,
total return, for every capital-committing leg -- and
``governance/retrofit-register.md`` RFR-12 records exactly how the platform has already
gotten this wrong once: three D4 strategies silently credit uncommitted capital ZERO
return instead of the cash rate, because no ``cash_tr_1m`` leg exists in their
``weights``. :func:`equity_risk_premium` does not repeat that error, and does not
re-decide "which cash rate" a second, independent way: it subtracts
``derived_series.cash_tr_1m`` -- the SEALED derived series ALREADY declared in
``pre-registration.yaml`` (``bond_total_return`` on ``policy_rate`` at
``duration_years: 0.0``, i.e. the pure carry term, the overnight policy rate
compounded simply over the month) -- via :func:`ah.eval.metrics.tails.derived_series_values`,
the SAME function :mod:`ah.eval.metrics.tails` uses to resolve every other derived
leg. There is no second cash-rate decision anywhere in this module.

1. ``implied_sharpe_{EXP,SLOW,REC,CRI,STAG,REF}`` -- a structural gap, not computed
--------------------------------------------------------------------------------------
DN-1.1's "by regime" qualifier means :func:`ah.data.derive.label_regime`'s six labels
(:data:`ah.data.derive.REGIME_LABELS`). Exactly as
``ah.eval.metrics.horizon``'s ``regime_duration_{mean,p50,p90}`` (see that module's
docstring's "Two structural gaps"), ``label_regime`` needs FIVE inputs and only THREE
are constructible from a generated factor (``cpi`` -> ``cpi_yoy``, ``equity_mkt`` ->
``drawdown``, ``hy_spread`` -> ``hy_oas``) -- ``usrec`` (NBER recession) and
``growth_yoy`` (industrial production) have no ``factors.yaml`` mapping at all. Regime
labels therefore cannot be honestly assigned to any generated path today, on ANY
ensemble, so all six names are always NaN, ``status=STRUCTURALLY_UNAVAILABLE``
(:data:`~ah.eval.battery.STRUCTURALLY_UNAVAILABLE`, matching
``ah.eval.metrics.horizon``'s marker so a reader of the report can tell this apart from
a genuine generator failure), carrying the ruleset version they would be evaluated
under once the gap closes (:data:`REGIME_RULESET_VERSION`, the same
``ah.data.derive.regime_thresholds()["version"]`` ``horizon.py`` records). Recorded as
``governance/retrofit-register.md`` RFR-27.

2. ``term_premium`` -- ``mean(ust_10y - policy_rate)``
-----------------------------------------------------------
A stated function of the generated rate factors, exactly as DN-1.1's own economic row
names it. Both ``ust_10y`` and ``policy_rate`` are LEVELS in percentage points
(``conventions.level_factors``), so this is a level-space yield-curve slope, not a
return -- no numeraire question arises (a numeraire governs how a CAPITAL-COMMITTING
RETURN LEG is quoted; a yield spread is neither). POOLED (not per-path): the mean over
every ``(path, month)`` observation.

3. ``equity_risk_premium`` -- ``mean(equity_mkt - cash_tr_1m)``
--------------------------------------------------------------------
``equity_mkt`` is total-return (``conventions.numeraire: total_return``); ``cash_tr_1m``
is the sealed derived cash-return series -- see "The numeraire" above. POOLED, exactly
as ``term_premium``.

4. ``money_pump_violations`` -- a no-arbitrage audit over the ZERO-COST legs
------------------------------------------------------------------------------
``enforce``, ``max: 0`` -- must be exactly zero, and Task 5's brief is explicit that a
metric wired to always report 0 without checking anything is worthless, so
``tests/test_economics.py`` proves a deliberately-violating ensemble produces a
non-zero count (the test IS the deliverable, not the metric formula).

**The audit.** ``conventions.numeraire_zero_cost_legs`` (``ah.strategies.Conventions
.zero_cost_legs``) names every self-financing, costless overlay leg -- a leg that
commits no capital, so a costless combination that NEVER LOSES and SOMETIMES GAINS,
over its own realized path, is a free lunch: a strictly dominating costless
combination in the sense DN-1.1's own economic row names. For each zero-cost leg
(resolved exactly as ``ah.eval.metrics.tails`` resolves any strategy leg -- a raw
active factor directly, or a declared ``derived_series`` via
:func:`~ah.eval.metrics.tails.derived_series_values`) and each PATH of the ensemble
independently, the leg "violates" on that path iff every month's realized return is
``>= 0`` AND at least one month's return is ``> 0`` (never negative, strictly positive
somewhere -- weakly dominates cash at zero cost, for the whole path). The reported
count is the number of ``(leg, path)`` pairs violating, POOLED across every qualifying
leg (this is a total COUNT, not a per-path average: a per-(leg,path) indicator, summed).

**Coverage limitation, stated rather than left implicit (Important 2, WP2.2 Task 5 fix
pass).** DN-1.1's own economic row names the audit as catching "a strictly dominating
COMBINATION of generated factors" -- this implementation narrows that to a PER-LEG check
with no combination search: it asks only "does any single zero-cost leg, on its own,
never lose money on some path", never "does some weighted COMBINATION of two or more
zero-cost legs (e.g. a relative-value spread between ``smb`` and ``hml``) dominate even
though neither leg alone does". A generator could construct exactly that kind of
multi-leg free lunch and this gate would report 0 violations, silently. It DOES catch
the degenerate single-leg case the deliverable test above exercises, and for any
genuinely stochastic per-leg process (any leg with real two-sided variance) the
per-path probability that 120 consecutive months are all ``>= 0`` is astronomically
small, so in practice this gate almost never fires except on a literally-degenerate
leg -- it is a narrow but non-vacuous check, not the full combinatorial audit the brief
describes. Recorded as ``governance/retrofit-register.md`` RFR-29 so WP2.3 knows the
gate's real coverage before relying on it as evidence of no-arbitrage compliance.

5. ``floor_violations`` -- structural floors from DN-1.1 Sec.II.4
------------------------------------------------------------------------
``enforce``, ``max: 0``. DN-1.1 Sec.II.4: "rates and spreads generated in softplus
space with floors (i >= -1%, spread >= 100bp)". Applied to the two disjoint groups
these floors literally name: :data:`RATE_FLOOR_FACTORS` (``policy_rate``, ``ust_2y``,
``ust_10y``, ``hqm_curve``) each floored at :data:`RATE_FLOOR_PCT` (-1.0, i.e. -1%);
:data:`SPREAD_FLOOR_FACTORS` (``ig_spread``, ``hy_spread``, ``funding_spread``) each
floored at :data:`SPREAD_FLOOR_PCT` (1.0, i.e. 100bp). ``cpi`` (an index level, not a
rate or a spread) and ``equity_vol`` (a volatility index) carry no DN-1.1-stated floor
and are excluded. WP2.8's ``constraints.py`` will make these structurally impossible by
construction (generating in softplus space); this metric is the check that the
constraint actually held, for a generator built before that lands. POOLED count of
``(factor, path, month)`` observations below their factor's floor.

**Consequence for an ensemble that omits the audited factors entirely (Important 7,
WP2.2 Task 5 fix pass), stated deliberately rather than discovered by WP2.4.** Both
``money_pump_violations`` and ``floor_violations`` are ``enforce``-severity, ``max: 0``
in ``pre-registration.yaml``, and both NaN (see :data:`ECONOMICS_MIN_OBS`'s docstring
below) when the ensemble emits NONE of ``conventions.numeraire_zero_cost_legs`` /
NONE of :data:`RATE_FLOOR_FACTORS`/:data:`SPREAD_FLOOR_FACTORS` respectively -- and
under THE ONE NaN RULE (``ah.eval.battery._passed``, ``pre-registration.yaml``'s
``conventions.nan_metric_rule``) a NaN value against an ``enforce`` threshold FAILS.
**This is intentional, not a bug to be softened**: these two gates exist precisely so
"the generator produces less" is never a route to a better-looking number, and an
ensemble that omits the audited factors altogether has, by construction, produced
LESS than one that emits them and passes honestly -- it has not demonstrated
compliance with an audit it structurally cannot be checked against, so THE ONE NaN
RULE's existing, uniform judgment (no metric-specific carve-out) is the correct one
here too. The consequence is real for WP2.4, though: **any ensemble not emitting at
least one of ``smb``/``hml``/``mom``/``credit_xs_hy`` and at least one
rate/spread floor-bearing factor hard-fails these two enforce gates on a battery run
that reaches ``run_full_battery``.** WP2.4's bootstrap generator must emit these
factors for the battery to reach a genuine verdict on them.
``tests/test_eval_battery.py::test_run_full_battery_orchestration_fixture_fails_on_the_money_pump_and_floor_gates``
pins this behaviour so a future change to it is a deliberate, tested decision rather
than a silent regression either way.

6. ``policy_anchor_deviation`` -- deviation from a simplified Taylor-type anchor
--------------------------------------------------------------------------------------
DN-1.1 Sec.II.2 defines the L1 policy anchor as
``i_t = r*_t + pi*_t + phi_pi*(pi_t - pi*_t) + phi_c*c_t + eps_t`` -- a Taylor-type
reaction to the GAP between realized and TREND inflation, plus a regime cycle term.
``r*_t`` (neutral real rate), ``pi*_t`` (trend inflation) and ``c_t`` (the L2 cycle
term) are LATENT Layer-1/Layer-2 states, not generator-visible output factors in
``factors.yaml`` -- an honest reading of DN-1.1's own equation cannot be evaluated from
generated factors alone, the identical structural gap ``ah.eval.metrics.horizon``'s
``ten_year_return_vs_valuation_*`` and this suite's own ``implied_sharpe_*`` record.
Rather than a second structural-gap NaN stub, this metric substitutes a STATED,
SIMPLIFIED anchor built only from quantities a generator DOES emit:

    anchor_t = TAYLOR_R_STAR + TAYLOR_PI_TARGET
               + TAYLOR_PHI_PI * (cpi_yoy_t - TAYLOR_PI_TARGET)

``cpi_yoy_t`` is the trailing 12-month percent change of the generated ``cpi`` level
(``(cpi_t / cpi_{t-12} - 1) * 100``, the same year-on-year convention
:func:`ah.data.derive.yoy` uses). :data:`TAYLOR_R_STAR` (0.75) is DN-1.1 Sec.II.2's own
table entry for the neutral-real-rate prior mean (``mu_r``); :data:`TAYLOR_PHI_PI`
(0.5) is that same table's ``phi_pi`` prior mean. :data:`TAYLOR_PI_TARGET` (2.0) is
**not** from DN-1.1** -- DN-1.1 states ``pi*`` is itself estimated with "a diffuse
prior -- the target can drift", deliberately not a fixed number -- so this constant
substitutes the conventional post-1990s central-bank inflation target from the
literature (consistent with this tier's own "Literature ranges" reference-data
column), used ONLY because the model's own latent ``pi*_t`` is unavailable. The cycle
term ``phi_c * c_t`` is DROPPED entirely (``c_t`` has no generator-visible proxy and
DN-1.1's table gives no ``phi_c`` prior to substitute) -- a stated simplification, not
an oversight. The reported value is the ROOT-MEAN-SQUARE deviation of ``policy_rate_t``
from ``anchor_t``, pooled over every ``(path, month >= 12)`` observation (month < 12 has
no defined ``cpi_yoy``). **Lower is better, but NOT unboundedly, and 0 is not the
target** -- see the module docstring's "Anti-gaming: two-sided ``policy_anchor_deviation``"
section below for why an exact-tracking generator is a WORSE, more degenerate generator
than a realistically noisy one, and why the sealed band is two-sided rather than a bare
``max``.

Anti-gaming: two-sided ``policy_anchor_deviation``, so tracking the anchor exactly is
not free
--------------------------------------------------------------------------------------
The RMS deviation reported above is **not** "lower is better without limit". A real
policy-setting process deviates from any Taylor-type anchor by roughly 1-2 percentage
points RMS in practice (discretion, the DROPPED ``phi_c*c_t`` cycle term, measurement
noise, everything the simplified anchor above does not capture) -- so a generator whose
``policy_rate`` DETERMINISTICALLY equals ``anchor_t`` every month scores exactly 0.0,
the numerically best possible value, while being LESS realistic than a generator with
genuine idiosyncratic variation around the anchor. This is the eighth instance of this
work package's dominant failure mode ("a metric that improves when the generator
produces less/simpler"), on the identical axis :func:`interval_coverage`'s sibling
metric in :mod:`ah.eval.metrics.calibration` already reasons about explicitly: an
over-wide predictive distribution is exactly as much a calibration failure as an
under-wide one, so that metric's sealed band is two-sided rather than treating one
direction as free. ``pre-registration.yaml``'s
``thresholds.panel.policy_anchor_deviation`` is likewise sealed TWO-SIDED here (a
``min`` bounded away from 0.0, not only a ``max``), so a deterministic anchor-follower
FAILS the low side rather than reading as the best possible generator.
``tests/test_economics.py``'s ``test_policy_anchor_deviation_near_zero_is_not_automatically_good``
is the deliverable proving the gaming route directly (a degenerate exact-tracker scores
strictly better than a realistically noisy one under the raw metric alone), and
``test_policy_anchor_deviation_degenerate_generator_fails_the_sealed_two_sided_band``
proves the sealed band catches it.

Anti-gaming floor: :data:`ECONOMICS_MIN_OBS`
--------------------------------------------------
Every one of the five computable metrics above (everything but the six
``implied_sharpe_*`` structural-gap stubs) is an aggregate over pooled
``(path, month)`` observations, and every one NaNs below :data:`ECONOMICS_MIN_OBS` (60)
pooled observations rather than reporting a small-sample-lucky number -- the identical
discipline ``ah.eval.reference``'s ``DRAWDOWN_MIN_EPISODES`` /
``VARIANCE_RATIO_MIN_SUMS`` state, applied here because a COUNT (``money_pump_violations``,
``floor_violations``) shrinks toward its own favourable floor of 0 simply by pooling
fewer observations, and a MEAN/RMS (the other three) is more likely to land inside a
sealed range by small-sample luck with too few observations -- "the generator produces
less" must never be a route to a better-looking number. Every aggregate also NaNs the
WHOLE metric (poisons, never silently drops) on any non-finite pooled observation --
the identical fix ``ah.eval.reference.drawdown_episodes`` applies to an overflowed
compounded return, for the identical reason: a NaN/inf comparison against a floor is
``False`` either way (never flags as a violation), so silently ignoring a non-finite
value would let a generator dodge ``money_pump_violations``/``floor_violations`` by
overflowing rather than by genuinely complying.

Registration is deferred, exactly as every other reference-dependent suite
-------------------------------------------------------------------------------
This suite needs a :class:`~ah.factors.FactorManifest` (for the active factor axis);
``reference`` is accepted for signature symmetry with every other suite builder in
``ah.eval.battery._REFERENCE_DEPENDENT_SUITE_BUILDERS`` but is not read (every metric
here is computed purely from the generated ensemble and sealed conventions/derived
series -- there is no train+validation band to compare against, per this tier's own
"Literature ranges" reference-data column). ``ah.eval.battery.run_full_battery`` is the
production caller, via that table's ``"economics"`` row.
"""

from __future__ import annotations

import numpy as np

from ah.data.derive import REGIME_LABELS, regime_thresholds
from ah.eval.battery import STRUCTURALLY_UNAVAILABLE, MetricFn, MetricSpec, register_suite
from ah.eval.metrics.tails import derived_series_values
from ah.eval.reference import ReferenceStats
from ah.factors import FactorManifest
from ah.gen.base import Ensemble, UnknownFactorError
from ah.strategies import DerivedSeries, load_conventions, load_derived_series

SUITE = "economics"
TIER = "economic"

# See the module docstring's "implied_sharpe_{...} -- a structural gap". Recorded for
# traceability (WP2.6 refits on regime labels; the plan requires the ruleset version be
# traceable), mirroring ah.eval.metrics.horizon.REGIME_RULESET_VERSION exactly.
REGIME_RULESET_VERSION = regime_thresholds()["version"]

# DN-1.1 Sec.II.2's table: mu_r (neutral real rate) prior mean and phi_pi (Taylor
# reaction coefficient) prior mean. See the module docstring's "policy_anchor_deviation"
# for the full derivation and what each constant is (and is not) sourced from.
TAYLOR_R_STAR = 0.75
TAYLOR_PI_TARGET = 2.0
TAYLOR_PHI_PI = 0.5

# DN-1.1 Sec.II.4: "rates and spreads generated in softplus space with floors
# (i >= -1%, spread >= 100bp)".
RATE_FLOOR_FACTORS = frozenset({"policy_rate", "ust_2y", "ust_10y", "hqm_curve"})
SPREAD_FLOOR_FACTORS = frozenset({"ig_spread", "hy_spread", "funding_spread"})
RATE_FLOOR_PCT = -1.0
SPREAD_FLOOR_PCT = 1.0

# See the module docstring's "Anti-gaming floor".
ECONOMICS_MIN_OBS = 60

_CASH_SERIES_ID = "cash_tr_1m"

__all__ = [
    "ECONOMICS_MIN_OBS",
    "RATE_FLOOR_FACTORS",
    "RATE_FLOOR_PCT",
    "REGIME_RULESET_VERSION",
    "SPREAD_FLOOR_FACTORS",
    "SPREAD_FLOOR_PCT",
    "SUITE",
    "TAYLOR_PHI_PI",
    "TAYLOR_PI_TARGET",
    "TAYLOR_R_STAR",
    "TIER",
    "build_economics_suite",
    "register_economics_suite",
]


# --------------------------------------------------------------------------- #
# leg resolution -- reuses ah.eval.metrics.tails.derived_series_values, never a second
# independent decision about how a derived leg's return is computed
# --------------------------------------------------------------------------- #


def _resolve_leg_returns(
    ensemble: Ensemble, name: str, derived: dict[str, DerivedSeries]
) -> np.ndarray | None:
    """``(n_paths, months)`` return slab for an active factor or declared derived
    series id; ``None`` if ``name`` resolves to neither, or to a factor absent from
    this ensemble."""
    series = derived.get(name)
    try:
        if series is not None:
            return derived_series_values(ensemble, series)
        return ensemble.factor(name)
    except UnknownFactorError:
        return None


# --------------------------------------------------------------------------- #
# term_premium / equity_risk_premium
# --------------------------------------------------------------------------- #


def _term_premium_metric() -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if "ust_10y" not in ensemble.factor_names or "policy_rate" not in ensemble.factor_names:
            return float("nan")
        diff = (ensemble.factor("ust_10y") - ensemble.factor("policy_rate")).reshape(-1)
        if diff.size < ECONOMICS_MIN_OBS or not bool(np.all(np.isfinite(diff))):
            return float("nan")
        return float(np.mean(diff))

    return fn


def _equity_risk_premium_metric(derived: dict[str, DerivedSeries]) -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if "equity_mkt" not in ensemble.factor_names:
            return float("nan")
        cash = _resolve_leg_returns(ensemble, _CASH_SERIES_ID, derived)
        if cash is None:
            return float("nan")
        diff = (ensemble.factor("equity_mkt") - cash).reshape(-1)
        if diff.size < ECONOMICS_MIN_OBS or not bool(np.all(np.isfinite(diff))):
            return float("nan")
        return float(np.mean(diff))

    return fn


# --------------------------------------------------------------------------- #
# money_pump_violations
# --------------------------------------------------------------------------- #


def _money_pump_violations_metric(derived: dict[str, DerivedSeries]) -> MetricFn:
    zero_cost_legs = load_conventions().zero_cost_legs

    def fn(ensemble: Ensemble) -> float:
        pooled_obs = 0
        violations = 0
        any_finite_check_failed = False
        for leg in sorted(zero_cost_legs):
            returns = _resolve_leg_returns(ensemble, leg, derived)
            if returns is None:
                continue
            if not bool(np.all(np.isfinite(returns))):
                any_finite_check_failed = True
                continue
            pooled_obs += returns.size
            for path in range(returns.shape[0]):
                row = returns[path]
                if np.all(row >= 0.0) and np.any(row > 0.0):
                    violations += 1
        if any_finite_check_failed:
            return float("nan")
        if pooled_obs < ECONOMICS_MIN_OBS:
            return float("nan")
        return float(violations)

    return fn


# --------------------------------------------------------------------------- #
# floor_violations
# --------------------------------------------------------------------------- #


def _floor_violations_metric() -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        pooled_obs = 0
        violations = 0
        for factor, floor in (
            *((f, RATE_FLOOR_PCT) for f in sorted(RATE_FLOOR_FACTORS)),
            *((f, SPREAD_FLOOR_PCT) for f in sorted(SPREAD_FLOOR_FACTORS)),
        ):
            if factor not in ensemble.factor_names:
                continue
            values = ensemble.factor(factor)
            if not bool(np.all(np.isfinite(values))):
                return float("nan")
            pooled_obs += values.size
            violations += int(np.sum(values < floor))
        if pooled_obs < ECONOMICS_MIN_OBS:
            return float("nan")
        return float(violations)

    return fn


# --------------------------------------------------------------------------- #
# policy_anchor_deviation
# --------------------------------------------------------------------------- #


def _cpi_yoy(cpi_level: np.ndarray) -> np.ndarray:
    """Trailing 12-month percent change, per path -- ``cpi_level`` is ``(n_paths,
    months)``; the result is ``(n_paths, months - 12)``, aligned to months
    ``12..months-1`` (matching :func:`ah.data.derive.yoy`'s convention)."""
    if cpi_level.shape[1] <= 12:
        return np.empty((cpi_level.shape[0], 0), dtype=np.float64)
    return (cpi_level[:, 12:] / cpi_level[:, :-12] - 1.0) * 100.0


def _policy_anchor_deviation_metric() -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        if "policy_rate" not in ensemble.factor_names or "cpi" not in ensemble.factor_names:
            return float("nan")
        cpi_yoy = _cpi_yoy(ensemble.factor("cpi").astype(np.float64))
        if cpi_yoy.shape[1] == 0:
            return float("nan")
        anchor = TAYLOR_R_STAR + TAYLOR_PI_TARGET + TAYLOR_PHI_PI * (cpi_yoy - TAYLOR_PI_TARGET)
        policy_rate_tail = ensemble.factor("policy_rate")[:, 12:]
        deviation = (policy_rate_tail - anchor).reshape(-1)
        if deviation.size < ECONOMICS_MIN_OBS or not bool(np.all(np.isfinite(deviation))):
            return float("nan")
        return float(np.sqrt(np.mean(deviation**2)))

    return fn


# --------------------------------------------------------------------------- #
# implied_sharpe_{regime} -- structural gap, see module docstring
# --------------------------------------------------------------------------- #


def _structural_gap_metric() -> MetricFn:
    def fn(ensemble: Ensemble) -> float:
        del ensemble
        return float("nan")

    return fn


# --------------------------------------------------------------------------- #
# build_economics_suite / register_economics_suite
# --------------------------------------------------------------------------- #


def _spec(
    name: str, fn: MetricFn, *, status: str = "ok", metadata: tuple[tuple[str, str], ...] = ()
) -> MetricSpec:
    return MetricSpec(name=name, tier=TIER, fn=fn, suite=SUITE, status=status, metadata=metadata)


def build_economics_suite(
    manifest: FactorManifest, reference: ReferenceStats
) -> tuple[MetricSpec, ...]:
    """Every ``economics``-tier :class:`~ah.eval.battery.MetricSpec`. ``manifest`` is
    accepted for signature symmetry (unused: every metric here reads the ensemble's own
    factor names directly, not ``manifest.active_factors()``, since a factor absent
    from a given ensemble must NaN identically to one the manifest never declared --
    see :class:`~ah.gen.base.UnknownFactorError`'s docstring). ``reference`` is
    likewise accepted but not read -- see the module docstring's "Registration is
    deferred"."""
    del manifest, reference
    derived = dict(load_derived_series())

    specs: list[MetricSpec] = []
    regime_metadata = (
        ("regime_ruleset_version", REGIME_RULESET_VERSION),
        ("gap", "RFR-27"),
    )
    for regime in REGIME_LABELS:
        specs.append(
            _spec(
                f"implied_sharpe_{regime}",
                _structural_gap_metric(),
                status=STRUCTURALLY_UNAVAILABLE,
                metadata=regime_metadata,
            )
        )
    specs.append(_spec("term_premium", _term_premium_metric()))
    specs.append(_spec("equity_risk_premium", _equity_risk_premium_metric(derived)))
    specs.append(_spec("money_pump_violations", _money_pump_violations_metric(derived)))
    specs.append(_spec("floor_violations", _floor_violations_metric()))
    specs.append(_spec("policy_anchor_deviation", _policy_anchor_deviation_metric()))
    return tuple(specs)


def register_economics_suite(manifest: FactorManifest, reference: ReferenceStats) -> None:
    """``register_suite("economics", build_economics_suite(manifest, reference))``."""
    register_suite(SUITE, build_economics_suite(manifest, reference))
