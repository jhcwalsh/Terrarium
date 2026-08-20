"""wp3-00 — the G3-pre seal machinery and the draft document's shape.

One sealed-sentence-per-test, G2 style: the mint refuses until the owner flips
the flag after the W11 review; the document and the judged code agree on the
sleeve set exactly; phantoms in the seal scope are errors; a sealed byte moved
without an amendment is a verify failure.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from ah.eval import g3seal
from ah.eval import sleevetails as st

ROOT = Path(__file__).resolve().parents[1]
SEALED_AT = "2026-08-01T00:00:00"


class TestDraftDocument:
    def test_structural_check_passes_on_the_real_document(self):
        g3seal.structural_check(yaml.safe_load(g3seal.G3_PREREG_PATH.read_text("utf-8")))

    def test_dry_run_digest_is_deterministic(self):
        a = g3seal.seal_g3(sealed_at=SEALED_AT, dry_run=True)
        b = g3seal.seal_g3(sealed_at="2099-01-01T00:00:00", dry_run=True)
        assert a == b  # sealed_at is recorded, never hashed — the G2 convention

    def test_mint_and_verify_refuse_while_unsealed(self, tmp_path, monkeypatch):
        """The W11 review gate, mechanical: flipping `sealed` is the owner's act.
        Pinned on a draft COPY (the real document sealed on 2026-08-01), so the
        refusal behavior stays tested after the mint, not only before it."""
        draft = tmp_path / "pre-registration-g3.yaml"
        text = g3seal.G3_PREREG_PATH.read_text("utf-8").replace("sealed: true", "sealed: false", 1)
        draft.write_text(text, encoding="utf-8")
        shutil.copy(ROOT / "factors.yaml", tmp_path / "factors.yaml")
        monkeypatch.setattr(g3seal, "G3_PREREG_PATH", draft)
        monkeypatch.setattr(g3seal, "G3_LOCK_PATH", tmp_path / "pre-registration-g3.lock")
        with pytest.raises(g3seal.G3SealError, match="W11"):
            g3seal.seal_g3(sealed_at=SEALED_AT)
        assert not (tmp_path / "pre-registration-g3.lock").exists()
        with pytest.raises(g3seal.G3SealError, match="not sealed"):
            g3seal.verify_g3()

    def test_the_real_document_is_sealed_and_verifies(self):
        """Post-mint (2026-08-01): the lock exists and every sealed byte matches."""
        assert g3seal.verify_g3().startswith("sha256:")

    def test_document_and_judged_code_agree_on_the_sleeve_set(self):
        doc = yaml.safe_load(g3seal.G3_PREREG_PATH.read_text("utf-8"))
        assert set(doc["sleeve_tail_thresholds"]) == set(st.hf_sleeve_members())

    def test_every_seal_scope_entry_exists(self):
        doc = yaml.safe_load(g3seal.G3_PREREG_PATH.read_text("utf-8"))
        for rel in doc["seal_scope"]["hashed_files"]:
            assert (ROOT / rel).exists(), f"seal_scope names phantom '{rel}'"
        assert (ROOT / doc["provenance_script"]).exists()
        assert (ROOT / "docs" / "data" / "secondaries.md").exists()  # cited source


class TestShapeRefusals:
    def _doc(self) -> dict:
        return yaml.safe_load(g3seal.G3_PREREG_PATH.read_text("utf-8"))

    def test_missing_sleeve_is_named(self):
        doc = self._doc()
        doc["sleeve_tail_thresholds"].pop("hf_cta")
        with pytest.raises(g3seal.G3SealError, match="hf_cta"):
            g3seal.structural_check(doc)

    def test_severity_drift_is_named(self):
        doc = self._doc()
        doc["sleeve_tail_thresholds"]["hf_macro"]["var_95"]["severity"] = "report"
        with pytest.raises(g3seal.G3SealError, match=r"hf_macro\.var_95"):
            g3seal.structural_check(doc)

    def test_membership_drift_is_named(self):
        doc = self._doc()
        doc["sleeve_tail_thresholds"]["hf_rv"]["members"] = ["albourne.hf_cb_arb_ret_m"]
        with pytest.raises(g3seal.G3SealError, match="hf_rv"):
            g3seal.structural_check(doc)

    def test_missing_gate_rule_is_named(self):
        doc = self._doc()
        del doc["episode_2022_criteria"]["gate_rule"]
        with pytest.raises(g3seal.G3SealError, match="gate_rule"):
            g3seal.structural_check(doc)


class TestMintAndTamper:
    def test_mint_verify_tamper_cycle(self, tmp_path, monkeypatch):
        """On tmp copies: flip sealed -> mint -> verify OK -> move one sealed
        byte -> verify names the mismatch."""
        prereg = tmp_path / "pre-registration-g3.yaml"
        shutil.copy(g3seal.G3_PREREG_PATH, prereg)
        # prereg.seal resolves factor_manifest beside the document
        shutil.copy(ROOT / "factors.yaml", tmp_path / "factors.yaml")
        text = prereg.read_text("utf-8").replace("sealed: false", "sealed: true", 1)
        prereg.write_text(text, encoding="utf-8")
        lock = tmp_path / "pre-registration-g3.lock"
        monkeypatch.setattr(g3seal, "G3_PREREG_PATH", prereg)
        monkeypatch.setattr(g3seal, "G3_LOCK_PATH", lock)

        digest = g3seal.seal_g3(sealed_at=SEALED_AT)
        assert lock.exists()
        recorded = json.loads(lock.read_text("utf-8"))
        assert recorded["digest"] == digest
        assert g3seal.verify_g3() == digest

        prereg.write_text(prereg.read_text("utf-8").replace("K = 4", "K = 5", 1), encoding="utf-8")
        with pytest.raises(g3seal.G3SealError, match="mismatch"):
            g3seal.verify_g3()


class TestJudgedCode:
    def test_judge_inside_and_outside_and_nan(self):
        import numpy as np

        rng = np.random.default_rng(7)
        band = st.SleeveBand(
            sleeve_id="hf_macro",
            statistic="var_95",
            severity="enforce",
            point=0.03,
            lo=0.02,
            hi=0.05,
            threshold_min=0.0,
            threshold_max=0.10,
        )
        calm = rng.normal(0.005, 0.02, size=(8, 120))
        report = st.judge_sleeve("hf_macro", calm, [band])
        assert report["enforce_passed"] is True

        wild = rng.normal(-0.05, 0.30, size=(8, 120))  # var far above max
        report = st.judge_sleeve("hf_macro", wild, [band])
        assert report["enforce_passed"] is False

        with_nan = calm.copy()
        with_nan[0, 0] = np.nan
        report = st.judge_sleeve("hf_macro", with_nan, [band])
        assert report["enforce_passed"] is False  # NaN is a fail, never a pass

    def test_shapes_are_refused(self):
        import numpy as np

        with pytest.raises(st.SleeveTailsError, match="n_paths"):
            st.judge_sleeve("hf_macro", np.zeros(120), [])


class TestER14Amendment:
    def test_the_er14_amendment_declares_every_ratified_coefficient(self):
        """Ratified coefficients are hashed into the entry BEFORE the estimator
        runs (design SS7 item 14). An artifact whose numbers were not declared
        first is indistinguishable from a tuned one."""
        from ah.eval.prereg import load_amendments

        log = ROOT / "governance" / "amendment-log.yaml"
        entry = {a.amendment_id: a for a in load_amendments(log)}["AM-2026-08-18-001"]
        declared = entry.payload["ratified_coefficients"]
        assert declared["lambda_RE"] == 0.30 and declared["lambda_INFRA_default"] == 0.60
        assert len(declared) == 15
        assert entry.payload["extends"] == "AM-2026-08-15-001"


class TestER16Amendment:
    def test_the_er16_amendment_declares_the_chosen_coefficients(self):
        """The chosen-PE values (D-ER16-1) are declared in the entry itself,
        with the ratification, the superseded G3 digest, and the honest
        post_hoc flag -- same discipline as AM-2026-08-18-001: values that
        were not declared first are indistinguishable from tuned ones."""
        from ah.eval.prereg import load_amendments

        log = ROOT / "governance" / "amendment-log.yaml"
        entry = {a.amendment_id: a for a in load_amendments(log)}["AM-2026-08-19-001"]
        assert entry.payload["ratified_coefficients"] == {
            "alpha_quarterly": 0.007399,
            "equity_mkt": 1.2,
        }
        assert entry.payload["ratification"] == "D-ER16-1"
        assert entry.payload["artifact"] == "mappings/sleeve-mappings-v1.3.yaml"
        assert entry.payload["generator"] == "scripts/make_sleeve_mappings_v1_3.py"
        assert entry.payload["superseded_lock_digest"] == (
            "sha256:9d00930c4ee16a4880713333e39ee6d79fb03e06c8312679acf3cbca91d91705"
        )
        assert entry.post_hoc is True  # the measured plane was seen first

    def test_the_v13_pair_is_inside_the_g3_seal_scope(self):
        """The chosen artifact and its generator are hashed -- a chosen row
        that could move without an amendment would defeat the point of
        choosing it in the open."""
        doc = yaml.safe_load(g3seal.G3_PREREG_PATH.read_text("utf-8"))
        listed = doc["seal_scope"]["hashed_files"]
        assert "mappings/sleeve-mappings-v1.3.yaml" in listed
        assert "scripts/make_sleeve_mappings_v1_3.py" in listed
        # v1.2 stays sealed beside it as the measured record.
        assert "mappings/sleeve-mappings-v1.2.yaml" in listed
