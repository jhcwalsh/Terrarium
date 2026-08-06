"""Show that the console's two checks actually recompute (Task 3 acceptance #3).

A check that has never been seen to go red has not been shown to work. This
script drives a **deliberately corrupted copy** through the identical functions
the console's pages call — ``ah.console.sanity_rows`` and
``ah.console.cash_identity`` — and prints the before/after verdicts.

Nothing real is touched. The world document is copied in memory and the ledger
rows are copied before perturbation; no store, no record and no artifact is
written. Run it against any world in any store::

    uv run python scripts/console_corruption_demo.py [DB_PATH] [WORLD_ID]

Defaults to the repo store and its first world.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

from ah.console import cash_identity, sanity_rows
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import START_CASH, simulate_play

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(db: Path, world_id: str | None) -> tuple[str, dict]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT world_id, json FROM worlds ORDER BY created_at").fetchall()
    finally:
        conn.close()
    if not rows:
        raise SystemExit(f"{db}: no worlds. Build one: uv run ah world build --preset stagflation")
    for r in rows:
        if world_id is None or r["world_id"] == world_id:
            return r["world_id"], json.loads(r["json"])
    raise SystemExit(f"{db}: no world {world_id}")


def main(argv: list[str]) -> int:
    db = Path(argv[1]) if len(argv) > 1 else _REPO_ROOT / "data" / "ah.db"
    wid, doc = _load(db, argv[2] if len(argv) > 2 else None)
    seed = int((doc.get("engine_defaults") or {}).get("base_seed") or 0)
    print(f"world {wid}  seed {seed}  store {db}\n")

    # ---------------------------------------------------------------- strip --
    clean = run_path(project_numeric(WorldSpec.model_validate(doc)), seed)
    rows = sanity_rows(clean)
    breaches = [r for r in rows if r[5]]
    print("SANITY STRIP, clean world")
    print(f"  {len(rows)} series checked, {len(breaches)} breach(es)")
    for r in breaches:
        print(f"    ! {r[0]}: {r[5]}")

    # Corrupting the WorldSpec does not work, and that is worth recording: the
    # contract refuses it before the engine ever runs. equity.vol_annual_pct is
    # bounded at 45 by schemas/worldspec-v1.2.schema.json, so
    # WorldSpec.model_validate raises rather than producing a bad decade.
    bad_doc = copy.deepcopy(doc)
    bad_doc["factor_conditions"]["equity"]["vol_annual_pct"] = 400.0
    try:
        WorldSpec.model_validate(bad_doc)
        spec_guard = "NOT REFUSED — the contract let an out-of-bounds vol through"
    except Exception as exc:
        spec_guard = f"refused by the contract ({type(exc).__name__})"
    print(f"\n  spec-level corruption (vol_annual_pct 400): {spec_guard}")

    # So corrupt what the strip actually consumes: the EnginePaths. This is the
    # honest target — the strip's job is to catch a bad decade, however it arose.
    bad_returns = {k: v.copy() for k, v in clean.returns.items()}
    bad_returns["equity"][12] = -150.0  # a month worse than total loss
    bad_rate = clean.rate.copy()
    bad_rate[5] = 0.05  # below the engine's own 0.1 floor
    bad = replace(clean, returns=bad_returns, rate=bad_rate)
    bad_rows = sanity_rows(bad)
    bad_breaches = [r for r in bad_rows if r[5]]
    print("\nSANITY STRIP, corrupted COPY of EnginePaths (equity m12 = -150%, rate m5 = 0.05)")
    print(f"  {len(bad_rows)} series checked, {len(bad_breaches)} breach(es)")
    for r in bad_breaches:
        print(f"    ! {r[0]}: min {r[1]:.6f} -> {r[5]}")
    strip_proved = bool(bad_breaches) and not breaches

    # ------------------------------------------------------------ identity --
    result = simulate_play(clean, None)
    res_clean = cash_identity(result.quarters, START_CASH)
    worst_clean = max(abs(x) for x in res_clean)
    print(
        f"\nCASH IDENTITY, clean ledger\n  {len(res_clean)} quarters, worst residual {worst_clean:.3e}"
    )

    # Corrupt a COPY of the displayed rows: one quarter's cash off by 0.25.
    bad_quarters = list(result.quarters)
    victim = len(bad_quarters) // 2
    bad_quarters[victim] = replace(bad_quarters[victim], cash=bad_quarters[victim].cash + 0.25)
    res_bad = cash_identity(bad_quarters, START_CASH)
    flagged = [i for i, x in enumerate(res_bad) if abs(x) >= 1e-6]
    print(f"\nCASH IDENTITY, corrupted COPY (+0.25 to Q{victim + 1} cash)")
    print(f"  quarters flagged: {flagged}")
    for i in flagged:
        print(f"    ! Q{i + 1} residual {res_bad[i]:+.4f}")
    identity_proved = bool(flagged) and worst_clean < 1e-6

    print("\n--- acceptance #3 ---")
    print(f"  sanity strip recomputes : {'PROVED' if strip_proved else 'NOT PROVED'}")
    print(f"  cash identity recomputes: {'PROVED' if identity_proved else 'NOT PROVED'}")
    print("  (nothing was written; both corruptions were applied to in-memory copies)")
    return 0 if (strip_proved and identity_proved) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
