"""DuckDB catalog + immutable vintage store (STEP1-DATA-PLAN §WP1.1).

A *vintage* is a dated snapshot label. Normalized series are written once to
Parquet under ``<root>/parquet/<vintage>/<source>/<series_id>.parquet`` and indexed
in a DuckDB catalog (``<root>/catalog.duckdb``). Nothing is ever overwritten:
re-writing a (vintage, series) raises. ``current`` is an append-only pointer,
advanced only when QC passes (a quarantined vintage cannot advance); ``as_of`` reads
resolve through the pointer history.

Canonical observation schema: ``(date, value, series_id, vintage)``. Frequency and
units live in the catalog, not the frame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ah.data.manifest import Requirement

CANONICAL_COLUMNS = ["date", "value", "series_id", "vintage"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    series_id VARCHAR PRIMARY KEY,
    source VARCHAR, code VARCHAR, frequency VARCHAR, units VARCHAR,
    license_tier VARCHAR, redistributable BOOLEAN,
    first_date DATE, last_date DATE,
    is_proxy BOOLEAN DEFAULT FALSE, methodology VARCHAR,
    freshness_sla INTEGER, notes VARCHAR
);
CREATE TABLE IF NOT EXISTS vintages (
    vintage_id VARCHAR PRIMARY KEY,
    created_at VARCHAR NOT NULL,
    status VARCHAR NOT NULL       -- pending | current | quarantined | superseded
);
CREATE TABLE IF NOT EXISTS observations_index (
    vintage_id VARCHAR, series_id VARCHAR, source VARCHAR, path VARCHAR,
    n_obs INTEGER, first_date DATE, last_date DATE,
    PRIMARY KEY (vintage_id, series_id)
);
CREATE TABLE IF NOT EXISTS current_pointer (
    seq INTEGER PRIMARY KEY, vintage_id VARCHAR NOT NULL, set_at VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS intake_log (
    id INTEGER PRIMARY KEY, source VARCHAR, file VARCHAR, sha256 VARCHAR,
    received_at VARCHAR, status VARCHAR, report VARCHAR
);
CREATE TABLE IF NOT EXISTS qc_results (
    id INTEGER PRIMARY KEY, vintage_id VARCHAR, series_id VARCHAR, rule VARCHAR,
    severity VARCHAR, passed BOOLEAN, detail VARCHAR, created_at VARCHAR
);
"""


class CatalogError(RuntimeError):
    pass


class ImmutableVintageError(CatalogError):
    """Raised on any attempt to overwrite an existing (vintage, series)."""


