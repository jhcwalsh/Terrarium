"""WP2.11: how much does the retained cycle forcing let the 1970s into the severe fit?

RECORDED LIMITATION, quantified rather than asserted. The severe-test L1 fit
UNMASKS the excluded decade's observations but RETAINS ``KFData.cycle``
(``c_t = 1 - 2*USREC``) across the gap, because the cycle is an exogenous forcing
on the state dynamics (``L_bar_t = delta_L * c_t``) rather than an observation.
So the severe fit still "knows" the 1970s NBER recession dating, and that
information can reach the fitted states through the state path that links the
pre-1970 and post-1979 segments.

This script measures the size of that channel where it actually matters: at the
**1965-01 backward-sampled state**, which is what ``simulate_decades(s0_date=...)`` draws
the severe test's start state from. 1965-01 sits BEFORE the gap, so 1970s
information reaches it only through the backward smoothing pass over masked
months -- a narrow channel, and this puts a number on it.

Method: rebuild the severe fit panel, take the severe posterior's MEAN theta, and
run FFBS twice under ONE shared PRNG key -- once on the panel as fitted (cycle
retained through the gap) and once with the cycle zeroed inside the gap (a total
exclusion). Report the difference in the backward-sampled state at 1965-01, and
for context the maximum difference anywhere on the grid, per state, in units of
that state's own path standard deviation. The forward filter is run too as a
control: it cannot see the future, so before the gap it must agree exactly.

Deterministic; no RNG, no clock, no network. Reads nothing but the local catalog
and the severe artifact.

Usage::

    uv run python scripts/measure_severe_cycle_sensitivity.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.gen.climate import fit as cf  # noqa: E402
from ah.gen.climate import model as cm  # noqa: E402
from ah.gen.climate.simulate import load_artifact  # noqa: E402
from ah.gen.severe import SEVERE_TEST_EXCLUSION, SEVERE_TEST_S0_DATE  # noqa: E402
from ah.splits import DataAccess  # noqa: E402

SEVERE_ARTIFACT = (
    _REPO_ROOT
    / "experiments"
    / "climate-l1-severe-f7d4119c7101-s20260726"
    / "climate-posterior.npz"
)
OUT = _REPO_ROOT / "experiments" / "wp211" / "cycle-sensitivity.json"


def _access(catalog: Catalog, vintage: str) -> DataAccess:
    def reader(series_id: str):
        try:
            return catalog.read_observations(vintage, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    args = parser.parse_args()

    artifact = load_artifact(SEVERE_ARTIFACT)
    theta = {name: float(np.mean(artifact.params[name])) for name in cm.PARAM_NAMES}

    config = cm.load_config()
    with Catalog(args.catalog_root) as catalog:
        fit_data = cf.build_fit_data(
            _access(catalog, args.vintage), config, exclude=SEVERE_TEST_EXCLUSION
        )

    kf_as_fitted = fit_data.kf
    inside = SEVERE_TEST_EXCLUSION.contains(fit_data.dates)
    cycle_zeroed = kf_as_fitted.cycle.copy()
    cycle_zeroed[inside] = 0.0
    kf_total = cm.KFData(
        y=kf_as_fitted.y,
        mask=kf_as_fitted.mask,
        aux_pi=kf_as_fitted.aux_pi,
        aux_c=kf_as_fitted.aux_c,
        cycle=cycle_zeroed,
        m0=kf_as_fitted.m0,
        p0=kf_as_fitted.p0,
    )

    # The FFBS (backward-sampled) path is the right object: the artifact's `states`
    # are FFBS draws, and only the BACKWARD pass can carry post-1979 information
    # (and hence the in-gap cycle) into a pre-1970 month. The SAME PRNG key is used
    # on both panels, so the same random numbers are drawn and the difference
    # isolates the panel change rather than sampling noise.
    import jax

    key = jax.random.PRNGKey(0)
    a = np.asarray(cm._ffbs_single(key, theta, kf_as_fitted))[:, : cm.N_STATES]
    b = np.asarray(cm._ffbs_single(key, theta, kf_total))[:, : cm.N_STATES]

    # Control: the FORWARD filter cannot see the future at all, so before the gap
    # the two filtered paths must be bit-identical. If this is not ~0 the
    # measurement is wrong, not the model.
    fa = np.asarray(cm._filter_pass(theta, kf_as_fitted)[0])[:, : cm.N_STATES]
    fb = np.asarray(cm._filter_pass(theta, kf_total)[0])[:, : cm.N_STATES]

    t0 = int(fit_data.dates.get_indexer([pd.Timestamp(SEVERE_TEST_S0_DATE)])[0])
    sd = a.std(axis=0)
    sd[sd == 0.0] = 1.0
    diff = np.abs(a - b)
    filtered_control = float(np.abs(fa[: t0 + 1] - fb[: t0 + 1]).max())

    doc = {
        "what": (
            "severe L1 fit AS RUN (cycle retained through the excluded decade) vs a "
            "TOTAL exclusion (cycle zeroed there too), at the severe posterior's mean "
            "theta; FFBS (backward-sampled) state path under one shared PRNG key, "
            "same masked observations in both"
        ),
        "s0_date": SEVERE_TEST_S0_DATE,
        "exclusion": SEVERE_TEST_EXCLUSION.label,
        "state_names": list(cm.STATE_NAMES),
        "abs_diff_at_s0": {name: float(diff[t0, i]) for i, name in enumerate(cm.STATE_NAMES)},
        "abs_diff_at_s0_in_own_sd": {
            name: float(diff[t0, i] / sd[i]) for i, name in enumerate(cm.STATE_NAMES)
        },
        "max_abs_diff_anywhere": {
            name: float(diff[:, i].max()) for i, name in enumerate(cm.STATE_NAMES)
        },
        "max_abs_diff_anywhere_in_own_sd": {
            name: float(diff[:, i].max() / sd[i]) for i, name in enumerate(cm.STATE_NAMES)
        },
        "state_sd_as_fitted": {name: float(sd[i]) for i, name in enumerate(cm.STATE_NAMES)},
        "forward_filter_control_max_abs_diff_up_to_s0": filtered_control,
        "forward_filter_control_note": (
            "must be ~0: the forward filter cannot see the future, so the in-gap cycle "
            "cannot reach a pre-1970 filtered state. A non-zero value here means the "
            "measurement is wrong, not the model."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps(doc, indent=2, sort_keys=True))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
