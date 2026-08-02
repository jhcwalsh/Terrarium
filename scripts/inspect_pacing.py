"""Print the pacing table and the curves it implies (WI-I6-1 inspect surface).

Run:  uv run python scripts/inspect_pacing.py

The owner-facing view of ``mappings/pacing-parameters-v1.0.yaml``: per
sleeve, the parameters, the implied annual distribution rate by age (calm,
and at the 2022-trough stress multiplier for context), and the call
schedule. Edit the YAML, run this, and the consequence of the edit is on
the screen before anything else moves. Deterministic; ASCII only.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ah.port.cashflow_tier1 import f_dist

_REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = _REPO_ROOT / "mappings" / "pacing-parameters-v1.0.yaml"
STRESS_2022 = {"dd": 0.2484, "spread_ratio": 1.18}  # the replay's trough states


def main() -> None:
    table = yaml.safe_load(ARTIFACT.read_text("utf-8"))
    print(f"pacing table {table['artifact_version']} (approved {table['approved']})")
    print(f"drift guard: {table['drift_guard']}")
    stress_mult = f_dist(STRESS_2022["dd"], STRESS_2022["spread_ratio"])
    for sleeve, row in table["sleeves"].items():
        y, b, life = row["yield_rate"], row["bow"], row["contractual_life_years"]
        print(f"\n{sleeve}: Y={y} B={b} L={life}y  rc_curve={row['rc_curve']}")
        print("  age | dist %/yr calm | at 2022-trough stress")
        for age in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
            calm = y * (age / life) ** b
            print(f"  {age:3d} | {calm:13.1%} | {calm * stress_mult:9.1%}")
        print(
            f"  (terminal liquidation at age >= {life}; stress multiplier "
            f"{stress_mult:.3f} = f_dist at the 2022 trough)"
        )
    print("\nopen questions:")
    for q in table["open_questions"]:
        print(f"  {q['id']}: {q['question'].strip().splitlines()[0]} ...")


if __name__ == "__main__":
    main()
