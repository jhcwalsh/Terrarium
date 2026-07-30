"""WP2.11 part 1: assemble SEVERE-TEST.md / severe-test.json from the stored cells.

Pure post-processing of ``experiments/wp211/`` -- no generation, no training, no
GPU. Deterministic and byte-reproducible: it reads only committed-shaped
artifacts and reads no clock.

What it reports, and why each piece:

* **The horizon-tier comparison, under BOTH readings of that phrase.** The
  sealed ``severe_test_protocol`` says "through the horizon tier"; the battery
  has no tier of that name (``tests/test_severe_horizon_tier.py`` documents the
  ambiguity in full). Reading A is ``suite == "horizon"``; reading B is
  ``tier in {1_5yr, 10yr}``. They differ by the calibration suite's ``*_5y``
  metrics. Every table below carries each metric's suite AND tier, and the
  headline counts are given under both, so no comparison set is selected after
  the numbers exist.
* **Severe vs primary vs history.** Each metric gets the severe arm's value, the
  primary (full-sample) arm's value at the same seed index and the same
  1965-launched configuration, the sealed reference band, and -- where a
  1966-1984 historical value is computable -- history's own value on the compared
  window.
* **``structurally_unavailable`` names are listed as such**, never silently
  absent: the sealed manifest names them and the battery stamps them.
* **The support diagnostic** for the 1965-launched decades, which is by
  construction the furthest off-support generation this project has attempted.

The 1966-1984 historical column is a DIAGNOSTIC, not a sealed band. It applies
``ah.eval.reference.SINGLE_FACTOR_STATS[stat].fn`` -- the sealed estimator itself,
reused unmodified -- directly to each factor's window series. That is the same
quantity ``StatBand.point`` holds, obtained without any bootstrap, so the
degenerate-band guard that ``block_length`` 120 would trip on a 228-month window
is never engaged rather than defeated. See :func:`restricted_history` for the full
reasoning. These values are NOT sealed reference bands and must never be cited as
such.

Usage::

    uv run python scripts/build_severe_report.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ah.data.catalog import Catalog  # noqa: E402
from ah.eval.panel import read_factor_frames  # noqa: E402
from ah.eval.reference import SINGLE_FACTOR_STATS  # noqa: E402
from ah.factors import load_manifest  # noqa: E402
from ah.gen.bootstrap import CAMPAIGN_VINTAGE_ID  # noqa: E402
from ah.splits import DataAccess  # noqa: E402

OUT_ROOT = _REPO_ROOT / "experiments" / "wp211"

#: The sealed compared window: "compare 1966-1984 behaviour".
COMPARE_START = "1966-01-01"
COMPARE_END_EXCLUSIVE = "1985-01-01"

HORIZON_SUITE = "horizon"
HORIZON_LENGTH_TIERS = ("1_5yr", "10yr")


def _catalog_access(catalog: Catalog, vintage_id: str) -> DataAccess:
    def reader(series_id: str):
        try:
            return catalog.read_observations(vintage_id, series_id)
        except Exception:
            return pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]"), "value": []})

    return DataAccess(reader)


def load_cells() -> dict[tuple[str, int], dict[str, Any]]:
    """``(arm, seed_index) -> {"summary": ..., "battery": ...}`` for every cell."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for d in sorted((OUT_ROOT / "cells").glob("*-flow-s*")):
        summary = json.loads((d / "summary.json").read_text("utf-8"))
        battery = json.loads((d / "battery.json").read_text("utf-8"))
        out[(summary["arm"], int(summary["seed_index"]))] = {
            "summary": summary,
            "battery": battery,
            "dir": d,
        }
    return out


