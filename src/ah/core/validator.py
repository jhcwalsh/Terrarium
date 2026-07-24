"""WorldSpec validator — the V-rules (WORLDSPEC.md §3, STEP0-PLAN §WP0.3).

The schema (WP0.2) is single-field truth and is enforced as **clamps**; this module
adds cross-field **coherence** (warnings) and the three **blocking** rules that have
no defined semantics otherwise (V10/V11 and custom-vintage-without-sleeves in V12).

``validate(world)`` is pure: it returns a :class:`ValidationResult` with the
clamped world, the clamps, the warnings, and any blocking findings. It never reads
the wall clock. ``stamp_validation`` writes ``provenance.validation`` and flips
``status`` to ``validated`` — the caller supplies ``validated_at`` (audit metadata,
kept out of the deterministic numeric path).

Note this module *does* read ``narrative`` (V7/V8 are narrative-coherence rules).
That is allowed: the narrative-blindness rule binds the **engine**, not the
validator (WORLDSPEC.md §2 table).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from ah.core.loader import worldspec_schema

VALIDATOR_VERSION = "1.0.0"

_MATRIX_ROW_TOL = 1e-6
_SPREAD_RESPONSE_BPS = 150  # V6
_DATE_RE = re.compile(r"^([0-9]{4})(?:-Q([1-4]))?$")


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Clamp:
    path: str
    submitted: float
    applied: float


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str


@dataclass
class ValidationResult:
    clamped_world: dict[str, Any]
    clamps: list[Clamp] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    blocking: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing blocks the world from reaching ``validated``."""
        return not self.blocking


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #


def validate(world: dict[str, Any]) -> ValidationResult:
    """Run V1-V12. Returns the clamped world plus clamps/warnings/blocking."""
    w = copy.deepcopy(world)
    clamps: list[Clamp] = []
    warnings: list[Finding] = []
    blocking: list[Finding] = []

    # Clamps first (later rules read the clamped values).
    _v9_bounds_clamps(w, clamps, warnings)
    _v2_windows_inside_horizon(w, clamps)
    _v3_spread_geometry(w, warnings)

    # Coherence warnings.
    _v1_rate_inflation(w, warnings)
    _v4_regime_condition(w, warnings)
    _v5_extreme_divergence(w, warnings)
    _v6_crisis_without_stress(w, warnings)
    _v7_narrative_dates(w, warnings)
    _v8_dispatch_hygiene(w, warnings)

    # Blocking rules.
    _v10_v11_regime_structure(w, blocking)
    _v12_vintage_consistency(w, warnings, blocking)

    return ValidationResult(w, clamps, warnings, blocking)


def stamp_validation(
    result: ValidationResult,
    *,
    validated_at: str,
    validator_version: str = VALIDATOR_VERSION,
) -> dict[str, Any]:
    """Write ``provenance.validation`` and flip status to ``validated`` if clean.

    ``validated_at`` is audit metadata supplied by the caller (never wall-clocked
    here, to keep the module deterministic). If the world has blocking findings,
    status is left unchanged (it never reaches ``validated``).
    """
    w = copy.deepcopy(result.clamped_world)
    w.setdefault("provenance", {})["validation"] = {
        "validator_version": validator_version,
        "validated_at": validated_at,
        "clamps": [
            {"path": c.path, "submitted": c.submitted, "applied": c.applied} for c in result.clamps
        ],
        "warnings": [{"rule": f.rule, "message": f.message} for f in result.warnings],
    }
    if result.ok and w.get("status") == "draft":
        w["status"] = "validated"
    return w


# --------------------------------------------------------------------------- #
# V9 — bounds clamps (drive from the schema so the bounds have one home)
# --------------------------------------------------------------------------- #


def _v9_bounds_clamps(world: dict[str, Any], clamps: list[Clamp], warnings: list[Finding]) -> None:
    schema = worldspec_schema()
    before = len(clamps)
    _clamp_node(schema, world, "", clamps)
    if len(clamps) - before > 3:
        warnings.append(
            Finding(
                "V9",
                "Compiler output required heavy clamping "
                f"({len(clamps) - before} fields) — review scenario interpretation.",
            )
        )


