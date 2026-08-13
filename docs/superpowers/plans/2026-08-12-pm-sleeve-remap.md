# PM Sleeve Re-Mapping (v1.1: Lagged Sum-Beta) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-estimate the private-market sleeve loadings with a lagged (Dimson
sum-beta) component so the appraisal lag stops leaking market beta into alpha,
adopt the new artifact in the product surface via a G3-lock amendment, and
fence the 1974 world's leaderboard from the old formulas.

**Architecture:** The sealed v1.0 estimator and artifact are never edited. A
new self-contained estimator (`scripts/estimate_sleeve_mappings_v1_1.py`)
re-fits ONLY the nine PM sleeves — de-smoothed composites regressed on
contemporaneous + lagged equity, loadings written as the summed beta — and
copies the seven HF rows verbatim from v1.0. Direct lending, whose asset-level
data the v1.0 report declared unusable, is instead anchored to the
market-priced Cliffwater BDC index with a declared de-leverage factor. The new
script + artifact join the G3 lock by amendment `AM-2026-08-12-001` (post_hoc:
true, disclosed). `ah/port/mapping.py` (unsealed, the "defendant") bumps its
`ARTIFACT_PATH` to v1.1; the 1974 preset moves to a new `world_id` block so
scores under the two formula sets can never share a leaderboard row.

**Tech Stack:** Python 3.12 / numpy / pandas / scipy `lsq_linear` / yaml;
DuckDB catalog vintage `2026-08-10.1` (verified present locally with all nine
`albourne.pm_*_ret_q` composites and `cliffwater.bdc_ret_m`, 262 monthly rows).

## Global Constraints

- **Sealed files are read-only**: `scripts/estimate_sleeve_mappings.py`,
  `mappings/sleeve-mappings-v1.0.yaml`, everything else in any lock's
  `hashed_files`. The three locks share files — after ANY sealed-doc edit,
  verify all three digests (memory: `two-seals-check-both-scopes`).
- **The amendment is written and committed BEFORE the estimation runs.** The
  declared parameters (lag rule, BDC de-lever factor, floor rule) are fixed in
  the design note + amendment first; the numbers land after. post_hoc is
  `true` either way (the trigger was a product finding) — the pre-declared
  procedure is what keeps this from being tuning.
- **Determinism**: the estimator is deterministic (no RNG); `train_val()` only.
- **No network in tests**; fixtures regenerate offline.
- **ASCII only** in anything echoed to the console by CLI/scripts.
- **Never weaken a test**; re-pin goldens only with the new-number rationale in
  the commit body.
- Branch `pm-remap-01-sum-beta`; merge `--no-ff` only after
  `uv run python scripts/check_gate.py <gate-log>` stamps `.gate-ok`
  (gate log read as its OWN step); plain push after green merge.
- Commits end with the standard trailers (Co-Authored-By + Claude-Session).

## Declared parameters (the amendment's substance — owner approves via this plan)

| Parameter | Value | Why |
|---|---|---|
| Lagged regressor | `equity_mkt` only, quarterly lags | dof discipline on 60–146-quarter panels; equity carries the appraisal-lag signal |
| Lag rule | n ≥ 80 quarters → 4 lags; 40 ≤ n < 80 → 2 lags; n < 40 → estimation refused, DN-5 prior adopted verbatim | pre-declared so lag count can't be tuned to taste |
| Reported loading | Dimson sum: contemporaneous + all lag betas, one number | runtime applies loadings to TRUE factors where no lag belongs; the lag lives only in the observation process |
| Bounds/priors on lags | each lag bounded `[0, inf)`, ridge prior 0; contemporaneous keeps its DN-5 prior | shrinkage target stays the recorded prior |
| `pm_direct_lending` | betas + residual sigma estimated on `cliffwater.bdc_ret_m` (monthly, market-priced), then multiplied by `bdc_delever_factor = 0.5`; alpha from the albourne DL composite mean net of those betas | v1.0's own report: the asset-level fit "should not be used"; BDCs are ~1x levered listed vehicles, hence the declared 0.5 |
| HF sleeves | copied verbatim from v1.0 | out of scope; unchanged inputs to the G1 record |
| De-smoothing | unchanged from v1.0 (family-routed Geltner/GLM) | the lag terms mop up what the operator misses; changing both at once would be unattributable |
| `residual_correlation`, `cta_rule` | copied verbatim from v1.0 | HF-only structures |
| Artifact/version | `mappings/sleeve-mappings-v1.1.yaml`, `mapping_version: map-2026.08.2` | append-only; v1.0 stays sealed as the G1-era record |
| World fence | `stagflation_1974` world_id `…601` → `…602` | scores under different formulas never share a leaderboard row |

**What this amendment does NOT do:** it does not re-score the G1-completion
gate (the FAIL stands, recorded under v1.0), does not touch the toy engine's
`_reported_marks` defect (a separate, later WP with its own
`TOY_ENGINE_VERSION` bump), and does not change `GEN_PLAY_ALPHA_VERSION` (the
alpha *definition* is unchanged; the world_id move is the fence).

## File map

