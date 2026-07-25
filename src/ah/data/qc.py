"""Quality-control framework (STEP1-DATA-PLAN §WP1.4).

Per-series checks (schema/dtype, monotonic non-duplicate dates, frequency
conformance, unit-class bounds, staleness vs SLA, jump detection, revision diff vs
prior vintage) plus cross-series identities. Severity is ``enforce`` or ``warn``:
a failing ``enforce`` check quarantines the vintage (the pointer then cannot
advance) and is written to ``qc_results``. Jump/revision have rule-specific
severity; everything else inherits the manifest's ``enforce`` flag.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ah.data.catalog import Catalog
from ah.data.manifest import Requirement

_FREQ_TO_PERIOD = {"D->M": "M", "M": "M", "Q": "Q", "A": "Y"}


@dataclass(frozen=True)
class QCFinding:
    series_id: str
    rule: str
    severity: str  # "enforce" | "warn"
    passed: bool
    detail: str


@dataclass
class QCReport:
    findings: list[QCFinding]

    @property
    def enforce_failures(self) -> list[QCFinding]:
        return [f for f in self.findings if f.severity == "enforce" and not f.passed]

    @property
    def passed(self) -> bool:
        return not self.enforce_failures


# --------------------------------------------------------------------------- #
# unit-class bounds
# --------------------------------------------------------------------------- #


def bounds_for(req: Requirement) -> tuple[float | None, float | None, bool]:
    """Return (low, high, strict_positive) for a requirement's units class."""
    sid = req.series_id.lower()
    u = req.units
    if u == "pct":
        low = 0.0 if ("oas" in sid or "spread" in sid) else -5.0
        return (low, 30.0, False)
    if u in ("index", "idx", "lvl"):
        return (0.0, None, u != "lvl")  # index/idx strictly positive
    if u == "ret":
        return (-0.8, 2.0, False)
    if u == "gap":  # credit-to-GDP gap: can be strongly negative in deleveragings
        return (-100.0, 100.0, False)
    if u == "0/1":
        return (0.0, 1.0, False)
    if u == "bps":
        return (0.0, None, False)
    return (None, None, False)


# --------------------------------------------------------------------------- #
# per-series checks
# --------------------------------------------------------------------------- #


def check_series(
    req: Requirement,
    frame: pd.DataFrame,
    *,
    asof: str | None = None,
    prior: pd.DataFrame | None = None,
    jump_k: float = 6.0,
    revision_tol: float = 1e-9,
) -> list[QCFinding]:
    sid = req.series_id
    base = "enforce" if req.enforce else "warn"
    out: list[QCFinding] = []

    def add(rule: str, passed: bool, detail: str, severity: str = base) -> None:
        out.append(QCFinding(sid, rule, severity, passed, detail))

    # schema / dtype
    if "date" not in frame.columns or "value" not in frame.columns:
        add("schema", False, "missing date/value columns")
        return out
    values = pd.to_numeric(frame["value"], errors="coerce")
    n_bad = int(values.isna().sum() - frame["value"].isna().sum())
    add("dtype", n_bad == 0, f"{n_bad} non-numeric value(s)")

    dates = pd.to_datetime(frame["date"])
    # monotonic + no duplicates
    add("monotonic", bool(dates.is_monotonic_increasing), "dates not sorted ascending")
    n_dup = int(dates.duplicated().sum())
    add("no_duplicates", n_dup == 0, f"{n_dup} duplicate date(s)")

    # frequency conformance (warn: real public series have occasional single gaps
    # that splice/proxy fill; gross frequency errors are prevented by the connectors)
    period = _FREQ_TO_PERIOD.get(req.frequency)
    if period is not None and len(dates) > 1:
        ordinals = pd.PeriodIndex(dates, freq=period).astype("int64")
        steps = np.diff(np.sort(ordinals.to_numpy()))
        irregular = int((steps != 1).sum())
        add(
            "frequency",
            irregular == 0,
            f"{irregular} irregular step(s) for {req.frequency}",
            severity="warn",
        )

    # unit-class bounds
    low, high, strict_pos = bounds_for(req)
    if low is not None:
        n = int((values < low).sum())
        add("bounds_low", n == 0, f"{n} value(s) < {low}")
    if high is not None:
        n = int((values > high).sum())
        add("bounds_high", n == 0, f"{n} value(s) > {high}")
    if strict_pos:
        n = int((values <= 0).sum())
        add("positive", n == 0, f"{n} non-positive value(s)")

    # staleness vs SLA — measured from the last observation's PERIOD END (a month-start
    # label represents the whole month, so month-old data is not 30 days stale)
    if asof is not None and len(dates) > 0:
        period_end = pd.Period(dates.max(), freq=period or "M").end_time
        age = (pd.Timestamp(asof) - period_end).days
        add("staleness", age <= req.sla_days, f"last obs {age}d old (SLA {req.sla_days}d)")

    # jump detection (always warn)
    if len(values.dropna()) > 5:
        diffs = values.diff()
        # use the PRIOR window's volatility so a spike does not inflate its own threshold
        roll = diffs.rolling(12, min_periods=3).std().shift(1)
        jumps = int((diffs.abs() > jump_k * roll).sum())
        add("jump", jumps == 0, f"{jumps} jump(s) > {jump_k}*rolling-sigma", severity="warn")

    # revision diff vs prior vintage
    if prior is not None:
        out.append(_revision_diff(req, frame, prior, revision_tol))

    return out