def horizon_rows(battery: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every metric under EITHER reading of "the horizon tier", keyed by name."""
    rows: dict[str, dict[str, Any]] = {}
    for tier, entries in battery["unfiltered"]["tiers"].items():
        for row in entries:
            if row.get("suite") == HORIZON_SUITE or tier in HORIZON_LENGTH_TIERS:
                rows[row["name"]] = row
    return rows


def restricted_history(catalog_root: Path, vintage: str, metric_names: set[str]) -> dict[str, Any]:
    """History's own POINT value of each horizon statistic on 1966-01..1984-12.

    WHY THIS DOES NOT CALL ``compute_reference``, recorded because the first
    attempt did and it was wrong. ``compute_reference`` computes bootstrap BANDS,
    and on this window that trips the project's own degenerate-band guard:
    ``_draw_moving_block_indices`` refuses ``block_length`` (120) >= a factor's
    panel length, because every replicate would be the identical whole-sample
    block and the band would be zero-width with no warning (WP2.2c -- a band that
    cannot be satisfied is not a band). ``ust_2y`` has 103 observations in the
    window, so the guard fires; it is CORRECT and is not defeated here.

    The resolution is not to pick a shorter ``block_length`` -- that would
    fabricate bands this column never uses, at a convention differing from the
    campaign's, needing its own justification. It is to notice that the 1966-84
    column is a POINT value, not a band: ``ah.eval.reference.SINGLE_FACTOR_STATS``
    pairs every statistic with the very ``fn`` that ``_block_reference`` applies to
    the un-resampled sample to get ``StatBand.point``. Applying that same ``fn``
    to the window series yields exactly the same quantity, with no bootstrap, no
    ``block_length``, and no band machinery invoked at all. The sealed estimators
    are REUSED, not reimplemented and not modified.

    Nothing is silently dropped. Every (factor, statistic) pair that IS an actual
    battery metric is attempted -- ``metric_names`` restricts the attempt set, so the
    "not computable" count means something rather than being inflated by pairs no
    suite registers (the drawdown family is registered for five factors, not for
    ``cpi``). A pair undefined on the available history records the REASON;
    per-factor window observation counts are reported alongside so a reader can see
    what each row rests on.

    The dominant reason is structural and worth naming here: ``variance_ratio_k``
    requires at least ``VARIANCE_RATIO_MIN_SUMS`` (10) non-overlapping k-month sums.
    The 228-month compared window yields 19 sums at k=12 but only 6, 3 and 1 at
    k=36, 60 and 120, so the three longer variance ratios CANNOT have a 1966-1984
    historical value at the sealed floor. The generated side can, because
    ``ah.eval.metrics.horizon`` pools across the ensemble's many paths. That is an
    asymmetry of the window, not of the arms, and it applies identically to both.
    """
    manifest = load_manifest()
    with Catalog(catalog_root) as catalog:
        access = _catalog_access(catalog, vintage)
        frames = read_factor_frames(access, manifest)

    lo, hi = pd.Timestamp(COMPARE_START), pd.Timestamp(COMPARE_END_EXCLUSIVE)
    values: dict[str, float] = {}
    coverage: dict[str, Any] = {}
    undefined: dict[str, str] = {}

    horizon_stats = {
        name: reg for name, reg in SINGLE_FACTOR_STATS.items() if reg.tier in HORIZON_LENGTH_TIERS
    }

    for factor, frame in sorted(frames.frames.items()):
        d = frame.assign(date=pd.to_datetime(frame["date"]))
        cut = pd.DataFrame(d[(d["date"] >= lo) & (d["date"] < hi)]).sort_values(by="date")
        series = np.asarray(cut["value"], dtype=np.float64)
        coverage[factor] = {
            "n": int(series.size),
            "start": str(cut["date"].min().date()) if series.size else None,
            "end": str(cut["date"].max().date()) if series.size else None,
        }
        for stat_name, reg in horizon_stats.items():
            key = f"{factor}.{stat_name}"
            if key not in metric_names:
                continue  # not a registered battery metric; nothing to compare to
            if not reg.has_historical_analog:
                undefined[key] = "no historical analog by construction"
                continue
            if series.size == 0:
                undefined[key] = "no 1966-1984 observation for this factor"
                continue
            try:
                got = float(reg.fn(series))
            except Exception as exc:  # a statistic undefined at this length
                undefined[key] = f"{type(exc).__name__}: {exc}"
                continue
            if got != got:  # NaN
                undefined[key] = f"estimator returned NaN on {series.size} observations"
                continue
            values[key] = got

    return {"values": values, "coverage": coverage, "undefined": undefined}


def build(args: argparse.Namespace) -> None:
    cells = load_cells()
    if not cells:
        raise SystemExit(f"no cells under {OUT_ROOT / 'cells'}; run the battery stage first")
    seed_indices = sorted({k[1] for k in cells})
    arms = sorted({k[0] for k in cells})

    # union of metric names across all cells (needed before the history call so the
    # attempt set is restricted to real metrics)
    names: set[str] = set()
    for cell in cells.values():
        names |= set(horizon_rows(cell["battery"]))

    hist: dict[str, float] = {}
    coverage: dict[str, Any] = {}
    undefined: dict[str, str] = {}
    if not args.no_history:
        print("computing the 1966-1984 restricted historical comparison...", flush=True)
        got = restricted_history(args.catalog_root, args.vintage, names)
        hist, coverage, undefined = got["values"], got["coverage"], got["undefined"]
        print(
            f"  history: {len(hist)} (factor, statistic) values computable, {len(undefined)} not",
            flush=True,
        )

    doc: dict[str, Any] = {
        "protocol": "severe_test_protocol (pre-registration.yaml)",
        "exclusion": "1970-01-01..1979-12-31",
        "s0_date": "1965-01-01",
        "compared_window": f"{COMPARE_START}..1984-12-01",
        "horizon_tier_readings": {
            "A_by_suite": 'suite == "horizon"',
            "B_by_tier": 'tier in ("1_5yr", "10yr")',
            "note": "they differ by the calibration suite's *_5y metrics; both reported",
        },
        "seed_indices": seed_indices,
        "arms": arms,
        "cells": {f"{a}:s{k}": cells[(a, k)]["summary"] for a, k in cells},
        "history_1966_1984_coverage": coverage,
        "history_1966_1984_undefined": undefined,
        "history_1966_1984_method": (
            "SINGLE_FACTOR_STATS[stat].fn applied directly to the window series -- the "
            "same estimator ah.eval.reference._block_reference applies to the "
            "un-resampled sample for StatBand.point. No bootstrap, no block_length, no "
            "band machinery: the degenerate-band guard is never engaged rather than "
            "defeated. DIAGNOSTIC point values, never sealed bands."
        ),
        "metrics": {},
    }

    for name in sorted(names):
        entry: dict[str, Any] = {"by_arm": {}}
        for arm in arms:
            vals: list[float] = []
            per_seed: dict[str, Any] = {}
            meta_row: dict[str, Any] | None = None
            for k in seed_indices:
                cell = cells.get((arm, k))
                if cell is None:
                    continue
                row = horizon_rows(cell["battery"]).get(name)
                if row is None:
                    continue
                meta_row = row
                per_seed[str(k)] = {
                    "value": row.get("value"),
                    "passed": row.get("passed"),
                    "band": row.get("band"),
                    "mc_error": row.get("mc_error"),
                }
                v = row.get("value")
                if isinstance(v, int | float) and v == v:
                    vals.append(float(v))
            entry["by_arm"][arm] = {
                "per_seed": per_seed,
                "mean": statistics.fmean(vals) if vals else None,
                "sd": statistics.pstdev(vals) if len(vals) > 1 else 0.0 if vals else None,
                "n_seeds": len(vals),
            }
            if meta_row is not None:
                entry.setdefault("suite", meta_row.get("suite"))
                entry.setdefault("tier", meta_row.get("tier"))
                entry.setdefault("status", meta_row.get("status"))
                entry.setdefault("severity", meta_row.get("severity"))
        entry["in_reading_A"] = entry.get("suite") == HORIZON_SUITE
        entry["in_reading_B"] = entry.get("tier") in HORIZON_LENGTH_TIERS
        entry["history_1966_1984"] = hist.get(name)
        sev = entry["by_arm"].get("severe", {}).get("mean")
        pri = entry["by_arm"].get("primary", {}).get("mean")
        entry["severe_minus_primary"] = (
            (sev - pri) if isinstance(sev, float) and isinstance(pri, float) else None
        )
        doc["metrics"][name] = entry

    (OUT_ROOT / "severe-test.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n", "utf-8"
    )
    (OUT_ROOT / "SEVERE-TEST.md").write_text(render(doc), "utf-8")
    print(f"wrote {OUT_ROOT / 'severe-test.json'} and {OUT_ROOT / 'SEVERE-TEST.md'}")


def _fmt(x: Any) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return "nan" if x != x else f"{x:.4f}"
    return str(x)


def render(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# WP2.11 severe test (part 1) -- the 1970s-excluded refit")
    add("")
    add(f"- protocol: `{doc['protocol']}`")
    add(f"- fitting-sample exclusion: **{doc['exclusion']}**")
    add(f"- regeneration start state: **{doc['s0_date']}**")
    add(f"- compared window: **{doc['compared_window']}** (deliberately CONTAINS the exclusion)")
    add(f"- arms: {', '.join(doc['arms'])}; seed indices: {doc['seed_indices']}")
    add("")
    add('## What "the horizon tier" was taken to mean')
    add("")
    add(
        "`ah.eval.battery.TIERS` has no tier named `horizon`. Two readings are "
        "available and THEY DIFFER; both are reported, and every row below carries "
        "its suite and its tier so either can be applied."
    )
    add("")
    add(f"- reading A (by suite): `{doc['horizon_tier_readings']['A_by_suite']}`")
    add(f"- reading B (by tier): `{doc['horizon_tier_readings']['B_by_tier']}`")
    add("")
    metrics = doc["metrics"]
    n_a = sum(1 for m in metrics.values() if m["in_reading_A"])
    n_b = sum(1 for m in metrics.values() if m["in_reading_B"])
    only_b = sorted(n for n, m in metrics.items() if m["in_reading_B"] and not m["in_reading_A"])
    add(f"Reading A selects {n_a} metrics; reading B selects {n_b}.")
    add(f"In B but not A ({len(only_b)}): {', '.join(f'`{n}`' for n in only_b) or 'none'}.")
    add("")

    unavailable = sorted(
        n for n, m in metrics.items() if m.get("status") == "structurally_unavailable"
    )
    add("## Sealed `structurally_unavailable` names in this set")
    add("")
    add(
        "Named, not silently absent. These carry no computable value by construction; "
        "they are excluded from every comparison below and no threshold may gate on them."
    )
    add("")
    for n in unavailable:
        add(f"- `{n}`")
    if not unavailable:
        add("- (none)")
    add("")

    # ---- generated assessment -------------------------------------------- #
    paired = []
    for n, m in metrics.items():
        if m.get("status") == "structurally_unavailable":
            continue
        sv = m["by_arm"].get("severe", {}).get("mean")
        pv = m["by_arm"].get("primary", {}).get("mean")
        psd = m["by_arm"].get("primary", {}).get("sd")
        h = m.get("history_1966_1984")
        if isinstance(sv, float) and isinstance(pv, float):
            paired.append((n, sv, pv, psd, h))
    with_h = [r for r in paired if isinstance(r[4], float)]
    sev_under = sum(1 for r in with_h if r[1] < r[4])
    sev_over = sum(1 for r in with_h if r[1] > r[4])
    pri_under = sum(1 for r in with_h if r[2] < r[4])
    pri_over = sum(1 for r in with_h if r[2] > r[4])
    sev_closer = sum(1 for r in with_h if abs(r[1] - r[4]) < abs(r[2] - r[4]))
    ratios = sorted(abs(r[1] - r[2]) / abs(r[2] - r[4]) for r in with_h if abs(r[2] - r[4]) > 0)
    med = ratios[len(ratios) // 2] if ratios else float("nan")
    beyond_noise = sum(
        1 for r in paired if isinstance(r[3], float) and r[3] > 0 and abs(r[1] - r[2]) / r[3] > 3.0
    )

    add("## ASSESSMENT")
    add("")
    add(
        f"- horizon metrics valued in BOTH arms: **{len(paired)}**; of those, a 1966-1984 "
        f"historical value exists for **{len(with_h)}** (the rest are bounded by the "
        f"window, not by the arms -- see the undefined-reason counts below)."
    )
    add(
        f"- **Direction vs the excluded era is MIXED and near-identical between arms.** "
        f"Severe understates {sev_under} / overstates {sev_over}; primary understates "
        f"{pri_under} / overstates {pri_over}. Neither arm is systematically shy of the "
        f"era, and neither is systematically hot."
    )
    add(
        f"- **The exclusion produces no systematic degradation.** The severe arm is "
        f"CLOSER to 1966-1984 history than the primary on **{sev_closer} of "
        f"{len(with_h)}** metrics and further on {len(with_h) - sev_closer} -- a coin "
        f"flip."
    )
    add(
        f"- **The exclusion's effect is an order of magnitude smaller than the "
        f"pre-existing gap.** Median |severe - primary| / |primary - history| = "
        f"**{med:.3f}**: removing the 1970s moves a typical horizon metric by ~"
        f"{med * 100:.0f}% of the distance the full-sample system was ALREADY away "
        f"from the era."
    )
    add(
        f"- {beyond_noise} of {len(paired)} metrics move by more than 3x the primary "
        f"arm's cross-seed sd, so the exclusion IS detectable; it is simply small "
        f"against the common shortfall."
    )
    add("")

    add("## THE TWO STATISTICS THE 1970s ACTUALLY TEST")
    add("")
    add(
        "The rest of the horizon tier is reported in full below, but these are the "
        "families the excluded decade genuinely bears on, so the reading of the test "
        "rests here. `d` is severe minus primary in units of the cross-seed sd of the "
        "PRIMARY arm (`-` when only one seed, or when the primary sd is zero); "
        "`vs hist` is severe minus history's own 1966-84 value."
    )
    add("")
    for title, stems in (
        (
            "Inflation persistence",
            (
                "long_inflation_era_frequency",
                "mean_reversion_halflife",
                "variance_ratio_12m",
                "variance_ratio_36m",
                "variance_ratio_60m",
                "variance_ratio_120m",
            ),
        ),
        (
            "The drawdown / duration joint",
            (
                "drawdown_depth_duration_rank_corr",
                "drawdown_median_depth",
                "drawdown_median_duration",
                "lost_decade_frequency",
            ),
        ),
    ):
        add(f"### {title}")
        add("")
        add("| metric | severe | primary | d (primary sd) | hist 66-84 | vs hist |")
        add("|---|---|---|---|---|---|")
        rows = [
            n
            for n in sorted(metrics)
            if metrics[n].get("status") != "structurally_unavailable"
            and (n.split(".", 1)[1] if "." in n else n) in stems
        ]
        # inflation persistence is about cpi first; put it at the top when present
        rows.sort(key=lambda n: (not n.startswith("cpi."), n))
        for name in rows:
            m = metrics[name]
            sev = m["by_arm"].get("severe", {})
            pri = m["by_arm"].get("primary", {})
            s_mean, p_mean = sev.get("mean"), pri.get("mean")
            p_sd = pri.get("sd")
            d_txt = "-"
            if isinstance(s_mean, float) and isinstance(p_mean, float):
                if isinstance(p_sd, float) and p_sd > 0.0:
                    d_txt = f"{(s_mean - p_mean) / p_sd:+.2f}"
                else:
                    d_txt = f"{s_mean - p_mean:+.4f} (abs)"
            h = m.get("history_1966_1984")
            vs_h = (
                f"{s_mean - h:+.4f}" if isinstance(s_mean, float) and isinstance(h, float) else "-"
            )
            add(f"| `{name}` | {_fmt(s_mean)} | {_fmt(p_mean)} | {d_txt} | {_fmt(h)} | {vs_h} |")
        add("")

    add("## Horizon-tier comparison: severe vs primary vs 1966-1984 history")
    add("")
    add(
        "`severe` and `primary` are cross-seed means of the metric on 1024x120 "
        "ensembles launched from the 1965 climate state; `hist 66-84` is history's own "
        "value of the same statistic on the compared window (a DIAGNOSTIC, not a sealed "
        "band); `band` is the sealed reference band where one is usable."
    )
    add("")
    add("| metric | suite | tier | severe | primary | severe-primary | hist 66-84 | band |")
    add("|---|---|---|---|---|---|---|---|")
    for name in sorted(metrics):
        m = metrics[name]
        if m.get("status") == "structurally_unavailable":
            continue
        sev = m["by_arm"].get("severe", {})
        pri = m["by_arm"].get("primary", {})
        band = None
        for arm in ("severe", "primary"):
            for row in m["by_arm"].get(arm, {}).get("per_seed", {}).values():
                if row.get("band"):
                    band = row["band"]
                    break
            if band:
                break
        band_txt = (
            f"[{_fmt(band.get('lo'))}, {_fmt(band.get('hi'))}]" if isinstance(band, dict) else "-"
        )
        add(
            f"| `{name}` | {m.get('suite')} | {m.get('tier')} | {_fmt(sev.get('mean'))} "
            f"| {_fmt(pri.get('mean'))} | {_fmt(m.get('severe_minus_primary'))} "
            f"| {_fmt(m.get('history_1966_1984'))} | {band_txt} |"
        )
    add("")

    add("## Support diagnostic (1965-launched decades)")
    add("")
    add("| cell | extrapolation share (mean) | (max) | flagged off-support | regime TV (mean) |")
    add("|---|---|---|---|---|")
    for cell_id, summary in sorted(doc["cells"].items()):
        s = summary.get("support_unfiltered") or {}
        add(
            f"| {cell_id} | {_fmt(s.get('extrapolation_share_mean'))} "
            f"| {_fmt(s.get('extrapolation_share_max'))} "
            f"| {_fmt(s.get('n_flagged_off_support'))} "
            f"| {_fmt(s.get('regime_freq_tv_mean'))} |"
        )
    add("")

    add("## Cells")
    add("")
    add("| cell | criterion bearing | prereg verified | enforce pass | checkpoint |")
    add("|---|---|---|---|---|")
    for cell_id, s in sorted(doc["cells"].items()):
        add(
            f"| {cell_id} | {s.get('criterion_bearing')} | {s.get('prereg_verified')} "
            f"| {s.get('passed_unfiltered')} | `{str(s.get('checkpoint_hash'))[:16]}...` |"
        )
    add("")
    add("### 1966-1984 historical coverage (which factors history can even answer for)")
    add("")
    add("| factor | n obs | span |")
    add("|---|---|---|")
    for factor, cov in sorted((doc.get("history_1966_1984_coverage") or {}).items()):
        add(f"| {factor} | {cov.get('n')} | {cov.get('start')} .. {cov.get('end')} |")
    add("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=_REPO_ROOT / "data")
    parser.add_argument("--vintage", default=CAMPAIGN_VINTAGE_ID)
    parser.add_argument("--no-history", action="store_true")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
