"""The pre-registration seal machinery: block-nested thresholds, seal/verify,
the amendment log, and ``block_addition`` (WP2.1b Item 2 / Task 4).

WP2.3 seals the pre-registration: thresholds **and the code that judges them** are
hashed together before any training run, and after that every change is a dated,
post-hoc-flagged amendment logged in ``governance/amendment-log.yaml``. This module
builds that machinery -- with the block structure from Task 1 (``ah.factors``) already
wired through it -- so the seal freezes the right shape. WP2.1b itself sealed nothing;
**WP2.3 did**, on 2026-07-26. ``pre-registration.yaml`` now carries ``sealed: true`` and
``pre-registration.lock`` is committed beside it, so :func:`verify` runs its full
sealed-document check set -- and the lock digest -- on every battery invocation. The
post-seal procedure (amend, edit, re-seal, commit all three together) is stated once, in
``pre-registration.yaml``'s header.

Layout
------
- :func:`load` parses ``pre-registration.yaml`` into a :class:`PreRegistration`.
- :func:`verify` checks a loaded pre-registration against a :class:`~ah.factors.FactorManifest`
  (document version, block coverage, cross-block coverage, threshold key validity,
  threshold sanity, and -- the hole this task closes, see below) -- and, if given a
  lock file, that the lock was sealed for *this* document and that the sealed digest
  still matches the files on disk.
- :func:`seal` computes (and, unless ``dry_run``, writes) the digest that WP2.3 will
  freeze: canonically, the pre-registration YAML, the factor manifest YAML it
  references, and the source text of every "judged" module (see "What the seal
  covers" below).
- :func:`load_amendments` / :func:`append_amendment` read/extend
  ``governance/amendment-log.yaml``, which is append-only by construction (appends use
  file-append mode, so prior bytes are provably untouched).
- :func:`apply_block_addition` merges a ``block_addition`` amendment's new thresholds
  into a :class:`PreRegistration`, leaving every pre-existing block's and pair's
  thresholds byte-identical -- additive, not a re-seal (see
  ``governance/amendment-log.yaml``'s header).

What the seal covers (project owner's ruling, wider than STEP2-PLAN Sec.WP2.3)
------------------------------------------------------------------------------
``CLAUDE.md`` states the invariant as "thresholds **and the code that judges them** are
hashed together before any training run". STEP2-GENERATOR-PLAN Sec.WP2.3 words the same
requirement more narrowly -- the YAML plus the source of every enforce-tier metric plus
``g2.py`` -- which would leave outside the seal several modules that can move a
pass/fail verdict on their own. **The invariant governs**, so
:func:`_default_judged_sources` covers, by category:

- *acceptance thresholds and the factor namespace they are keyed to*: the
  pre-registration YAML and the ``factors.yaml`` it names (added by :func:`seal`), plus
  ``ah/factors.py``, which decides which blocks and factors are active at all;
- *sealed input data an estimator is defined over*: ``fixtures/worlds/conditional/*.json``
  (:data:`_REQUIRED_JUDGED_FIXTURE_GLOBS`). These are not fixtures in the disposable
  sense. ``conventions.condition_adherence_*_estimator`` defines each of its statistics as
  "pooled across every checked-in ``fixtures/worlds/conditional/*.json`` world tagged X",
  so editing one world's ``factor_conditions.inflation.average_pct`` from 12.0 to 3.0
  changes every inflation metric's value -- and, before these files joined the seal, did
  so with no lock violation and no amendment, leaving the estimator not reconstructible
  from the sealed set alone. They are sealed input data in exactly the sense
  ``factors.yaml`` is: a document the thresholds are keyed to, not code. Unlike the metric
  suites, this is a REQUIRED glob -- an empty directory raises rather than silently
  shrinking the seal, since a suite whose authored worlds vanished would report NaN
  everywhere rather than erroring;
- *the metrics being judged*: the enforce-tier metric suites under
  ``src/ah/eval/metrics/`` that exist yet. **This is a fixed name list**
  (``_METRIC_SUITE_NAMES``), not a directory scan: a helper module added under
  ``eval/metrics/`` beside the suites -- or any new judging module anywhere else --
  joins the seal only by being added to ``_METRIC_SUITE_NAMES`` /
  ``_REQUIRED_JUDGED_SOURCES``. WP2.2 must do that in the same PR that adds the module,
  or the module silently sits outside the hash;
- *the statistics the bands are derived from*: ``ah/eval/reference.py``;
- *the split boundaries that define the reference data*: ``ah/splits.py``, which
  hardcodes where ``train``, ``validation`` and ``holdout`` begin and end. Moving
  ``VALIDATION.end`` by a year silently changes every band in every block with no lock
  violation unless this module is itself hashed -- it defines what "train+validation"
  *means*, which is exactly as load-bearing as the code that computes statistics over
  it (final branch review finding, closed here);
- *the code that compares values to thresholds and decides*: ``ah/eval/prereg.py``
  (this module) and ``ah/eval/g2.py``;
- *the code that interprets the sealed D4 definitions*: ``ah/strategies.py``;
- *the code that renders the verdict*: ``ah/battery/report.py`` and
  ``ah/battery/stylized.py``;
- *the code that orchestrates metric suites into that verdict, and the code that reads
  the historical panel feeding* :mod:`ah.eval.reference` *in the first place* (WP2.2
  Task 1): ``ah/eval/battery.py`` and ``ah/eval/panel.py``. Both are judging code
  created outside ``src/ah/eval/metrics/``, so per the rule stated two paragraphs up
  they join this list in the same commit that adds them, rather than sitting outside
  the hash until someone notices.

This module hashing its own source is intentional and non-circular: the digest lands in
the lock file, never back inside ``prereg.py``. **Consequence, stated plainly so it is
not a surprise during WP2.2:** WP2.3 inherits this default, and once it seals, an edit
to *any* file in that list -- including a refactor of ``prereg.py`` or a new statistic
in ``reference.py`` -- requires a dated amendment in
``governance/amendment-log.yaml``.

Considered and excluded
~~~~~~~~~~~~~~~~~~~~~~~~
WP2.3 settled the two questions WP2.1b left open here; ``pre-registration.yaml``'s
``seal_scope:`` block is the sealed record, and ``governance/decision-register.md`` row
``S2-SEAL-SCOPE-2`` / ``governance/retrofit-register.md`` RFR-50 carry the same account.
What remains deliberately **outside** the seal, and why:

- ``ah/gen/base.py`` -- ``Ensemble.factor()`` resolves every D4 strategy leg (the
  lookup a strategy's ``weights``/``params`` series names go through at evaluation
  time). It is the generator layer's *container*, though -- the defendant whose output
  is judged, not the judge itself. Hashing it would turn every WP2.5-2.9 generator
  change (a new block, a new factor, a bugfix inside ``Ensemble``) into a dated
  amendment, which inverts the seal's purpose: it exists to freeze the judge, not to
  freeze the thing being judged.
- ``ah/data/splice.py`` -- **excluded on evidence, not on principle.** Its
  ``PROXY_RULES`` would backfill ``policy_rate`` (pre-1954) and ``hy_spread``
  (pre-1996), but ``ah.data.refresh`` does not apply them and
  :func:`ah.eval.panel.read_factor_frames` never calls this module at all, so no sealed
  band is a function of its code. The sealed reference run *demonstrates* that rather
  than assuming it: both factors appear in ``reference_run.missing_factors`` precisely
  because the backfills are absent from the frozen campaign vintage -- which is also the
  answer to RFR-10's standing question about which backfills the vintage contains
  (neither). What the vintage holds is pinned by the sealed ``campaign_vintage_id``, not
  by this module. If a later work package applies either rule, that produces a new
  vintage -- a campaign restart and a dated amendment regardless -- and ``splice.py``
  joins the seal at that point, because it will then be on the read path.

Two entries WP2.1b listed here are now **inside** the seal, each named in
:data:`_REQUIRED_JUDGED_SOURCES` / :data:`_REQUIRED_JUDGED_DATA` with its own reasoning:
``ah/data/derive.py`` (it *is* on the read path -- :data:`ah.eval.panel._DERIVED_EXPRS`
calls it at panel-read time for ``equity_mkt``/``ig_spread``/``funding_spread``, so
sealing only the binding was not enough) and ``src/ah/battery/thresholds.yaml`` (read by
the already-sealed ``ah/battery/report.py``; a sealed estimator over an unsealed input
is exactly the failure :data:`_REQUIRED_JUDGED_FIXTURE_GLOBS` exists to prevent).

Independent verifiability (why paths in the lock are relative)
---------------------------------------------------------------
A committed lock has to verify in CI, in a reviewer's clone, and under WSL2 (which
``CLAUDE.md`` requires for the L1/L2 work). The digest is therefore keyed on
**relative, forward-slashed** paths, never on the absolute path of the checkout that
produced it, and the lock stores them in that form. Two roots exist, in this priority:
the repository root (where the judged *code* lives) and the pre-registration's own
directory at seal time / the lock's own directory at verify time (where the sealed
*documents* live). In the real layout -- ``pre-registration.lock`` written beside
``pre-registration.yaml`` at the repo root -- the two roots are the same directory. A
path under neither root cannot be independently verified and is rejected at seal time.

The hole this task closes
--------------------------
``ah.strategies.load_conventions`` treats a *missing* ``conventions:`` block as "no
structured conventions declared" rather than an error -- a deliberate concession so
minimal hand-written test fixtures (that predate the block) keep loading. That
concession is safe everywhere it was made *except* here: this is the file the seal
hashes, so a deleted or misspelled ``conventons:`` key would silently disable the
level-factor/return-factor classification the loader would otherwise enforce, and
:mod:`ah.strategies` has no top-level unknown-key check that would catch the typo.
:func:`verify` therefore re-checks, unconditionally: the ``conventions`` block is
present; it declares every key :func:`ah.strategies.load_conventions` reads
(``percent_to_decimal``, ``months_per_year``, ``return_bearing_factors``,
``level_factors``, ``rebalance_cadences``, ``static_weights_composition``); and
``return_bearing_factors``/``level_factors`` together classify **exactly** the active
factor set of the given manifest -- every active factor in one of the two, none in
both, and nothing outside the active set. That last clause is
:func:`ah.strategies._validate_conventions`'s own rule, verbatim in effect: a check
whose stated purpose is closing a divergence with :mod:`ah.strategies` must not open a
new one, so :func:`verify` never green-lights a file
:func:`ah.strategies.load_conventions` would raise on. To make that true rather than
aspirational, :func:`_check_string_set_field` also mirrors
:func:`ah.strategies._require_string_set`'s own three rejection modes for each of
``return_bearing_factors``/``level_factors`` individually, before the cross-list
checks below run: neither list may be empty, every entry must be a non-empty string,
and neither list may repeat an entry (a final branch review finding -- the earlier
version of this check accepted all three, which ``ah.strategies`` would raise on).
(The check reads
``PreRegistration.raw`` directly rather than calling :mod:`ah.strategies`, which would
re-read the file from a path this module is not guaranteed to have -- e.g. after
:func:`apply_block_addition` produces an in-memory-only result.) A block addition
consequently requires the ``conventions`` block to be edited to classify the new
block's factors; :func:`apply_block_addition` merges thresholds only and deliberately
does not touch ``conventions`` -- see its docstring.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from ah.core.digest import canonical_json
from ah.data.derive import REGIME_LABELS
from ah.eval.reference import (
    ACF_ABS_MAX_LAG,
    ACF_R_MAX_LAG,
    AGG_GAUSSIANITY_HORIZONS,
    CROSS_BLOCK_STATS,
    PANEL_STATS,
    SINGLE_FACTOR_STATS,
    STRATEGY_STATS,
    VARIANCE_RATIO_HORIZONS,
)
from ah.factors import FactorManifest
from ah.splits import SPLITS

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PREREG_PATH = _REPO_ROOT / "pre-registration.yaml"

SCHEMA_VERSION = "1.0"

# The eight WP2.2 metric suites (STEP2-GENERATOR-PLAN Sec.WP2.2); only some exist yet
# (see `ah.eval.reference`'s module docstring), so a missing one is skipped rather than
# erroring -- this task's dry-run seal must not block on files WP2.2 hasn't written.
_METRIC_SUITE_NAMES = (
    "monthly",
    "horizon",
    "tails",
    "utility",
    "memorization",
    "economics",
    "conditional",
    "calibration",
)

# Every other module that can influence a pass/fail verdict (see the module docstring's
# "What the seal covers"). Unlike the metric suites these all exist today and are
# REQUIRED: a missing one means `_REPO_ROOT` is wrong or a judging module moved, and
# silently sealing without it is precisely the "seal appears stronger than it is"
# failure this list exists to prevent.
_REQUIRED_JUDGED_SOURCES = (
    ("src", "ah", "eval", "g2.py"),
    ("src", "ah", "eval", "reference.py"),
    ("src", "ah", "eval", "prereg.py"),
    ("src", "ah", "eval", "battery.py"),
    ("src", "ah", "eval", "panel.py"),
    ("src", "ah", "strategies.py"),
    ("src", "ah", "factors.py"),
    ("src", "ah", "splits.py"),
    ("src", "ah", "battery", "report.py"),
    ("src", "ah", "battery", "stylized.py"),
    # WP2.2 Task 3 fix pass 1 (Minor 1): the two ensemble pooling conventions, shared by
    # every metric suite. It sits under `eval/metrics/` but is not a suite, so
    # `_METRIC_SUITE_NAMES` does not reach it -- and it decides how an ensemble becomes
    # the flat series every sealed estimator is defined over, which moves every metric
    # value in the platform. Exactly the "helper module added beside the suites" case
    # the module docstring warns joins the seal only by being named.
    ("src", "ah", "eval", "metrics", "_pooling.py"),
    # WP2.2b Task 7: the negative-control suite. Judging code created outside
    # `src/ah/eval/metrics/`, so per the rule stated in the module docstring it joins
    # this list in the same commit that adds it. It is judging code in the strict sense
    # -- it defines what "the battery caught this control" MEANS (the substantive vs.
    # NaN-driven split, and the reference-band criterion the battery itself does not
    # apply), and `G2-EVIDENCE.md` cites its table as the record that the battery
    # detects badness at all. A version of that record produced by unsealed code would
    # be exactly the "seal appears stronger than it is" failure this list prevents.
    ("src", "ah", "eval", "negative_controls.py"),
    # WP2.3, closing governance/retrofit-register.md RFR-10's first half. `derive.py`
    # is ON THE READ PATH: `ah.eval.panel._DERIVED_EXPRS` calls `derive.add`,
    # `derive.difference` and `derive.funding_stress` at panel-read time for
    # `equity_mkt`, `ig_spread` and `funding_spread` respectively, so every band for
    # those three factors -- and every cross-block band involving them -- is a function
    # of these helper bodies, computed fresh on each read rather than stored in the
    # vintage. Sealing the BINDING (which helper, which units algebra) via `panel.py`
    # was not enough: an edit to `add`'s body would change what a sealed band is a band
    # OF, with no lock violation. RFR-10's other half, `ah/data/splice.py`, is
    # deliberately NOT here -- see `pre-registration.yaml`'s `seal_scope:` block for
    # the argument (its PROXY_RULES are registered but not applied by
    # `ah.data.refresh`, and `read_factor_frames` never calls it, so it cannot move a
    # band; what the frozen vintage contains is pinned by the sealed
    # `campaign_vintage_id`, not by that module).
    ("src", "ah", "data", "derive.py"),
)

# Sealed threshold DATA read by a sealed judging module. `ah/battery/report.py`
# (already sealed above) reads `ah/battery/thresholds.yaml` through `load_thresholds()`,
# so before WP2.3 a sealed estimator was defined over an unsealed input -- the exact
# failure mode `_REQUIRED_JUDGED_FIXTURE_GLOBS` was introduced to close for the
# authored conditional worlds. Every entry in it is `status: todo` and blocks nothing
# today; that makes sealing it cheap, not unnecessary.
_REQUIRED_JUDGED_DATA = (("src", "ah", "battery", "thresholds.yaml"),)

# Sealed input DATA (not code) that an estimator is defined over: `(directory parts,
# glob)` pairs. See the module docstring's "sealed input data an estimator is defined
# over". REQUIRED, like `_REQUIRED_JUDGED_SOURCES`: a glob matching nothing raises.
_REQUIRED_JUDGED_FIXTURE_GLOBS: tuple[tuple[tuple[str, ...], str], ...] = (
    # WP2.2 Task 6 fix pass 1 (Important 5): the authored condition-adherence worlds
    # `conventions.condition_adherence_*_estimator` pools over by name.
    (("fixtures", "worlds", "conditional"), "*.json"),
)


class PreRegError(RuntimeError):
    """Raised when a pre-registration fails to load, verify, or seal."""


# --------------------------------------------------------------------------- #
# public data types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Threshold:
    """One acceptance band: ``value in [min, max]`` (either bound may be absent)."""

    min: float | None
    max: float | None
    severity: str  # "enforce" | "report"


@dataclass(frozen=True)
class Decision:
    """One entry of ``pre-registration.yaml``'s ``decisions:`` block (Item 3, R5/J3)."""

    decision_id: str
    status: str
    consequence: str


