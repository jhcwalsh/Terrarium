"""Gap register + status reports (STEP1-DATA-PLAN §WP1.9).

``GAPS.md`` is generated per refresh from the manifest vs the catalog: per required
series — coverage %, missing head/tail, proxy share, license blockers, staleness —
plus an "anticipated additions" section of known-likely needs. ``DATA-STATUS.md``
summarizes the vintage: per-source freshness, QC summary, revision-diff highlights.

The emergent-requirements rule is process, not code: any workstream needing an
unregistered series adds it to ``requirements.yaml`` (priority + rationale) in the
same PR so the manifest stays the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement, Requirements

_FREQ = {"D->M": "M", "M": "M", "Q": "Q", "A": "Y"}

# Known-likely additions to seed GAPS.md (STEP1-DATA-PLAN §WP1.9).
ANTICIPATED_ADDITIONS: list[tuple[str, str]] = [
    ("MSCI World TR", "COMM pending — global developed equity"),
    ("Commodities index TR", "COMM decision open (GSCI/BCOM vs academic equal-weight)"),
    ("HFRI composites", "cross-check for Albourne HF strategy returns"),
    ("EDHECinfra", "listed/unlisted infrastructure benchmark"),
    ("PitchBook/LCD multiples & leverage", "structural covariates for PE"),
    ("Dry-powder aggregates", "pacing / market-state covariate"),
    ("Green Street cap rates", "transaction-based RE cap rates"),
    ("SOA mortality tables", "Step-3 institutional twin (liabilities)"),
    ("Daily equity returns", "vol-state refinement"),
]


@dataclass
class SeriesGap:
    series_id: str
    present: bool
    first: str | None
    last: str | None
    n_obs: int
    expected_start: str | None
    coverage_pct: float
    missing_head: bool
    missing_tail: bool
    license_tier: str
    license_blocker: str | None
    stale: bool


def _expected_count(min_start: str | None, asof: str, frequency: str) -> int:
    if min_start is None:
        return 0
    period = _FREQ.get(frequency, "M")
    try:
        rng = pd.period_range(pd.Period(min_start, freq=period), pd.Period(asof, freq=period))
    except Exception:
        return 0
    return len(rng)


def _index_row(catalog: Catalog, vintage: str, series_id: str):
    return catalog.con.execute(
        "SELECT first_date, last_date, n_obs FROM observations_index "
        "WHERE vintage_id = ? AND series_id = ?",
        [vintage, series_id],
    ).fetchone()


def series_gap(catalog: Catalog, req: Requirement, *, asof: str) -> SeriesGap:
    vintage = catalog.current_vintage()
    row = _index_row(catalog, vintage, req.series_id) if vintage else None

    license_blocker = None
    if req.intake == "manual" and req.license_tier in ("REG", "COMM"):
        if row is None:
            license_blocker = f"{req.license_tier} manual intake not yet delivered"
        elif req.notes and "pending-license" in req.notes:
            license_blocker = "pending-license"

    if row is None:
        return SeriesGap(
            req.series_id,
            False,
            None,
            None,
            0,
            req.min_start,
            0.0,
            True,
            True,
            req.license_tier,
            license_blocker,
            True,
        )

    first, last, n_obs = str(row[0]), str(row[1]), int(row[2])
    expected = _expected_count(req.min_start, asof, req.frequency)
    coverage = min(1.0, n_obs / expected) if expected > 0 else 1.0
    missing_head = req.min_start is not None and first[:7] > req.min_start
    stale = (pd.Timestamp(asof) - pd.Timestamp(last)).days > req.sla_days
    return SeriesGap(
        req.series_id,
        True,
        first,
        last,
        n_obs,
        req.min_start,
        round(coverage * 100, 1),
        missing_head,
        stale,
        req.license_tier,
        license_blocker,
        stale,
    )


def gap_register(catalog: Catalog, reqs: Requirements, *, asof: str) -> list[SeriesGap]:
    return [series_gap(catalog, r, asof=asof) for r in reqs]


def generate_gaps_md(gaps: list[SeriesGap]) -> str:
    lines = [
        "# GAPS.md — data gap register (generated)",
        "",
        f"- required series: {len(gaps)}",
        f"- present: {sum(g.present for g in gaps)}",
        f"- with license blockers: {sum(g.license_blocker is not None for g in gaps)}",
        "",
        "| series | present | coverage % | first | last | missing head | stale | license | blocker |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for g in sorted(gaps, key=lambda x: (x.present, x.series_id)):
        lines.append(
            f"| {g.series_id} | {'yes' if g.present else 'NO'} | {g.coverage_pct} | "
            f"{g.first or '-'} | {g.last or '-'} | {'yes' if g.missing_head else ''} | "
            f"{'yes' if g.stale else ''} | {g.license_tier} | {g.license_blocker or ''} |"
        )
    lines += ["", "## Anticipated additions (known-likely needs)", ""]
    lines += [f"- **{name}** — {why}" for name, why in ANTICIPATED_ADDITIONS]
    lines += [
        "",
        "> Emergent-requirements rule: any workstream needing an unregistered series adds",
        "> it to `requirements.yaml` (priority + rationale) in the same PR.",
    ]
    return "\n".join(lines) + "\n"


def generate_data_status_md(catalog: Catalog, reqs: Requirements, *, asof: str) -> str:
    vintage = catalog.current_vintage() or "(none)"
    # per-source freshness: latest last_date per source
    freshness = catalog.con.execute(
        "SELECT source, MAX(last_date) FROM observations_index "
        "WHERE vintage_id = ? GROUP BY source ORDER BY source",
        [vintage],
    ).fetchall()
    qc = catalog.con.execute(
        "SELECT severity, passed, COUNT(*) FROM qc_results WHERE vintage_id = ? "
        "GROUP BY severity, passed",
        [vintage],
    ).fetchall()
    revisions = catalog.con.execute(
        "SELECT series_id, detail FROM qc_results "
        "WHERE vintage_id = ? AND rule = 'revision_diff' AND passed = FALSE",
        [vintage],
    ).fetchall()

    lines = [
        "# DATA-STATUS.md (generated)",
        "",
        f"- current vintage: `{vintage}`",
        f"- as of: {asof}",
        "",
        "## Per-source freshness",
        "",
        "| source | latest obs |",
        "| --- | --- |",
    ]
    lines += [f"| {src} | {last} |" for src, last in freshness]
    lines += ["", "## QC summary", "", "| severity | passed | count |", "| --- | --- | --- |"]
    lines += [f"| {sev} | {passed} | {n} |" for sev, passed, n in qc]
    lines += ["", "## Revision-diff highlights", ""]
    if revisions:
        lines += [f"- `{sid}`: {detail}" for sid, detail in revisions]
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"