- Create: `docs/superpowers/specs/2026-08-12-pm-remap-design.md` (pre-declaration)
- Create: `scripts/estimate_sleeve_mappings_v1_1.py` (new sealed judge, self-contained)
- Create: `tests/test_estimate_v11.py` (unit tests via importlib, like `test_gate_guard.py`)
- Create: `mappings/sleeve-mappings-v1.1.yaml` + `MAPPINGS-v1.1.md` (run output)
- Modify: `governance/amendment-log.yaml` (AM-2026-08-12-001)
- Modify: `pre-registration-g3.yaml` seal_scope + `pre-registration-g3.lock` (reseal)
- Modify: `src/ah/port/mapping.py:28` (ARTIFACT_PATH → v1.1)
- Modify: `src/ah/presets/stagflation_1974.json` (world_id …602)
- Regenerate: `app/fixtures/gen.bundle.gz`; re-pin `tests/test_gen_adapter.py`,
  `tests/test_port_mapping.py`, `tests/test_bundle.py` goldens as needed
- Modify: `CHANGELOG.md`

---

### Task 1: Design note + amendment entry (the pre-declaration commit)

**Files:**
- Create: `docs/superpowers/specs/2026-08-12-pm-remap-design.md`
- Modify: `governance/amendment-log.yaml` (append entry)

**Interfaces:**
- Produces: the declared-parameters record that Task 2's code and Task 4's
  seal event cite. Nothing imports it; the estimator hard-codes the same
  values and Task 4's seal commit asserts they match.

- [ ] **Step 1: Write the design note** — contents: the two findings
  (reported-marks display defect noted-and-deferred; PM loadings under-beta'd
  with the MAPPINGS.md under-correction warning quoted), the declared
  parameters table copied verbatim from this plan, and the explicit
  non-goals (no G1 re-score, no engine change). One page.

- [ ] **Step 2: Append the amendment entry** to `governance/amendment-log.yaml`
  (match the existing entry style exactly — 2-space list indent, quoted date):

```yaml
- amendment_id: AM-2026-08-12-001
  date: '2026-08-12'
  payload:
    artifact: mappings/sleeve-mappings-v1.1.yaml
    estimator: scripts/estimate_sleeve_mappings_v1_1.py
    design_note: docs/superpowers/specs/2026-08-12-pm-remap-design.md
    declared_parameters:
      lagged_regressor: equity_mkt only; artifact loading is the Dimson sum
      lag_rule: {n_ge_80: 4, n_40_to_79: 2, n_lt_40: prior_adopted}
      bdc_anchor: {series: cliffwater.bdc_ret_m, delever_factor: 0.5,
        applies_to: pm_direct_lending, alpha_source: albourne_dl_composite}
      hf_sleeves: verbatim from v1.0
      desmoothing: unchanged from v1.0 (family-routed)
      world_fence: stagflation_1974 world_id -601 -> -602
    superseded_lock_digest: PENDING-TASK-4
  post_hoc: true
  rationale: >-
    PM sleeve loadings re-estimated with a lagged (Dimson sum-beta) component.
    TRIGGER, disclosed: a product-surface credibility finding on the 1974
    generated world (PE decade Sharpe 1.30; pe/pc/re visibly decoupled from
    public factors) -- the realized form of the warning MAPPINGS.md itself
    recorded at estimation time ("the de-smoother is under-correcting; the
    equity-beta shortfall sorts by how equity-like the sleeve is") and of its
    explicit instruction that pm_direct_lending "should not be used", which
    v1.0 adoption drove past without an owner decision. post_hoc TRUE: v1.0
    results were seen before this amendment. What keeps it honest: the
    procedure (lag rule, de-lever factor, floor rule) is declared in the
    design note and THIS entry before the v1.1 estimator ever runs; the
    G1-completion verdict is NOT re-scored and stands under v1.0; v1.1 is
    forward-only for the product surface and twin. The sealed v1.0 estimator
    and artifact are untouched; the v1.1 estimator and artifact join
    seal_scope in the commit that creates them (the AM-2026-08-01-001
    planned-arrival pattern). superseded_lock_digest is filled at the Task-4
    seal event in the same commit that reseals G3.
  type: protocol_change
```

- [ ] **Step 3: Run the amendment-log machine checks**

Run: `uv run pytest tests -k "amendment or seal_guard" -q`
Expected: PASS (entry is format-valid; no sealed file has changed yet so all
three lock digests still verify)

- [ ] **Step 4: Commit**

```bash
git checkout -b pm-remap-01-sum-beta
git add docs/superpowers/specs/2026-08-12-pm-remap-design.md governance/amendment-log.yaml
git commit -m "docs+governance: declare AM-2026-08-12-001 (PM sum-beta re-map) before estimation"
```

---

### Task 2: The v1.1 estimator, test-first

**Files:**
- Create: `tests/test_estimate_v11.py`
- Create: `scripts/estimate_sleeve_mappings_v1_1.py`