def _clamp_node(
    node_schema: dict[str, Any],
    value: Any,
    pointer: str,
    clamps: list[Clamp],
) -> None:
    node_type = node_schema.get("type")
    if node_type == "object" and isinstance(value, dict):
        for key, sub in node_schema.get("properties", {}).items():
            if key in value:
                _clamp_leaf(sub, value, key, f"{pointer}/{key}", clamps)
    elif node_type == "array" and isinstance(value, list):
        item_schema = node_schema.get("items", {})
        for i, _item in enumerate(value):
            _clamp_leaf(item_schema, value, i, f"{pointer}/{i}", clamps)


def _clamp_leaf(
    node_schema: dict[str, Any],
    parent: Any,
    key: Any,
    pointer: str,
    clamps: list[Clamp],
) -> None:
    value = parent[key]
    node_type = node_schema.get("type")
    if node_type in ("object", "array"):
        _clamp_node(node_schema, value, pointer, clamps)
        return
    if node_type not in ("number", "integer"):
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return
    lo = node_schema.get("minimum")
    hi = node_schema.get("maximum")
    applied: float = value
    if lo is not None and value < lo:
        applied = lo
    if hi is not None and value > hi:
        applied = hi
    if applied != value:
        if node_type == "integer":
            applied = int(applied)
        parent[key] = applied
        clamps.append(Clamp(pointer, value, applied))


# --------------------------------------------------------------------------- #
# small navigation helpers
# --------------------------------------------------------------------------- #


def _obj(world: dict[str, Any], *keys: str) -> dict[str, Any]:
    node: Any = world
    for k in keys:
        node = node.get(k) if isinstance(node, dict) else None
        if node is None:
            return {}
    return node if isinstance(node, dict) else {}


def _num(world: dict[str, Any], *keys: str) -> float | None:
    node: Any = world
    for k in keys:
        node = node.get(k) if isinstance(node, dict) else None
        if node is None:
            return None
    return node if isinstance(node, (int, float)) and not isinstance(node, bool) else None


# --------------------------------------------------------------------------- #
# V2 — windows / peaks inside the horizon (clamp to horizon end)
# --------------------------------------------------------------------------- #


def _v2_windows_inside_horizon(world: dict[str, Any], clamps: list[Clamp]) -> None:
    quarters = _num(world, "horizon", "quarters")
    if quarters is None:
        return
    q = int(quarters)
    last = q - 1

    for section in ("inflation", "credit"):
        pk = _num(world, "factor_conditions", section, "peak_quarter")
        if pk is not None and pk > last:
            world["factor_conditions"][section]["peak_quarter"] = last
            clamps.append(Clamp(f"/factor_conditions/{section}/peak_quarter", pk, last))

    windows = world.get("factor_conditions", {}).get("crisis_windows")
    if not isinstance(windows, list):
        return
    for i, win in enumerate(windows):
        if not isinstance(win, dict):
            continue
        start = win.get("start_quarter")
        length = win.get("length_quarters")
        if not isinstance(start, int) or not isinstance(length, int):
            continue
        base = f"/factor_conditions/crisis_windows/{i}"
        if length > q:  # window longer than the whole horizon
            clamps.append(Clamp(f"{base}/length_quarters", length, q))
            win["length_quarters"] = length = q
        if start + length > q:
            new_start = max(0, q - length)
            clamps.append(Clamp(f"{base}/start_quarter", start, new_start))
            win["start_quarter"] = new_start


# --------------------------------------------------------------------------- #
# V3 — spread geometry (swap + warn)
# --------------------------------------------------------------------------- #


def _v3_spread_geometry(world: dict[str, Any], warnings: list[Finding]) -> None:
    credit = _obj(world, "factor_conditions", "credit")
    start = credit.get("hy_spread_start_bps")
    peak = credit.get("hy_spread_peak_bps")
    if isinstance(start, (int, float)) and isinstance(peak, (int, float)) and peak < start:
        credit["hy_spread_start_bps"], credit["hy_spread_peak_bps"] = peak, start
        warnings.append(
            Finding(
                "V3",
                f"HY spread peak ({peak}) below start ({start}); swapped so peak >= start.",
            )
        )


# --------------------------------------------------------------------------- #
# V1 / V4 / V5 / V6 — coherence warnings
# --------------------------------------------------------------------------- #


def _v1_rate_inflation(world: dict[str, Any], warnings: list[Finding]) -> None:
    avg = _num(world, "factor_conditions", "inflation", "average_pct")
    end = _num(world, "factor_conditions", "policy_rate", "end_pct")
    if avg is not None and end is not None and avg >= 5 and end <= 2:
        warnings.append(
            Finding(
                "V1",
                "Deeply negative real rates throughout — financial repression. "
                "Confirm this is intended.",
            )
        )


