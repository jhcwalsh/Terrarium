"""System F (har-masked) -- ruling K3, sealed at AM-2026-08-10-001.

The sealed text (``multi_seed_decision_rule.har_masked_ablation`` and
``ablation_systems.F``): system D's architecture, hyperparameters and seeds,
with ``equity_vol`` treated as MISSING before 1986-01. Under the sealed
complete-case ``block_draw_span_rule`` a month lacking any factor cannot enter
a block, so the masked TRAINING source is exactly the campaign source
restricted to dates >= the cutoff -- no missingness channel, no architecture
change (the architecture is sealed IDENTICAL).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import ah.gen.bootstrap as bs
import ah.gen.systems as systems
from ah.gen.joinery.waypoints import JoineryError


def _tiny_source(n_rows: int = 60, start: str = "1984-01-01") -> bs.BootstrapSource:
    dates = pd.date_range(start, periods=n_rows, freq="MS")
    rng = np.random.Generator(np.random.PCG64(7))
    values = rng.normal(0.0, 1.0, size=(n_rows, 3)) + 10.0
    return bs.BootstrapSource(
        factor_names=("a", "b", "c"),
        dates=dates,
        values=values,
        labels=tuple(["EXP"] * n_rows),
        ruleset_version="regime_ruleset_v1",
        vintage_id="test-v",
        active_blocks=("global",),
    )


class TestHarMaskedSource:
    def test_restricts_rows_to_the_cutoff_and_keeps_alignment(self):
        src = _tiny_source()
        masked = bs.har_masked_source_from(src)
        assert masked.dates[0] == pd.Timestamp(bs.HAR_MASK_CUTOFF)
        assert masked.dates[-1] == src.dates[-1]
        # alignment: the surviving rows are bit-identical to the tail of the original
        keep = src.dates >= pd.Timestamp(bs.HAR_MASK_CUTOFF)
        np.testing.assert_array_equal(masked.values, src.values[keep])
        assert masked.labels == tuple(np.asarray(src.labels)[keep])
        assert masked.factor_names == src.factor_names
        assert masked.vintage_id == src.vintage_id

    def test_cutoff_is_the_sealed_one(self):
        assert bs.HAR_MASK_CUTOFF == "1986-01-01"

    def test_a_source_entirely_before_the_cutoff_is_refused(self):
        src = _tiny_source(n_rows=12, start="1953-04-01")
        with pytest.raises(bs.BootstrapError):
            bs.har_masked_source_from(src)


class TestSystemFRegistration:
    def test_f_is_in_the_systems_table_as_sealed(self):
        rows = [r for r in systems.SYSTEMS if r.letter == "F"]
        assert len(rows) == 1
        row = rows[0]
        assert row.system_id == systems.SYSTEM_F_ID == "har-masked"
        assert row.neural is True
        assert row.family == "flow"

    def test_f_train_seeds_are_the_flow_seeds(self):
        """The sealed clause: identical architecture, hyperparameters AND SEEDS."""
        for k in range(3):
            assert systems.train_seed_for("har-masked", k) == systems.train_seed_for("flow", k)

    def test_build_refuses_without_a_manifest_entry(self, tmp_path, monkeypatch):
        """F has no WP2.9 primary checkpoint: EVERY index resolves through the
        committed manifest, and an absent entry is a refusal, not a fallback."""
        monkeypatch.setattr(
            systems, "seed_checkpoint_manifest_path", lambda: tmp_path / "absent.json"
        )
        with pytest.raises(JoineryError, match="manifest"):
            systems.build("har-masked", seed_index=0)


class TestHierFlowV2:
    """The campaign-3 D sampler (sealed ablation_systems.D: ONE sampler,
    hier-flow-v2). hier-flow-v1 freezes as the campaign-2 replay surface; the
    v2 id resolves ONLY through the campaign-3 manifest -- and so do the flow
    checkpoints B/C compose at the live campaign, because a silent fallback to
    the wp210 (campaign-2) manifest would evaluate campaign-3 cells on
    campaign-2 weights."""

    def test_v2_is_the_single_d_row(self):
        d_rows = [r for r in systems.SYSTEMS if r.letter == "D"]
        assert [r.system_id for r in d_rows] == [systems.SYSTEM_D_V2_ID]
        assert systems.SYSTEM_D_V2_ID == "hier-flow-v2"
        assert d_rows[0].family == "flow"

    def test_v2_build_refuses_without_the_campaign3_manifest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            systems, "seed_checkpoint_manifest_path", lambda: tmp_path / "absent.json"
        )
        with pytest.raises(JoineryError, match="manifest"):
            systems.build("hier-flow-v2", seed_index=0)

    def test_live_flow_resolution_never_falls_back_to_the_campaign2_manifest(
        self, tmp_path, monkeypatch
    ):
        """B/C at the live campaign resolve v2 weights; an absent campaign-3
        manifest is a refusal even though the wp210 manifest exists."""
        monkeypatch.setattr(
            systems, "seed_checkpoint_manifest_path", lambda: tmp_path / "absent.json"
        )
        with pytest.raises(JoineryError, match="manifest"):
            systems.build(systems.neural_rollout_id("flow"), seed_index=1)

    def test_the_campaign2_manifest_path_is_frozen_and_distinct(self):
        live = systems.seed_checkpoint_manifest_path()
        frozen = systems.campaign2_seed_checkpoint_manifest_path()
        assert frozen.name == "wp210-seed-checkpoints.json"
        assert live.name == "campaign3-seed-checkpoints.json"
        assert live != frozen

    def test_diffusion_still_resolves_the_campaign2_primary(self):
        """hier-diffusion does not race at campaign-3; its replay surface keeps
        resolving the campaign-2 pins exactly as before."""
        path, expected = systems._checkpoint_for("diffusion", 0)
        from ah.gen.blocks import diffusion as df

        assert path == Path(df.DEFAULT_CHECKPOINT)
        assert expected == df.PINNED_CHECKPOINT_SHA256