**Interfaces:**
- Consumes: `ah.data.catalog.Catalog`, `ah.splits.DataAccess`,
  `ah.data.desmooth.geltner_ar1/glm_ma`,
  `ah.eval.sleevetails.pm_sleeve_members/smoothing_family`,
  `ah.eval.panel.read_factor_frames`, `ah.factors.load_manifest` — all
  read-only imports of sealed machinery (importing does not edit).
- Produces: module-level pure functions `lag_count(n)`,
  `dimson_frame(x, n_lags)`, `fit_sum_beta(y, x, spec, n_lags)`,
  `delever(loadings, sigma, factor)`, `merge_artifact(v10_doc, pm_rows)`;
  `main()` writes `mappings/sleeve-mappings-v1.1.yaml` + `MAPPINGS-v1.1.md`.

- [ ] **Step 1: Write the failing tests** (load the script via importlib, the
  `test_gate_guard.py` pattern — scripts/ is not a package):

```python
"""AM-2026-08-12-001: the v1.1 PM estimator's pure functions.

The defect being fixed is the test: a contemporaneous-only regression on
appraisal-lagged observations understates beta; the Dimson sum recovers it.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "estimate_v11", _ROOT / "scripts" / "estimate_sleeve_mappings_v1_1.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_lag_count_follows_the_declared_rule():
    assert _mod.lag_count(125) == 4
    assert _mod.lag_count(80) == 4
    assert _mod.lag_count(60) == 2
    assert _mod.lag_count(40) == 2
    assert _mod.lag_count(39) == 0  # refused -> prior adopted


def test_dimson_frame_adds_lagged_equity_columns_only():
    idx = pd.date_range("2000-01-01", periods=10, freq="QS")
    x = pd.DataFrame({r: np.arange(10.0) for r in _mod.REGRESSORS}, index=idx)
    out = _mod.dimson_frame(x, 2)
    assert list(out.columns) == list(_mod.REGRESSORS) + [
        "equity_mkt_lag1", "equity_mkt_lag2"
    ]
    assert out["equity_mkt_lag1"].iloc[3] == x["equity_mkt"].iloc[2]
    assert len(out) == 8  # lagged rows dropped, never zero-filled


def test_sum_beta_recovers_beta_hidden_by_appraisal_lag():
    """The defect, synthesized: true beta 1.0, observations a (0.5, 0.3, 0.2)
    moving average of truth. Contemporaneous-only fit sees ~0.5; the summed
    Dimson betas must recover ~1.0."""
    rng = np.random.default_rng(7)
    n = 400
    f = rng.standard_normal(n) * 0.05
    true = 1.0 * f
    obs = 0.5 * true + 0.3 * np.roll(true, 1) + 0.2 * np.roll(true, 2)
    obs[:2] = true[:2]
    idx = pd.date_range("1950-01-01", periods=n, freq="QS")
    x = pd.DataFrame({r: np.zeros(n) for r in _mod.REGRESSORS}, index=idx)
    x["equity_mkt"] = f
    y = pd.Series(obs, index=idx)
    spec = {r: (0.0, 0.0, 0.0) for r in _mod.REGRESSORS}
    spec["equity_mkt"] = (0.0, float("inf"), 1.0)
    summed, _alpha, _resid, per_lag = _mod.fit_sum_beta(y, x, spec, n_lags=2)
    naive, _, _, _ = _mod.fit_sum_beta(y, x, spec, n_lags=0)
    assert naive[0] < 0.7          # the defect reproduced
    assert abs(summed[0] - 1.0) < 0.15  # the fix recovers it


def test_delever_scales_betas_and_sigma_not_alpha():
    loadings = {"equity_mkt": 0.8, "d_ig": -0.4, "smb": 0.0}
    out, sigma = _mod.delever(loadings, sigma=0.20, factor=0.5)
    assert out == {"equity_mkt": 0.4, "d_ig": -0.2, "smb": 0.0}
    assert sigma == 0.10


def test_merge_artifact_replaces_pm_rows_and_copies_hf_verbatim():
    v10 = {
        "mapping_version": "map-2026.08",
        "sleeves": {"hf_event": {"alpha_monthly": 0.001}},
        "pm_sleeves": {"pm_buyout": {"alpha_quarterly": 0.033}},
        "residual_correlation": {"hf_event": {"hf_event": 1.0}},
        "cta_rule": {"kind": "tsm_overlay"},
    }
    new_pm = {"pm_buyout": {"alpha_quarterly": 0.010, "loadings": {"equity_mkt": 1.1}}}
    out = _mod.merge_artifact(v10, new_pm)
    assert out["mapping_version"] == _mod.MAPPING_VERSION
    assert out["sleeves"] == v10["sleeves"]                      # verbatim
    assert out["residual_correlation"] == v10["residual_correlation"]
    assert out["cta_rule"] == v10["cta_rule"]
    assert out["pm_sleeves"]["pm_buyout"]["alpha_quarterly"] == 0.010
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_estimate_v11.py -q`
Expected: FAIL at import — the script file does not exist.

- [ ] **Step 3: Write the estimator.** Self-contained (the sealed v1.0 script
  cannot be edited and is not imported; shared logic is deliberately
  duplicated — a sealed judge must be readable alone):

