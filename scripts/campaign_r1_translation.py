"""Campaign R1 Track A. Run:  uv run python scripts/campaign_r1_translation.py

The twin over observed factor history on the frozen campaign vintage, priors
scored, measured PM loadings as a NOT-ADOPTED diagnostic. Deterministic:
observed inputs, frozen artifacts, no RNG. Writes
docs/data/CAMPAIGN-R1-TRANSLATION.md (served by the tools hub).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.port import campaign_exhibit as ce  # noqa: E402

OUT = _REPO_ROOT / "docs" / "data" / "CAMPAIGN-R1-TRANSLATION.md"


def main() -> int:
    catalog = Catalog(_REPO_ROOT / "data")
    try:
        reg = ce.load_regressors(catalog, ce.CAMPAIGN_VINTAGE)
    finally:
        catalog.close()
    mapping = ce.load_real_mapping()
    results = []
    plane = []
    for name, (start, end) in ce.WINDOWS.items():
        window = reg.loc[start:end]
        for source in ("prior", "measured"):
            if name == "full_span":
                # the twin loop refuses windows beyond the fixture cohort's
                # contract; the long span shows the sleeve planes instead
                rows = ce.pm_plane_stats(name, window, mapping, source=source)
                plane.extend(rows)
                print(f"  {name:10s} {source:8s} sleeve planes: {len(rows)} sleeves")
                continue
            result = ce.run_window(name, window, mapping, source=source)
            results.append(result)
            print(
                f"  {name:10s} {source:8s} q={result.quarters:3d} "
                f"dd_true={result.max_dd_true:+.4f} dd_rep={result.max_dd_reported:+.4f} "
                f"forced={result.forced_sale_quarters}"
            )
    OUT.write_text(
        ce.render_markdown(results, vintage=ce.CAMPAIGN_VINTAGE, plane=plane),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT.relative_to(_REPO_ROOT)} ({len(results)} twin runs, {len(plane)} planes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