@dataclass(frozen=True)
class PreRegistration:
    """The parsed ``pre-registration.yaml``.

    ``block_thresholds``, ``cross_block_thresholds`` and ``panel_thresholds`` are the
    structured, validated view of the ``thresholds:`` YAML block -- its ``blocks:``,
    ``cross_blocks:`` and ``panel:`` sections, keyed ``"<factor>.<stat>"``,
    ``"<factorA>~<factorB>.<stat>"`` and (for a whole-panel statistic that belongs to no
    factor or pair) a bare ``"<stat>"`` respectively. ``raw`` is the full parsed
    document (used by :func:`verify`'s ``conventions`` check, which this module
    implements independently of :mod:`ah.strategies` -- see the module docstring).

    ``source_path`` is the resolved path :func:`load` read this document from. It is
    what binds a :class:`PreRegistration` to a lock file: :func:`verify` requires the
    lock's ``prereg_path`` to name *this* document, so verifying pre-registration A
    against a lock sealed for B is rejected even when their contents happen to match.
    """

    sealed: bool
    active_blocks: tuple[str, ...]
    block_thresholds: Mapping[str, Mapping[str, Threshold]]
    cross_block_thresholds: Mapping[tuple[str, str], Mapping[str, Threshold]]
    decisions: Mapping[str, Decision]
    raw: Mapping[str, Any]
    source_path: Path
    panel_thresholds: Mapping[str, Threshold] = MappingProxyType({})
    # WP2.2 Task 4. The `thresholds.strategies` section: flat, keyed
    # `"<strategy_id>.<stat>"` (a D4 benchmark strategy from this same document's
    # `d4_strategies:` block, and a stat registered in
    # `ah.eval.reference.STRATEGY_STATS`). Flat like `panel_thresholds` -- there is no
    # per-strategy outer nesting -- but, unlike a panel key, DOES carry a dot, because
    # the axis (which strategy) has to be named somewhere and panel keys are reserved
    # for statistics that belong to no single strategy/factor/pair at all.
    strategy_thresholds: Mapping[str, Threshold] = MappingProxyType({})


@dataclass(frozen=True)
class Amendment:
    """One entry of ``governance/amendment-log.yaml``.

    ``type`` is one of :data:`AMENDMENT_TYPES`. ``date`` is supplied by the caller --
    never ``date.today()`` (the repo's no-clock-reads invariant; see
    ``ah.eval.prereg``'s callers, never this module, for where "today" would come
    from). ``payload`` carries type-specific data; for ``block_addition`` it is
    ``{"block": <id>, "block_thresholds": {...}, "cross_block_thresholds": {...}}``,
    each sub-mapping shaped like ``pre-registration.yaml``'s own ``thresholds.blocks.*``
    / ``thresholds.cross_blocks.*`` (see :func:`apply_block_addition`).
    """

    amendment_id: str
    type: str
    date: str
    rationale: str
    post_hoc: bool
    payload: Mapping[str, Any] = MappingProxyType({})


AMENDMENT_TYPES: frozenset[str] = frozenset(
    {"threshold_change", "protocol_change", "block_addition", "correction"}
)


# --------------------------------------------------------------------------- #
# small parsing helpers (shared by load() and apply_block_addition())
# --------------------------------------------------------------------------- #

_THRESHOLD_KEYS = frozenset({"min", "max", "severity"})
_DECISION_KEYS = frozenset({"status", "consequence"})
_AMENDMENT_KEYS = frozenset({"amendment_id", "type", "date", "rationale", "post_hoc", "payload"})
_REQUIRED_CONVENTIONS_KEYS = (
    "percent_to_decimal",
    "months_per_year",
    "return_bearing_factors",
    "level_factors",
    "rebalance_cadences",
    "static_weights_composition",
    # WP2.2 Task 1 fix pass, Critical 3: the sealed numeraire. Optional to
    # ah.strategies (fixtures predating it load with a permissive default) but
    # REQUIRED here, so the real sealed pre-registration can never silently drop the
    # one statement that stops an excess-return leg being weighted beside a
    # total-return leg.
    "numeraire",
    "numeraire_zero_cost_legs",
)


