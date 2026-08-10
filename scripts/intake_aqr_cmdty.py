"""Intake the AQR CFTLR workbook into the vintage store (ruling K2's last mile).

Operational, offline (no network: the workbook is owner-supplied at
``data/aqr/``). Parses the two registered series through the same connector
``docs/data/CMDTY-REPORT.md`` was verified with and applies them through
``ah.data.refresh.apply_intake_frames`` -- the SAME QC-gated, append-only,
advance-only-on-pass path every manual delivery takes (WP2R.2; the PriMaRS
precedent). Raw AQR values land in the gitignored local store ONLY; the REG
licence forbids committing or redistributing them, and nothing here writes
outside ``data/``.

Idempotent per vintage id: re-running with the same --vintage is refused by
the store, exactly as ``ah data intake apply`` is.

Run:  uv run python scripts/intake_aqr_cmdty.py --vintage 2026-08-10.aqr1
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WORKBOOK = ROOT / "data" / "aqr" / "Commodities for the Long Run Index Level Data Monthly.xlsx"

SERIES_BY_CODE = {
    "ew_excess": "aqr.cmdty_ew_excess",
    "ew_spot": "aqr.cmdty_ew_spot",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vintage", required=True, help="Vintage id to write (e.g. 2026-08-10.aqr1)"
    )
    args = parser.parse_args()

    from ah.data.catalog import Catalog
    from ah.data.cmdty_close import ATTRIBUTION
    from ah.data.connectors.aqr_cftlr import parse_workbook
    from ah.data.manifest import load_requirements
    from ah.data.refresh import apply_intake_frames

    if not WORKBOOK.exists():
        print(f"workbook not found at {WORKBOOK} -- the owner-supplied file is required")
        return 1

    parsed = parse_workbook(WORKBOOK)
    frames = {SERIES_BY_CODE[code]: frame for code, frame in parsed.items()}
    for sid, frame in sorted(frames.items()):
        print(
            f"{sid}: {len(frame)} obs, {frame['date'].min().date()}..{frame['date'].max().date()}"
        )

    catalog = Catalog(ROOT / "data")
    now = datetime.now(UTC)
    outcome = apply_intake_frames(
        catalog,
        load_requirements(),
        frames=frames,
        vintage=args.vintage,
        asof=now.strftime("%Y-%m-%d"),
        created_at=now.isoformat(),
    )
    if outcome.already_exists:
        print(f"vintage {args.vintage} already exists; nothing applied")
        return 1
    status = "QUARANTINED" if outcome.quarantined else "current"
    print(
        f"vintage {args.vintage} {status}: wrote {len(outcome.written)} series, "
        f"carried forward {len(outcome.carried_forward)}."
    )
    if outcome.quarantined and outcome.qc is not None:
        for f in outcome.qc.enforce_failures:
            print(f"  QC enforce: {f.series_id} {f.rule} ({f.detail})")
        return 1
    print(ATTRIBUTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