```python
"""Estimate sleeve-mappings v1.1 (AM-2026-08-12-001): PM sleeves re-fit with
a lagged (Dimson sum-beta) equity component; HF rows verbatim from v1.0.

Run:  uv run python scripts/estimate_sleeve_mappings_v1_1.py

Declared BEFORE this ran (design note 2026-08-12-pm-remap-design.md):
* Lags on equity_mkt only. n>=80 quarters -> 4 lags; 40<=n<80 -> 2; n<40 ->
  estimation refused, the DN-5 prior row is adopted verbatim and recorded.
* The artifact loading is the SUM of contemporaneous+lag betas: runtime
  applies loadings to TRUE factors, where the appraisal lag does not belong.
* pm_direct_lending is anchored to cliffwater.bdc_ret_m (monthly, listed,
  marked to market): betas and residual sigma estimated there, then
  multiplied by BDC_DELEVER = 0.5 (declared; listed BDCs run ~1x leverage);
  alpha comes from the albourne DL composite mean net of those betas.
* De-smoothing, residual_correlation, cta_rule, HF sleeves: v1.0 verbatim.
Deterministic: no RNG anywhere; train+validation only.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import lsq_linear

from ah.data.catalog import Catalog
from ah.data.desmooth import geltner_ar1, glm_ma
from ah.eval.panel import read_factor_frames
from ah.eval.sleevetails import pm_sleeve_members, smoothing_family
from ah.factors import load_manifest
from ah.splits import DataAccess

_REPO_ROOT = Path(__file__).resolve().parents[1]

MAPPING_VERSION = "map-2026.08.2"
V10_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.0.yaml"
OUT_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.1.yaml"
REPORT_PATH = _REPO_ROOT / "MAPPINGS-v1.1.md"

REGRESSORS = ("equity_mkt", "smb", "hml", "mom", "d_level", "d_slope", "d_ig")
_RETURN_FACTORS = frozenset({"equity_mkt", "smb", "hml", "mom"})
RIDGE_SCALE = 0.5

BDC_SERIES = "cliffwater.bdc_ret_m"
BDC_DELEVER = 0.5
BDC_SLEEVE = "pm_direct_lending"


def lag_count(n: int) -> int:
    """The declared lag rule. 0 means: estimation refused, prior adopted."""
    if n >= 80:
        return 4
    if n >= 40:
        return 2
    return 0


def dimson_frame(x: pd.DataFrame, n_lags: int) -> pd.DataFrame:
    """Append equity_mkt lag columns; drop rows without a full lag history."""
    out = x.copy()
    for j in range(1, n_lags + 1):
        out[f"equity_mkt_lag{j}"] = out["equity_mkt"].shift(j)
    return out.dropna()


def fit_sum_beta(
    y: pd.Series,
    x: pd.DataFrame,
    spec: dict[str, tuple[float, float, float]],
    n_lags: int,
) -> tuple[np.ndarray, float, pd.Series, np.ndarray]:
    """Bounded ridge fit (v1.0's machinery) over the Dimson design.

    Returns (summed_betas_over_REGRESSORS, alpha, residuals, per_lag_betas).
    summed_betas[i] is the REGRESSORS[i] beta, with equity_mkt as the Dimson
    sum of the contemporaneous and all lag coefficients. Lags are bounded
    [0, inf) with ridge prior 0 — shrinkage never invents lag beta.
    """
    design_frame = dimson_frame(x, n_lags)
    joined = pd.concat([y.rename("y"), design_frame], axis=1, sort=True).dropna()
    yv = joined["y"].to_numpy()

    lag_cols = [f"equity_mkt_lag{j}" for j in range(1, n_lags + 1)]
    full_spec = dict(spec)
    for c in lag_cols:
        full_spec[c] = (0.0, float("inf"), 0.0)
    cols = list(REGRESSORS) + lag_cols
    free = [c for c in cols if not (full_spec[c][0] == 0.0 == full_spec[c][1])]

    design = joined[free].to_numpy()
    n, k = design.shape
    lo = np.array([full_spec[c][0] for c in free])
    hi = np.array([full_spec[c][1] for c in free])
    prior = np.array([full_spec[c][2] for c in free])

    y_c = yv - yv.mean()
    x_c = design - design.mean(axis=0)
    lam = RIDGE_SCALE * k / n
    scale = np.std(x_c, axis=0)
    scale[scale == 0.0] = 1.0
    aug_a = np.vstack([x_c, np.sqrt(lam * n) * np.diag(scale)])
    aug_b = np.concatenate([y_c, np.sqrt(lam * n) * scale * prior])
    result = lsq_linear(aug_a, aug_b, bounds=(lo, hi))

    beta_all = np.array([result.x[free.index(c)] if c in free else 0.0 for c in cols])
    full_design = joined[cols].to_numpy()
    alpha = float(yv.mean() - full_design.mean(axis=0) @ beta_all)
    residuals = pd.Series(yv - alpha - full_design @ beta_all, index=joined.index)

    per_lag = beta_all[len(REGRESSORS):]
    summed = beta_all[: len(REGRESSORS)].copy()
    summed[REGRESSORS.index("equity_mkt")] += float(per_lag.sum())
    return summed, alpha, residuals, per_lag


def delever(loadings: dict[str, float], sigma: float, factor: float):
    """Scale betas and residual sigma by the declared leverage factor."""
    return {k: v * factor for k, v in loadings.items()}, sigma * factor


def merge_artifact(v10_doc: dict, pm_rows: dict) -> dict:
    """v1.1 = v1.0 with pm_sleeves replaced; everything else verbatim."""
    out = dict(v10_doc)
    out["mapping_version"] = MAPPING_VERSION
    out["pm_sleeves"] = pm_rows
    return out


def pm_constraints() -> dict[str, dict[str, tuple[float, float, float]]]:
    """DN-5 priors from the sealed cashflow-tier1 artifact (v1.0's rule)."""
    doc = yaml.safe_load(
        (_REPO_ROOT / "mappings" / "cashflow-tier1-v1.0.yaml").read_text(encoding="utf-8")
    )
    inf = float("inf")
    out: dict[str, dict[str, tuple[float, float, float]]] = {}
    for sleeve, priors in (doc.get("pm_growth_loadings") or {}).items():
        spec: dict[str, tuple[float, float, float]] = {}
        for regressor in REGRESSORS:
            prior = float(priors.get(regressor, 0.0))
            if prior > 0:
                spec[regressor] = (0.0, inf, prior)
            elif prior < 0:
                spec[regressor] = (-inf, 0.0, prior)
            else:
                spec[regressor] = (0.0, 0.0, 0.0)
        out[sleeve] = spec
    return out


def _to_quarterly(s: pd.Series, how: str) -> pd.Series:
    quarters = pd.PeriodIndex(s.index, freq="Q")
    out = (
        (1.0 + s).groupby(quarters).prod() - 1.0
        if how == "compound"
        else s.groupby(quarters).last()
    )
    out.index = pd.PeriodIndex(out.index).to_timestamp()
    return out.sort_index()


def _regressor_frame(access: DataAccess, *, quarterly: bool) -> pd.DataFrame:
    frames = read_factor_frames(access, load_manifest()).frames

    def series(fid: str) -> pd.Series:
        f = frames[fid]
        s = pd.Series(
            pd.to_numeric(f["value"]).to_numpy(dtype=float),
            index=pd.to_datetime(f["date"]),
        )
        if not quarterly:
            return s
        return _to_quarterly(s, "compound" if fid in _RETURN_FACTORS else "last")

    x = pd.DataFrame(
        {
            "equity_mkt": series("equity_mkt"),
            "smb": series("smb"),
            "hml": series("hml"),
            "mom": series("mom"),
            "d_level": series("ust_10y").diff(),
            "d_slope": (series("ust_10y") - series("ust_2y")).diff(),
            "d_ig": series("ig_spread").diff(),
        }
    )
    return x.dropna()


def _dated_composite(access, members, *, family: str) -> pd.Series:
    desmoother = geltner_ar1 if family == "geltner" else glm_ma
    cols = []
    for sid in members:
        frame = access.train_val(sid)
        values = pd.to_numeric(frame["value"]).to_numpy(dtype=float)
        cols.append(pd.Series(desmoother(values).truth, index=pd.to_datetime(frame["date"])))
    return pd.concat(cols, axis=1).mean(axis=1, skipna=True).sort_index()


def _sigma_annual(resid: pd.Series, periods_per_year: float) -> float:
    return float(resid.std(ddof=1) * np.sqrt(periods_per_year))


def main() -> None:
    catalog = Catalog(_REPO_ROOT / "data")
    vintage = catalog.current_vintage()
    if vintage is None:
        raise SystemExit("no current vintage")
    access = DataAccess(lambda sid: catalog.read_observations(vintage, sid))
    v10 = yaml.safe_load(V10_PATH.read_text(encoding="utf-8"))
    specs = pm_constraints()
    xq = _regressor_frame(access, quarterly=True)
    xm = _regressor_frame(access, quarterly=False)

    pm_rows: dict[str, dict] = {}
    report = [
        "# MAPPINGS-v1.1.md — PM sum-beta re-estimation (AM-2026-08-12-001)",
        "",
        f"Vintage `{vintage}`; train+validation only; lag rule and BDC anchor",
        "declared in docs/superpowers/specs/2026-08-12-pm-remap-design.md",
        "BEFORE this ran. HF sleeves verbatim from v1.0.",
        "",
        "| sleeve | route | n | lags | b_mkt v1.0 | b_mkt v1.1 | per-lag | alpha_q v1.0 | alpha_q v1.1 | sigma_ann |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for sleeve, members in pm_sleeve_members().items():
        if sleeve not in specs:
            continue
        old = v10["pm_sleeves"][sleeve]
        prior_row = specs[sleeve]

        if sleeve == BDC_SLEEVE:
            # market-priced anchor: monthly regression on the listed BDC index
            frame = access.train_val(BDC_SERIES)
            y_bdc = pd.Series(
                pd.to_numeric(frame["value"]).to_numpy(dtype=float),
                index=pd.to_datetime(frame["date"]),
            )
            inf = float("inf")
            bdc_spec = {r: (-inf, inf, 0.0) for r in REGRESSORS}
            summed, _a, resid, per_lag = fit_sum_beta(y_bdc, xm, bdc_spec, n_lags=0)
            loadings = dict(zip(REGRESSORS, summed, strict=True))
            loadings, sigma = delever(loadings, _sigma_annual(resid, 12.0), BDC_DELEVER)
            # alpha from the asset-level composite, net of the anchored betas
            y_dl = _dated_composite(access, members, family=smoothing_family(sleeve))
            joined = pd.concat([y_dl.rename("y"), xq], axis=1, sort=True).dropna()
            beta_vec = np.array([loadings[r] for r in REGRESSORS])
            alpha = float(
                joined["y"].to_numpy().mean()
                - joined[list(REGRESSORS)].to_numpy().mean(axis=0) @ beta_vec
            )
            n_obs, lags, route = len(y_bdc), 0, "bdc-anchor*0.5"
        else:
            y = _dated_composite(access, members, family=smoothing_family(sleeve))
            n_obs = len(pd.concat([y.rename("y"), xq], axis=1, sort=True).dropna())
            lags = lag_count(n_obs)
            if lags == 0:
                # refused: DN-5 prior adopted verbatim, recorded as such
                loadings = {r: prior_row[r][2] for r in REGRESSORS}
                alpha = float(old["alpha_quarterly"])
                sigma = float(old["residual_sigma_annual"])
                per_lag, route = np.array([]), "prior-adopted"
            else:
                summed, alpha, resid, per_lag = fit_sum_beta(y, xq, prior_row, lags)
                loadings = dict(zip(REGRESSORS, summed, strict=True))
                sigma = _sigma_annual(resid, 4.0)
                route = f"sum-beta({lags})"

        pm_rows[sleeve] = {
            "family": smoothing_family(sleeve),
            "n_quarters": int(n_obs),
            "route": route,
            "alpha_quarterly": round(float(alpha), 6),
            "loadings": {r: round(float(loadings[r]), 4) for r in REGRESSORS},
            "residual_sigma_annual": round(float(sigma), 4),
            "prior_v10": {
                "source": "sleeve-mappings-v1.0.yaml",
                "equity_mkt": float(old["loadings"]["equity_mkt"]),
                "alpha_quarterly": float(old["alpha_quarterly"]),
            },
        }
        report.append(
            f"| {sleeve} | {route} | {n_obs} | {lags} "
            f"| {float(old['loadings']['equity_mkt']):+.3f} "
            f"| {loadings['equity_mkt']:+.3f} "
            f"| {np.array2string(np.round(per_lag, 3))} "
            f"| {float(old['alpha_quarterly']):+.4f} | {alpha:+.4f} | {sigma:.1%} |"
        )

    out = merge_artifact(v10, pm_rows)
    header = (
        "# mappings/sleeve-mappings-v1.1.yaml - scripts/estimate_sleeve_mappings_v1_1.py\n"
        f"# AM-2026-08-12-001; vintage {vintage}; PM rows re-estimated (Dimson\n"
        "# sum-beta / BDC anchor / prior-adopted, per-row 'route'); HF rows,\n"
        "# residual_correlation and cta_rule verbatim from v1.0.\n"
    )
    OUT_PATH.write_text(
        header + yaml.safe_dump(out, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
        newline="\n",
    )
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH.name} + {REPORT_PATH.name} ({len(pm_rows)} PM sleeves)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the unit tests**

Run: `uv run pytest tests/test_estimate_v11.py -q`
Expected: PASS (all five)

- [ ] **Step 5: Lint/type/commit**

```bash
uv run ruff check scripts/estimate_sleeve_mappings_v1_1.py tests/test_estimate_v11.py --fix
uv run ruff format scripts/estimate_sleeve_mappings_v1_1.py tests/test_estimate_v11.py
uv run pyright scripts/estimate_sleeve_mappings_v1_1.py > pyright.log; echo "EXIT: $?" >> pyright.log
# READ pyright.log as its own step before committing
git add scripts/estimate_sleeve_mappings_v1_1.py tests/test_estimate_v11.py
git commit -m "feat: v1.1 PM estimator - Dimson sum-beta, BDC anchor, prior floor (TDD)"
```

---

### Task 3: Run the estimation, sanity-read the numbers

**Files:**
- Create (by running): `mappings/sleeve-mappings-v1.1.yaml`, `MAPPINGS-v1.1.md`

**Interfaces:**
- Consumes: Task 2's `main()`.
- Produces: the v1.1 artifact Task 4 seals and Task 5 adopts.

- [ ] **Step 1: Run** `uv run python scripts/estimate_sleeve_mappings_v1_1.py`
Expected: `wrote sleeve-mappings-v1.1.yaml + MAPPINGS-v1.1.md (9 PM sleeves)`

- [ ] **Step 2: Read `MAPPINGS-v1.1.md` and record in the commit body:** per
  sleeve, v1.0 vs v1.1 equity beta and alpha. Sanity expectations (NOT
  targets — record surprises, do not tune): buyout/growth/vc/secondaries
  summed betas should move up toward their priors (0.29 → nearer 1.2 for
  buyout); alphas should fall correspondingly; direct lending should carry a
  nonzero equity and d_ig beta from the BDC anchor with sigma near
  0.5 × 21.6% ≈ 10.8%; any sleeve routed `prior-adopted` must have n < 40.

- [ ] **Step 3: Determinism check** — run it twice; `git diff --stat` must
  show the second run changed nothing.

- [ ] **Step 4: Commit**

```bash
git add mappings/sleeve-mappings-v1.1.yaml MAPPINGS-v1.1.md
git commit -m "feat: sleeve-mappings v1.1 - PM rows re-estimated (numbers in body)"
```

---

### Task 4: The seal event (one commit, per the AM-2026-08-09 lesson)

**Files:**
- Modify: `pre-registration-g3.yaml` (seal_scope.hashed_files: add the two new files)
- Modify: `pre-registration-g3.lock` (via `seal_g3`)
- Modify: `governance/amendment-log.yaml` (fill `superseded_lock_digest`)

**Interfaces:**
- Consumes: `ah.eval.g3seal.seal_g3(sealed_at=...)` and `verify_g3()`; the
  pattern in `scripts/campaign3_apply_amendment.py`.

- [ ] **Step 1: Record the CURRENT G3 lock digest** (it becomes
  `superseded_lock_digest`): read `pre-registration-g3.lock`.

- [ ] **Step 2: Edit `pre-registration-g3.yaml` seal_scope** — after the
  v1.0 estimator/artifact lines (`:177-178`), add:

```yaml
    # AM-2026-08-12-001 (post_hoc, disclosed): the v1.1 PM re-estimation joins
    # in the commit that creates it — same planned-arrival pattern as -001.
    # v1.0 stays sealed above as the G1-era record; v1.1 is forward-only.
    - scripts/estimate_sleeve_mappings_v1_1.py
    - mappings/sleeve-mappings-v1.1.yaml