# Every registered statistic -> the `conventions.<key>` block in `pre-registration.yaml`
# that defines its estimator. WP2.2 Task 2 established the rule ("a band is meaningless
# without the estimator that produced it"); Task 3 registered eight statistics with no
# block at all, which is how a convention becomes forgettable. The mapping is explicit
# rather than derived from the statistic name because one block legitimately defines a
# family (`acf_estimator` covers 29 lag-indexed keys, `drawdown_episode_estimator`
# covers three summaries of one episode definition) -- a name-derived rule would either
# forbid that or accept anything.
#
# `tests/test_prereg.py::test_every_registered_statistic_has_an_estimator_definition` is
# the machine check, in both directions: every key of SINGLE_FACTOR_STATS /
# CROSS_BLOCK_STATS / PANEL_STATS must appear here, and every block named here must
# exist in the real pre-registration. It is a test rather than a `verify()` clause
# deliberately: `verify()` runs against synthetic, minimal pre-registrations all over
# the suite, and requiring twenty prose blocks of every fixture would buy nothing --
# the invariant is about the ONE real sealed document.
ESTIMATOR_CONVENTION_KEYS: Mapping[str, str] = MappingProxyType(
    {
        **{k: "elementary_moment_estimators" for k in ("mean", "std", "skew", "excess_kurtosis")},
        "correlation": "elementary_moment_estimators",
        "crisis_corr_lift": "crisis_corr_lift_estimator",
        **{f"acf_r_lag{lag}": "acf_estimator" for lag in range(1, ACF_R_MAX_LAG + 1)},
        **{f"acf_abs_lag{lag}": "acf_estimator" for lag in range(1, ACF_ABS_MAX_LAG + 1)},
        "acf_abs_decay": "acf_abs_decay_estimator",
        # WP2.2c Item 3: the joint (cumulative) ACF statistics, and the three
        # band-exceedance gates built over families of per-factor band comparisons.
        "acf_r_sum": "acf_sum_estimator",
        "acf_abs_sum": "acf_sum_estimator",
        "moment_band_exceedance_fraction": "band_exceedance_gate_estimator",
        "tail_band_exceedance_fraction": "band_exceedance_gate_estimator",
        "dependence_band_exceedance_fraction": "band_exceedance_gate_estimator",
        "hill_tail_index_5pct": "hill_tail_index_estimator",
        "hill_tail_index_1pct": "hill_tail_index_estimator",
        **{
            f"agg_gaussianity_{s}": "agg_gaussianity_estimator" for _, s in AGG_GAUSSIANITY_HORIZONS
        },
        "leverage_correlation": "leverage_correlation_estimator",
        "cross_block_corr_matrix_distance": "cross_block_corr_matrix_distance_estimator",
        **{f"variance_ratio_{s}": "variance_ratio_estimator" for _, s in VARIANCE_RATIO_HORIZONS},
        "mean_reversion_halflife": "mean_reversion_halflife_estimator",
        "drawdown_median_depth": "drawdown_episode_estimator",
        "drawdown_median_duration": "drawdown_episode_estimator",
        "drawdown_depth_duration_rank_corr": "drawdown_episode_estimator",
        "lost_decade_frequency": "lost_decade_frequency_estimator",
        "long_inflation_era_frequency": "long_inflation_era_frequency_estimator",
        "ergodicity_gap": "ergodicity_gap_estimator",
        "regime_duration_mean": "regime_duration_estimator",
        "regime_duration_p50": "regime_duration_estimator",
        "regime_duration_p90": "regime_duration_estimator",
        "ten_year_return_vs_valuation_slope": "ten_year_return_vs_valuation_estimator",
        "ten_year_return_vs_valuation_r2": "ten_year_return_vs_valuation_estimator",
        # WP2.2 Task 4.
        "tail_dependence_lower": "tail_dependence_estimator",
        "tail_dependence_upper": "tail_dependence_estimator",
        "discriminative_score": "discriminative_score_estimator",
        "predictive_score": "predictive_score_estimator",
        "tstr_degradation": "tstr_degradation_estimator",
        "var_95": "d4_var_es_estimator",
        "es_95": "d4_var_es_estimator",
        "var_99": "d4_var_es_estimator",
        "es_99": "d4_var_es_estimator",
        "elicitability_score": "elicitability_score_estimator",
        # WP2.2 Task 4 fix pass 2 (BLOCKING 1): renamed from `..._stat`/`..._pvalue` --
        # see ah.eval.reference.STRATEGY_STATS's identical comment.
        "kupiec_pof_lr_1path": "kupiec_pof_estimator",
        "kupiec_pof_chi2_tail_1path": "kupiec_pof_estimator",
        "christoffersen_independence_lr_1path": "christoffersen_independence_estimator",
        "christoffersen_independence_chi2_tail_1path": "christoffersen_independence_estimator",
        "christoffersen_conditional_coverage_lr_1path": "christoffersen_conditional_coverage_estimator",
        "christoffersen_conditional_coverage_chi2_tail_1path": (
            "christoffersen_conditional_coverage_estimator"
        ),
        # WP2.2 Task 5.
        "nn_distance_p05": "memorization_nn_distance_estimator",
        "nn_distance_p50": "memorization_nn_distance_estimator",
        "membership_inference_auc": "membership_inference_auc_estimator",
        "near_duplicate_fraction": "near_duplicate_fraction_estimator",
        "pit_ks_stat_1y": "pit_ks_stat_estimator",
        "pit_ks_stat_5y": "pit_ks_stat_estimator",
        "interval_coverage_50_1y": "interval_coverage_estimator",
        "interval_coverage_90_1y": "interval_coverage_estimator",
        "interval_coverage_50_5y": "interval_coverage_estimator",
        "interval_coverage_90_5y": "interval_coverage_estimator",
        **{f"implied_sharpe_{r}": "implied_sharpe_estimator" for r in REGIME_LABELS},
        "term_premium": "term_premium_estimator",
        "equity_risk_premium": "equity_risk_premium_estimator",
        "money_pump_violations": "money_pump_estimator",
        "floor_violations": "floor_violations_estimator",
        "policy_anchor_deviation": "policy_anchor_deviation_estimator",
        # WP2.2 Task 6. One convention key per condition type, covering its {mean, p90}
        # pair -- the same "one family, one key" shape acf_estimator (many lags) and
        # drawdown_episode_estimator (three summaries of one episode definition) already
        # use, since p90 is a sub-variant of the same per-path error definition, not an
        # independent estimator.
        "condition_adherence_error_inflation": "condition_adherence_inflation_estimator",
        "condition_adherence_error_p90_inflation": "condition_adherence_inflation_estimator",
        "condition_adherence_error_rate": "condition_adherence_rate_estimator",
        "condition_adherence_error_p90_rate": "condition_adherence_rate_estimator",
        "condition_adherence_error_crisis_timing": "condition_adherence_crisis_timing_estimator",
        "condition_adherence_error_p90_crisis_timing": "condition_adherence_crisis_timing_estimator",
        "condition_adherence_error_crisis_severity": "condition_adherence_crisis_severity_estimator",
        "condition_adherence_error_p90_crisis_severity": "condition_adherence_crisis_severity_estimator",
        # One shared key for all eight off-support names -- a single estimator family
        # parameterized by level, the same shape variance_ratio_estimator covers four
        # horizons with.
        "off_support_adherence_at_typical": "off_support_estimator",
        "off_support_adherence_at_p95": "off_support_estimator",
        "off_support_adherence_at_p99": "off_support_estimator",
        "off_support_adherence_at_beyond": "off_support_estimator",
        "off_support_pass_rate_at_typical": "off_support_estimator",
        "off_support_pass_rate_at_p95": "off_support_estimator",
        "off_support_pass_rate_at_p99": "off_support_estimator",
        "off_support_pass_rate_at_beyond": "off_support_estimator",
    }
)


def missing_estimator_definitions(prereg: PreRegistration) -> tuple[str, ...]:
    """Registered statistics whose estimator definition is missing from ``prereg``.

    Two failure modes, both reported: a statistic absent from
    :data:`ESTIMATOR_CONVENTION_KEYS` entirely (nobody said which block defines it), and
    one whose named block is absent from the document's ``conventions:``. Returned
    sorted, as ``"<stat>"`` / ``"<stat> -> <missing conventions key>"``.
    """
    conventions = prereg.raw.get("conventions")
    present = set(conventions) if isinstance(conventions, dict) else set()
    missing: list[str] = []
    for stat in sorted({*SINGLE_FACTOR_STATS, *CROSS_BLOCK_STATS, *PANEL_STATS, *STRATEGY_STATS}):
        key = ESTIMATOR_CONVENTION_KEYS.get(stat)
        if key is None:
            missing.append(stat)
        elif key not in present:
            missing.append(f"{stat} -> {key}")
    return tuple(missing)


def _require_mapping(value: object, what: str, source: Path) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise PreRegError(f"{source}: {what} must be a mapping, got {type(value).__name__}")
    return value


def _parse_optional_number(value: object, what: str, source: Path) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreRegError(f"{source}: {what} must be numeric or null, got {value!r}")
    return float(value)


def _parse_threshold_map(raw: object, what: str, source: Path) -> dict[str, Threshold]:
    raw_map = _require_mapping(raw, what, source)
    out: dict[str, Threshold] = {}
    for key, entry in raw_map.items():
        if not isinstance(key, str) or not key:
            raise PreRegError(f"{source}: {what} has a non-string/empty key {key!r}")
        entry_map = _require_mapping(entry, f"{what}.{key}", source)
        unknown = sorted(k for k in entry_map if k not in _THRESHOLD_KEYS)
        if unknown:
            raise PreRegError(f"{source}: {what}.{key} has unknown key(s) {unknown}")
        min_v = _parse_optional_number(entry_map.get("min"), f"{what}.{key}.min", source)
        max_v = _parse_optional_number(entry_map.get("max"), f"{what}.{key}.max", source)
        severity = entry_map.get("severity")
        if not isinstance(severity, str) or not severity:
            raise PreRegError(f"{source}: {what}.{key}.severity must be a non-empty string")
        out[key] = Threshold(min=min_v, max=max_v, severity=severity)
    return out


def _parse_pair_key(key: object, source: Path) -> tuple[str, str]:
    if not isinstance(key, str) or key.count("|") != 1:
        raise PreRegError(f"{source}: cross-block key {key!r} must be 'blockA|blockB'")
    parts = key.split("|")
    if not all(parts):
        raise PreRegError(f"{source}: cross-block key {key!r} must name two non-empty blocks")
    a, b = sorted(parts)
    return (a, b)


