"""The sleeve-level tail battery — G3-pre's judged code (wp3-00, DN-5 §7 option 1).

Judges GENERATED sleeve returns (WP3.2's mappings applied to ensembles) against
tail thresholds authored from history. Everything here COMPOSES sealed Step-2
machinery rather than restating it — the ``g2.py`` pattern: two implementations
of one sealed inequality is two things that can disagree.

* Tail estimators: :func:`ah.eval.metrics.tails.var_es` (sealed).
* Bands: :func:`ah.eval.reference.block_bootstrap_band` (sealed), length-matched
  to the judged 120-month sleeve paths.
* Reference surface: :meth:`ah.splits.DataAccess.train_val` — the holdout is
  structurally unreachable from this module.

The reference composite for a modeled sleeve (owner decision, 2026-08-01:
**per modeled sleeve**, pooling member series) is the equal-weight monthly mean
over the sleeve's member sub-strategy series (taxonomy mapping, pinned
version), each member **de-smoothed** (GLM MA(k), the D1 primary) on its
train+validation span before pooling — generated sleeve returns are true
returns, so the reference must be on the true-return scale.

This module becomes sealed when ``pre-registration-g3.lock`` is minted; until
then it is draft judged code awaiting the W11 pre-seal review.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.desmooth import glm_ma
from ah.data.taxonomy import load_taxonomy
from ah.eval.metrics.tails import var_es
from ah.eval.reference import block_bootstrap_band
from ah.splits import DataAccess

__all__ = [
    "BAND_BLOCK_LENGTH",
    "BAND_N_RESAMPLES",
    "BAND_SEED_BASE",
    "JUDGED_MONTHS",
    "K_HALF_WIDTHS",
    "STATISTICS",
    "SleeveBand",
    "SleeveTailsError",
    "hf_sleeve_members",
    "judge_sleeve",
    "reference_composite",
    "sleeve_bands",
]

#: Length-matching: replicates carry the judged path length (120 months), so a
#: length-sensitive tail estimator sees the same sample size on both sides —
#: the WP2.2 convention, reused verbatim.
JUDGED_MONTHS = 120
BAND_N_RESAMPLES = 1000
BAND_BLOCK_LENGTH = 24
#: The central percentile mass of the replicate band (0.95 -> [2.5, 97.5]),
#: passed to the sealed band machinery verbatim.
BAND_LEVEL = 0.95
#: Per-sleeve seeds are BAND_SEED_BASE + a stable offset from the sleeve id, so
#: adding a sleeve never re-rolls another sleeve's band (the 7919 discipline).
BAND_SEED_BASE = 20260801
#: Threshold width: band midpoint +/- K half-widths — the same K = 4 the owner
#: ratified for D6 (decision register, 2026-07-31).
K_HALF_WIDTHS = 4.0

#: The judged statistics. `enforce` on the 95-family (the core tail claim, well
#: estimated at 120 months); `report` on the 99-family (six-ish tail points per
#: replicate — too noisy to gate on honestly). Rationale travels to the seal.
STATISTICS: tuple[tuple[str, float, str], ...] = (
    ("var_95", 0.95, "enforce"),
    ("es_95", 0.95, "enforce"),
    ("var_99", 0.99, "report"),
    ("es_99", 0.99, "report"),
)


class SleeveTailsError(RuntimeError):
    """A sleeve, member set, or judged array that violates the G3-pre contract."""


def hf_sleeve_members() -> dict[str, tuple[str, ...]]:
    """Modeled HF sleeve -> its member series ids, from the pinned taxonomy.

    Only sleeves that are BOTH modeled-in-v1 AND fed by at least one delivered
    ``albourne.hf_*`` series appear — on taxonomy-v1.1 that is the seven HF
    group sleeves. PM sleeves are structurally unavailable (no COMM delivery)
    and are named as such in the seal document, never silently absent here.
    """
    taxonomy = load_taxonomy()
    members: dict[str, list[str]] = {}
    for series_id, sleeve_id in taxonomy.series_to_sleeve.items():
        if series_id.startswith("albourne.hf_"):
            members.setdefault(sleeve_id, []).append(series_id)
    return {
        sleeve_id: tuple(sorted(ids))
        for sleeve_id, ids in sorted(members.items())
        if taxonomy.sleeve(sleeve_id).modeled_in_v1
    }


#: Sleeve groups whose marks move on an APPRAISAL CALENDAR rather than by
#: return smoothing. DN-5 §5.2's two-mechanism table, verbatim: "Return
#: smoothing (GLM) | HF sleeves, private credit"; "Appraisal lag (Geltner) |
#: Real estate, infrastructure | AR(1) partial adjustment on *levels*, tied to
#: a valuation calendar". Keyed by GROUP, not by sleeve id, so the rule is
#: DN-5's sentence rather than a hand-maintained list. DN-5's own warning for
#: getting this wrong: "applying one form to all sleeves ... produces real
#: estate that reacts a quarter too fast."
GELTNER_GROUPS: frozenset[str] = frozenset({"pm_re", "pm_infra"})


def smoothing_family(sleeve_id: str) -> str:
    """``"geltner"`` for appraisal-calendar sleeves, ``"glm"`` otherwise (DN-5 §5.2)."""
    return "geltner" if load_taxonomy().sleeve(sleeve_id).group in GELTNER_GROUPS else "glm"


def pm_sleeve_members() -> dict[str, tuple[str, ...]]:
    """Modeled PM sleeve -> its member series ids, from the pinned taxonomy.

    The private-markets sibling of :func:`hf_sleeve_members`, added 2026-08-08
    when the first PriMaRS delivery landed and made these sleeves estimable.

    DELIBERATELY SEPARATE rather than a generalization of ``hf_sleeve_members``.
    That function's result defines the G3 document's ``sleeve_tail_thresholds``
    key set (``tests/test_g3seal.py`` asserts the two agree), so widening it
    would pull PM sleeves into the sealed JUDGED set and require tail
    thresholds invented after their data was in hand -- the post-hoc move the
    pre-registration discipline exists to prevent. PM tail thresholds need
    their own pre-registration, before anyone looks. This function feeds
    ESTIMATION (the smoothing kernel, the factor->sleeve mappings), never
    judgement.
    """
    taxonomy = load_taxonomy()
    members: dict[str, list[str]] = {}
    for series_id, sleeve_id in taxonomy.series_to_sleeve.items():
        if series_id.startswith("albourne.pm_"):
            members.setdefault(sleeve_id, []).append(series_id)
    return {
        sleeve_id: tuple(sorted(ids))
        for sleeve_id, ids in sorted(members.items())
        if taxonomy.sleeve(sleeve_id).modeled_in_v1
    }


def reference_composite(access: DataAccess, member_ids: tuple[str, ...]) -> np.ndarray:
    """The sleeve's reference series: equal-weight mean of de-smoothed members.

    Each member is read through ``access.train_val`` (holdout excluded by
    construction), de-smoothed with the D1 primary (GLM MA(k)) over its own
    span, then averaged per month over the members present that month
    (min one). Returned as a 1-D float array in month order.
    """
    if not member_ids:
        raise SleeveTailsError("a sleeve with no member series cannot have a reference")
    per_member: list[pd.Series] = []
    for series_id in member_ids:
        frame = access.train_val(series_id)
        if frame.empty:
            raise SleeveTailsError(
                f"{series_id}: no train+validation observations — a member with no "
                "history cannot enter the composite silently"
            )
        truth = glm_ma(pd.to_numeric(frame["value"]).to_numpy(dtype=float)).truth
        per_member.append(pd.Series(truth, index=pd.to_datetime(frame["date"])))
    panel = pd.concat(per_member, axis=1)
    composite = panel.mean(axis=1, skipna=True)  # equal-weight over present members
    return composite.sort_index().to_numpy(dtype=float)


@dataclass(frozen=True)
class SleeveBand:
    sleeve_id: str
    statistic: str
    severity: str
    point: float  # the statistic on the full composite
    lo: float  # replicate band, 2.5th percentile
    hi: float  # replicate band, 97.5th percentile
    threshold_min: float  # midpoint - K * half_width
    threshold_max: float  # midpoint + K * half_width


def _stat_fn(level: float, which: str) -> Callable[[np.ndarray], float]:
    def fn(panel: np.ndarray) -> float:
        returns = panel[:, 0] if panel.ndim == 2 else panel
        var, es = var_es(returns, level)
        return float(var if which == "var" else es)

    return fn


def _sleeve_seed(sleeve_id: str) -> int:
    # Stable, content-derived offset: adding/removing one sleeve never re-rolls
    # another's band. Not a hash of anything mutable.
    offset = sum(ord(c) for c in sleeve_id)
    return BAND_SEED_BASE + 7919 * offset


def sleeve_bands(sleeve_id: str, composite: np.ndarray) -> list[SleeveBand]:
    """Bands + thresholds for one sleeve, via the sealed band machinery."""
    if composite.ndim != 1 or composite.size <= BAND_BLOCK_LENGTH:
        raise SleeveTailsError(
            f"{sleeve_id}: composite must be 1-D and longer than the block length "
            f"({BAND_BLOCK_LENGTH}); got shape {composite.shape}"
        )
    panel = composite[:, None]
    bands: list[SleeveBand] = []
    for name, level, severity in STATISTICS:
        which = name.split("_", 1)[0]
        fn = _stat_fn(level, which)
        band = block_bootstrap_band(
            fn,
            panel,
            seed=_sleeve_seed(sleeve_id),
            n_resamples=BAND_N_RESAMPLES,
            level=BAND_LEVEL,
            block_length=BAND_BLOCK_LENGTH,
            resample_length=JUDGED_MONTHS,
            context=f"sleevetails:{sleeve_id}:{name}",
        )
        lo, hi = float(band.lo), float(band.hi)
        midpoint = (lo + hi) / 2.0
        half = (hi - lo) / 2.0
        bands.append(
            SleeveBand(
                sleeve_id=sleeve_id,
                statistic=name,
                severity=severity,
                point=float(band.point),
                lo=lo,
                hi=hi,
                threshold_min=float(midpoint - K_HALF_WIDTHS * half),
                threshold_max=float(midpoint + K_HALF_WIDTHS * half),
            )
        )
    return bands


def judge_sleeve(
    sleeve_id: str, generated: np.ndarray, bands: list[SleeveBand]
) -> dict[str, object]:
    """Judge one sleeve's generated returns against its sealed bands.

    ``generated`` is ``(n_paths, months)`` of TRUE sleeve returns (WP3.2's
    mapping output). Per statistic: the mean over paths of the per-path
    statistic must sit inside ``[threshold_min, threshold_max]``. A NaN
    statistic on either side is a failure at enforce severity, never a pass —
    the anti-gaming rule, unchanged from Step 2.
    """
    if generated.ndim != 2:
        raise SleeveTailsError(
            f"{sleeve_id}: generated returns must be (n_paths, months); got {generated.shape}"
        )
    results = []
    all_enforce_ok = True
    for band in bands:
        which, level = band.statistic.split("_", 1)
        # A path carrying any non-finite value scores NaN directly — the sealed
        # estimator is never handed NaN input (its NaN quantile would produce an
        # empty tail slice), and a NaN per-path statistic makes the sleeve fail
        # below: the anti-gaming rule, absence never scores better than presence.
        per_path = np.array(
            [
                (
                    float(var_es(generated[i], float(level) / 100.0)[0 if which == "var" else 1])
                    if np.all(np.isfinite(generated[i]))
                    else np.nan
                )
                for i in range(generated.shape[0])
            ]
        )
        value = float(np.mean(per_path))
        inside = bool(band.threshold_min <= value <= band.threshold_max)
        ok = inside and np.isfinite(value)
        if band.severity == "enforce" and not ok:
            all_enforce_ok = False
        results.append(
            {
                "statistic": band.statistic,
                "severity": band.severity,
                "value": value,
                "threshold_min": band.threshold_min,
                "threshold_max": band.threshold_max,
                "ok": ok,
            }
        )
    return {"sleeve_id": sleeve_id, "results": results, "enforce_passed": all_enforce_ok}