```

- [ ] **Step 3: Fill the amendment's `superseded_lock_digest`** with Step 1's
  value (replacing `PENDING-TASK-4`).

- [ ] **Step 4: Re-seal G3 and verify all three locks:**

```bash
uv run python -c "from ah.eval.g3seal import seal_g3, verify_g3; print(seal_g3(sealed_at='2026-08-12')); print(verify_g3())"
uv run pytest tests -k "seal_guard or amendment or prereg" -q
```
Expected: new G3 digest printed; verify passes; main and G5 lock digests
UNCHANGED (no shared file touched — if either moved, STOP: something sealed
was edited unintentionally).

- [ ] **Step 5: Commit (everything above in this one commit)**

```bash
git add pre-registration-g3.yaml pre-registration-g3.lock governance/amendment-log.yaml
git commit -m "governance: seal v1.1 estimator+artifact into G3 lock (AM-2026-08-12-001)"
```

---

### Task 5: Adopt v1.1 in the runtime + move the world fence

**Files:**
- Modify: `src/ah/port/mapping.py:28` (`ARTIFACT_PATH` → `sleeve-mappings-v1.1.yaml`)
- Modify: `src/ah/presets/stagflation_1974.json:95` (world_id `…601` → `…602`)
- Modify: `tests/test_port_mapping.py`, `tests/test_gen_adapter.py`,
  `tests/test_bundle.py`, `tests/test_serve.py` — re-pin ONLY goldens that
  encode v1.0 numbers/world_id, with the reason in each docstring
- Regenerate: `app/fixtures/gen.bundle.gz` via `scripts/gen_bundle_fixtures.py`

**Interfaces:**
- Consumes: `load_artifact()` (cached — consumers pick v1.1 up by path).
- Produces: the adapter/twin/bundle now run on v1.1; world `…602` is the only
  world new sessions build.

- [ ] **Step 1: Write the failing adoption test first** (add to
  `tests/test_port_mapping.py`):

```python
def test_runtime_consumes_the_v11_artifact():
    """AM-2026-08-12-001: the runtime's default artifact is v1.1. Written
    FAILING against v1.0 before ARTIFACT_PATH moved."""
    from ah.port.mapping import load_artifact

    doc = load_artifact()
    assert doc["mapping_version"] == "map-2026.08.2"
    assert doc["pm_sleeves"]["pm_direct_lending"]["route"] == "bdc-anchor*0.5"
