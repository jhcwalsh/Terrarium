"""Declarative intake schemas + validation (STEP1-DATA-PLAN §WP1.3).

A manual-intake file type is described by an :class:`IntakeSchema`: required
columns, per-column dtype/bounds, and (optionally) a period column + frequency for
duplicate-period and silent-gap detection. ``validate`` returns a list of
:class:`Violation` — an empty list means the drop is clean. Schemas fail *loudly and
kindly*: every violation names exactly what is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

Dtype = str  # "period" | "float" | "int" | "str"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: Dtype = "float"
    required: bool = True
    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class Violation:
    kind: str
    column: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.column}: {self.detail}"


@dataclass(frozen=True)
class IntakeSchema:
    name: str
    source: str
    columns: list[ColumnSpec]
    period_col: str | None = None
    frequency: str | None = None  # "Q" | "M" | "A"
    group_col: str | None = None  # e.g. "strategy": one series per group value
    notes: str = field(default="")

    def value_columns(self) -> list[ColumnSpec]:
        return [c for c in self.columns if c.dtype in ("float", "int")]

    def validate(self, df: pd.DataFrame) -> list[Violation]:
        violations: list[Violation] = []

        if df is None or len(df) == 0:
            return [Violation("empty", "-", "no rows in file")]

        present = set(df.columns)
        for col in self.columns:
            if col.required and col.name not in present:
                violations.append(Violation("missing_column", col.name, "required column absent"))
        if any(v.kind == "missing_column" for v in violations):
            return violations  # cannot check further without the columns

        # dtype + bounds
        for col in self.columns:
            if col.name not in present:
                continue
            series = df[col.name]
            if col.dtype in ("float", "int"):
                numeric = pd.to_numeric(series, errors="coerce")
                n_bad = int(numeric.isna().sum() - series.isna().sum())
                if n_bad > 0:
                    violations.append(
                        Violation("non_numeric", col.name, f"{n_bad} non-numeric value(s)")
                    )
                if col.min is not None:
                    below = int((numeric < col.min).sum())
                    if below:
                        violations.append(
                            Violation("out_of_bounds", col.name, f"{below} value(s) < {col.min}")
                        )
                if col.max is not None:
                    above = int((numeric > col.max).sum())
                    if above:
                        violations.append(
                            Violation("out_of_bounds", col.name, f"{above} value(s) > {col.max}")
                        )

        # period: duplicates + silent gaps
        if self.period_col and self.period_col in present and self.frequency:
            violations.extend(self._check_periods(df))

        return violations

    def _check_periods(self, df: pd.DataFrame) -> list[Violation]:
        assert self.period_col is not None and self.frequency is not None
        out: list[Violation] = []
        # Parse probe: every period must be parseable before the per-group checks
        # below re-parse them. The result is deliberately discarded -- an unparseable
        # period is reported once here for the whole frame, not once per group.
        try:
            pd.PeriodIndex([pd.Period(str(v), freq=self.frequency) for v in df[self.period_col]])
        except Exception as exc:
            return [Violation("bad_period", self.period_col, f"unparseable period(s): {exc}")]

        # If grouped, check per group; else globally.
        groups = (
            [g for _, g in df.groupby(self.group_col)]
            if self.group_col and self.group_col in df.columns
            else [df]
        )
        for g in groups:
            idx = pd.PeriodIndex(
                [pd.Period(str(v), freq=self.frequency) for v in g[self.period_col]]
            )
            dups = idx[idx.duplicated()].unique()
            if len(dups):
                out.append(
                    Violation(
                        "duplicate_period", self.period_col, f"repeated: {list(map(str, dups))}"
                    )
                )
            ordinals = sorted(int(p.ordinal) for p in idx.drop_duplicates())
            gaps = [
                (ordinals[i], ordinals[i + 1])
                for i in range(len(ordinals) - 1)
                if ordinals[i + 1] - ordinals[i] != 1
            ]
            if gaps:
                out.append(
                    Violation(
                        "gap", self.period_col, f"{len(gaps)} silent gap(s) in the period index"
                    )
                )
        return out


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a CSV or XLSX intake file into a DataFrame."""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p)


def render_report(schema: IntakeSchema, filename: str, violations: list[Violation]) -> str:
    if not violations:
        return f"OK: {filename} validated against schema '{schema.name}' with no violations."
    lines = [
        f"REJECTED: {filename} failed schema '{schema.name}' ({len(violations)} violation(s)):"
    ]
    lines += [f"  - {v}" for v in violations]
    return "\n".join(lines)
