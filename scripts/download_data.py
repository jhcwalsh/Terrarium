"""Download real public data, write a vintage, validate, and summarize.

Operational (not a test): drives the connectors over the network to pull the auto
(public) series into a real catalog vintage under ./data, runs the QC checks, and
prints a found/not-found + QC summary. FRED needs FRED_API_KEY; other public sources
are keyless. Manual/licensed intakes (Albourne/Cliffwater/NCREIF) are not fetched.
"""

from __future__ import annotations

import os
import traceback
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ah.data.catalog import Catalog
from ah.data.connectors.bis import BisConnector
from ah.data.connectors.fred import FredConnector
from ah.data.connectors.french import FrenchConnector
from ah.data.connectors.jst import JstConnector
from ah.data.connectors.shiller import ShillerConnector
from ah.data.connectors.treasury_hqm import TreasuryHqmConnector
from ah.data.manifest import Requirement, requirements
from ah.data.qc import check_series

ROOT = Path(__file__).resolve().parents[1]

CONNECTORS = {
    "fred": FredConnector(),
    "french": FrenchConnector(),
    "shiller": ShillerConnector(),
    "jst": JstConnector(),
    "bis": BisConnector(),
    "treasury_hqm": TreasuryHqmConnector(),
}
# One fetched artifact can serve many series (French/JST/Shiller are multi-series files).
_FETCH_CACHE: dict[tuple[str, str], object] = {}


def _load_env() -> None:
    if os.environ.get("FRED_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("FRED_API_KEY=") and "=" in line:
                os.environ["FRED_API_KEY"] = line.split("=", 1)[1].strip()


# Sources whose ONE download serves many series (cache the artifact); FRED is a
# per-series API call and must never be cached across series.
_SHARED_FILE = {"french", "jst", "shiller"}


def _fetch(conn, req: Requirement):
    if req.source not in _SHARED_FILE:
        return conn.fetch(req)  # per-series (FRED, BIS, Treasury)
    key = (req.source, "MOM" if req.code == "Mom" else "MAIN")
    if key not in _FETCH_CACHE:
        _FETCH_CACHE[key] = conn.fetch(req)
    return _FETCH_CACHE[key]


def main() -> int:
    _load_env()
    asof = datetime.now(UTC).strftime("%Y-%m-%d")
    vintage = asof
    reqs = requirements()
    data_root = ROOT / "data"
    cat = Catalog(data_root)
    if cat.vintage_status(vintage) is None:
        cat.create_vintage(vintage, created_at=datetime.now(UTC).isoformat())

    rows: list[dict] = []
    for req in reqs.by_intake("auto"):
        conn = CONNECTORS.get(req.source)
        if conn is None:
            continue
        rec: dict = {
            "series": req.series_id,
            "source": req.source,
            "status": "?",
            "n": 0,
            "span": "-",
            "qc": "",
        }
        try:
            raw = _fetch(conn, req)
            df = conn.parse(raw, req)
            if df.empty:
                rec["status"] = "EMPTY"
            else:
                cat.register_series(req)
                if (
                    cat.con.execute(
                        "SELECT 1 FROM observations_index WHERE vintage_id=? AND series_id=?",
                        [vintage, req.series_id],
                    ).fetchone()
                    is None
                ):
                    cat.write_observations(vintage, req.series_id, df)
                findings = check_series(req, df, asof=asof)
                # data-quality rules that matter (exclude staleness: month-start labels
                # make month-old obs look stale under daily SLAs)
                dq = [f for f in findings if f.rule not in ("staleness", "jump") and not f.passed]
                rec["status"] = "OK" if not dq else "QC-FAIL"
                rec["n"] = len(df)
                rec["span"] = (
                    f"{pd.to_datetime(df['date']).min().date()}..{pd.to_datetime(df['date']).max().date()}"
                )
                rec["qc"] = ";".join(f"{f.rule}({f.detail})" for f in dq) or "clean"
        except Exception as exc:
            rec["status"] = "FETCH/PARSE-FAIL"
            rec["qc"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:120]}"
            traceback.print_exc(limit=1)
        rows.append(rec)
        print(f"  {rec['status']:16} {rec['series']:24} n={rec['n']:>6} {rec['span']}")

    # advance pointer if nothing has a data-quality failure
    dq_fail = [r for r in rows if r["status"] == "QC-FAIL"]
    ok = [r for r in rows if r["status"] == "OK"]
    if ok and not dq_fail:
        cat.advance_pointer(vintage, when=datetime.now(UTC).isoformat())

    print("\n================ SUMMARY ================")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    for status, n in sorted(by_status.items()):
        print(f"  {status:18} {n}")
    print(f"\n  vintage: {vintage}  current_pointer: {cat.current_vintage()}")
    print(f"  written OK: {len(ok)} / attempted {len(rows)}")
    if dq_fail:
        print("  QC-FAIL series:")
        for r in dq_fail:
            print(f"    - {r['series']}: {r['qc']}")
    fails = [r for r in rows if r["status"] == "FETCH/PARSE-FAIL"]
    if fails:
        print("  FETCH/PARSE-FAIL series:")
        for r in fails:
            print(f"    - {r['series']} ({r['source']}): {r['qc']}")
    cat.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