```

Run: `uv run pytest tests/test_port_mapping.py::test_runtime_consumes_the_v11_artifact -q`
Expected: FAIL (`map-2026.08` != `map-2026.08.2`)

- [ ] **Step 2: Bump `ARTIFACT_PATH`** in `src/ah/port/mapping.py` to
  `"sleeve-mappings-v1.1.yaml"` and update its module docstring line naming
  v1.0. Run the new test: PASS.

- [ ] **Step 3: Move the world fence** — in
  `src/ah/presets/stagflation_1974.json` set
  `"world_id": "00000000-0000-4000-9000-000000000602"`. Grep tests/fixtures
  for `000000000601` and update every reference.

- [ ] **Step 4: Regenerate the committed gen bundle**

Run: `uv run python scripts/gen_bundle_fixtures.py`
Expected: `app/fixtures/gen.bundle.gz` rewritten (toy bundle byte-identical —
if `toy.bundle.gz` changed, STOP: the toy path must be untouched by this WP).

- [ ] **Step 5: Run the blast-radius suites; re-pin with reasons**

Run: `uv run pytest tests/test_port_mapping.py tests/test_gen_adapter.py tests/test_bundle.py tests/test_serve.py tests/test_credibility.py -q > blast.log 2>&1; echo "EXIT: $?" >> blast.log`
Then READ `blast.log` as its own step. Update any golden digest/value pins
that encode v1.0 PM numbers; each re-pin's docstring gains one line: "re-pinned
under map-2026.08.2 (AM-2026-08-12-001)". App-side: `cd app && npm run test`
(bundle allowlist unchanged — 0.5 contract untouched — so only fixture bytes
move).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: adopt sleeve-mappings v1.1; world fence 601->602; re-pin goldens"
```

