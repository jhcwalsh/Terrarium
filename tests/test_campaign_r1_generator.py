"""Campaign R1 Track B: the compare/render step and the runner's plumbing.

The 3.5 h re-run itself never executes in tests — these pin the pure pieces:
cell planning, checkpoint-hash refusal, the comparison arithmetic, and the
report's not-a-gate guard header.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    """Load a scripts/ module by path (the test_prereg.py pattern — resolvable
    without putting scripts/ on pyright's import path)."""
    spec = importlib.util.spec_from_file_location(f"_{name}", ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


crc = _load_script("campaign_r1_compare")


def _per_seed_row(k: int, *, diff: float, beats: bool = True) -> dict:
    return {
        "seed_index": k,
        "challenger_mean_elicitability": -2.5 + diff,
        "benchmark_mean_elicitability": -2.2,
        "difference": diff,
        "challenger_band_exceedance": 12,
        "benchmark_band_exceedance": 13,
        "beats_this_seed": beats,
    }


def _doc(diffs: list[float], *, beats: bool = True) -> dict:
    return {
        "per_seed": [_per_seed_row(k, diff=d, beats=beats) for k, d in enumerate(diffs)],
        "pooled": {
            "mean_d": sum(diffs) / len(diffs),
            "sd_d_ddof1": 0.02,
            "pooled_beat": beats,
        },
    }


def test_compare_flags_the_drift_and_keeps_the_identical():
    baseline = _doc([-0.34, -0.30])
    rerun = _doc([-0.34, -0.25])  # seed 1 drifted, seed 0 identical
    rows = crc.compare_cells(baseline, rerun)
    diff_rows = [r for r in rows if r["metric"].startswith("difference")]
    assert diff_rows[0]["delta"] == pytest.approx(0.0)
    assert diff_rows[1]["delta"] == pytest.approx(0.05)


def test_compare_refuses_a_seed_with_no_baseline():
    baseline = _doc([-0.34])
    rerun = _doc([-0.34, -0.30])
    with pytest.raises(SystemExit, match="no recorded baseline"):
        crc.compare_cells(baseline, rerun)


def test_render_pins_the_not_a_gate_header():
    baseline = _doc([-0.34, -0.30])
    rerun = _doc([-0.33, -0.29])
    rows = crc.compare_cells(baseline, rerun)
    text = crc.render_markdown(
        rows,
        vintage="2026-08-07.5",
        baseline_vintage="2026-08-02.4",
        baseline_verdict="PROMOTE",
        rerun_pooled=rerun["pooled"],
        baseline_pooled=baseline["pooled"],
    )
    assert "not a gate" in text.lower()
    assert "holdout" in text.lower() and "spent" in text.lower()
    assert "hier-flow-v1" in text  # the standing caveat carries forward
    assert "band" in text.lower() and "exceedance" in text.lower()
    assert "2026-08-07.5" in text and "2026-08-02.4" in text
    text.encode("ascii")


def test_render_carries_findings_when_given():
    baseline = _doc([-0.34])
    rerun = _doc([-0.34])
    text = crc.render_markdown(
        crc.compare_cells(baseline, rerun),
        vintage="v-new",
        baseline_vintage="v-old",
        baseline_verdict="PROMOTE",
        rerun_pooled=rerun["pooled"],
        baseline_pooled=baseline["pooled"],
        findings=["the finding text"],
    )
    assert "## Findings" in text and "the finding text" in text


def test_generator_report_is_committed_with_the_findings():
    """Written after the real re-run: the report must exist, carry the guard
    header, and state the three findings — bit-identical grading, the
    trailing-edge explanation, and the sealed check's refusal."""
    path = ROOT / "docs" / "data" / "CAMPAIGN-R1-GENERATOR.md"
    assert path.exists(), "run scripts/campaign_r1_generator.py --phase report"
    text = path.read_text(encoding="utf-8")
    assert "not a gate" in text.lower()
    assert "BIT-IDENTICAL" in text
    assert "train+validation boundary" in text
    assert "REFUSED" in text and "criterion-bearing" in text
    assert "2026-08-07.5" in text and "2026-08-02.4" in text


def test_runner_plans_exactly_the_six_campaign_cells():
    crg = _load_script("campaign_r1_generator")

    cells = crg.plan_rerun_cells()
    assert len(cells) == 6
    assert {c.system_id for c in cells} == {"bootstrap-v1", "hier-flow-v1"}
    assert sorted(c.seed_index for c in cells if c.system_id == "hier-flow-v1") == [0, 1, 2]


def test_runner_refuses_a_checkpoint_hash_mismatch():
    crg = _load_script("campaign_r1_generator")

    manifest = {"flow:0": {"checkpoint": "x/checkpoint.pt", "checkpoint_hash": "aaaa"}}
    with pytest.raises(SystemExit, match="hash"):
        crg.verify_checkpoint_entry(manifest, "flow:0", actual_hash="bbbb")


def test_hub_serves_the_campaign_r1_generator_report():
    from ah.hub import DOCS

    rel, title, _ = DOCS["campaign-r1-generator"]
    assert rel == "docs/data/CAMPAIGN-R1-GENERATOR.md"
    assert "Campaign R1" in title
