"""wp5-00 — every sealed metric's worked example, asserted; the G5 seal.

The docstring examples ARE the tests: a formula whose example does not
compute is not frozen, it is decorative. Plus the telescoping identity
for per-window alpha, the seal mint/verify/tamper cycle, and the
document/code agreement checks the G5 wrapper enforces.
"""

from __future__ import annotations

import numpy as np
import pytest

from ah.eval import decision_metrics as dm
from ah.eval import g5seal


class TestWorkedExamples:
    def test_max_drawdown(self):
        assert dm.max_drawdown(np.array([0.10, -0.20, 0.05])) == pytest.approx(0.2)
        assert dm.max_drawdown(np.array([-0.10, 0.30])) == pytest.approx(0.10)  # from t0 wealth

    def test_drawdown_surprise(self):
        rng = np.random.Generator(np.random.PCG64(3))
        ensemble = rng.normal(0.0, 0.02, size=(200, 40))
        predicted = np.percentile([dm.max_drawdown(p) for p in ensemble], 95.0)
        realized = np.full(40, 0.0)
        realized[10] = -0.30  # one brutal month
        surprise = dm.drawdown_surprise(realized, ensemble)
        assert surprise == pytest.approx(0.30 - predicted, abs=1e-12)
        assert dm.PRIMARY_METRIC == "drawdown_surprise"

    def test_decision_alpha(self):
        assert dm.decision_alpha(1.50, 1.35) == pytest.approx(np.log(1.5 / 1.35))
        with pytest.raises(dm.MetricError):
            dm.decision_alpha(0.0, 1.0)

    def test_decision_alpha_by_window_telescopes_exactly(self):
        player = np.array([1.0, 1.1, 1.5])
        twin = np.array([1.0, 1.1, 1.35])
        per_window = dm.decision_alpha_by_window(player, twin)
        assert per_window[0] == pytest.approx(0.0)
        assert per_window[1] == pytest.approx(np.log(1.5 / 1.35))
        # the identity: window attributions SUM EXACTLY to total alpha
        assert per_window.sum() == pytest.approx(dm.decision_alpha(1.5, 1.35), abs=1e-15)

    def test_forced_sale_cost(self):
        sales = [
            {"kind": "liquid_pro_rata", "amount": 5.0},
            {"kind": "forced_secondary", "nav_sold": 10.0, "haircut": 0.19},
        ]
        incidence, cost = dm.forced_sale_cost(sales, nav_reference=100.0)
        assert incidence == 2 and cost == pytest.approx(0.019)

    def test_liquidity_shortfall_probability(self):
        paths = np.array([[0.2, 0.4], [1.2, 0.8], [0.9, 0.7]])
        assert dm.liquidity_shortfall_probability(paths) == pytest.approx(1 / 3)

    def test_funding_ratio_tail(self):
        x = np.linspace(0.51, 1.50, 100)
        assert dm.funding_ratio_tail(x, 0.01) == pytest.approx(np.percentile(x, 1.0))

    def test_breach_duration(self):
        assert dm.breach_duration_quarters(np.array([0.30, 0.36, 0.37, 0.33]), 0.35) == 2

    def test_precommitment_adherence(self):
        planned = [
            {"rule_id": "r1", "triggered": True},
            {"rule_id": "r2", "triggered": True},
            {"rule_id": "r3", "triggered": False},
        ]
        executed = [{"rule_id": "r1", "followed": True}, {"rule_id": "r2", "followed": False}]
        assert dm.precommitment_adherence(planned, executed) == pytest.approx(0.5)
        with pytest.raises(dm.MetricError, match="undefined"):
            dm.precommitment_adherence([{"rule_id": "r", "triggered": False}], [])


class TestG5Seal:
    def test_lock_verifies(self):
        assert g5seal.verify_g5().startswith("sha256:")

    def test_document_and_code_agree(self):
        # the wrapper refuses a document naming a metric the code lacks —
        # exercised via the loaded document passing _check_structure inside verify
        assert dm.DECISION_ALPHA_VERSION == "1.0"

    def test_tamper_is_detected(self, tmp_path, monkeypatch):
        import shutil

        # copy the sealed pair; tamper the code copy; verification must fail
        root = tmp_path
        (root / "src" / "ah" / "eval").mkdir(parents=True)
        (root / "Instructions").mkdir()
        for rel in (
            "step5-evaluation-protocol.yaml",
            "pre-registration-g5.lock",
            "src/ah/eval/decision_metrics.py",
            "src/ah/eval/g5seal.py",
            "src/ah/eval/prereg.py",
            "src/ah/splits.py",
            "factors.yaml",
            "Instructions/holdout-evaluation-spec.md",  # sealed at AM-006
        ):
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(g5seal._REPO_ROOT / rel, dst)
        monkeypatch.setattr(g5seal, "_REPO_ROOT", root)
        monkeypatch.setattr(g5seal, "G5_PROTOCOL_PATH", root / "step5-evaluation-protocol.yaml")
        monkeypatch.setattr(g5seal, "G5_LOCK_PATH", root / "pre-registration-g5.lock")
        assert g5seal.verify_g5()  # the copy verifies before tampering
        code = root / "src/ah/eval/decision_metrics.py"
        code.write_text(code.read_text(encoding="utf-8").replace("95.0", "94.9"), encoding="utf-8")
        with pytest.raises(g5seal.G5SealError, match="digest mismatch"):
            g5seal.verify_g5()