def _parse_decision(raw: object, decision_id: object, source: Path) -> Decision:
    if not isinstance(decision_id, str) or not decision_id:
        raise PreRegError(f"{source}: decisions has a non-string/empty id {decision_id!r}")
    entry_map = _require_mapping(raw, f"decisions.{decision_id}", source)
    unknown = sorted(k for k in entry_map if k not in _DECISION_KEYS)
    if unknown:
        raise PreRegError(f"{source}: decisions.{decision_id} has unknown key(s) {unknown}")
    status = entry_map.get("status")
    consequence = entry_map.get("consequence")
    if not isinstance(status, str) or not status:
        raise PreRegError(f"{source}: decisions.{decision_id}.status must be a non-empty string")
    if not isinstance(consequence, str) or not consequence:
        raise PreRegError(
            f"{source}: decisions.{decision_id}.consequence must be a non-empty string"
        )
    return Decision(decision_id=decision_id, status=status, consequence=consequence)


def _require_string_tuple(value: object, what: str, source: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise PreRegError(f"{source}: '{what}' must be a non-empty list of non-empty strings")
    return tuple(value)


# --------------------------------------------------------------------------- #
# load()
# --------------------------------------------------------------------------- #


def load(path: Path | None = None) -> PreRegistration:
    """Parse ``pre-registration.yaml`` (defaulting to the repo root) into a :class:`PreRegistration`.

    Structural validation only -- consistency against a :class:`~ah.factors.FactorManifest`
    (block/pair coverage, the ``conventions`` closure) is :func:`verify`'s job, not
    this function's, so a caller can load a pre-registration and choose which
    manifest to verify it against (e.g. the post-``block_addition`` manifest).
    """
    resolved = (path if path is not None else _DEFAULT_PREREG_PATH).resolve()
    if not resolved.exists():
        raise PreRegError(f"{resolved}: not found")
    doc = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise PreRegError(f"{resolved}: top level must be a mapping")

    sealed = doc.get("sealed", False)
    if not isinstance(sealed, bool):
        raise PreRegError(f"{resolved}: 'sealed' must be a boolean, got {sealed!r}")

    active_blocks = _require_string_tuple(doc.get("active_blocks"), "active_blocks", resolved)

    thresholds_doc = doc.get("thresholds") or {}
    if not isinstance(thresholds_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds' must be a mapping")

    blocks_doc = thresholds_doc.get("blocks") or {}
    if not isinstance(blocks_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds.blocks' must be a mapping")
    block_thresholds: dict[str, Mapping[str, Threshold]] = {}
    for block_id, entries in blocks_doc.items():
        if not isinstance(block_id, str) or not block_id:
            raise PreRegError(
                f"{resolved}: thresholds.blocks has a non-string/empty key {block_id!r}"
            )
        block_thresholds[block_id] = MappingProxyType(
            _parse_threshold_map(entries, f"thresholds.blocks.{block_id}", resolved)
        )

    cross_doc = thresholds_doc.get("cross_blocks") or {}
    if not isinstance(cross_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds.cross_blocks' must be a mapping")
    cross_block_thresholds: dict[tuple[str, str], Mapping[str, Threshold]] = {}
    for pair_key, entries in cross_doc.items():
        pair = _parse_pair_key(pair_key, resolved)
        cross_block_thresholds[pair] = MappingProxyType(
            _parse_threshold_map(entries, f"thresholds.cross_blocks.{pair_key}", resolved)
        )

    panel_doc = thresholds_doc.get("panel") or {}
    if not isinstance(panel_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds.panel' must be a mapping")
    panel_thresholds = _parse_threshold_map(panel_doc, "thresholds.panel", resolved)

    strategies_doc = thresholds_doc.get("strategies") or {}
    if not isinstance(strategies_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds.strategies' must be a mapping")
    strategy_thresholds = _parse_threshold_map(strategies_doc, "thresholds.strategies", resolved)

    decisions_doc = doc.get("decisions") or {}
    if not isinstance(decisions_doc, dict):
        raise PreRegError(f"{resolved}: 'decisions' must be a mapping")
    decisions: dict[str, Decision] = {
        decision_id: _parse_decision(entry, decision_id, resolved)
        for decision_id, entry in decisions_doc.items()
    }

    return PreRegistration(
        sealed=sealed,
        active_blocks=active_blocks,
        block_thresholds=MappingProxyType(block_thresholds),
        cross_block_thresholds=MappingProxyType(cross_block_thresholds),
        decisions=MappingProxyType(decisions),
        raw=MappingProxyType(doc),
        source_path=resolved,
        panel_thresholds=MappingProxyType(panel_thresholds),
        strategy_thresholds=MappingProxyType(strategy_thresholds),
    )


# --------------------------------------------------------------------------- #
# verify()
# --------------------------------------------------------------------------- #


def _check_string_set_field(
    conventions: Mapping[str, Any], key: str, errors: list[str]
) -> set[str] | None:
    """Validate ``conventions[key]`` exactly as :func:`ah.strategies._require_string_set`
    would: a non-empty list of distinct, non-empty strings.

    Mirrors that function's three rejection modes -- empty (or missing/non-list),
    non-string entries, and duplicate entries -- so :func:`verify` never green-lights a
    file :func:`ah.strategies.load_conventions` would raise on (see the module
    docstring's "The hole this task closes"). Returns the field as a ``set[str]`` when
    valid; returns ``None`` and appends to ``errors`` otherwise, naming the offending
    key and value(s).
    """
    value = conventions.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"conventions.{key} must be a non-empty list of strings, got {value!r}")
        return None
    non_strings = sorted({repr(v) for v in value if not isinstance(v, str) or not v})
    if non_strings:
        errors.append(f"conventions.{key} has non-string/empty entry(ies) {non_strings}")
        return None
    seen: set[str] = set()
    duplicates: set[str] = set()
    for entry in value:
        if entry in seen:
            duplicates.add(entry)
        seen.add(entry)
    if duplicates:
        errors.append(f"conventions.{key} lists {sorted(duplicates)} more than once")
        return None
    return set(value)


def _check_conventions(raw: Mapping[str, Any], manifest: FactorManifest, errors: list[str]) -> None:
    """The hole-closing check -- see the module docstring."""
    conventions = raw.get("conventions")
    if not isinstance(conventions, dict):
        errors.append("pre-registration is missing the 'conventions' block")
        return

    missing_keys = sorted(k for k in _REQUIRED_CONVENTIONS_KEYS if k not in conventions)
    if missing_keys:
        errors.append(f"conventions block is missing required key(s) {missing_keys}")

    rb_set = _check_string_set_field(conventions, "return_bearing_factors", errors)
    lv_set = _check_string_set_field(conventions, "level_factors", errors)
    if rb_set is None or lv_set is None:
        return

    overlap = sorted(rb_set & lv_set)
    if overlap:
        errors.append(
            f"conventions.return_bearing_factors and conventions.level_factors both "
            f"classify {overlap}; a factor must be exactly one"
        )
    active = set(manifest.active_factors())
    classified = rb_set | lv_set
    unclassified = sorted(active - classified)
    if unclassified:
        errors.append(
            f"conventions does not classify active factor(s) {unclassified} as "
            f"return_bearing_factors or level_factors"
        )
    # ah.strategies._validate_conventions' own rule: the classification must cover
    # exactly the active factor set, no more. Kept identical here so verify() can never
    # pass a file load_conventions() would raise on (see the module docstring).
    non_active = sorted(classified - active)
    if non_active:
        errors.append(
            f"conventions classifies non-active factor(s) {non_active}; "
            f"return_bearing_factors and level_factors must cover exactly the active "
            f"factor set, no more"
        )


def _check_threshold_sanity(th: Threshold, label: str, errors: list[str]) -> None:
    if th.severity not in ("enforce", "report"):
        errors.append(f"{label}: severity must be 'enforce' or 'report', got {th.severity!r}")
    if th.min is not None and th.max is not None and th.min > th.max:
        errors.append(f"{label}: min ({th.min}) > max ({th.max})")


def _check_block_threshold_key(
    key: str, block: str, manifest: FactorManifest, errors: list[str]
) -> None:
    """A per-block threshold key must be ``"<factor>.<stat>"`` and must judge something.

    ``pre-registration.yaml`` states this naming rule; without the check a sealed
    ``enforce`` threshold can name a statistic nothing computes -- a threshold that
    judges nothing, silently, forever. ``<factor>`` must belong to *this* block (that is
    how :func:`ah.eval.reference.compute_reference` keys it) and ``<stat>`` must be a
    registered :data:`~ah.eval.reference.SINGLE_FACTOR_STATS` entry.
    """
    label = f"thresholds.blocks.{block}.{key!r}"
    if key.count(".") != 1 or "~" in key:
        errors.append(
            f"{label}: a per-block threshold key must be '<factor>.<stat>' "
            f"(exactly one '.', no '~')"
        )
        return
    factor, stat = key.split(".")
    if factor not in manifest.blocks[block]:
        errors.append(
            f"{label}: factor '{factor}' does not belong to block '{block}', so no "
            f"reference statistic is computed under this key"
        )
    if stat not in SINGLE_FACTOR_STATS:
        errors.append(
            f"{label}: '{stat}' is not a registered single-factor statistic; known: "
            f"{sorted(SINGLE_FACTOR_STATS)}"
        )


def _check_cross_block_threshold_key(
    key: str, pair: tuple[str, str], manifest: FactorManifest, errors: list[str]
) -> None:
    """A cross-block key must be ``"<factorA>~<factorB>.<stat>"``, A from ``pair[0]``.

    The pair key is sorted and :func:`ah.eval.reference.compute_reference` keys
    ``"<factor from pair[0]>~<factor from pair[1]>.<stat>"``, so the reversed form names
    a statistic nothing computes.
    """
    label = f"thresholds.cross_blocks.{pair[0]}|{pair[1]}.{key!r}"
    if key.count("~") != 1 or key.count(".") != 1 or key.index("~") > key.index("."):
        errors.append(
            f"{label}: a cross-block threshold key must be '<factorA>~<factorB>.<stat>' "
            f"(exactly one '~', then exactly one '.')"
        )
        return
    factors, stat = key.split(".")
    factor_a, factor_b = factors.split("~")
    if factor_a not in manifest.blocks[pair[0]] or factor_b not in manifest.blocks[pair[1]]:
        errors.append(
            f"{label}: '{factor_a}~{factor_b}' is not a factor of block '{pair[0]}' "
            f"paired with a factor of block '{pair[1]}' (the pair key is sorted, and the "
            f"factor order must follow it), so no reference statistic is computed under "
            f"this key"
        )
    if stat not in CROSS_BLOCK_STATS:
        errors.append(
            f"{label}: '{stat}' is not a registered cross-block statistic; known: "
            f"{sorted(CROSS_BLOCK_STATS)}"
        )


def _check_panel_threshold_key(key: str, errors: list[str]) -> None:
    """A panel threshold key must be a bare registered whole-panel statistic name.

    A whole-panel statistic (:data:`~ah.eval.reference.PANEL_STATS`) is a property of
    the entire factor panel and belongs to no single factor or pair, so -- unlike the
    other two sections -- its key carries no ``"<factor>."`` or ``"<factorA>~<factorB>."``
    prefix. Accepting a prefixed key here would seal a threshold under a name nothing
    computes, which is the same silent failure ``_check_block_threshold_key`` exists to
    stop.
    """
    label = f"thresholds.panel.{key!r}"
    if "." in key or "~" in key:
        errors.append(
            f"{label}: a panel threshold key must be a bare '<stat>' name (a whole-panel "
            f"statistic belongs to no factor or pair, so no '.' or '~' prefix is valid)"
        )
        return
    if key not in PANEL_STATS:
        errors.append(
            f"{label}: '{key}' is not a registered panel statistic; known: {sorted(PANEL_STATS)}"
        )


def _check_strategy_threshold_key(key: str, raw: Mapping[str, Any], errors: list[str]) -> None:
    """A strategy threshold key must be ``"<strategy_id>.<stat>"``, strategy_id sealed here.

    ``strategy_id`` is looked up in THIS document's own ``d4_strategies:`` block
    (``prereg.raw``), never via :func:`ah.strategies.load_d4_strategies` -- that
    function always reads the real repo-root ``pre-registration.yaml`` regardless of
    which document is being verified, which would silently pass a threshold naming a
    strategy that exists only in the real file while verifying an unrelated (e.g. test
    fixture) document, or reject a strategy that genuinely is declared in the document
    under test. Reading ``prereg.raw`` directly is the same choice
    :func:`_check_conventions` already makes, for the identical reason (see the module
    docstring's "The hole this task closes").
    """
    label = f"thresholds.strategies.{key!r}"
    if key.count(".") != 1 or "~" in key:
        errors.append(
            f"{label}: a strategy threshold key must be '<strategy_id>.<stat>' "
            f"(exactly one '.', no '~')"
        )
        return
    strategy_id, stat = key.split(".")
    d4_strategies = raw.get("d4_strategies")
    known_strategies = set(d4_strategies) if isinstance(d4_strategies, dict) else set()
    if strategy_id not in known_strategies:
        errors.append(
            f"{label}: '{strategy_id}' is not a d4_strategies entry in this document; "
            f"known: {sorted(known_strategies)}"
        )
    if stat not in STRATEGY_STATS:
        errors.append(
            f"{label}: '{stat}' is not a registered strategy statistic; known: "
            f"{sorted(STRATEGY_STATS)}"
        )


def _stat_of(key: str) -> str:
    """The statistic name a threshold key ends in.

    ``"equity_mkt.skew"`` -> ``"skew"``; ``"a~b.correlation"`` -> ``"correlation"``;
    a bare panel key is its own statistic. Key SHAPE is validated by the four
    ``_check_*_threshold_key`` functions above; this one only splits, so a malformed
    key reaches it harmlessly (it is reported by those checks, not by this one).
    """
    return key.rsplit(".", 1)[-1]


def _factors_of(key: str) -> tuple[str, ...]:
    """The factor id(s) a block/cross-block threshold key is keyed to (``()`` for others)."""
    if "." not in key:
        return ()
    head = key.rsplit(".", 1)[0]
    if "~" in head:
        return tuple(head.split("~"))
    return (head,)


def _check_splits(raw: Mapping[str, Any], errors: list[str]) -> None:
    """The sealed ``splits:`` block must equal :data:`ah.splits.SPLITS`, exactly.

    ``governance/retrofit-register.md`` RFR-6. ``ah/splits.py`` is inside the seal, so
    a change to a boundary already invalidates the lock -- but a lock violation says
    "some hashed file changed", not "the reference span moved". This check makes the
    two representations of the same fact, the sealed document and the code, provably
    identical: the document is the normative statement (the seal's self-containment
    rule), and the code is checked against it, never the other way round.
    """
    splits_doc = raw.get("splits")
    if not isinstance(splits_doc, dict):
        errors.append(
            "pre-registration is missing the 'splits' block (the sealed train/"
            "validation/holdout boundaries -- see governance/retrofit-register.md RFR-6)"
        )
        return
    expected = {name: {"start": split.start, "end": split.end} for name, split in SPLITS.items()}
    declared = {
        name: {
            "start": entry.get("start"),
            "end": entry.get("end"),
        }
        for name, entry in splits_doc.items()
        if isinstance(entry, dict)
    }
    if declared != expected:
        errors.append(
            f"splits block {declared} does not match ah.splits.SPLITS {expected}; the "
            f"sealed span boundaries and the code that reads them must be identical "
            f"(the sealed document is normative)"
        )


def _check_structurally_unavailable(
    prereg: PreRegistration, raw: Mapping[str, Any], errors: list[str]
) -> None:
    """No ``enforce`` threshold may name a ``structurally_unavailable`` statistic.

    Such a statistic is NaN on every ensemble, always, until a missing input exists
    (see :data:`ah.eval.battery.STRUCTURALLY_UNAVAILABLE`), and under THE ONE NaN RULE
    a NaN ``enforce`` metric FAILS -- so an ``enforce`` band on one of these names
    fails **every run forever**, which reads in the artifact as a real generator defect
    rather than as a platform gap. Before WP2.3 the status was *visible* on the metric
    but not *enforced* on the threshold; this closes that.

    The list is read from the sealed document itself (``structurally_unavailable_
    statistics:``) rather than imported from :mod:`ah.eval.battery`, for two reasons:
    the suites cannot be imported here (they import :mod:`ah.eval.battery`, which
    imports this module), and the sealed file must be reconstructible on its own -- a
    reader must be able to see which names were known-unavailable at seal time without
    running the code. ``tests/test_prereg.py`` asserts the sealed list equals the set a
    real suite registration actually marks, in both directions.
    """
    entries = raw.get("structurally_unavailable_statistics")
    if not isinstance(entries, dict) or not entries:
        errors.append(
            "pre-registration is missing a non-empty 'structurally_unavailable_"
            "statistics' block; without it an enforce threshold could be sealed on a "
            "statistic that is NaN on every ensemble forever"
        )
        return
    unavailable = set(entries)
    labelled: list[tuple[str, str]] = []
    for block, block_entries in prereg.block_thresholds.items():
        labelled += [(f"thresholds.blocks.{block}.{k}", k) for k in block_entries]
    for pair, pair_entries in prereg.cross_block_thresholds.items():
        labelled += [(f"thresholds.cross_blocks.{pair[0]}|{pair[1]}.{k}", k) for k in pair_entries]
    labelled += [(f"thresholds.panel.{k}", k) for k in prereg.panel_thresholds]
    labelled += [(f"thresholds.strategies.{k}", k) for k in prereg.strategy_thresholds]
    for label, key in labelled:
        threshold = _lookup_any(prereg, key)
        if threshold is None or threshold.severity != "enforce":
            continue
        if _stat_of(key) in unavailable:
            errors.append(
                f"{label}: severity 'enforce' on statistic '{_stat_of(key)}', which "
                f"this document declares structurally_unavailable -- a NaN enforce "
                f"metric fails every run forever (THE ONE NaN RULE). Seal it 'report' "
                f"or omit it."
            )


def _lookup_any(prereg: PreRegistration, key: str) -> Threshold | None:
    for entries in prereg.block_thresholds.values():
        if key in entries:
            return entries[key]
    for entries in prereg.cross_block_thresholds.values():
        if key in entries:
            return entries[key]
    if key in prereg.panel_thresholds:
        return prereg.panel_thresholds[key]
    return prereg.strategy_thresholds.get(key)


def _check_threshold_data_availability(
    prereg: PreRegistration, raw: Mapping[str, Any], errors: list[str]
) -> None:
    """No threshold may be keyed to a factor (or D4 strategy) with no computable statistic.

    ``governance/retrofit-register.md`` RFR-5: :func:`verify` already checks that a key
    names a real factor of the right block and a registered statistic, but not that the
    factor has *data*. On the sealed campaign vintage three active factors have none
    (``commodities`` is declared unavailable; ``policy_rate`` and ``hy_spread`` have no
    train+validation observations), so a threshold keyed to one of them judges nothing
    -- silently, forever -- exactly the failure the key checks exist to stop.

    The unavailable sets are read from the sealed ``reference_run:`` block (the run that
    produced every band in this file), not recomputed: the check must hold in a checkout
    with no catalog, and the sealed document must be self-contained.
    """
    run = raw.get("reference_run")
    if not isinstance(run, dict):
        errors.append(
            "pre-registration is missing the 'reference_run' block (the run every "
            "sealed band was derived from)"
        )
        return
    missing_raw = run.get("missing_factors")
    missing = set(missing_raw) if isinstance(missing_raw, list) else set()
    uncomputable_raw = run.get("uncomputable_d4_strategies")
    uncomputable = set(uncomputable_raw) if isinstance(uncomputable_raw, list) else set()

    for block, entries in prereg.block_thresholds.items():
        for key in entries:
            hit = sorted(set(_factors_of(key)) & missing)
            if hit:
                errors.append(
                    f"thresholds.blocks.{block}.{key!r}: factor(s) {hit} have no "
                    f"computable reference statistic on the sealed campaign vintage "
                    f"(reference_run.missing_factors), so this threshold judges nothing"
                )
    for pair, entries in prereg.cross_block_thresholds.items():
        for key in entries:
            hit = sorted(set(_factors_of(key)) & missing)
            if hit:
                errors.append(
                    f"thresholds.cross_blocks.{pair[0]}|{pair[1]}.{key!r}: factor(s) "
                    f"{hit} have no computable reference statistic on the sealed "
                    f"campaign vintage (reference_run.missing_factors)"
                )
    for key in prereg.strategy_thresholds:
        strategy_id = key.rsplit(".", 1)[0]
        if strategy_id in uncomputable:
            errors.append(
                f"thresholds.strategies.{key!r}: D4 strategy '{strategy_id}' has at "
                f"least one leg with no data on the sealed campaign vintage "
                f"(reference_run.uncomputable_d4_strategies), so this threshold judges "
                f"nothing"
            )


def _check_ensemble_size(
    raw: Mapping[str, Any],
    n_paths: int | None,
    months: int | None,
    errors: list[str],
) -> None:
    """The sealed ``ensemble_size:`` block, and (when given) the run's own size.

    The acceptance bands in this file are the sampling distribution of a statistic on
    ONE length-matched series, while the ensemble side reports an average over
    ``n_paths`` paths. The direction is conservative -- the ensemble estimator is
    tighter than the band's null, so the bound is safe at any size -- but the gates'
    POWER rises without limit in ``n_paths``, so ``max: 0.5`` calibrated at one
    ensemble size is not the same criterion at another. The size is therefore sealed,
    and a criterion-bearing run at a different size needs a dated amendment.
    """
    size = raw.get("ensemble_size")
    if not isinstance(size, dict):
        errors.append(
            "pre-registration is missing the 'ensemble_size' block (the sealed "
            "n_paths/months the gate bounds are calibrated at)"
        )
        return
    sealed_paths = size.get("n_paths")
    sealed_months = size.get("months")
    if not isinstance(sealed_paths, int) or isinstance(sealed_paths, bool) or sealed_paths < 1:
        errors.append(f"ensemble_size.n_paths must be a positive integer, got {sealed_paths!r}")
        return
    if not isinstance(sealed_months, int) or isinstance(sealed_months, bool) or sealed_months < 1:
        errors.append(f"ensemble_size.months must be a positive integer, got {sealed_months!r}")
        return
    if n_paths is not None and n_paths != sealed_paths:
        errors.append(
            f"ensemble has {n_paths} paths but the sealed criterion size is "
            f"{sealed_paths}; the gate bounds are calibrated at the sealed size and "
            f"mean something different at any other, so a criterion-bearing run at "
            f"{n_paths} paths requires a dated amendment"
        )
    if months is not None and months != sealed_months:
        errors.append(
            f"ensemble paths are {months} months but the sealed criterion length is "
            f"{sealed_months}; every length-matched band in this file was drawn at "
            f"{sealed_months}"
        )


def _canonical_key(resolved: Path, doc_root: Path) -> str:
    """The path's stable, checkout-independent identity: a relative posix path.

    Tried against the repository root first (where judged *code* lives) and then
    ``doc_root`` (where the sealed *documents* live -- the pre-registration's own
    directory at seal time, the lock's at verify time). Forward slashes, so a lock
    sealed on Windows verifies on Linux. A path under neither root cannot be
    independently verified from the lock alone, and is a :class:`PreRegError`.
    """
    for root in (_REPO_ROOT, doc_root):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    raise PreRegError(
        f"{resolved}: cannot be sealed -- it lies under neither the repository root "
        f"({_REPO_ROOT}) nor the pre-registration's own directory ({doc_root}), so a "
        f"lock recording it could not be verified in another checkout"
    )


def _resolve_key(key: str, doc_root: Path) -> Path | None:
    """Inverse of :func:`_canonical_key`: the first existing candidate, or ``None``.

    ``doc_root`` is tried *first* here (the reverse of :func:`_canonical_key`'s order)
    so that a lock sitting beside the documents it sealed always re-reads those
    documents rather than same-named files at the repository root. In the real layout
    the two roots are identical, so the order is immaterial there.
    """
    for root in (doc_root, _REPO_ROOT):
        candidate = root / key
        if candidate.exists():
            return candidate
    return None


def _read_text(path: Path) -> str:
    """``path.read_text('utf-8')``, with any failure named as a :class:`PreRegError`."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PreRegError(f"{path}: could not read as UTF-8 text ({exc})") from exc


def _hash_files(paths: Iterable[Path], *, doc_root: Path) -> tuple[str, list[str]]:
    """Canonical SHA-256 over the current text content of every path in ``paths``.

    Reuses :func:`ah.core.digest.canonical_json` for the serialization (sorted keys,
    compact, deterministic) and ``hashlib.sha256`` for the digest itself -- the same
    primitive :func:`ah.core.digest.sha256_of_arrays` wraps, so this is not a second
    hashing scheme, just that module's canonicalize-then-hash pattern applied to file
    text instead of float arrays (``digest.py`` has no generic text-file hasher to
    call directly).

    The canonical-JSON keys are :func:`_canonical_key` paths -- **relative**, so the
    digest is a function of file content and repo-relative identity only, never of
    where the checkout happens to live. Returns ``(digest, sorted_relative_keys)``;
    the key list is sorted, so hashing is independent of the order ``paths`` was
    given in.
    """
    keyed: dict[str, Path] = {}
    for raw_path in paths:
        resolved = Path(raw_path).resolve()
        key = _canonical_key(resolved, doc_root)
        previous = keyed.get(key)
        if previous is not None and previous != resolved:
            raise PreRegError(
                f"two different files claim the same sealed identity '{key}': "
                f"{previous} and {resolved}"
            )
        keyed[key] = resolved
    contents = {key: _read_text(keyed[key]) for key in sorted(keyed)}
    digest_hex = (
        "sha256:" + hashlib.sha256(canonical_json({"files": contents}).encode("utf-8")).hexdigest()
    )
    return digest_hex, sorted(keyed)


def _verify_lock(lock_path: Path, prereg: PreRegistration, errors: list[str]) -> None:
    doc_root = lock_path.resolve().parent
    try:
        lock_doc = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{lock_path}: could not read/parse lock file ({exc})")
        return
    if not isinstance(lock_doc, dict):
        errors.append(f"{lock_path}: lock file must contain a JSON object")
        return
    hashed_files = lock_doc.get("hashed_files")
    stored_digest = lock_doc.get("digest")
    stored_prereg_path = lock_doc.get("prereg_path")
    if (
        not isinstance(hashed_files, list)
        or not isinstance(stored_digest, str)
        or not isinstance(stored_prereg_path, str)
    ):
        errors.append(
            f"{lock_path}: malformed lock file (missing 'hashed_files', 'digest' or 'prereg_path')"
        )
        return

    # Bind the lock to *this* pre-registration: without it, verifying document A
    # against a lock sealed for document B passes whenever their contents match.
    try:
        own_key = _canonical_key(prereg.source_path, doc_root)
    except PreRegError as exc:
        errors.append(str(exc))
        return
    if own_key != stored_prereg_path:
        errors.append(
            f"{lock_path}: sealed for pre-registration '{stored_prereg_path}', but was "
            f"asked to verify '{own_key}' ({prereg.source_path})"
        )
        return
    if stored_prereg_path not in hashed_files:
        errors.append(
            f"{lock_path}: sealed pre-registration '{stored_prereg_path}' is not in the "
            f"lock's own hashed_files -- the document it judges was never hashed"
        )
        return

    resolved: list[Path] = []
    missing: list[str] = []
    for key in hashed_files:
        candidate = _resolve_key(str(key), doc_root)
        if candidate is None:
            missing.append(str(key))
        else:
            resolved.append(candidate)
    if missing:
        errors.append(f"{lock_path}: hashed file(s) no longer exist: {missing}")
        return
    try:
        recomputed_digest, _ = _hash_files(resolved, doc_root=doc_root)
    except PreRegError as exc:
        errors.append(str(exc))
        return
    if recomputed_digest != stored_digest:
        errors.append(
            f"{lock_path}: recomputed digest {recomputed_digest} does not match sealed "
            f"digest {stored_digest} -- a hashed file changed since sealing"
        )


def verify(
    prereg: PreRegistration,
    manifest: FactorManifest,
    *,
    lock_path: Path | None = None,
    ensemble_n_paths: int | None = None,
    ensemble_months: int | None = None,
) -> None:
    """Check ``prereg`` against ``manifest``; raise :class:`PreRegError` listing every failure.

    Checks (Instructions/WP2.1b-PRE-SEAL-PATCH.md Item 2, plus the conventions closure
    documented in this module's docstring):

    - ``schema_version`` is :data:`SCHEMA_VERSION`, and the ``decisions`` block is
      present (a misspelled ``decisons:`` would otherwise drop R5 and J3 from the
      sealed file with no error);
    - the ``conventions`` block is present and complete, and
      ``return_bearing_factors``/``level_factors`` together classify exactly the
      active factor set (none missing, none doubled, none extra);
    - ``prereg.active_blocks == manifest.active_blocks``;
    - every active block has a ``thresholds.blocks`` entry, and no entry names an
      inactive block;
    - every ``manifest.cross_block_pairs()`` pair has a ``thresholds.cross_blocks``
      entry, and no entry names an inactive block;
    - every threshold *key* is well formed and judges something real:
      ``"<factor>.<stat>"`` with the factor in that block and the stat registered in
      :data:`~ah.eval.reference.SINGLE_FACTOR_STATS`, and
      ``"<factorA>~<factorB>.<stat>"`` with the factors drawn in order from the pair's
      two blocks and the stat in :data:`~ah.eval.reference.CROSS_BLOCK_STATS`, a
      bare ``"<stat>"`` under ``thresholds.panel`` registered in
      :data:`~ah.eval.reference.PANEL_STATS`, and (WP2.2 Task 4)
      ``"<strategy_id>.<stat>"`` under ``thresholds.strategies`` with the strategy id a
      ``d4_strategies`` entry of *this same document* and the stat registered in
      :data:`~ah.eval.reference.STRATEGY_STATS`;
    - every threshold's ``severity`` is ``enforce``/``report``, and ``min <= max``
      when both are given;
    - if ``lock_path`` is given and exists, the lock was sealed for *this*
      pre-registration (``prereg.source_path``) and the digest recomputed from its
      ``hashed_files`` (read fresh from disk) matches the digest it recorded.

    **Sealed-document checks (WP2.3), applied only when ``prereg.sealed``.** A draft
    need not carry the full sealed apparatus -- the synthetic, minimal
    pre-registrations this project's tests verify all over the suite would otherwise
    have to grow four prose blocks each to buy nothing -- but a document claiming
    ``sealed: true`` must:

    - carry a ``splits:`` block equal to :data:`ah.splits.SPLITS` (RFR-6);
    - carry a ``reference_run:`` block, and seal no threshold keyed to a factor listed
      in its ``missing_factors`` or a D4 strategy listed in its
      ``uncomputable_d4_strategies`` (RFR-5);
    - carry a ``structurally_unavailable_statistics:`` block, and seal no ``enforce``
      threshold on any statistic named in it (a NaN ``enforce`` metric fails every run
      forever);
    - carry an ``ensemble_size:`` block naming the ``n_paths``/``months`` the gate
      bounds are calibrated at.

    ``ensemble_n_paths``/``ensemble_months``, when given, are checked against that
    sealed size. They are optional because a diagnostic or negative-control run at a
    small ensemble is legitimate and must not be blocked; what must not happen is a
    *criterion-bearing* run at an unsealed size, which is why
    :attr:`ah.eval.battery.BatteryReport.criterion_bearing` records the comparison on
    every report and ``ah/eval/g2.py`` is where the hard gate belongs.

    Every failure is collected and reported together -- no section returns early on
    another section's fault.
    """
    errors: list[str] = []

    schema_version = prereg.raw.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got {schema_version!r}; this is "
            f"a versioned document and an unrecognized version is not silently readable"
        )
    if "decisions" not in prereg.raw:
        errors.append(
            "pre-registration is missing the 'decisions' block (a misspelling such as "
            "'decisons:' would silently drop the sealed Item-3 decisions)"
        )

    _check_conventions(prereg.raw, manifest, errors)

    if prereg.active_blocks != manifest.active_blocks:
        errors.append(
            f"prereg.active_blocks {prereg.active_blocks} != "
            f"manifest.active_blocks {manifest.active_blocks}"
        )

    for block in manifest.active_blocks:
        if block not in prereg.block_thresholds:
            errors.append(f"active block '{block}' has no thresholds.blocks entry")
    for block in prereg.block_thresholds:
        if not manifest.is_active(block):
            errors.append(f"thresholds.blocks references inactive block '{block}'")

    active_pairs = set(manifest.cross_block_pairs())
    for pair in active_pairs:
        if pair not in prereg.cross_block_thresholds:
            errors.append(f"active cross-block pair {pair} has no thresholds.cross_blocks entry")
    for pair in prereg.cross_block_thresholds:
        block_a, block_b = pair
        if not (manifest.is_active(block_a) and manifest.is_active(block_b)):
            errors.append(f"thresholds.cross_blocks references inactive block in pair {pair}")

    for block, entries in prereg.block_thresholds.items():
        block_is_active = manifest.is_active(block)
        for key, th in entries.items():
            _check_threshold_sanity(th, f"thresholds.blocks.{block}.{key}", errors)
            # Key validity is only meaningful against a block the manifest declares as
            # active; an inactive/unknown block is already reported above.
            if block_is_active:
                _check_block_threshold_key(key, block, manifest, errors)
    for pair, entries in prereg.cross_block_thresholds.items():
        pair_is_active = manifest.is_active(pair[0]) and manifest.is_active(pair[1])
        for key, th in entries.items():
            _check_threshold_sanity(
                th, f"thresholds.cross_blocks.{pair[0]}|{pair[1]}.{key}", errors
            )
            if pair_is_active:
                _check_cross_block_threshold_key(key, pair, manifest, errors)
    for key, th in prereg.panel_thresholds.items():
        _check_threshold_sanity(th, f"thresholds.panel.{key}", errors)
        _check_panel_threshold_key(key, errors)
    for key, th in prereg.strategy_thresholds.items():
        _check_threshold_sanity(th, f"thresholds.strategies.{key}", errors)
        _check_strategy_threshold_key(key, prereg.raw, errors)

    if prereg.sealed:
        _check_splits(prereg.raw, errors)
        _check_threshold_data_availability(prereg, prereg.raw, errors)
        _check_structurally_unavailable(prereg, prereg.raw, errors)
        _check_ensemble_size(prereg.raw, ensemble_n_paths, ensemble_months, errors)

    if lock_path is not None and lock_path.exists():
        _verify_lock(lock_path, prereg, errors)

    if errors:
        raise PreRegError(
            "pre-registration verification failed:\n" + "\n".join(f"- {e}" for e in errors)
        )


# --------------------------------------------------------------------------- #
# seal()
# --------------------------------------------------------------------------- #


def _default_judged_sources() -> tuple[Path, ...]:
    """Every module that can influence a pass/fail verdict -- see the module docstring.

    Resolved lazily (called from :func:`seal`, not at import time) against *this
    repository's* real code -- fixed regardless of which
    ``pre-registration.yaml``/``factors.yaml`` pair is being sealed, because "the code
    that judges the thresholds" is a property of the codebase, not of a particular
    fixture.

    The WP2.2 metric suites mostly don't exist yet, so a missing one is skipped rather
    than erroring. :data:`_REQUIRED_JUDGED_SOURCES` and
    :data:`_REQUIRED_JUDGED_FIXTURE_GLOBS` are the opposite: every one of those files
    exists today, and a missing one raises :class:`PreRegError` rather than quietly
    shrinking the seal.
    """
    metric_suites = [
        _REPO_ROOT / "src" / "ah" / "eval" / "metrics" / f"{name}.py"
        for name in _METRIC_SUITE_NAMES
    ]
    required = [
        _REPO_ROOT.joinpath(*parts) for parts in (*_REQUIRED_JUDGED_SOURCES, *_REQUIRED_JUDGED_DATA)
    ]
    absent = [str(p) for p in required if not p.exists()]
    if absent:
        raise PreRegError(
            f"judged source(s) missing from the repository: {absent}. The seal covers "
            f"every module that can influence a pass/fail verdict; sealing without one "
            f"would silently weaken the guarantee. If a judging module moved, update "
            f"ah.eval.prereg._REQUIRED_JUDGED_SOURCES."
        )

    fixture_data: list[Path] = []
    for parts, pattern in _REQUIRED_JUDGED_FIXTURE_GLOBS:
        directory = _REPO_ROOT.joinpath(*parts)
        # Sorted, so the seal is independent of filesystem iteration order (the digest
        # itself re-sorts by canonical key, but the returned tuple is also read by tests
        # and by anyone auditing what was hashed).
        matches = sorted(p for p in directory.glob(pattern) if p.is_file())
        if not matches:
            raise PreRegError(
                f"sealed input data missing from the repository: no file matches "
                f"'{pattern}' under {directory}. A sealed estimator is defined by name "
                f"over these documents (see ah.eval.prereg's module docstring); sealing "
                f"without them would leave the estimator unreconstructible from the "
                f"sealed set. If the data moved, update "
                f"ah.eval.prereg._REQUIRED_JUDGED_FIXTURE_GLOBS."
            )
        fixture_data.extend(matches)

    return tuple([*(p for p in metric_suites if p.exists()), *required, *fixture_data])


def seal(
    prereg_path: Path,
    *,
    out_path: Path | None = None,
    judged_sources: Iterable[Path] | None = None,
    sealed_at: str,
    dry_run: bool = False,
) -> str:
    """Compute the pre-registration digest and, unless ``dry_run``, write ``out_path``.

    ``out_path`` is required for a real seal and must be omitted (or ``None``) for a
    ``dry_run``, which writes nothing: a caller computing a digest for a report header
    should not have to invent a filename that is never created.

    Hashes, canonically (:func:`_hash_files`): the ``prereg_path`` YAML bytes, the
    ``factors.yaml`` bytes it references (its ``factor_manifest`` field, resolved
    relative to ``prereg_path``'s directory), and the source text of every file in
    ``judged_sources`` (defaulting to :func:`_default_judged_sources`, resolved lazily
    so files WP2.2 hasn't added yet are silently skipped rather than erroring).

    ``sealed_at`` is a required, caller-supplied string -- never read from the clock
    (the repo's no-time-based-defaults invariant); it is recorded in the lock file but
    plays no part in the digest itself, so sealing the same inputs at two different
    ``sealed_at`` values gives the same digest (verified by
    ``tests/test_prereg.py::test_seal_is_deterministic``).

    The lock file, written only when ``dry_run`` is false, is JSON:
    ``{"digest": ..., "hashed_files": [...], "prereg_path": ..., "sealed_at": ...}``.
    ``hashed_files`` is every file that went into the digest, as **relative,
    forward-slashed** paths (see the module docstring's "Independent verifiability"),
    so a reader -- and :func:`verify`, in any checkout on any OS -- sees exactly what
    was hashed without re-deriving the default list. ``prereg_path`` is the entry among
    them that is the sealed document itself, which is what binds the lock to one
    pre-registration.
    """
    prereg_path = Path(prereg_path)
    if not prereg_path.exists():
        raise PreRegError(f"{prereg_path}: not found")
    doc = yaml.safe_load(prereg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise PreRegError(f"{prereg_path}: top level must be a mapping")
    manifest_name = doc.get("factor_manifest", "factors.yaml")
    if not isinstance(manifest_name, str) or not manifest_name:
        raise PreRegError(f"{prereg_path}: 'factor_manifest' must be a non-empty string")
    factors_path = (prereg_path.parent / manifest_name).resolve()
    if not factors_path.exists():
        raise PreRegError(
            f"{prereg_path}: factor_manifest '{manifest_name}' resolves to missing "
            f"file {factors_path}"
        )

    resolved_judged = (
        tuple(judged_sources) if judged_sources is not None else _default_judged_sources()
    )
    resolved_prereg = prereg_path.resolve()
    doc_root = resolved_prereg.parent
    all_paths = [resolved_prereg, factors_path, *(Path(p) for p in resolved_judged)]
    digest, hashed_files = _hash_files(all_paths, doc_root=doc_root)

    if not dry_run:
        if out_path is None:
            raise PreRegError("seal(): out_path is required unless dry_run=True")
        lock_doc = {
            "digest": digest,
            "hashed_files": hashed_files,
            "prereg_path": _canonical_key(resolved_prereg, doc_root),
            "sealed_at": sealed_at,
        }
        Path(out_path).write_text(
            json.dumps(lock_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return digest


# --------------------------------------------------------------------------- #
# amendment log
# --------------------------------------------------------------------------- #


def _parse_amendment(entry: object, source: Path) -> Amendment:
    entry_map = _require_mapping(entry, "amendment entry", source)
    unknown = sorted(k for k in entry_map if k not in _AMENDMENT_KEYS)
    if unknown:
        raise PreRegError(f"{source}: amendment has unknown key(s) {unknown}")

    amendment_id = entry_map.get("amendment_id")
    amendment_type = entry_map.get("type")
    date = entry_map.get("date")
    rationale = entry_map.get("rationale")
    post_hoc = entry_map.get("post_hoc")
    raw_payload = entry_map.get("payload") or {}

    if not isinstance(amendment_id, str) or not amendment_id:
        raise PreRegError(f"{source}: amendment 'amendment_id' must be a non-empty string")
    if amendment_type not in AMENDMENT_TYPES:
        raise PreRegError(
            f"{source}: amendment '{amendment_id}' type must be one of "
            f"{sorted(AMENDMENT_TYPES)}, got {amendment_type!r}"
        )
    if not isinstance(date, str) or not date:
        raise PreRegError(f"{source}: amendment '{amendment_id}' 'date' must be a non-empty string")
    if not isinstance(rationale, str) or not rationale:
        raise PreRegError(
            f"{source}: amendment '{amendment_id}' 'rationale' must be a non-empty string"
        )
    if not isinstance(post_hoc, bool):
        raise PreRegError(f"{source}: amendment '{amendment_id}' 'post_hoc' must be a boolean")
    if not isinstance(raw_payload, dict):
        raise PreRegError(f"{source}: amendment '{amendment_id}' 'payload' must be a mapping")

    return Amendment(
        amendment_id=amendment_id,
        type=amendment_type,
        date=date,
        rationale=rationale,
        post_hoc=post_hoc,
        payload=MappingProxyType(dict(raw_payload)),
    )


def load_amendments(path: Path) -> tuple[Amendment, ...]:
    """Parse every entry of ``governance/amendment-log.yaml`` (or ``path``), in file order."""
    path = Path(path)
    if not path.exists():
        raise PreRegError(f"{path}: not found")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise PreRegError(f"{path}: top level must be a mapping")
    raw_list = doc.get("amendments") or []
    if not isinstance(raw_list, list):
        raise PreRegError(f"{path}: 'amendments' must be a list")

    amendments: list[Amendment] = []
    seen_ids: set[str] = set()
    for entry in raw_list:
        amendment = _parse_amendment(entry, path)
        if amendment.amendment_id in seen_ids:
            raise PreRegError(f"{path}: duplicate amendment_id '{amendment.amendment_id}'")
        seen_ids.add(amendment.amendment_id)
        amendments.append(amendment)
    return tuple(amendments)


def _validate_amendment_for_append(path: Path, amendment: Amendment) -> None:
    """Reject anything :func:`load_amendments` would reject, *before* it is written.

    The log is append-only, so a bad entry is permanent: writing an unknown ``type`` or
    a duplicate ``amendment_id`` produces a log that :func:`load_amendments` then
    refuses forever. Validation therefore happens at write time; the load-time checks
    stay as defence in depth (they also cover logs edited by hand).
    """
    if not isinstance(amendment.amendment_id, str) or not amendment.amendment_id:
        raise PreRegError(f"{path}: amendment 'amendment_id' must be a non-empty string")
    if amendment.type not in AMENDMENT_TYPES:
        raise PreRegError(
            f"{path}: amendment '{amendment.amendment_id}' type must be one of "
            f"{sorted(AMENDMENT_TYPES)}, got {amendment.type!r}"
        )
    if not isinstance(amendment.date, str) or not amendment.date:
        raise PreRegError(
            f"{path}: amendment '{amendment.amendment_id}' 'date' must be a non-empty string"
        )
    if not isinstance(amendment.rationale, str) or not amendment.rationale:
        raise PreRegError(
            f"{path}: amendment '{amendment.amendment_id}' 'rationale' must be a non-empty string"
        )
    if not isinstance(amendment.post_hoc, bool):
        raise PreRegError(
            f"{path}: amendment '{amendment.amendment_id}' 'post_hoc' must be a boolean, "
            f"got {amendment.post_hoc!r}"
        )
    existing = {a.amendment_id for a in load_amendments(path)}
    if amendment.amendment_id in existing:
        raise PreRegError(
            f"{path}: amendment_id '{amendment.amendment_id}' is already in the log; ids "
            f"must be unique and the log is append-only, so a duplicate could never be "
            f"removed"
        )


def append_amendment(path: Path, amendment: Amendment) -> None:
    """Append ``amendment`` to the log at ``path``, which must already exist.

    Append-only by construction: this opens ``path`` in file-append mode ('a') and
    writes only the new entry's bytes, so every byte already on disk is untouched --
    not merely unchanged in content, but literally never written to again. The new
    entry is one YAML block-sequence item (``yaml.safe_dump`` on a one-element list),
    valid appended directly after the log's ``amendments:`` key (a YAML block sequence
    may start at the same indentation as its parent key) or after a prior entry.

    Because those bytes can never be taken back, the entry is validated *first*
    (:func:`_validate_amendment_for_append`) and nothing is written if it fails.
    """
    path = Path(path)
    if not path.exists():
        raise PreRegError(f"{path}: not found; create the amendment log before appending to it")
    _validate_amendment_for_append(path, amendment)

    entry: dict[str, Any] = {
        "amendment_id": amendment.amendment_id,
        "type": amendment.type,
        "date": amendment.date,
        "rationale": amendment.rationale,
        "post_hoc": amendment.post_hoc,
    }
    if amendment.payload:
        entry["payload"] = dict(amendment.payload)

    block = yaml.safe_dump([entry], default_flow_style=False, sort_keys=True, allow_unicode=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(block)


# --------------------------------------------------------------------------- #
# apply_block_addition()
# --------------------------------------------------------------------------- #


def apply_block_addition(
    prereg: PreRegistration, manifest_after: FactorManifest, amendment: Amendment
) -> PreRegistration:
    """Merge a ``block_addition`` amendment's new thresholds into ``prereg``.

    ``block_addition`` is additive by construction (see
    ``governance/amendment-log.yaml``'s header): it requires new per-block thresholds
    for exactly one newly-active block, plus new cross-block joint thresholds for
    every pair that block forms with each of ``prereg``'s pre-existing active blocks
    -- both supplied on ``amendment.payload`` (``"block"``, ``"block_thresholds"``,
    ``"cross_block_thresholds"``, shaped like ``pre-registration.yaml``'s own
    ``thresholds.blocks.*`` / ``thresholds.cross_blocks.*``). It does **not**
    invalidate any pre-existing block's or pair's thresholds: every value already in
    ``prereg.block_thresholds`` / ``prereg.cross_block_thresholds`` is carried over by
    reference (the same :class:`Threshold` objects, not rebuilt), so it is provably
    byte-identical -- via canonical-JSON serialization -- before and after, which is
    the patch's acceptance criterion for a block addition. This is why a block
    addition is not a re-seal.

    ``manifest_after`` must be exactly ``prereg``'s active blocks plus the one new
    block (i.e. the manifest state *after* activating it); the new cross-block pairs
    required are computed from ``manifest_after.cross_block_pairs()``, filtered to
    pairs containing the new block -- ``FactorManifest.cross_block_pairs()``
    deliberately covers only active blocks, and in ``manifest_after`` the new block
    *is* active, so this is already the correct set without widening that method.

    **Thresholds only.** The ``conventions`` block is carried over untouched: the
    amendment payload has no room for it, and the new block's factors must be
    classified as return-bearing or level in ``pre-registration.yaml`` itself, by hand,
    as part of the same amendment. :func:`verify` will reject the merged result until
    that edit lands (the new block's factors are active and unclassified) -- which is
    the correct outcome, not a gap: a block addition that forgot to declare its
    factors' units would otherwise seal a set of thresholds over series whose units
    nothing states.

    Returns a new :class:`PreRegistration` (``prereg`` is not mutated) whose
    ``active_blocks`` is ``manifest_after.active_blocks``, and whose ``source_path``
    is ``prereg``'s (the merge is in-memory; no new document was read).
    """
    if amendment.type != "block_addition":
        raise PreRegError(
            f"apply_block_addition requires an amendment of type 'block_addition', "
            f"got '{amendment.type}'"
        )
    src = Path(f"<amendment {amendment.amendment_id}>")

    new_block = amendment.payload.get("block")
    if not isinstance(new_block, str) or not new_block:
        raise PreRegError(f"{src}: payload.block must be a non-empty string")
    if new_block in prereg.active_blocks:
        raise PreRegError(f"{src}: block '{new_block}' is already active in the pre-registration")
    if not manifest_after.is_active(new_block):
        raise PreRegError(f"{src}: block '{new_block}' is not active in manifest_after")
    expected_active = set(prereg.active_blocks) | {new_block}
    if set(manifest_after.active_blocks) != expected_active:
        raise PreRegError(
            f"{src}: manifest_after.active_blocks {manifest_after.active_blocks} must "
            f"equal prereg.active_blocks {prereg.active_blocks} plus exactly the new "
            f"block '{new_block}'"
        )

    raw_block_thresholds = amendment.payload.get("block_thresholds")
    if not isinstance(raw_block_thresholds, dict) or not raw_block_thresholds:
        raise PreRegError(f"{src}: payload.block_thresholds must be a non-empty mapping")
    new_block_thresholds = MappingProxyType(
        _parse_threshold_map(raw_block_thresholds, "payload.block_thresholds", src)
    )

    raw_cross_thresholds = amendment.payload.get("cross_block_thresholds")
    if not isinstance(raw_cross_thresholds, dict):
        raise PreRegError(f"{src}: payload.cross_block_thresholds must be a mapping")
    parsed_cross: dict[tuple[str, str], Mapping[str, Threshold]] = {}
    for pair_key, entries in raw_cross_thresholds.items():
        pair = _parse_pair_key(pair_key, src)
        parsed_cross[pair] = MappingProxyType(
            _parse_threshold_map(entries, f"payload.cross_block_thresholds.{pair_key}", src)
        )

    expected_new_pairs = {p for p in manifest_after.cross_block_pairs() if new_block in p}
    missing_pairs = expected_new_pairs - set(parsed_cross)
    if missing_pairs:
        raise PreRegError(
            f"{src}: missing cross-block thresholds for new pair(s) {sorted(missing_pairs)}"
        )
    extra_pairs = set(parsed_cross) - expected_new_pairs
    if extra_pairs:
        raise PreRegError(
            f"{src}: declares cross-block threshold(s) for pair(s) {sorted(extra_pairs)} "
            f"that are not a new pair formed by block '{new_block}'"
        )

    merged_block_thresholds = dict(prereg.block_thresholds)
    merged_block_thresholds[new_block] = new_block_thresholds

    merged_cross_thresholds = dict(prereg.cross_block_thresholds)
    merged_cross_thresholds.update(parsed_cross)

    new_raw = dict(prereg.raw)
    new_raw["active_blocks"] = list(manifest_after.active_blocks)

    return PreRegistration(
        sealed=prereg.sealed,
        active_blocks=manifest_after.active_blocks,
        block_thresholds=MappingProxyType(merged_block_thresholds),
        cross_block_thresholds=MappingProxyType(merged_cross_thresholds),
        decisions=prereg.decisions,
        raw=MappingProxyType(new_raw),
        source_path=prereg.source_path,
        # Panel and strategy statistics are not block-scoped, so a block addition
        # neither adds to nor invalidates them: carried over by reference, provably
        # byte-identical.
        panel_thresholds=prereg.panel_thresholds,
        strategy_thresholds=prereg.strategy_thresholds,
    )