---

### Task 6: Console walk (the merge gate for numeric surfaces)

**Files:**
- None modified — verification only, findings recorded in the merge commit body.

- [ ] **Step 1: Rebuild the 1974 world + credibility console**

```bash
uv run ah world build --preset stagflation_1974
uv run ah credibility --preset stagflation_1974 --out credibility-v11.html
```

- [ ] **Step 2: Open and READ the console** (memory:
  `console-walk-before-merge` — it has caught two defect classes the unit
  suite missed). Check, and record actual values: (a) PE decade Sharpe is no
  longer ~1.30 — expect materially lower now beta carries more of the return;
  (b) pe/pc/re correlation-to-equity rows reflect the new loadings (pe well
  above the old 0.48 path-level figure; pc nonzero); (c) tail bands: worst PE
  drawdown now deeper than before (more beta = more drawdown) but bounded by
  real-month history; (d) no new red flags introduced.

- [ ] **Step 3: Spot-check the play surface end-to-end** — start the session
  service (`uv run uvicorn ah.serve:app --port 8787`; if one is already
  listening, kill it first via `Get-NetTCPConnection -LocalPort 8787` →
  `Stop-Process` — port 8787, never 8000), run the scratchpad
  `play_decade.py` against a fresh `…602` run, confirm: session opens, decade
  completes, alpha prints, privates in the outcome move with the tape. Kill
  the server after.

