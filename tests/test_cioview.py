"""cio-01: the CIO view builder and the play-state exposure it rides on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ah.cioview import _frozen_paths, build_cio_view, validate_cio_view
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec
from ah.play import PRIVATE_ASSETS, simulate_play

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "src" / "ah" / "presets"


def _paths(preset: str = "stagflation"):
    doc: dict[str, Any] = json.loads((PRESETS / f"{preset}.json").read_text(encoding="utf-8"))
    nw = project_numeric(WorldSpec.model_validate(doc))
    return run_path(nw, doc["engine_defaults"]["base_seed"])


def test_per_asset_private_flows_sum_to_totals():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert abs(sum(q.private_calls.values()) - q.calls_paid) < 1e-9
        assert abs(sum(q.private_distributions.values()) - q.distributions_received) < 1e-9
        assert abs(sum(q.private_unfunded.values()) - q.unfunded_total) < 1e-9
        assert set(q.private_calls) == set(PRIVATE_ASSETS)


def test_per_asset_expired_sums_to_the_quarter_total():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert abs(sum(q.private_expired.values()) - q.expired_undrawn) < 1e-9
        assert set(q.private_expired) == set(PRIVATE_ASSETS)


def test_per_asset_values_close_against_the_book():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        total = q.cash + sum(q.liquid_values.values()) + sum(q.private_true.values())
        assert abs(total - q.nav_true) < 1e-9
        total_rep = q.cash + sum(q.liquid_values.values()) + sum(q.private_reported.values())
        assert abs(total_rep - q.nav_reported) < 1e-9


def test_monthly_marks_close_on_the_quarter():
    result = simulate_play(_paths(), None)
    for q in result.quarters:
        assert len(q.nav_true_months) == 3
        assert len(q.nav_reported_months) == 3
        assert abs(q.nav_true_months[2] - q.nav_true) < 1e-9
        assert abs(q.nav_reported_months[2] - q.nav_reported) < 1e-9
        assert all(v > 0 for v in q.nav_true_months)


def test_opening_book_recorded():
    result = simulate_play(_paths(), None)
    op = result.opening
    total = op["cash"] + sum(op["liquid_values"].values()) + sum(op["private_true"].values())
    assert abs(total - op["nav_true"]) < 1e-9
    assert set(op["private_unfunded"]) == set(PRIVATE_ASSETS)


def _pq(label: str, forecast: bool) -> dict[str, Any]:
    return {
        "label": label,
        "forecast": forecast,
        "calls": 1.0,
        "distributions": 1.5,
        "net": 0.5,
        "navOpen": 30.0,
        "navClose": 30.5,
        "unfundedOpen": 15.0,
        "unfundedClose": 14.0,
        "callRateUnfunded": 0.0667,
        "callRateNav": 0.0333,
        "coverage": 0.459,
        "expiredUndrawn": 0.0,
    }


def _minimal_view() -> dict[str, Any]:
    """Smallest payload that passes every check — the seed for defect tests."""
    return {
        "meta": {
            "runId": "r1",
            "seed": "42",
            "worldTitle": "t",
            "worldVersion": "toy-v0.6",
            "linkageVersion": "public-0.1",
            "decisionAlphaVersion": "port-v4-ladder",
            "asOfLabel": "Y1 Q1",
            "asOfMonth": 2,
            "plane": "reported",
            "planesAvailable": ["reported", "true"],
            "unitLabel": "$m",
            "unitSuffix": "m",
            "currency": "USD",
            "watermark": "w",
            "disclaimer": "d",
        },
        "plan": {
            "totalValue": 100.0,
            "growthPct": None,
            "netOfFlows": None,
            "windowLabel": "Since inception",
            "history": {"values": [100.0, 100.5, 100.0 + 1e-9], "worldStartIndex": 0},
        },
        "allocation": {
            "goals": [{"id": "growth", "label": "Growth", "tolerancePct": 5.0}],
            "classes": [
                {
                    "id": "equity",
                    "label": "Equity",
                    "goalId": "growth",
                    "targetPct": 100.0,
                    "bandPct": 5.0,
                    "currentPct": 100.0,
                    "value": 100.0,
                    "returns": [1.0],
                }
            ],
            "alertPolicy": {"watchFraction": 0.75},
        },
        "performance": {
            "periods": ["1Q"],
            "annualisedFromIndex": 1,
            "total": [1.2],
            "benchmark": [1.1],
        },
        "liquidity": {
            "tiers": [{"id": "t1", "tier": 1, "label": "T1", "note": "", "value": 100.0}],
            "forecast12m": {
                "distributions": 2.0,
                "income": 0.0,
                "calls": 3.0,
                "payout": 1.0,
                "net": -2.0,
            },
        },
        "privateCashflows": {
            "histCount": 1,
            "classes": [{"id": "pe", "label": "PE"}],
            "series": {
                "aggregate": [_pq("Y1Q1", False)],
                "pe": [_pq("Y1Q1", False)],
            },
        },
    }


def test_validator_passes_a_well_formed_view():
    assert validate_cio_view(_minimal_view()) == []


def test_validator_catches_unbalanced_weights():
    v = _minimal_view()
    v["allocation"]["classes"][0]["currentPct"] = 90.0
    assert any("currentPct sums" in e for e in validate_cio_view(v))


def test_validator_catches_forecast_flag_mismatch():
    v = _minimal_view()
    v["privateCashflows"]["series"]["pe"][0]["forecast"] = True
    assert any("forecast flag" in e for e in validate_cio_view(v))


def test_validator_catches_expired_undrawn_aggregate_mismatch():
    v = _minimal_view()
    v["privateCashflows"]["series"]["aggregate"][0]["expiredUndrawn"] = 9.0
    assert any("expiredUndrawn" in e for e in validate_cio_view(v))


def test_validator_catches_net_identity_break():
    v = _minimal_view()
    v["liquidity"]["forecast12m"]["net"] = 5.0
    assert any("components imply" in e for e in validate_cio_view(v))


def test_validator_catches_plane_not_available():
    v = _minimal_view()
    v["meta"]["plane"] = "true"
    v["meta"]["planesAvailable"] = ["reported"]
    assert any("planesAvailable" in e for e in validate_cio_view(v))


def _view(plane: str = "reported", revealed: int = 60, fq: int = 4, preset: str = "stagflation"):
    return build_cio_view(
        _paths(preset),
        {},
        run_id="r-test",
        seed=42,
        world_title="Stagflation",
        world_version="toy-v0.6",
        alpha_version="port-v4-ladder",
        start_targets=None,
        plane=plane,
        revealed_months=revealed,
        forecast_quarters=fq,
    )


def test_view_validates_clean_on_both_planes():
    for plane in ("reported", "true"):
        assert validate_cio_view(_view(plane)) == []


def test_plan_history_is_monthly_and_truncated_at_the_pointer():
    v = _view(revealed=60)
    assert len(v["plan"]["history"]["values"]) == 60  # 20 closed quarters * 3
    assert v["plan"]["history"]["worldStartIndex"] == 0
    assert v["meta"]["asOfLabel"] == "Y5 Q4"


def test_planes_disagree_where_smoothing_bites():
    rep, tru = _view("reported"), _view("true")
    assert rep["plan"]["totalValue"] != tru["plan"]["totalValue"]
    # plane-invariant: the cash account has no planes (DN-8 section 4)
    rep_cash = next(t for t in rep["liquidity"]["tiers"] if "cash" in t["classIds"])
    tru_cash = next(t for t in tru["liquidity"]["tiers"] if "cash" in t["classIds"])
    assert rep_cash["value"] == tru_cash["value"]


def test_unreached_windows_are_null_not_zero():
    v = _view(revealed=15)  # 5 closed quarters: 3Y/5Y/10Y unreachable
    idx = {p: i for i, p in enumerate(v["performance"]["periods"])}
    for p in ("3Y", "5Y", "10Y"):
        assert v["performance"]["total"][idx[p]] is None
    for p in ("1Q", "1Y"):
        assert v["performance"]["total"][idx[p]] is not None


def test_benchmark_is_the_twin():
    v = _view()
    assert v["performance"]["benchmarkLabel"] == "Policy twin (hold course)"
    assert v["performance"]["benchmark"][0] is not None


def test_forecast_rows_are_flagged_and_suppressable():
    v = _view(fq=4)
    pcf = v["privateCashflows"]
    n_hist = pcf["histCount"]
    for _key, rows in pcf["series"].items():
        assert len(rows) == n_hist + 4
        assert all(r["forecast"] is (i >= n_hist) for i, r in enumerate(rows))
    v0 = _view(fq=0)
    assert all(
        not r["forecast"] for rows in v0["privateCashflows"]["series"].values() for r in rows
    )
    assert len(v0["privateCashflows"]["series"]["aggregate"]) == v0["privateCashflows"]["histCount"]


def test_aggregate_private_series_is_the_sum_of_classes():
    v = _view()
    pcf = v["privateCashflows"]
    ids = [c["id"] for c in pcf["classes"]]
    for i, agg in enumerate(pcf["series"]["aggregate"]):
        for field_name in ("calls", "distributions", "navClose", "unfundedClose", "expiredUndrawn"):
            s = sum(pcf["series"][cid][i][field_name] for cid in ids)
            assert abs(s - agg[field_name]) < 0.51, (i, field_name)


def test_expired_undrawn_is_a_positive_magnitude_present_on_every_row():
    v = _view()
    pcf = v["privateCashflows"]
    for rows in pcf["series"].values():
        for r in rows:
            assert r["expiredUndrawn"] >= 0.0


def test_vintage_ladder_is_nonempty_and_ordered_oldest_first():
    v = _view()
    vintages = v["privateCashflows"]["vintages"]
    assert vintages

    def chrono_key(cohort_id: str) -> int:
        # asset-sK is the seeded ladder: K=0 is the newest rung, larger K
        # is older. asset-vY is a commitment made during play: larger Y is
        # newer. Both encode an offset from the same base vintage year, so
        # -K and +Y are directly comparable across assets.
        _, tag = cohort_id.rsplit("-", 1)
        n = int(tag[1:])
        return -n if tag[0] == "s" else n

    keys = [chrono_key(x["id"]) for x in vintages]
    assert keys == sorted(keys)
    for x in vintages:
        assert x["navTrue"] >= 0.0
        assert x["label"]
        # honesty: reported NAV per cohort is not tracked by the engine, so
        # it must not appear as a fabricated figure.
        assert "navReported" not in x


def test_vintage_ladder_ids_are_the_as_of_quarters_cohorts():
    v = _view()
    result = simulate_play(_paths(), {})
    n_q = v["meta"]["asOfMonth"] // 3 + 1
    expected = set(result.quarters[n_q - 1].vintage_nav)
    got = {x["id"] for x in v["privateCashflows"]["vintages"]}
    assert got == expected


def test_forecast12m_net_identity_and_signs():
    v = _view()
    f = v["liquidity"]["forecast12m"]
    for k in ("distributions", "income", "calls", "payout"):
        assert f[k] >= 0.0
    assert abs(f["net"] - (f["distributions"] + f["income"] - f["calls"] - f["payout"])) < 1.0


def test_tiers_close_on_plan_total_and_privates_are_illiquid():
    v = _view()
    tiers = v["liquidity"]["tiers"]
    assert (
        abs(sum(t["value"] for t in tiers) - v["plan"]["totalValue"])
        < v["plan"]["totalValue"] * 0.005
    )
    illiquid = [t for t in tiers if t.get("liquid") is False]
    assert illiquid and set(illiquid[0]["classIds"]) == set(PRIVATE_ASSETS)


def test_markets_has_no_conditions_and_paths_match_history():
    v = _view()
    assert "conditions" not in v.get("markets", {})
    h = len(v["plan"]["history"]["values"])
    for s in v["markets"]["returns"]:
        assert len(s["path"]) == h


def test_listed_and_private_classes_have_returns_on_both_planes():
    # liquid sleeves have no reporting plane (port/portfolio.py:73 - "liquid
    # marks are true"); the reported-plane allocation tape must still carry
    # them from the true tape, or six of nine classes ship null columns.
    for plane in ("reported", "true"):
        v = _view(plane)
        by_id = {c["id"]: c for c in v["allocation"]["classes"]}
        assert by_id["equity"]["returns"][0] is not None
        assert by_id["pe"]["returns"][0] is not None


def test_frozen_paths_agree_with_the_live_run_over_the_revealed_window():
    paths = _paths()
    live = simulate_play(paths, None)
    frozen = simulate_play(_frozen_paths(paths, 60, 4), None)
    for i in range(20):
        lq, fq = live.quarters[i], frozen.quarters[i]
        assert abs(lq.nav_true - fq.nav_true) < 1e-9
        assert abs(lq.nav_reported - fq.nav_reported) < 1e-9
        assert abs(lq.calls_paid - fq.calls_paid) < 1e-9
        assert abs(lq.distributions_received - fq.distributions_received) < 1e-9


def test_allocation_guards_zero_total_instead_of_raising():
    from ah.cioview import _allocation
    from ah.play import PlayQuarter, PlayResult

    zeroed = PlayQuarter(
        quarter=0,
        month=2,
        cash=0.0,
        nav_true=0.0,
        nav_reported=0.0,
        calls_paid=0.0,
        distributions_received=0.0,
        spending_paid=0.0,
        forced_sale_total=0.0,
        private_weight_true=0.0,
        unfunded_total=0.0,
        liquid_values={"equity": 0.0},
        private_true={},
        private_reported={},
    )
    active = PlayResult(
        quarters=[zeroed], final_value=0.0, forced_sale_quarters=0, total_forced_sales=0.0
    )
    alloc = _allocation(active, {"equity": 0.0}, "true", 1, {})
    equity = next(c for c in alloc["classes"] if c["id"] == "equity")
    assert equity["currentPct"] is None


def test_view_is_byte_deterministic():
    a = json.dumps(_view(), sort_keys=True, separators=(",", ":"))
    b = json.dumps(_view(), sort_keys=True, separators=(",", ":"))
    assert a == b


def test_golden_views_validate_on_every_preset():
    for preset in ("stagflation", "goldilocks"):
        for plane in ("reported", "true"):
            for revealed in (12, 60, 120):
                errors = validate_cio_view(_view(plane, revealed, preset=preset))
                assert errors == [], (preset, plane, revealed, errors)


def test_committed_cio_fixtures_match_the_builder():
    """The app's renderer tests consume these fixtures; drift is a contract
    break. Regenerate with scripts/gen_cio_fixture.py when the builder
    legitimately changes."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from gen_cio_fixture import _decided_map, build  # type: ignore
    finally:
        sys.path.pop(0)
    for plane in ("reported", "true"):
        committed = (ROOT / "app" / "fixtures" / f"cio-sample.{plane}.json").read_text(
            encoding="utf-8"
        )
        assert committed == build(plane), f"{plane} fixture is stale - regenerate"
    committed_decided = (ROOT / "app" / "fixtures" / "cio-sample.decided.json").read_text(
        encoding="utf-8"
    )
    assert committed_decided == build("reported", _decided_map()), (
        "decided fixture is stale - regenerate"
    )


def test_decided_fixture_actually_diverges_from_the_twin():
    """The Excess row is the product's argument as a number; a fixture where
    it is identically zero pins nothing."""
    import json

    doc = json.loads(
        (ROOT / "app" / "fixtures" / "cio-sample.decided.json").read_text(encoding="utf-8")
    )
    total = doc["performance"]["total"]
    bench = doc["performance"]["benchmark"]
    diffs = [
        abs(t - b) for t, b in zip(total, bench, strict=True) if t is not None and b is not None
    ]
    assert diffs, "no comparable periods in the decided fixture"
    assert max(diffs) > 0.05, f"decided fixture does not diverge from the twin: {diffs}"
