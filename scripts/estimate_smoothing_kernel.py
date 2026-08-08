"""Estimate the forward-smoothing kernel (WP3.3) and write its frozen artifact.

Run:  uv run python scripts/estimate_smoothing_kernel.py

SM-10's consistency requirement, implemented: the forward smoother applied to a
sleeve must be the exact inverse of that sleeve's de-smoother, so ``reported``
and ``true`` are ONE model seen two ways. Per modeled HF sleeve, θ comes from
the D1 primary (GLM MA(k)) fitted on the sleeve's RAW reported composite,
train+validation only. Two families per DN-5 §5.2:

* ``glm`` — HF sleeves (and private credit when it exists): MA(k) on returns.
  Parameterized here from delivered data.
* ``geltner`` — real estate / infrastructure: AR(1) partial adjustment on
  LEVELS tied to a valuation calendar. **PARAMETERIZED 2026-08-08**, when the
  first PriMaRS delivery fired the trigger this script recorded while PM was
  undelivered. ``desmooth.geltner_ar1`` implements the partial-adjustment model
  in return space (differencing the level recursion gives
  ``r*_t = (r_t - phi*r_{t-1}) / (1 - phi)``), so no level series is
  constructed; the observation frequency IS the valuation calendar, and PM
  marks are quarterly.

Sleeve -> family routing is ``sleevetails.smoothing_family``, keyed by taxonomy
GROUP so it encodes DN-5 §5.2's sentence rather than a hand-kept list.

FREQUENCY DEVIATION, recorded (DN-5 SM-11 asks for one stickiness scalar per
family): the PM glm sleeves are fitted and reported but do NOT enter the glm
stickiness pool, because a quarterly MA weight is not commensurable with a
monthly one and pooling them would silently move an already-sealed number. The
glm stickiness therefore stays monthly-HF-pooled and BYTE-IDENTICAL to the
sealed value; the geltner scalar is pooled over the quarterly PM sleeves only.
Deviation is in the seal's favour.

State-dependent stickiness (DN-5 §5.3): one scalar per family. Calibrated on
the IN-SAMPLE stress episodes (NBER recession months per fred.USREC — 2008-09
and 2020 on this panel), DELIBERATELY NOT on 2021-23 as DN-5 suggests: 2021+
is the holdout span AND 2022 is the sealed judging episode; calibrating
stickiness there would gut the sealed mark_lag criterion. Recorded deviation.
Mechanism measured: refit θ on stress months vs calm months; stickiness
``s = max(0, 1 - θ0_stress / θ0_calm)`` pooled across sleeves (a lower θ0 in
stress = more weight on lagged truth = stickier marks).

Output: ``mappings/smoothing-kernel-v1.0.yaml``. Deterministic, no RNG.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.data.desmooth import DesmoothResult, geltner_ar1, glm_ma
from ah.eval.sleevetails import hf_sleeve_members, pm_sleeve_members, smoothing_family
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]
KERNEL_VERSION = "smooth-2026.08"


def _raw_composite(access: DataAccess, members: tuple[str, ...]) -> pd.Series:
    cols = []
    for sid in members:
        frame = access.train_val(sid)
        cols.append(
            pd.Series(
                pd.to_numeric(frame["value"]).to_numpy(dtype=float),
                index=pd.to_datetime(frame["date"]),
            )
        )
    return pd.concat(cols, axis=1, sort=True).mean(axis=1, skipna=True).sort_index()


def _stress_split(
    composite: pd.Series,
    usrec: pd.Series,
    fitter: Callable[[np.ndarray], DesmoothResult],
    *,
    min_stress: int,
    min_calm: int,
) -> tuple[float | None, float | None]:
    """Refit on calm vs NBER-stress observations; None unless both sides are
    big enough to fit honestly. Thresholds are in the composite's OWN periods,
    so a quarterly sleeve is judged on quarters, not on month-counts."""
    mask = usrec.reindex(composite.index).ffill().fillna(False).astype(bool).to_numpy()
    values = composite.to_numpy()
    if mask.sum() < min_stress or (~mask).sum() < min_calm:
        return None, None
    calm = fitter(values[~mask]).theta
    stress = fitter(values[mask]).theta
    # geltner theta is [a, phi]; a lower a (= higher phi) means stickier marks
    return float(calm[0]), float(stress[0])


def _append_stickiness(
    lines: list[str], calm: list[float], stress: list[float], *, param: str
) -> None:
    if not calm:
        lines.append("    stickiness: null  # too few stress observations to fit honestly")
        lines.append(f"    stickiness_evidence: {{n_sleeves_pooled: 0, parameter: {param}}}")
        return
    pooled_calm = float(np.mean(calm))
    pooled_stress = float(np.mean(stress))
    value = max(0.0, 1.0 - pooled_stress / pooled_calm)
    lines.append(f"    stickiness: {value:.4f}")
    lines.append(
        f"    stickiness_evidence: {{a_calm_pooled: {pooled_calm:.4f}, "
        f"a_stress_pooled: {pooled_stress:.4f}, n_sleeves_pooled: {len(calm)}, "
        f"parameter: {param}, frequency: Q}}"
    )


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))

    usrec_frame = access.train_val("fred.USREC")
    usrec = pd.Series(
        pd.to_numeric(usrec_frame["value"]).to_numpy(dtype=float) > 0.5,
        index=pd.to_datetime(usrec_frame["date"]),
    )

    lines = [
        "# mappings/smoothing-kernel-v1.0.yaml — scripts/estimate_smoothing_kernel.py",
        f"# vintage {vintage}; train+validation only; SM-10: exact inverse of the D1 primary.",
        f"kernel_version: {KERNEL_VERSION}",
        f'campaign_vintage_id: "{vintage}"',
        "desmoothing_method: glm_ma  # the paired inverse (SM-10); one model, two views",
        "stickiness_calibration: >-",
        "  Calibrated on IN-SAMPLE NBER stress months (2008-09, 2020) — deliberately",
        "  NOT DN-5 5.3's 2021-23, which is holdout span and the sealed judging",
        "  episode; using it would gut the sealed mark_lag criterion. Recorded",
        "  deviation from the design note, in the seal's favour.",
        "families:",
    ]

    # ----- geltner: the PM appraisal-calendar sleeves (trigger fired 2026-08-08)
    pm_members = pm_sleeve_members()
    geltner_sleeves = {s: m for s, m in pm_members.items() if smoothing_family(s) == "geltner"}
    glm_pm_sleeves = {s: m for s, m in pm_members.items() if smoothing_family(s) == "glm"}

    lines += [
        "  geltner:",
        "    status: PARAMETERIZED  # first PriMaRS delivery, 2026-08-08 (AM-2026-08-08-002)",
        "    form: AR(1) partial adjustment; desmooth.geltner_ar1 in return space",
        "    frequency: Q  # PM marks; the observation frequency is the valuation calendar",
        "    sleeves:",
    ]
    g_calm: list[float] = []
    g_stress: list[float] = []
    for sleeve, members in sorted(geltner_sleeves.items()):
        composite = _raw_composite(access, members)
        fit = geltner_ar1(composite.to_numpy())
        a, phi = float(fit.theta[0]), float(fit.theta[1])
        lines.append(f"      {sleeve}: {{a: {a:.4f}, phi: {phi:.4f}, n_obs: {len(composite)}}}")
        c, s = _stress_split(composite, usrec, geltner_ar1, min_stress=6, min_calm=20)
        if c is not None and s is not None:
            g_calm.append(c)
            g_stress.append(s)
    _append_stickiness(lines, g_calm, g_stress, param="phi")

    # ----- glm: HF sleeves (monthly) -- the sealed pool, unchanged
    lines += ["  glm:", "    sleeves:"]
    theta0_calm: list[float] = []
    theta0_stress: list[float] = []
    for sleeve, members in sorted(hf_sleeve_members().items()):
        composite = _raw_composite(access, members)
        fit = glm_ma(composite.to_numpy())
        theta = ", ".join(f"{t:.4f}" for t in fit.theta)
        lines.append(f"      {sleeve}: {{k: {fit.k}, theta: [{theta}]}}")

        mask = usrec.reindex(composite.index).fillna(False).astype(bool).to_numpy()
        if mask.sum() >= 18 and (~mask).sum() >= 60:
            calm_fit = glm_ma(composite.to_numpy()[~mask])
            stress_fit = glm_ma(composite.to_numpy()[mask])
            theta0_calm.append(float(calm_fit.theta[0]))
            theta0_stress.append(float(stress_fit.theta[0]))

    pooled_calm = float(np.mean(theta0_calm))
    pooled_stress = float(np.mean(theta0_stress))
    stickiness = max(0.0, 1.0 - pooled_stress / pooled_calm)
    lines.append(f"    stickiness: {stickiness:.4f}")
    lines.append(
        f"    stickiness_evidence: {{theta0_calm_pooled: {pooled_calm:.4f}, "
        f"theta0_stress_pooled: {pooled_stress:.4f}, "
        f"n_sleeves_pooled: {len(theta0_calm)}, frequency: M}}"
    )

    # ----- glm: the PM sleeves (quarterly) -- fitted and reported, pool excluded
    lines.append("    pm_sleeves:  # quarterly; excluded from the stickiness pool (see header)")
    for sleeve, members in sorted(glm_pm_sleeves.items()):
        composite = _raw_composite(access, members)
        fit = glm_ma(composite.to_numpy())
        theta = ", ".join(f"{t:.4f}" for t in fit.theta)
        note = "  # fell back to Geltner (boundary)" if fit.fell_back else ""
        lines.append(
            f"      {sleeve}: {{k: {fit.k}, theta: [{theta}], "
            f"n_obs: {len(composite)}, method: {fit.method}}}{note}"
        )

    out = _REPO_ROOT / "mappings" / "smoothing-kernel-v1.0.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {out.name}: {len(theta0_calm)}-sleeve pooled stickiness {stickiness:.3f} "
        f"(theta0 {pooled_calm:.3f} calm -> {pooled_stress:.3f} stress)"
    )


if __name__ == "__main__":
    main()
