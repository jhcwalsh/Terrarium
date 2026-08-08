"""Land the Cliffwater BDC Index delivery in the vintage store.

Run from the repo root (no network; reads a local vendor file):

    uv run python scripts/ingest_cwbdc.py [--source data/CWBDC-monthly-2004-2026.csv]

Applies the delivery through the standard manual-intake path -- schema
validation, QC, vintage commit, and a pointer that advances only on pass. The
parse (and the units discussion the vendor's column names require) lives in
``ah.data.connectors.cliffwater_bdc``; this is the driver.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.data.connectors.cliffwater_bdc import SERIES_ID, to_drop_frame  # noqa: E402
from ah.data.intake import ingest_file, to_series_frames  # noqa: E402
from ah.data.manifest import load_requirements  # noqa: E402
from ah.data.refresh import apply_intake_frames  # noqa: E402
from ah.data.schemas import get_schema  # noqa: E402

DEFAULT_SOURCE = ROOT / "data" / "CWBDC-monthly-2004-2026.csv"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"missing vendor file {args.source}")
        return 1
    frame = to_drop_frame(pd.read_csv(args.source))
    print(
        f"{len(frame)} monthly observations {frame['period'].iloc[0]}..{frame['period'].iloc[-1]}; "
        f"mean {frame['ret'].mean():.4%}, vol {frame['ret'].std(ddof=1):.4%}"
    )

    today = datetime.now(UTC).date().isoformat()
    now = datetime.now(UTC).isoformat()
    drop_dir = args.data_root / "intake"
    drop_dir.mkdir(parents=True, exist_ok=True)
    drop = drop_dir / f"cliffwater-bdc_{today}.csv"
    frame.to_csv(drop, index=False)
    print(f"wrote drop {drop}")

    schema = get_schema("cliffwater_bdc")
    if schema is None:
        print("schema 'cliffwater_bdc' not registered")
        return 1
    cat = Catalog(args.data_root)
    try:
        result = ingest_file(cat, drop, schema, received_at=now)
        print(result.report)
        if not result.accepted or result.frame is None:
            return 1
        frames = {SERIES_ID: next(iter(to_series_frames(schema, result.frame).values()))}
        for n in range(1, 100):
            vintage = f"{today}.{n}"
            outcome = apply_intake_frames(
                cat,
                load_requirements(),
                frames=frames,
                vintage=vintage,
                asof=today,
                created_at=now,
            )
            if not outcome.already_exists:
                break
        else:
            print("no free vintage id")
            return 1
        status = "QUARANTINED" if outcome.quarantined else "current"
        print(
            f"vintage {vintage} {status}: wrote {len(outcome.written)} series, "
            f"carried forward {len(outcome.carried_forward)}."
        )
        if outcome.quarantined and outcome.qc is not None:
            for f in outcome.qc.enforce_failures:
                print(f"  QC enforce: {f.series_id} {f.rule} ({f.detail})")
            return 1
        return 0
    finally:
        cat.close()


if __name__ == "__main__":
    raise SystemExit(main())