class Catalog:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.parquet_root = self.root / "parquet"
        self.parquet_root.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.root / "catalog.duckdb"))
        self.con.execute(_SCHEMA)

    def _scalar(self, sql: str, params: list[Any] | None = None) -> Any:
        row = self.con.execute(sql, params or []).fetchone()
        return None if row is None else row[0]

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> Catalog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- series registry --------------------------------------------------- #

    def register_series(self, req: Requirement, *, is_proxy: bool = False) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO series "
            "(series_id, source, code, frequency, units, license_tier, redistributable, "
            " is_proxy, freshness_sla, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                req.series_id,
                req.source,
                req.code,
                req.frequency,
                req.units,
                req.license_tier,
                req.redistributable,
                is_proxy,
                req.sla_days,
                req.notes,
            ],
        )

    def get_series(self, series_id: str) -> dict[str, Any] | None:
        row = self.con.execute("SELECT * FROM series WHERE series_id = ?", [series_id]).fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self.con.description]
        return dict(zip(cols, row, strict=True))

    def _source_of(self, series_id: str) -> str:
        row = self.con.execute(
            "SELECT source FROM series WHERE series_id = ?", [series_id]
        ).fetchone()
        return str(row[0]) if row else series_id.split(".", 1)[0]

    # -- vintages ---------------------------------------------------------- #

    def create_vintage(self, vintage_id: str, *, created_at: str, status: str = "pending") -> None:
        exists = self.con.execute(
            "SELECT 1 FROM vintages WHERE vintage_id = ?", [vintage_id]
        ).fetchone()
        if exists:
            raise ImmutableVintageError(f"vintage {vintage_id} already exists")
        self.con.execute(
            "INSERT INTO vintages(vintage_id, created_at, status) VALUES (?,?,?)",
            [vintage_id, created_at, status],
        )

    def vintage_status(self, vintage_id: str) -> str | None:
        row = self.con.execute(
            "SELECT status FROM vintages WHERE vintage_id = ?", [vintage_id]
        ).fetchone()
        return str(row[0]) if row else None

    def quarantine_vintage(self, vintage_id: str) -> None:
        self.con.execute(
            "UPDATE vintages SET status = 'quarantined' WHERE vintage_id = ?", [vintage_id]
        )

    # -- observations (immutable) ----------------------------------------- #

    def write_observations(self, vintage_id: str, series_id: str, frame: pd.DataFrame) -> str:
        """Write a series' observations for a vintage. Never overwrites."""
        if self.vintage_status(vintage_id) is None:
            raise CatalogError(f"unknown vintage {vintage_id}; create it first")
        already = self.con.execute(
            "SELECT 1 FROM observations_index WHERE vintage_id = ? AND series_id = ?",
            [vintage_id, series_id],
        ).fetchone()
        if already:
            raise ImmutableVintageError(
                f"({vintage_id}, {series_id}) already written; vintages are immutable"
            )

        source = self._source_of(series_id)
        df = frame.copy()
        if "date" not in df or "value" not in df:
            raise CatalogError("frame must have 'date' and 'value' columns")
        df["series_id"] = series_id
        df["vintage"] = vintage_id
        # `is_proxy` is the one optional column that survives storage: a
        # synthetic observation (splice backfill, declared gap fill) must stay
        # flagged in the stored frame or the substitution becomes silent.
        extra = ["is_proxy"] if "is_proxy" in df.columns else []
        df = df.reindex(columns=CANONICAL_COLUMNS + extra)
        df = df.sort_values(by="date", ignore_index=True)

        out_dir = self.parquet_root / vintage_id / source
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{series_id}.parquet"
        if path.exists():
            raise ImmutableVintageError(f"{path} already exists; vintages are immutable")
        df.to_parquet(path, index=False)

        first = str(pd.to_datetime(df["date"]).min().date())
        last = str(pd.to_datetime(df["date"]).max().date())
        self.con.execute(
            "INSERT INTO observations_index "
            "(vintage_id, series_id, source, path, n_obs, first_date, last_date) "
            "VALUES (?,?,?,?,?,?,?)",
            [vintage_id, series_id, source, str(path), len(df), first, last],
        )
        return str(path)

    def read_observations(self, vintage_id: str, series_id: str) -> pd.DataFrame:
        row = self.con.execute(
            "SELECT path FROM observations_index WHERE vintage_id = ? AND series_id = ?",
            [vintage_id, series_id],
        ).fetchone()
        if row is None:
            raise CatalogError(f"no observations for ({vintage_id}, {series_id})")
        return pd.read_parquet(row[0])

    # -- current pointer + as-of ------------------------------------------ #

    def advance_pointer(self, vintage_id: str, *, when: str) -> None:
        """Make ``vintage_id`` current. Refuses if it is quarantined (QC gate)."""
        status = self.vintage_status(vintage_id)
        if status is None:
            raise CatalogError(f"unknown vintage {vintage_id}")
        if status == "quarantined":
            raise CatalogError(
                f"vintage {vintage_id} is quarantined; pointer not advanced (QC failed)"
            )
        prev = self.current_vintage()
        if prev is not None and prev != vintage_id:
            self.con.execute(
                "UPDATE vintages SET status = 'superseded' WHERE vintage_id = ?", [prev]
            )
        self.con.execute(
            "UPDATE vintages SET status = 'current' WHERE vintage_id = ?", [vintage_id]
        )
        seq = self._scalar("SELECT COALESCE(MAX(seq), 0) + 1 FROM current_pointer")
        self.con.execute(
            "INSERT INTO current_pointer(seq, vintage_id, set_at) VALUES (?,?,?)",
            [seq, vintage_id, when],
        )

    def current_vintage(self) -> str | None:
        row = self.con.execute(
            "SELECT vintage_id FROM current_pointer ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else None

    def asof(self, as_of: str) -> str | None:
        """The vintage that was current at ``as_of`` (latest pointer <= as_of)."""
        row = self.con.execute(
            "SELECT vintage_id FROM current_pointer WHERE set_at <= ? "
            "ORDER BY set_at DESC, seq DESC LIMIT 1",
            [as_of],
        ).fetchone()
        return str(row[0]) if row else None

    def read_asof(self, series_id: str, as_of: str) -> pd.DataFrame:
        vintage = self.asof(as_of)
        if vintage is None:
            raise CatalogError(f"no vintage current as of {as_of}")
        return self.read_observations(vintage, series_id)

    def latest_vintage_with(self, series_id: str) -> str | None:
        """The most recent *pointer-history* vintage that holds ``series_id``, or None.

        A vintage is supposed to be a complete as-of snapshot, but ``ah.data.refresh``
        only fetches series that are missing or stale, so a series that was neither
        would never be written into the new vintage and would silently vanish from
        every pinned read. This walks the append-only ``current_pointer`` newest-first
        and reports where the series was last seen, which is what lets ``refresh``
        carry it forward instead of dropping it. Read-only; no fallback is applied at
        read time, so a pinned ``read_observations`` stays exactly as literal as before.
        """
        rows = self.con.execute(
            "SELECT p.vintage_id FROM current_pointer p "
            "JOIN observations_index o ON o.vintage_id = p.vintage_id "
            "WHERE o.series_id = ? ORDER BY p.seq DESC LIMIT 1",
            [series_id],
        ).fetchone()
        return str(rows[0]) if rows else None

    # -- logs -------------------------------------------------------------- #

    def _next_id(self, table: str) -> int:
        return int(self._scalar(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}"))

    def record_intake(
        self, *, source: str, file: str, sha256: str, received_at: str, status: str, report: str
    ) -> int:
        rid = self._next_id("intake_log")
        self.con.execute(
            "INSERT INTO intake_log(id, source, file, sha256, received_at, status, report) "
            "VALUES (?,?,?,?,?,?,?)",
            [rid, source, file, sha256, received_at, status, report],
        )
        return rid

    def record_qc(
        self,
        *,
        vintage_id: str,
        series_id: str,
        rule: str,
        severity: str,
        passed: bool,
        detail: str,
        created_at: str,
    ) -> int:
        rid = self._next_id("qc_results")
        self.con.execute(
            "INSERT INTO qc_results"
            "(id, vintage_id, series_id, rule, severity, passed, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [rid, vintage_id, series_id, rule, severity, passed, detail, created_at],
        )
        return rid