def _regime_names(world: dict[str, Any]) -> set[str]:
    regimes = _obj(world, "regimes")
    names: set[str] = set()
    mode = regimes.get("mode")
    if mode == "sequence":
        for seg in regimes.get("sequence") or []:
            if isinstance(seg, dict) and isinstance(seg.get("regime"), str):
                names.add(seg["regime"])
    elif mode == "transition_matrix":
        tm = regimes.get("transition_matrix") or {}
        for s in tm.get("states") or []:
            if isinstance(s, str):
                names.add(s)
        if isinstance(tm.get("initial_state"), str):
            names.add(tm["initial_state"])
    return names


def _v4_regime_condition(world: dict[str, Any], warnings: list[Finding]) -> None:
    avg = _num(world, "factor_conditions", "inflation", "average_pct")
    if avg is None:
        return
    names = _regime_names(world)
    if "stagflation" in names and avg < 4:
        warnings.append(Finding("V4", f"stagflation regime with average inflation {avg}% (<4%)."))
    if "deflation_boom" in names and avg > 2:
        warnings.append(
            Finding("V4", f"deflation_boom regime with average inflation {avg}% (>2%).")
        )


def _v5_extreme_divergence(world: dict[str, Any], warnings: list[Finding]) -> None:
    eq = _num(world, "factor_conditions", "equity", "drift_annual_pct")
    pe = _num(world, "structural", "private_equity", "entry_multiple_drift_annual_pct")
    if eq is None or pe is None:
        return
    # Primary pattern from WORLDSPEC.md, plus its symmetric reverse.
    if (eq >= 8 and pe <= -3) or (eq <= -8 and pe >= 3):
        warnings.append(
            Finding(
                "V5",
                "PE valuation trend runs strongly against public equity trend — "
                "plausible but unusual; confirm.",
            )
        )


def _v6_crisis_without_stress(world: dict[str, Any], warnings: list[Finding]) -> None:
    credit = _obj(world, "factor_conditions", "credit")
    start = credit.get("hy_spread_start_bps")
    peak = credit.get("hy_spread_peak_bps")
    if not (isinstance(start, (int, float)) and isinstance(peak, (int, float))):
        return
    windows = world.get("factor_conditions", {}).get("crisis_windows") or []
    for win in windows:
        if not isinstance(win, dict):
            continue
        sev = win.get("severity")
        if isinstance(sev, (int, float)) and sev >= 0.5 and peak < start + _SPREAD_RESPONSE_BPS:
            warnings.append(
                Finding(
                    "V6",
                    f"Severe crisis (severity {sev}) with no credit-spread "
                    f"response (peak {peak} < start {start} + "
                    f"{_SPREAD_RESPONSE_BPS}).",
                )
            )
            return


# --------------------------------------------------------------------------- #
# V7 / V8 — narrative coherence
# --------------------------------------------------------------------------- #


def _parse_date(text: str) -> tuple[int, int] | None:
    """('YYYY' | 'YYYY-Qn') -> (year, quarter); quarter 0 means year-only."""
    m = _DATE_RE.match(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 0)


def _horizon_span(world: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]] | None:
    start = _obj(world, "horizon").get("start")
    quarters = _num(world, "horizon", "quarters")
    if not isinstance(start, str) or quarters is None:
        return None
    m = re.match(r"^([0-9]{4})-Q([1-4])$", start)
    if not m:
        return None
    y0, q0 = int(m.group(1)), int(m.group(2))
    n = int(quarters)
    last_idx = (q0 - 1) + (n - 1)
    y1, q1 = y0 + last_idx // 4, last_idx % 4 + 1
    return (y0, q0), (y1, q1)


def _v7_narrative_dates(world: dict[str, Any], warnings: list[Finding]) -> None:
    span = _horizon_span(world)
    if span is None:
        return
    (y0, q0), (y1, q1) = span
    for disp in _obj(world, "narrative").get("dispatches") or []:
        if not isinstance(disp, dict) or not isinstance(disp.get("date"), str):
            continue
        parsed = _parse_date(disp["date"])
        if parsed is None:
            continue
        y, q = parsed
        # year-only ('YYYY') is inside if within the calendar-year span
        inside = y0 <= y <= y1 if q == 0 else (y0, q0) <= (y, q) <= (y1, q1)
        if not inside:
            warnings.append(
                Finding("V7", f"Dispatch date {disp['date']} falls outside the horizon.")
            )


