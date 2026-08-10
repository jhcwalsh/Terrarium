"""Materialize THE pinned equity_vol HAR draw (campaign-3 wiring, step 2).

Operational, not a test (network: the French daily donor). AM-2026-08-09-002
admits the HAR backcast months to the extended panel with panel consumption
fixed to ONE pinned ensemble draw -- seed 20260809 via
``ah.data.vol_backcast.paths`` on the registered provenance artifact (its
sha256 is pinned in the amendment payload and in
``vol_backcast.PINNED_PROVENANCE_SHA256``). This script performs that draw
exactly once and writes it to ``src/ah/data/equity_vol_pinned_draw.json`` --
package data, committed, and hashed by the campaign-3 seal -- so the factor
read surface never regenerates model months and every consumer sees the same
history.

Refusals, in order: a provenance file whose sha differs from the pin; a
feature panel that does not cover the pinned span 1953-04..1985-12 without
gaps. Re-running against the same provenance and the same donor history
reproduces the same values (paths() is deterministic in (fit, seed)); the
committed file's own sha is what the campaign-3 pre-registration pins, so an
accidental re-materialization that changes bytes is caught at seal time, not
trusted silently.

Run:  uv run python scripts/volext_materialize_draw.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROVENANCE = ROOT / "artifacts" / "volext" / "equity-vol-backcast-provenance.json"


def main() -> int:
    import numpy as np
    import pandas as pd

    from ah.data import vol_backcast as vb
    from ah.data.connectors.french import FrenchConnector
    from ah.data.manifest import load_requirements

    raw = PROVENANCE.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != vb.PINNED_PROVENANCE_SHA256:
        print(f"provenance sha {sha} != pinned {vb.PINNED_PROVENANCE_SHA256} -- refusing")
        return 1
    payload = json.loads(raw.decode("utf-8"))
    f = vb.fit_from_provenance(payload)
    print(f"provenance verified ({PROVENANCE.name}); fit n={f.n_obs} r2={f.r2:.3f}")

    reqs = load_requirements()
    french = FrenchConnector()

    def _fetch(sid: str) -> pd.Series:
        req = reqs[sid]
        frame = french.parse(french.fetch(req), req)
        print(
            f"{sid}: {len(frame)} obs, {frame['date'].min().date()}..{frame['date'].max().date()}"
        )
        return frame.set_index("date")["value"]

    mkt_rf = _fetch("french.mkt_rf_d")
    rf = _fetch("french.rf_d")
    total = (mkt_rf + rf.reindex(mkt_rf.index).fillna(0.0)).dropna()
    features = vb.realized_features(vb.close_from_returns(total))

    start, end = vb.PINNED_DRAW_SPAN
    span = pd.date_range(f"{start}-01", f"{end}-01", freq="MS") + pd.offsets.MonthEnd(0)
    missing = span.difference(features.index)
    if len(missing) > 0:
        print(f"feature panel is missing {len(missing)} month(s) of the pinned span -- refusing")
        return 1

    mu = f.predict(features.loc[span]).to_numpy()
    resid_path = vb.paths(f, len(span), n_draws=1, seed=vb.PINNED_DRAW_SEED)[0]
    values = np.exp(mu + resid_path)

    doc = {
        "artifact": "equity_vol_pinned_draw",
        "rule_id": vb.RULE_ID,
        "amendment_id": "AM-2026-08-09-002",
        "provenance_sha256": vb.PINNED_PROVENANCE_SHA256,
        "seed": vb.PINNED_DRAW_SEED,
        "draw_index": 0,
        "n_months": len(span),
        "span": list(vb.PINNED_DRAW_SPAN),
        "caveat": (
            "MODEL OUTPUT: one block-bootstrap draw of the registered HAR backcast "
            "(conditional mean + resampled residual path, log space), NOT observation. "
            "Every panel month sourced from this file is is_proxy=True under "
            f"{vb.RULE_ID}. Tail diagnostics regenerate the full ensemble from the "
            "provenance artifact (owner decision D2); this single path exists so the "
            "sealed panel is one history, not a fresh draw per reader."
        ),
        "values": {ts.strftime("%Y-%m"): float(v) for ts, v in zip(span, values, strict=True)},
    }
    # LF bytes, explicitly: the repo normalizes to LF (.gitattributes eol=lf), and the
    # campaign-3 prereg pins this file's sha -- on-disk bytes must equal committed bytes.
    vb.PINNED_DRAW_PATH.write_bytes(json.dumps(doc, indent=2).encode("utf-8") + b"\n")
    out_sha = hashlib.sha256(vb.PINNED_DRAW_PATH.read_bytes()).hexdigest()
    print(f"wrote {vb.PINNED_DRAW_PATH} ({len(span)} months)")
    print(f"pinned draw sha256: {out_sha}")

    # credibility readings, mirrored into the wiring report by hand
    s = pd.Series(values, index=span)
    for label, month in [
        ("1962-10 (Cuban missile crisis)", "1962-10"),
        ("1970-05 (Penn Central month)", "1970-05"),
        ("1974-09 (bear-market trough quarter)", "1974-09"),
        ("1982-08 (Volcker pivot)", "1982-08"),
    ]:
        sel = s[s.index.strftime("%Y-%m") == month]
        if len(sel):
            print(f"  {label}: {float(sel.iloc[0]):.1f}")
    print(f"  min {s.min():.1f}  median {s.median():.1f}  max {s.max():.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
