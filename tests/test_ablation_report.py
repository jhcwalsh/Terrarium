"""WP2.10 acceptance: ``ABLATION.md`` is GENERATED, never hand-assembled.

The plan's acceptance wording is "tables generated, not hand-assembled". The test
of that is reproducibility: the document must be a pure function of the stored
grid artifacts. These tests build a small synthetic grid on disk, render it twice,
and assert byte-identity -- and assert that changing an artifact changes the
document, so the first assertion is not satisfied by a constant.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

from test_ablation import make_report  # type: ignore[import-not-found]  # noqa: E402


def _load_builder():
    path = _REPO_ROOT / "scripts" / "build_ablation_report.py"
    spec = importlib.util.spec_from_file_location("build_ablation_report", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_ablation_report"] = module
    spec.loader.exec_module(module)
    return module


builder = _load_builder()

from ah.gen import systems  # noqa: E402


def _summary(cell_id, letter, system_id, seed_index, sample_seed, train_seed, n_fail=0):
    return {
        "cell_id": cell_id,
        "letter": letter,
        "system_id": system_id,
        "seed_index": seed_index,
        "sample_seed": sample_seed,
        "train_seed": train_seed,
        "family": "flow" if train_seed is not None else None,
        "generator_id": system_id,
        "checkpoint_hash": None if train_seed is None else "a" * 64,
        "config_hash": None if train_seed is None else "cfg:1234",
        "vintage_id": "2026-07-26.1",
        "n_paths": 1024,
        "months": 120,
        "criterion_bearing": True,
        "prereg_verified": True,
        "prereg_digest": "sha256:x",
        "passed_unfiltered": n_fail == 0,
        "unfiltered": {"n_enforce": 5, "n_enforce_failures": n_fail, "enforce_results": []},
        "filtered": {"n_enforce": 5, "n_enforce_failures": 0, "enforce_results": []},
        "system_description": "synthetic",
        "waypoints_bound": True,
        "reconciliation_applied": True,
        "climate_layer": "simulated",
        "layer_artifacts": {},
        "residual_model": None,
        "cb_contract_fingerprint": "f" * 64,
        "n_rejections": 102,
        "support_unfiltered": {
            "extrapolation_share_mean": 0.11,
            "n_flagged_off_support": 3,
            "regime_freq_tv_mean": 0.2,
        },
        "reconciliation_unfiltered": {
            "n_decades": 1024,
            "per_factor": {
                "cpi": {
                    "variant": "proportional_via_log",
                    "mean_abs_adjustment_p50": 0.1,
                    "mean_abs_adjustment_p90": 0.2,
                    "mean_abs_adjustment_max": 0.5,
                    "n_flagged_decades": 7,
                }
            },
        },
        "waypoint_tolerance_unfiltered": {"all_ok": True},
        "sampler_fallbacks": {},
        "block_sampler": "Synthetic",
        "block_sampler_batch": 128,
        "block_sampler_device": "cuda",
        "timings": {
            "build_s": 1.0,
            "assemble_unfiltered_s": 2.0,
            "assemble_filtered_s": 3.0,
            "battery_s": 4.0,
            "total_s": 10.0,
        },
    }


@pytest.fixture
def grid_root(tmp_path: Path) -> Path:
    """A two-system, three-seed synthetic grid on disk."""
    root = tmp_path / "wp210"
    cells = root / "cells"
    cells.mkdir(parents=True)
    plan = [
        ("E", "bootstrap-v1", None, (5.0, 5.1, 4.9)),
        ("D", "hier-flow-v1", 20260728, (4.0, 4.2, 3.8)),
    ]
    for letter, system_id, train_base, elics in plan:
        for k, elic in enumerate(elics):
            cell_id = f"{letter}:{system_id}:{k}"
            slug = f"{letter}-{system_id}-s{k}"
            d = cells / slug
            d.mkdir()
            report = make_report(elicitability=(elic, elic + 0.5, elic - 0.5))
            (d / "battery.json").write_text(json.dumps(report), "utf-8")
            (d / "summary.json").write_text(
                json.dumps(
                    _summary(
                        cell_id,
                        letter,
                        system_id,
                        k,
                        20260727 + 7919 * k,
                        None if train_base is None else train_base + 7919 * k,
                    )
                ),
                "utf-8",
            )
    (root / "grid.json").write_text(
        json.dumps(
            {
                "n_paths": 1024,
                "months": 120,
                "vintage_id": "2026-07-26.1",
                "reference_seed": 20260726,
                "n_resamples": 1000,
                "level": 0.9,
                "block_length": 120,
                "block_batch": 128,
                "sampler_device": "cuda",
                "cells": [],
                "failures": [],
            }
        ),
        "utf-8",
    )
    (root / "historical-strategy-returns.json").write_text(
        json.dumps(
            {
                sid: {
                    "dates": [f"{1962 + i // 12:04d}-{i % 12 + 1:02d}-01" for i in range(720)],
                    "values": [0.004 * ((i % 17) - 8) for i in range(720)],
                }
                for sid in ("sixty_forty", "momentum", "carry")
            }
            | {"eqw_factors": None, "endowment_proxy": None}
        ),
        "utf-8",
    )
    return root


PREREG = _REPO_ROOT / "pre-registration.yaml"


def test_the_document_is_reproducible_from_the_artifacts(grid_root: Path) -> None:
    """Acceptance: generated, not hand-assembled."""
    first = builder.render(builder.build(grid_root, PREREG))
    second = builder.render(builder.build(grid_root, PREREG))
    assert first == second
    assert first.startswith("# ABLATION.md")


def test_the_document_changes_when_an_artifact_changes(grid_root: Path) -> None:
    """...and the reproducibility above is not the reproducibility of a constant."""
    before = builder.render(builder.build(grid_root, PREREG))
    target = grid_root / "cells" / "D-hier-flow-v1-s0" / "battery.json"
    target.write_text(json.dumps(make_report(elicitability=(99.0, 99.0, 99.0))), "utf-8")
    after = builder.render(builder.build(grid_root, PREREG))
    assert after != before
    assert "99.0" in after


def test_the_document_carries_every_sealed_rule_input(grid_root: Path) -> None:
    doc = builder.build(grid_root, PREREG)
    text = builder.render(doc)
    for heading in (
        "Clause (i)",
        "Clause (ii)",
        "Head-to-head against `bootstrap-v1`",
        "Benchmark draw-span bias",
        "Clauses (2)-(4)",
        "Criterion-bearing status",
        "Conditional tier -- REPORTED, NOT GATING",
        "Cross-seed dispersion convention",
    ):
        assert heading in text, heading
    entry = doc["head_to_head"]["systems"]["hier-flow-v1"]
    assert len(entry["per_seed"]) == 3
    pooled = entry["pooled_full_sample"]
    assert set(pooled) >= {
        "mean_d",
        "sd_d_ddof1",
        "mean_is_negative",
        "abs_mean_exceeds_sd",
        "pooled_beat",
    }
    assert "pooled_restricted_1990_2020" in entry


def test_the_comparison_set_named_in_the_document_is_the_sealed_one(grid_root: Path) -> None:
    doc = builder.build(grid_root, PREREG)
    assert doc["comparison_set"]["strategy_ids"] == ["sixty_forty", "momentum", "carry"]
    assert sorted(doc["comparison_set"]["excluded_strategy_ids"]) == [
        "endowment_proxy",
        "eqw_factors",
    ]


def test_the_restricted_window_actually_narrows_the_realization_sample(
    grid_root: Path,
) -> None:
    doc = builder.build(grid_root, PREREG)
    r = doc["restricted"]
    assert r["computable"] is True
    for sid in ("sixty_forty", "momentum", "carry"):
        assert r["n_realizations_restricted"][sid] < r["n_realizations_full"][sid]
        assert r["n_realizations_restricted"][sid] == 372  # 1990-01..2020-12
    # a restricted mean genuinely differs from the full-sample mean
    any_cell = next(iter(r["per_cell"].values()))
    assert any_cell["mean"] != pytest.approx(any_cell["full_sample_mean"])


def test_the_document_names_the_untested_arms(grid_root: Path) -> None:
    text = builder.render(builder.build(grid_root, PREREG))
    for system_id in systems.UNTESTED_ARMS:
        assert system_id in text


def test_the_builder_refuses_an_empty_grid(tmp_path: Path) -> None:
    (tmp_path / "cells").mkdir(parents=True)
    with pytest.raises(SystemExit, match="no completed cells"):
        builder.build(tmp_path, PREREG)