def _v8_dispatch_hygiene(world: dict[str, Any], warnings: list[Finding]) -> None:
    dispatches = _obj(world, "narrative").get("dispatches")
    if not isinstance(dispatches, list):
        return
    if not (3 <= len(dispatches) <= 10):
        warnings.append(Finding("V8", f"Expected 3-10 dispatches, found {len(dispatches)}."))
    if any(isinstance(d, dict) and not (d.get("headline") or "").strip() for d in dispatches):
        warnings.append(Finding("V8", "One or more dispatches have an empty headline."))
    keys: list[tuple[int, int]] = []
    for d in dispatches:
        if isinstance(d, dict) and isinstance(d.get("date"), str):
            parsed = _parse_date(d["date"])
            if parsed is not None:
                keys.append(parsed)
    if any(keys[i + 1] < keys[i] for i in range(len(keys) - 1)):
        warnings.append(Finding("V8", "Dispatch dates are not non-decreasing."))


# --------------------------------------------------------------------------- #
# V10 / V11 — regime structure (blocking)
# --------------------------------------------------------------------------- #


def _v10_v11_regime_structure(world: dict[str, Any], blocking: list[Finding]) -> None:
    regimes = _obj(world, "regimes")
    mode = regimes.get("mode")
    quarters = _num(world, "horizon", "quarters")

    if mode == "sequence":
        segs = regimes.get("sequence")
        if not isinstance(segs, list) or not segs:
            blocking.append(Finding("V10", "sequence mode requires a non-empty sequence."))
            return
        if quarters is None:
            return
        ordered = sorted(segs, key=lambda s: s.get("from_quarter", -1))
        cursor = 0
        for seg in ordered:
            f, t = seg.get("from_quarter"), seg.get("to_quarter")
            if not isinstance(f, int) or not isinstance(t, int) or t < f:
                blocking.append(Finding("V10", f"Malformed segment {seg}."))
                return
            if f != cursor:
                blocking.append(
                    Finding(
                        "V10",
                        f"Sequence has a gap/overlap at quarter {cursor} "
                        f"(next segment starts at {f}).",
                    )
                )
                return
            cursor = t + 1
        if cursor != int(quarters):
            blocking.append(
                Finding(
                    "V10",
                    f"Sequence tiles [0,{cursor - 1}] but horizon is "
                    f"{int(quarters)} quarters; must tile [0,{int(quarters) - 1}].",
                )
            )

    elif mode == "transition_matrix":
        tm = regimes.get("transition_matrix")
        if not isinstance(tm, dict):
            blocking.append(Finding("V11", "transition_matrix mode requires a transition_matrix."))
            return
        states = tm.get("states") or []
        matrix = tm.get("matrix") or []
        n = len(states)
        if len(matrix) != n or any(len(row) != n for row in matrix):
            blocking.append(Finding("V11", f"Transition matrix must be square on {n} states."))
            return
        for i, row in enumerate(matrix):
            total = sum(row)
            if abs(total - 1.0) > _MATRIX_ROW_TOL:
                blocking.append(
                    Finding("V11", f"Transition matrix row {i} sums to {total} (!= 1).")
                )
                return


# --------------------------------------------------------------------------- #
# V12 — vintage consistency (warn or block)
# --------------------------------------------------------------------------- #

_SLEEVES = ("private_equity", "private_credit", "real_estate", "infrastructure")


def _v12_vintage_consistency(
    world: dict[str, Any], warnings: list[Finding], blocking: list[Finding]
) -> None:
    structural = _obj(world, "structural")
    vintage = structural.get("parameter_vintage")
    present = [s for s in _SLEEVES if isinstance(structural.get(s), dict)]
    if vintage in ("historical_average", "current"):
        if present:
            warnings.append(
                Finding(
                    "V12",
                    f"parameter_vintage='{vintage}' ignores sleeve overrides present "
                    f"in the document: {present}.",
                )
            )
    elif vintage == "custom" and not present:
        blocking.append(
            Finding(
                "V12",
                "parameter_vintage='custom' requires at least one sleeve object.",
            )
        )
