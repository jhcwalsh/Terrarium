"""Measure the WP2.3 sealed evidence that does NOT come out of ``compute_reference``.

This is the *provenance script* for four groups of numbers quoted inside
``pre-registration.yaml``. Before the WP2.3 re-seal each of them came from an ad-hoc
prototype that was never committed, so a reader could not reproduce them; this script
is the fix. Every number it prints is quoted verbatim somewhere in the sealed document,
and the sealed document names this script.

1. **The memorization null** (``thresholds.panel.nn_distance_p05`` / ``p50``). The right
   null for "how close does a generated 24-month block sit to a training window" is
   HISTORY'S OWN self-similarity, measured with exactly the search a generated block
   gets: every non-overlapping train block of a qualifying factor, searched against
   every *sliding* window of that same factor that does not overlap it. That is
   literally ``ah.eval.metrics.memorization._sliding_leave_one_out_epsilon``'s inner
   distance list, so this script calls the sealed private helpers rather than
   reimplementing them -- a re-derivation that used its own copy of the estimator would
   measure a different quantity from the one the battery judges.

2. **The D4 strategy historical statistics** (``thresholds.strategies``). Computed
   through ``ah.eval.metrics.tails._historical_strategy_returns``, i.e. the same code
   path the battery uses, so the sealed bands and the judged values cannot diverge in
   how a strategy is built from resolved series.

3. **The spread-floor evidence** (``decisions.S2-SPREAD-FLOOR`` /
   ``governance/retrofit-register.md`` RFR-41): what fraction of each
   ``SPREAD_FLOOR_FACTORS`` member's train+validation observations sit below the
   DN-1.1 literal 100bp floor, and what each factor's observed minimum is.

4. **The RFR-12 numeraire counterfactual** (``decisions.S2-NUMERAIRE-BIAS``). With
   ``policy_rate`` restored to the campaign vintage, option (a) -- give ``momentum``'s
   flat months the cash return instead of 0.0 -- is buildable for the first time. This
   measures what taking it would COST: the sample it truncates and the movement in the
   tail statistics the D4 criterion is actually made of. The decision is recorded in the
   sealed file; this is the evidence behind it.

Usage (offline; reads the local catalog, no network)::

    uv run python scripts/measure_seal_evidence.py --out seal-evidence.json

Determinism: nothing here draws a random number. Every quantity is a deterministic
function of the pinned campaign vintage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.eval.metrics import memorization as mem
from ah.eval.metrics.economics import SPREAD_FLOOR_FACTORS, SPREAD_FLOOR_PCT
from ah.eval.metrics.tails import BACKTEST_LEVEL, _historical_strategy_returns, var_es
from ah.eval.reference import ReferenceStats, compute_reference
from ah.factors import load_manifest
from ah.strategies import load_d4_strategies, load_derived_series

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Must match `pre-registration.yaml`'s `reference_run:` block. Imported from the
# reference script rather than restated so the two cannot drift.
from compute_campaign_reference import (  # noqa: E402  (path-relative sibling import)
    BLOCK_LENGTH,
    CAMPAIGN_VINTAGE_ID,
    LEVEL,
    N_RESAMPLES,
    REFERENCE_SEED,
    RESAMPLE_LENGTH,
    catalog_access,
)


def memorization_null(reference: ReferenceStats, manifest: Any) -> dict[str, Any]:
    """History's own self-similarity, pooled over every qualifying active factor.

    Per factor: build the same standardized train blocks and sliding candidate set the
    battery builds (``_FactorMemorizationInputs``), then take each non-overlapping train
    block's nearest neighbour over every non-overlapping sliding window. Pool across
    factors and report the 5th and 50th percentiles -- the two numbers the sealed
    ``nn_distance_*`` floors are half of.
    """
    pooled: list[float] = []
    per_factor: dict[str, Any] = {}
    for factor in manifest.active_factors():
        if factor not in reference.historical_series:
            continue
        inputs = mem._FactorMemorizationInputs(reference, factor)
        if not inputs.qualifies:
            per_factor[factor] = {"qualifies": False, "n": 0}
            continue
        candidates = inputs.train_candidates
        n_candidates = candidates.shape[0]
        starts = np.arange(n_candidates)
        block = mem.MEMORIZATION_BLOCK_MONTHS
        n_blocks = (n_candidates + block - 1) // block
        distances: list[float] = []
        for i in range(n_blocks):
            s = i * block
            if s >= n_candidates:
                break
            keep = np.abs(starts - s) >= block
            if not bool(np.any(keep)):
                continue
            distances.append(mem._nearest_neighbor_distance(candidates[s], candidates[keep]))
        pooled.extend(distances)
        arr = np.asarray(distances, dtype=np.float64)
        per_factor[factor] = {
            "qualifies": True,
            "n": int(arr.size),
            "p05": float(np.percentile(arr, 5)),
            "p50": float(np.percentile(arr, 50)),
        }
    pool = np.asarray(pooled, dtype=np.float64)
    return {
        "n": int(pool.size),
        "n_factors": sum(1 for v in per_factor.values() if v["qualifies"]),
        "p05": float(np.percentile(pool, 5)),
        "p50": float(np.percentile(pool, 50)),
        "sealed_floor_p05": float(np.percentile(pool, 5)) / 2.0,
        "sealed_floor_p50": float(np.percentile(pool, 50)) / 2.0,
        "per_factor": per_factor,
    }


def _path_stats(path: np.ndarray) -> dict[str, float]:
    var95, es95 = var_es(path, BACKTEST_LEVEL)
    var99, es99 = var_es(path, 0.99)
    return {
        "n": int(path.size),
        "mean": float(np.mean(path)),
        "sd": float(np.std(path, ddof=1)),
        "var_95": float(var95),
        "es_95": float(es95),
        "var_99": float(var99),
        "es_99": float(es99),
        "exceedance_rate_95": float(np.mean(path < -var95)),
    }


def d4_strategy_stats(reference: ReferenceStats) -> dict[str, Any]:
    """Each D4 strategy's historical realized path statistics, or why it has none."""
    derived = load_derived_series()
    out: dict[str, Any] = {}
    for strategy in load_d4_strategies():
        path = _historical_strategy_returns(reference, strategy, derived)
        if path is None or path.size == 0:
            out[strategy.strategy_id] = {"computable": False}
            continue
        stats = _path_stats(path)
        stats["computable"] = True
        out[strategy.strategy_id] = stats
    return out


