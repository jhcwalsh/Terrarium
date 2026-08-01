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
  LEVELS tied to a valuation calendar. **UNPARAMETERIZED**: no PM series is
  delivered (the sealed PM unavailability); the family is named in the
  artifact with its trigger, never given invented numbers.

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

from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.data.desmooth import glm_ma
from ah.eval.sleevetails import hf_sleeve_members
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
        "  geltner:",
        "    status: UNPARAMETERIZED  # no PM series delivered; the sealed PM unavailability",
        "    trigger: first PM delivery -> parameterize by amendment before any RE/infra",
        "      reported path is generated",
        "  glm:",
        "    sleeves:",
    ]

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
        f"n_sleeves_pooled: {len(theta0_calm)}}}"
    )

    out = _REPO_ROOT / "mappings" / "smoothing-kernel-v1.0.yaml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {out.name}: {len(theta0_calm)}-sleeve pooled stickiness {stickiness:.3f} "
        f"(theta0 {pooled_calm:.3f} calm -> {pooled_stress:.3f} stress)"
    )


if __name__ == "__main__":
    main()