- [ ] **Step 4: Anything anomalous** → STOP and report to the owner before
  merging (the walk is a gate, not a formality).

---

### Task 7: Changelog, gate, merge, push

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: CHANGELOG entry** under today: v1.1 mappings (what changed,
  the amendment id, the world fence move, what was NOT re-scored).

- [ ] **Step 2: Run the full gate to a file, in the background**

```bash
uv run pytest --cov=ah.core --cov-report=term-missing --cov-fail-under=90 > gate.log 2>&1; echo "EXIT: $?" >> gate.log
```
(~28 min. Do not chain anything onto it.)

- [ ] **Step 3: READ the gate log as its own tool call** — the `EXIT:` line
  AND the pass count (memory: `gate-exit-line-must-be-read`).

- [ ] **Step 4: Validate + stamp + merge + push**

```bash
uv run python scripts/check_gate.py gate.log
git checkout main
git merge --no-ff pm-remap-01-sum-beta   # hook verifies .gate-ok
git push origin main
```

- [ ] **Step 5: Report to the owner:** the v1.0→v1.1 beta/alpha table, the
  console-walk values, and the two follow-ups still queued (the
  `_reported_marks` engine fix with its `TOY_ENGINE_VERSION` bump; the
  write-up update).

---

## Self-review notes

- **Spec coverage:** amendment drafted (Task 1, sealed at Task 4);
  re-estimation with lagged component (Tasks 2–3); direct-lending BDC anchor
  (Task 2); adoption + fence + re-pin (Task 5); console gate (Task 6);
  discipline (Task 7). The `_reported_marks` display fix is explicitly out of
  scope (owner-sequenced after this).
- **Ordering honesty:** parameters are committed (Task 1) before estimation
  runs (Task 3); the seal event is one commit with the superseded digest in
  the payload; main/G5 locks are asserted unchanged.
- **Type consistency:** `fit_sum_beta` returns
  `(summed, alpha, residuals, per_lag)` everywhere it is called (tests, BDC
  route, quarterly route); `delever` returns `(loadings, sigma)`;
  `merge_artifact(v10_doc, pm_rows)` matches its test.
- **Known risks:** (a) if the constituent-trimmed n for any sleeve differs
  from the raw row counts probed during planning (e.g. DL showed 60 raw rows
  vs 39 in v1.0), the lag rule handles it — that is what the rule is for;
  (b) `test_port_mapping.py` may pin v1.0 semantics beyond the version string
  — re-pin with reasons, never delete; (c) the `lru_cache` on
  `load_artifact` means any test that monkeypatches the path must clear it —
  existing tests already handle this seam.