def _revision_diff(
    req: Requirement, frame: pd.DataFrame, prior: pd.DataFrame, tol: float
) -> QCFinding:
    # Licensed files should not silently rewrite history -> enforce; public revisions warn.
    severity = "enforce" if req.license_tier in ("REG", "COMM") else "warn"
    cur = frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")["value"]
    old = prior.assign(date=pd.to_datetime(prior["date"])).set_index("date")["value"]
    common = cur.index.intersection(old.index)
    changed = int(
        (cur.loc[common].astype(float).sub(old.loc[common].astype(float)).abs() > tol).sum()
    )
    return QCFinding(
        req.series_id,
        "revision_diff",
        severity,
        changed == 0,
        f"{changed} historical value(s) changed vs prior vintage",
    )


# --------------------------------------------------------------------------- #
# cross-series identities
# --------------------------------------------------------------------------- #


def check_cross_series(frames: dict[str, pd.DataFrame]) -> list[QCFinding]:
    out: list[QCFinding] = []
    # Baa yield >= Aaa yield (credit quality ordering) — a real per-date identity.
    if "fred.BAA" in frames and "fred.AAA" in frames:
        baa = _indexed(frames["fred.BAA"])
        aaa = _indexed(frames["fred.AAA"])
        common = baa.index.intersection(aaa.index)
        n = int((baa.loc[common] < aaa.loc[common] - 1e-9).sum())
        out.append(
            QCFinding(
                "fred.BAA", "identity_baa_ge_aaa", "warn", n == 0, f"{n} date(s) with Baa < Aaa"
            )
        )
    return out


def _indexed(frame: pd.DataFrame) -> pd.Series:
    return frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")["value"].astype(float)


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #


def run_qc(
    catalog: Catalog,
    vintage_id: str,
    reqs_frames: list[tuple[Requirement, pd.DataFrame]],
    *,
    asof: str,
    created_at: str,
    priors: dict[str, pd.DataFrame] | None = None,
) -> QCReport:
    """Run all checks, persist to qc_results, and quarantine on any enforce failure."""
    priors = priors or {}
    findings: list[QCFinding] = []
    for req, frame in reqs_frames:
        findings.extend(check_series(req, frame, asof=asof, prior=priors.get(req.series_id)))
    frames_by_id = {req.series_id: f for req, f in reqs_frames}
    findings.extend(check_cross_series(frames_by_id))

    for f in findings:
        catalog.record_qc(
            vintage_id=vintage_id,
            series_id=f.series_id,
            rule=f.rule,
            severity=f.severity,
            passed=f.passed,
            detail=f.detail,
            created_at=created_at,
        )

    report = QCReport(findings)
    if not report.passed:
        catalog.quarantine_vintage(vintage_id)
    return report
