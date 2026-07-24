"""WP1.10 acceptance: the `ah data` CLI surface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from ah.cli import app

RUNNER = CliRunner()


def _invoke(*args: str):
    return RUNNER.invoke(app, list(args))


def test_data_refresh_dry_run(tmp_path: Path) -> None:
    result = _invoke("data", "refresh", "--dry-run", "--data-root", str(tmp_path / "d"))
    assert result.exit_code == 0
    assert "dry-run" in result.stdout


def test_data_refresh_from_fixtures_commits(tmp_path: Path) -> None:
    fixtures = tmp_path / "fx"
    fixtures.mkdir()
    dates = [ts.date() for ts in pd.date_range("2026-05-01", periods=2, freq="MS")]
    pd.DataFrame({"date": dates, "value": [2.0, 2.1]}).to_csv(
        fixtures / "fred.DGS10.csv", index=False
    )

    data_root = tmp_path / "d"
    result = _invoke(
        "data",
        "refresh",
        "--fixtures",
        str(fixtures),
        "--source",
        "fred",
        "--vintage",
        "2026-06-05",
        "--asof",
        "2026-06-05",
        "--data-root",
        str(data_root),
    )
    assert result.exit_code == 0
    assert "committed" in result.stdout
    assert (data_root / "GAPS.md").exists()
    assert (data_root / "DATA-STATUS.md").exists()

    # idempotent re-run
    again = _invoke(
        "data",
        "refresh",
        "--fixtures",
        str(fixtures),
        "--source",
        "fred",
        "--vintage",
        "2026-06-05",
        "--asof",
        "2026-06-05",
        "--data-root",
        str(data_root),
    )
    assert "no-op" in again.stdout


def test_data_status(tmp_path: Path) -> None:
    result = _invoke("data", "status", "--data-root", str(tmp_path / "d"))
    assert result.exit_code == 0
    assert "DATA-STATUS.md" in result.stdout


def test_data_asof_empty(tmp_path: Path) -> None:
    result = _invoke("data", "asof", "2026-01-01", "--data-root", str(tmp_path / "d"))
    assert result.exit_code == 0
    assert "no vintage" in result.stdout


def test_data_episode_brief(tmp_path: Path) -> None:
    result = _invoke("data", "episode", "2022", "--data-root", str(tmp_path / "d"))
    assert result.exit_code == 0
    assert "Episode brief - 2022" in result.stdout


def test_data_episode_unknown_year(tmp_path: Path) -> None:
    assert _invoke("data", "episode", "1999", "--data-root", str(tmp_path / "d")).exit_code != 0


def test_data_intake_validate_clean(tmp_path: Path) -> None:
    drop = tmp_path / "pm-returns_2026Q2.csv"
    drop.write_text(
        "period,strategy,ret\n2026Q1,buyout,0.03\n2026Q2,buyout,-0.02\n", encoding="utf-8"
    )
    result = _invoke(
        "data",
        "intake",
        "validate",
        str(drop),
        "--schema",
        "albourne_pm_returns",
        "--data-root",
        str(tmp_path / "d"),
    )
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_data_intake_validate_rejects(tmp_path: Path) -> None:
    drop = tmp_path / "pm-returns_2026Q2.csv"
    drop.write_text("period,strategy,ret\n2026Q1,buyout,5.0\n", encoding="utf-8")  # out of bounds
    result = _invoke(
        "data",
        "intake",
        "validate",
        str(drop),
        "--schema",
        "albourne_pm_returns",
        "--data-root",
        str(tmp_path / "d"),
    )
    assert result.exit_code != 0
    assert "REJECTED" in result.stdout
