"""Write the private-markets de-smoothing validation exhibit.

Run from the repo root, after every delivery:

    uv run python scripts/validate_desmoothing.py

Reads the current vintage, puts every modeled PM sleeve through its OWN
de-smoothing family (``sleevetails.smoothing_family``, so the exhibit audits
what the kernel actually applies), aligns any registered market-priced
comparator, and writes ``docs/data/DESMOOTHING-VALIDATION.md``.

Deterministic and read-only against the store: no RNG, no writes to the
catalog. The logic lives in ``ah.data.desmooth_validation``; this is the
driver.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.data.desmooth_validation import (  # noqa: E402
    COMPARATORS,
    check_sleeve,
    render_markdown,
    to_quarterly,
)
from ah.eval.sleevetails import pm_sleeve_members, smoothing_family  # noqa: E402

OUT_PATH = ROOT / "docs" / "data" / "DESMOOTHING-VALIDATION.md"


def _series(catalog: Catalog, vintage: str, series_id: str) -> pd.Series | None:
    try:
        frame = catalog.read_observations(vintage, series_id)
    except Exception:
        return None
    if frame.empty:
        return None
    values = pd.Series(
        pd.to_numeric(frame["value"]).to_numpy(dtype=float),
        index=pd.PeriodIndex(pd.DatetimeIndex(frame["date"]), freq="Q")
        if series_id.endswith("_q")
        else pd.DatetimeIndex(frame["date"]),
    )
    return values.sort_index()


def main() -> int:
    catalog = Catalog(ROOT / "data")
    try:
        vintage = catalog.current_vintage()
        if vintage is None:
            print("no current vintage")
            return 1

        checks = []
        for sleeve, members in pm_sleeve_members().items():
            family = smoothing_family(sleeve)
            for series_id in members:
                reported = _series(catalog, vintage, series_id)
                if reported is None:
                    continue
                comparator_id = COMPARATORS.get(series_id)
                comparator = None
                if comparator_id:
                    raw = _series(catalog, vintage, comparator_id)
                    if raw is not None:
                        # monthly comparator -> the reported series' own quarters
                        comparator = to_quarterly(raw) if not comparator_id.endswith("_q") else raw
                checks.append(
                    check_sleeve(
                        series_id,
                        reported,
                        family=family,
                        comparator=comparator,
                        comparator_id=comparator_id if comparator is not None else None,
                    )
                )

        if not checks:
            print("no PM series in the current vintage; nothing to validate")
            return 1

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(
            render_markdown(checks, vintage=vintage, as_of=datetime.now(UTC).date().isoformat()),
            encoding="utf-8",
            newline="\n",
        )
        noops = [c.series_id for c in checks if c.is_noop]
        print(f"wrote {OUT_PATH.relative_to(ROOT)}: {len(checks)} series checked")
        print(f"  no-ops (de-smoother recovered nothing): {noops or 'none'}")
        for c in checks:
            if c.comparator_ratio is not None:
                print(
                    f"  comparator {c.series_id} vs {c.comparator}: "
                    f"{c.comparator_ratio:.2f}x on {c.n_overlap} shared quarters"
                )
        return 0
    finally:
        catalog.close()


if __name__ == "__main__":
    raise SystemExit(main())
