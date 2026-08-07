"""Download the eight registered private-markets series from Albourne PriMaRS
and land them in the vintage store through the standard manual-intake path.

Run from the repo root (needs network + ALBOURNE_TOKEN/.env):

    uv run python scripts/download_primars.py

What it does, in the intake pipeline's own terms: fetch TWR history for the
mapped indices (ah.data.connectors.albourne_primars), write the drop file
``data/intake/albourne-pm-returns_<asof>.csv``, validate it against the
``albourne_pm_returns`` schema, then apply it as a new vintage — QC runs, and
the current pointer advances only on pass, exactly as ``ah data intake apply``
would. Licensed values stay under gitignored ``data/``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.data.catalog import Catalog  # noqa: E402
from ah.data.connectors.albourne_primars import (  # noqa: E402
    PM_INDEX_MAP,
    fetch_pm_payload,
    payload_to_intake_frame,
)
from ah.data.intake import ingest_file, to_series_frames  # noqa: E402
from ah.data.manifest import load_requirements  # noqa: E402
from ah.data.refresh import apply_intake_frames  # noqa: E402
from ah.data.schemas import get_schema  # noqa: E402


def main() -> int:
    today = datetime.now(UTC).date().isoformat()
    now = datetime.now(UTC).isoformat()

    print(f"fetching {len(PM_INDEX_MAP)} PriMaRS indices...")
    payload = fetch_pm_payload()
    frame = payload_to_intake_frame(payload)
    per = frame.groupby("strategy")["period"].agg(["min", "max", "count"])
    print(per.to_string())

    drop_dir = ROOT / "data" / "intake"
    drop_dir.mkdir(parents=True, exist_ok=True)
    drop = drop_dir / f"albourne-pm-returns_{today}.csv"
    frame.to_csv(drop, index=False)
    print(f"wrote drop {drop} ({len(frame)} rows)")

    schema = get_schema("albourne_pm_returns")
    assert schema is not None
    cat = Catalog(ROOT / "data")
    try:
        result = ingest_file(cat, drop, schema, received_at=now)
        print(result.report)
        if not result.accepted or result.frame is None:
            return 1
        frames = to_series_frames(schema, result.frame)
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
            print("could not find a free vintage id")
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
