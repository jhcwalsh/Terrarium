"""Generic manual-intake loader (STEP1-DATA-PLAN §WP1.3).

Drops land in ``data/intake/<source>/`` named ``<series-group>_<asof>.csv|xlsx``.
Each file is checksummed, validated against its schema, and either accepted (clean
round-trip to a validated frame + optional canonical per-series frames) or rejected
with a human-readable report — never partially ingested. Provenance (source, file,
hash, when, status) is written to the catalog ``intake_log``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ah.data.catalog import Catalog
from ah.data.schemas.base import IntakeSchema, Violation, read_table, render_report


class IntakeError(ValueError):
    pass


@dataclass
class IntakeResult:
    accepted: bool
    report: str
    schema: str
    series_group: str
    asof: str
    sha256: str
    frame: pd.DataFrame | None = None
    violations: list[Violation] = field(default_factory=list)


def parse_intake_filename(filename: str) -> tuple[str, str]:
    """``<series-group>_<asof>.<ext>`` -> (series_group, asof)."""
    stem = Path(filename).stem
    if "_" not in stem:
        raise IntakeError(f"filename '{filename}' must be <series-group>_<asof>.<ext>")
    group, asof = stem.rsplit("_", 1)
    if not group or not asof:
        raise IntakeError(f"filename '{filename}' must be <series-group>_<asof>.<ext>")
    return group, asof


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_file(path: str | Path, schema: IntakeSchema) -> IntakeResult:
    """Read + validate a drop file; never raises on data violations (they're reported)."""
    p = Path(path)
    group, asof = parse_intake_filename(p.name)
    sha = _sha256(p)
    try:
        df = read_table(p)
    except Exception as exc:
        v = [Violation("unreadable", "-", str(exc))]
        return IntakeResult(
            False, render_report(schema, p.name, v), schema.name, group, asof, sha, None, v
        )

    violations = schema.validate(df)

    # WP2R.1: the taxonomy boundary. For an Albourne schema grouped by strategy,
    # every vendor code must map to a platform sleeve_id — an unmapped code is an
    # intake error with a readable report, never a silent drop or a silent accept
    # (STEP2R-CONSOLIDATION-PLAN §WP2R.1). New codes are a mapping-file change
    # (taxonomy/albourne_mapping.yaml), made on delivery.
    if schema.source == "albourne" and schema.group_col and schema.group_col in df.columns:
        from ah.data.taxonomy import unmapped_codes

        for code in unmapped_codes(df[schema.group_col].dropna().unique()):
            violations.append(
                Violation(
                    "unmapped_strategy",
                    schema.group_col,
                    f"vendor code '{code}' maps to no sleeve_id in "
                    "taxonomy/albourne_mapping.yaml; add the mapping (or the reasoned "
                    "exclusion) before this file can be ingested",
                )
            )

    accepted = not violations
    return IntakeResult(
        accepted=accepted,
        report=render_report(schema, p.name, violations),
        schema=schema.name,
        series_group=group,
        asof=asof,
        sha256=sha,
        frame=df if accepted else None,
        violations=violations,
    )


def to_series_frames(schema: IntakeSchema, frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Canonical per-series ``(date, value)`` frames from a validated returns file.

    Only applies to return schemas with a single value column named ``ret`` and a
    period column; grouped files (``group_col``) yield one series per group value.
    """
    value_cols = [c for c in schema.value_columns() if c.name == "ret"]
    if schema.period_col is None or not value_cols:
        return {}
    out: dict[str, pd.DataFrame] = {}
    if schema.group_col and schema.group_col in frame.columns:
        for gval, g in frame.groupby(schema.group_col):
            sid = f"{schema.source}.{gval}"
            out[sid] = _canonical(g, schema.period_col)
    else:
        out[schema.source] = _canonical(frame, schema.period_col)
    return out


def _canonical(g: pd.DataFrame, period_col: str) -> pd.DataFrame:
    dates = [pd.Period(str(v)).to_timestamp() for v in g[period_col]]
    return pd.DataFrame({"date": dates, "value": pd.to_numeric(g["ret"]).to_numpy()}).sort_values(
        by="date", ignore_index=True
    )


def ingest_file(
    catalog: Catalog, path: str | Path, schema: IntakeSchema, *, received_at: str
) -> IntakeResult:
    """Validate a drop and record it in ``intake_log`` (accepted or rejected)."""
    result = validate_file(path, schema)
    catalog.record_intake(
        source=schema.source,
        file=Path(path).name,
        sha256=result.sha256,
        received_at=received_at,
        status="accepted" if result.accepted else "rejected",
        report=result.report,
    )
    return result
