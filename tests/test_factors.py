"""WP2.1b Task 1 acceptance: factor manifest with a block layer.

The block layer (STEP2-GENERATOR-PLAN / Instructions/WP2.1b-PRE-SEAL-PATCH.md Item 2)
makes a later jurisdiction addition (e.g. `uk`) an additive `block_addition` amendment
rather than a wholesale re-seal: existing per-block thresholds stay byte-identical.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ah.factors import FactorManifest, ManifestError, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_load_manifest_active_blocks_and_factors() -> None:
    manifest = load_manifest()
    assert manifest.active_blocks == ("global", "us")
    factors = manifest.active_factors()
    for f in (
        "equity_mkt",
        "smb",
        "hml",
        "mom",
        "equity_vol",
        "commodities",
        "ig_spread",
        "hy_spread",
    ):
        assert f in factors
    for f in ("policy_rate", "ust_2y", "ust_10y", "cpi", "hqm_curve", "funding_spread"):
        assert f in factors
    for f in ("bank_rate", "gilt_nominal_10y", "gilt_real_10y", "rpi", "cpi_uk"):
        assert f not in factors


def test_load_manifest_is_cached_by_identity() -> None:
    a = load_manifest()
    b = load_manifest()
    assert a is b


def test_block_of_known_and_unknown_factor() -> None:
    manifest = load_manifest()
    assert manifest.block_of("ust_2y") == "us"
    with pytest.raises(KeyError):
        manifest.block_of("nope")


def test_cross_block_pairs_on_real_manifest() -> None:
    manifest = load_manifest()
    assert manifest.cross_block_pairs() == (("global", "us"),)


def test_is_active() -> None:
    manifest = load_manifest()
    assert manifest.is_active("global") is True
    assert manifest.is_active("us") is True
    assert manifest.is_active("uk") is False


def test_active_block_absent_from_factor_blocks_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global, nonexistent]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_factor_duplicated_across_blocks_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n"
        "  global: [equity_mkt, cpi]\n"
        "  us: [cpi, ust_2y]\n"
        "active_blocks: [global, us]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_three_block_active_manifest_yields_deterministic_cross_pairs(tmp_path: Path) -> None:
    cfg = tmp_path / "factors.yaml"
    cfg.write_text(
        "factor_blocks:\n"
        "  global: [equity_mkt]\n"
        "  us: [ust_2y]\n"
        "  uk: [gilt_nominal_10y]\n"
        "active_blocks: [global, us, uk]\n",
        encoding="utf-8",
    )
    manifest = load_manifest(cfg)
    assert manifest.cross_block_pairs() == (
        ("global", "uk"),
        ("global", "us"),
        ("uk", "us"),
    )


def test_empty_block_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: []\n  us: [ust_2y]\nactive_blocks: [global, us]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_active_factors_deterministic_order(tmp_path: Path) -> None:
    cfg = tmp_path / "factors.yaml"
    cfg.write_text(
        "factor_blocks:\n"
        "  global: [b_factor, a_factor]\n"
        "  us: [z_factor]\n"
        "active_blocks: [global, us]\n",
        encoding="utf-8",
    )
    manifest = load_manifest(cfg)
    # block order (as declared in active_blocks), then declaration order within block.
    assert manifest.active_factors() == ("b_factor", "a_factor", "z_factor")


def test_manifest_is_frozen_dataclass() -> None:
    manifest = load_manifest()
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError, dataclass-generated
        manifest.active_blocks = ("global",)  # type: ignore[misc]


def test_load_manifest_default_path_is_repo_root_factors_yaml() -> None:
    manifest = load_manifest()
    assert isinstance(manifest, FactorManifest)
    assert (ROOT / "factors.yaml").exists()