def spread_floor_evidence(reference: ReferenceStats) -> dict[str, Any]:
    """RFR-41 / S2-SPREAD-FLOOR: how much of history a literal 100bp floor rejects."""
    out: dict[str, Any] = {"sealed_floor_pct": SPREAD_FLOOR_PCT}
    for factor in sorted(SPREAD_FLOOR_FACTORS):
        series = reference.historical_series.get(factor)
        if series is None or series.empty:
            out[factor] = {"available": False}
            continue
        values = series.to_numpy(dtype=np.float64)
        out[factor] = {
            "available": True,
            "n": int(values.size),
            "min": float(np.min(values)),
            "fraction_below_100bp": float(np.mean(values < 1.0)),
            "fraction_below_sealed_floor": float(np.mean(values < SPREAD_FLOOR_PCT)),
        }
    return out


def momentum_cash_counterfactual(reference: ReferenceStats) -> dict[str, Any]:
    """RFR-12 option (a), costed: what a ``cash_tr_1m`` residual leg would do to
    ``momentum``'s historical sample and to its sealed tail statistics.

    ``momentum`` is long-only and binary: fully invested when the 12-1 signal is
    strictly positive, FLAT otherwise, and a flat month books exactly 0.0. Under
    ``conventions.numeraire: total_return`` a flat month should book the cash return.
    Option (a) is therefore ``realized_t = position_t * equity_mkt_t + (1 - position_t)
    * cash_tr_1m_t``. Building it requires ``policy_rate``, which the campaign vintage
    now carries -- so the option is available, and its cost is measurable rather than
    hypothetical.
    """
    strategies = {s.strategy_id: s for s in load_d4_strategies()}
    derived = load_derived_series()
    momentum = strategies["momentum"]
    baseline = _historical_strategy_returns(reference, momentum, derived)
    if baseline is None:
        return {"buildable": False, "reason": "momentum has no historical path"}

    equity = reference.historical_series["equity_mkt"]
    policy = reference.historical_series.get("policy_rate")
    if policy is None or policy.empty:
        return {"buildable": False, "reason": "policy_rate has no historical series"}

    joined = pd.concat({"equity_mkt": equity, "policy_rate": policy}, axis=1, join="inner")
    joined = joined.sort_index()
    eq = joined["equity_mkt"].to_numpy(dtype=np.float64)
    rate = joined["policy_rate"].to_numpy(dtype=np.float64)

    # cash_tr_1m, exactly as `derived_series.cash_tr_1m` seals it: r_t = 0.01*y_{t-1}/12,
    # r_0 = 0.0.
    cash = np.zeros_like(rate)
    cash[1:] = 0.01 * rate[:-1] / 12.0

    lookback = int(momentum.lookback or 12)
    skip = int(momentum.params["skip_months"])
    position = np.zeros_like(eq)
    for t in range(lookback, eq.size):
        signal = float(np.sum(eq[t - lookback : t - skip]))
        position[t] = 1.0 if signal > 0.0 else 0.0
    with_cash = position * eq + (1.0 - position) * cash
    without_cash = position * eq

    return {
        "buildable": True,
        "baseline_span_months": int(baseline.size),
        "with_cash_span_months": int(with_cash.size),
        "months_lost": int(baseline.size - with_cash.size),
        "span_start": str(pd.Timestamp(joined.index[0]).date()),
        "span_end": str(pd.Timestamp(joined.index[-1]).date()),
        "flat_month_fraction": float(np.mean(position == 0.0)),
        "baseline_full_sample": _path_stats(baseline),
        "truncated_no_cash": _path_stats(without_cash),
        "truncated_with_cash": _path_stats(with_cash),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    args = parser.parse_args()

    manifest = load_manifest()
    with Catalog(args.catalog_root) as catalog:
        access = catalog_access(catalog, args.vintage)
        reference = compute_reference(
            access,
            manifest,
            vintage_id=args.vintage,
            seed=REFERENCE_SEED,
            n_resamples=N_RESAMPLES,
            level=LEVEL,
            block_length=BLOCK_LENGTH,
            resample_length=RESAMPLE_LENGTH,
        )

    payload = {
        "vintage_id": args.vintage,
        "missing_factors": list(reference.missing_factors),
        "memorization_null": memorization_null(reference, manifest),
        "d4_strategy_stats": d4_strategy_stats(reference),
        "spread_floor_evidence": spread_floor_evidence(reference),
        "momentum_cash_counterfactual": momentum_cash_counterfactual(reference),
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    mn = payload["memorization_null"]
    print(
        f"memorization null: n={mn['n']} over {mn['n_factors']} factors, "
        f"p05={mn['p05']:.4f} p50={mn['p50']:.4f} -> floors {mn['sealed_floor_p05']:.4f} / "
        f"{mn['sealed_floor_p50']:.4f}"
    )
    for sid, s in payload["d4_strategy_stats"].items():
        if s["computable"]:
            print(
                f"  {sid:16s} n={s['n']:5d} mean={s['mean']:.5f} sd={s['sd']:.5f} "
                f"var95={s['var_95']:.5f} es95={s['es_95']:.5f} "
                f"var99={s['var_99']:.5f} es99={s['es_99']:.5f} exc={s['exceedance_rate_95']:.4f}"
            )
        else:
            print(f"  {sid:16s} NO COMPUTABLE HISTORICAL PATH")


if __name__ == "__main__":
    main()
