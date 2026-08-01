"""De-smooth every albourne.hf_* series and write DESMOOTHING.md (WP2R.2).

Run:  uv run python scripts/run_hf_desmoothing.py [--vintage <id>]

Reads the 21 HF sub-strategy series from the current vintage (or --vintage),
runs the D1 primary (GLM MA(k)) with the Geltner AR(1) secondary beside it,
computes diagnostics against french.mkt_rf as the equity reference, ASSERTS the
plan's acceptance criteria (volatility ratio >= 1, means unchanged within
tolerance, beta shift upward for series the primary says are smoothed), and
writes DESMOOTHING.md at the repo root.

The committed report carries fitted parameters and diagnostics only — never
observation values — so nothing COMM-licensed is redistributed; the inputs stay
in gitignored data/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.data.desmooth import desmooth_series, generate_desmoothing_md
from ah.data.manifest import requirements

_REPO_ROOT = Path(__file__).resolve().parents[1]

MEAN_TOLERANCE = 5e-4  # monthly return units; "means unchanged within tolerance"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vintage", default=None)
    parser.add_argument("--out", type=Path, default=_REPO_ROOT / "DESMOOTHING.md")
    args = parser.parse_args()

    catalog = Catalog(_REPO_ROOT / "data")
    vintage = args.vintage or catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage; run the intake apply first")

    hf_ids = sorted(r.series_id for r in requirements() if r.series_id.startswith("albourne.hf_"))
    equity_frame = catalog.read_observations(vintage, "french.mkt_rf")
    equity_by_date = equity_frame.set_index("date")["value"]

    primaries, secondaries, failures = [], [], []
    for series_id in hf_ids:
        frame = catalog.read_observations(vintage, series_id)
        # align the equity reference to this series' own dates (starts differ)
        equity = equity_by_date.reindex(pd.to_datetime(frame["date"])).to_numpy(dtype=float)
        primary = desmooth_series(series_id, frame, method="glm_ma", equity=equity)
        secondary = desmooth_series(series_id, frame, method="geltner_ar1", equity=equity)
        primaries.append(primary)
        secondaries.append(secondary)

        d = primary.diagnostics
        assert d is not None
        if not d.sigma_ratio >= 1.0:
            failures.append(f"{series_id}: sigma_ratio {d.sigma_ratio:.3f} < 1")
        if not abs(d.mean_diff) <= MEAN_TOLERANCE:
            failures.append(f"{series_id}: mean moved {d.mean_diff:+.5f} (> {MEAN_TOLERANCE})")
        # beta shift: only meaningful where the fit found real smoothing
        material_weights = primary.k > 0 and max(primary.theta[1:], default=0.0) > 0.10
        betas_finite = np.isfinite(d.beta_before) and np.isfinite(d.beta_after)
        if material_weights and betas_finite and d.beta_after < d.beta_before - 0.02:
            failures.append(
                f"{series_id}: beta fell {d.beta_before:.2f} -> {d.beta_after:.2f} "
                "despite material smoothing weights"
            )

    if failures:
        raise SystemExit("acceptance FAILED:\n  " + "\n  ".join(failures))

    material = [r.series_id for r in primaries if r.k > 0 and max(r.theta[1:], default=0.0) > 0.10]
    negligible = [r.series_id for r in primaries if r.series_id not in material]

    md = generate_desmoothing_md(primaries)
    md += (
        "\n## HF sections (WP2R.2)\n\n"
        f"Vintage: `{vintage}`; equity reference: `french.mkt_rf`; primary method GLM MA(k),\n"
        "Geltner AR(1) run as secondary (table below). Parameters and diagnostics only —\n"
        "no observation values; the COMM-licensed inputs stay in gitignored `data/`.\n\n"
        f"**Material smoothing** (some lag weight > 0.10): {', '.join(material) or 'none'}.\n\n"
        f"**Negligible smoothing**: {', '.join(negligible) or 'none'}.\n\n"
        "### Geltner AR(1) secondary\n\n" + generate_desmoothing_md(secondaries).split("\n", 2)[2]
    )
    args.out.write_text(md, encoding="utf-8", newline="\n")
    print(
        f"wrote {args.out.name}: {len(primaries)} series de-smoothed on {vintage}; "
        f"material smoothing in {len(material)}, negligible in {len(negligible)}; "
        "acceptance PASSED"
    )


if __name__ == "__main__":
    main()
