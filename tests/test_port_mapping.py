"""WP3.2 — the mapping artifact and its runtime applier.

The artifact exists with the declared shape and provenance; the applier is
bit-deterministic per (ensemble, seed), reproduces the artifact's residual
correlation, and the CTA sleeve is a warm-up-flat, RNG-free rule — never a
regression (DN-5 §3.4, pinned).
"""

from __future__ import annotations

import numpy as np
import pytest
import yaml

from ah.gen.base import AbsentLayer, Ensemble, EnsembleMeta
from ah.port import mapping as mp

FACTORS = ["equity_mkt", "smb", "hml", "mom", "ust_10y", "ust_2y", "ig_spread"]


def _ensemble(n_paths: int = 6, months: int = 120, seed: int = 5) -> Ensemble:
    rng = np.random.default_rng(seed)
    paths = np.empty((n_paths, months, len(FACTORS)))
    paths[:, :, 0] = rng.normal(0.006, 0.045, size=(n_paths, months))  # equity_mkt
    paths[:, :, 1] = rng.normal(0.0, 0.02, size=(n_paths, months))  # smb
    paths[:, :, 2] = rng.normal(0.0, 0.02, size=(n_paths, months))  # hml
    paths[:, :, 3] = rng.normal(0.003, 0.03, size=(n_paths, months))  # mom
    paths[:, :, 4] = 4.0 + np.cumsum(rng.normal(0, 0.08, size=(n_paths, months)), axis=1)
    paths[:, :, 5] = 3.5 + np.cumsum(rng.normal(0, 0.08, size=(n_paths, months)), axis=1)
    paths[:, :, 6] = 1.2 + np.cumsum(rng.normal(0, 0.04, size=(n_paths, months)), axis=1)
    meta = EnsembleMeta(
        generator_id="test-gen",
        vintage_id="test",
        seed=seed,
        n_paths=n_paths,
        months=months,
        conditioning={},
        active_blocks=("global", "us"),
    )
    return Ensemble(
        paths=paths,
        factor_names=list(FACTORS),
        meta=meta,
        regimes=AbsentLayer("test double"),
        slow_states=AbsentLayer("test double"),
    )


class TestArtifact:
    def test_artifact_exists_with_declared_shape_and_provenance(self):
        """re-pinned under map-2026.08.2 (AM-2026-08-12-001).
        Re-pinned again under map-2026.08.3 (ER-14 close-out, D-ER14-2,
        2026-08-18): ARTIFACT_PATH moved to sleeve-mappings-v1.2.yaml (C1
        extended to pm_buyout, F5a/F5b/F5c); HF rows verbatim."""
        doc = mp.load_artifact()
        assert doc["mapping_version"] == "map-2026.08.3"
        assert doc["desmoothing_method"].startswith("glm_ma")  # SM-10 pairing
        assert set(doc["sleeves"]) == {
            "hf_credit",
            "hf_equity_ls",
            "hf_event",
            "hf_macro",
            "hf_multi",
            "hf_rv",
        }
        for spec in doc["sleeves"].values():
            assert set(spec["loadings"]) == set(doc["regressors"])
            assert spec["residual_sigma_annual"] > 0
        assert "hy_spread" in doc["structural_omissions"]  # named, never silent

    def test_structural_zeros_hold_in_the_artifact(self):
        doc = mp.load_artifact()
        assert doc["sleeves"]["hf_rv"]["loadings"]["equity_mkt"] == 0.0  # DN-5 zero
        assert doc["sleeves"]["hf_event"]["loadings"]["d_ig"] <= 0.0  # flipped sign


class TestApplier:
    def test_deterministic_and_shaped(self):
        ens = _ensemble()
        a = mp.sleeve_returns(ens, seed=123)
        b = mp.sleeve_returns(ens, seed=123)
        assert set(a) == {
            "hf_credit",
            "hf_cta",
            "hf_equity_ls",
            "hf_event",
            "hf_macro",
            "hf_multi",
            "hf_rv",
        }
        for name in a:
            assert a[name].shape == (6, 120)
            np.testing.assert_array_equal(a[name], b[name])
        c = mp.sleeve_returns(ens, seed=124)
        assert not np.array_equal(a["hf_event"], c["hf_event"])  # seed moves residuals

    def test_residual_correlation_is_reproduced(self):
        """With loadings removed, cross-sleeve shocks must carry the artifact's
        correlation (checked on a large panel, loose tolerance)."""
        ens = _ensemble(n_paths=40, months=240, seed=9)
        out = mp.sleeve_returns(ens, seed=77)
        doc = mp.load_artifact()
        slabs = mp._regressor_slabs(ens)
        regressors = list(doc["regressors"])

        def residual(name: str) -> np.ndarray:
            spec = doc["sleeves"][name]
            beta = np.array([float(spec["loadings"][r]) for r in regressors])
            x = np.stack([slabs[r] for r in regressors], axis=-1)
            return (out[name] - float(spec["alpha_monthly"]) - x @ beta).ravel()

        want = float(doc["residual_correlation"]["hf_event"]["hf_credit"])
        got = float(np.corrcoef(residual("hf_event"), residual("hf_credit"))[0, 1])
        assert got == pytest.approx(want, abs=0.05)

    def test_cta_is_a_rule_flat_in_warmup_and_rng_free(self):
        ens = _ensemble()
        out = mp.sleeve_returns(ens, seed=1)["hf_cta"]
        assert np.all(out[:, :12] == 0.0)  # warm-up: no signal, no position
        other = mp.sleeve_returns(ens, seed=999)["hf_cta"]
        np.testing.assert_array_equal(out, other)  # seed-independent: a rule

    def test_missing_factor_is_loud(self):
        ens = _ensemble()
        ens.factor_names[0] = "not_equity"
        with pytest.raises(Exception, match="equity_mkt"):
            mp.sleeve_returns(ens, seed=1)

    def test_artifact_and_report_agree_on_version(self):
        """Re-pinned under map-2026.08.3 (ER-14 close-out, D-ER14-2,
        2026-08-18): the runtime's report moved with ARTIFACT_PATH, from
        MAPPINGS.md (v1.1) to MAPPINGS-v1.2.md."""
        text = (mp._REPO_ROOT / "MAPPINGS-v1.2.md").read_text(encoding="utf-8")
        assert yaml.safe_load(mp.ARTIFACT_PATH.read_text("utf-8"))["mapping_version"] in text


def test_runtime_consumes_the_v12_artifact():
    """AM-2026-08-12-001: the runtime's default artifact is v1.1. Written
    FAILING against v1.0 before ARTIFACT_PATH moved.
    Re-pinned under map-2026.08.3 (ER-14 close-out, D-ER14-2, 2026-08-18):
    ARTIFACT_PATH moved to sleeve-mappings-v1.2.yaml (C1 extended to
    pm_buyout, F5a/F5b/F5c); pm_direct_lending's route is v1.1 verbatim
    (F5b: no coefficient moves)."""
    from ah.port.mapping import load_artifact

    doc = load_artifact()
    assert doc["mapping_version"] == "map-2026.08.3"
    assert doc["pm_sleeves"]["pm_direct_lending"]["route"] == "bdc-anchor*0.5"
