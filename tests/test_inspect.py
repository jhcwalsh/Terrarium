"""wp5-02 acceptance: the --inspect renderer.

One code path, any RunRecord -> a static, self-contained, DETERMINISTIC figure
page that regenerates the run from its stored inputs and verifies the digest as
it renders. These tests run the real CLI against a real preset world (the same
harness test_cli.py uses) and assert the page's structural contract rather than
pixel content.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ah.cli import app
from ah.core.engine import ASSETS, REPORTED_SLEEVES
from ah.inspect import InspectError, render_inspect_page
from ah.store.db import connect

RUNNER = CliRunner()


def _invoke(db: Path, *args: str):
    return RUNNER.invoke(app, ["--db", str(db), *args])


@pytest.fixture(scope="module")
def stored_run(tmp_path_factory) -> tuple[Path, str, str]:
    tmp = tmp_path_factory.mktemp("inspect")
    db = tmp / "ah.db"
    build = _invoke(db, "world", "build", "--preset", "stagflation")
    assert build.exit_code == 0, build.stdout
    wid = build.stdout.strip()
    run = _invoke(db, "run", "--paths", "16")
    assert run.exit_code == 0, run.stdout
    rid = run.stdout.strip()
    return db, wid, rid


class TestRenderPage:
    def test_page_is_self_contained_and_structurally_complete(self, stored_run):
        db, _wid, rid = stored_run
        conn = connect(db)
        page = render_inspect_page(conn, rid)
        # self-contained: no external fetches of any kind
        for marker in ("http://", "https://", "src=", "@import"):
            assert marker not in page, marker
        # the five panels the kickoff names
        assert "Factor panel" in page
        assert "Sleeve panel" in page
        assert "Reported vs true" in page
        assert "Episode annotations" in page
        assert "Correlogram" in page
        # every asset charted; every smoothed sleeve in the toggle section
        for asset in ASSETS:
            assert f"{asset}: growth of 1.0" in page
        for sleeve in REPORTED_SLEEVES:
            assert f"{sleeve}: true (solid) vs reported (dashed)" in page
        # identity + verification stamp
        assert rid in page
        assert "DIGEST VERIFIED" in page
        assert "DIGEST MISMATCH" not in page

    def test_render_is_deterministic(self, stored_run):
        db, _wid, rid = stored_run
        conn = connect(db)
        assert render_inspect_page(conn, rid) == render_inspect_page(conn, rid)

    def test_tampered_digest_renders_a_loud_mismatch(self, tmp_path):
        # its own store (a WAL-mode file copy would miss uncheckpointed writes,
        # and the shared fixture must stay untampered for the other tests)
        db = tmp_path / "tampered.db"
        assert _invoke(db, "world", "build", "--preset", "stagflation").exit_code == 0
        run = _invoke(db, "run", "--paths", "8")
        assert run.exit_code == 0
        rid = run.stdout.strip()
        conn = connect(db)
        conn.execute(
            "UPDATE run_records SET outputs_digest = ? WHERE run_id = ?",
            ("sha256:" + "0" * 64, rid),
        )
        conn.commit()
        page = render_inspect_page(conn, rid)
        assert "DIGEST MISMATCH" in page
        assert "DIGEST VERIFIED" not in page

    def test_missing_run_raises_inspect_error(self, stored_run):
        db, _wid, _rid = stored_run
        conn = connect(db)
        with pytest.raises(InspectError, match="no run_record"):
            render_inspect_page(conn, "nope")


class TestCli:
    def test_inspect_writes_the_page_where_told(self, stored_run, tmp_path):
        db, _wid, rid = stored_run
        out = tmp_path / "figs" / "page.html"
        result = _invoke(db, "inspect", rid, "--out", str(out))
        assert result.exit_code == 0, result.stdout
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "Correlogram" in text and rid in text
        # CLI output stays ASCII (the cp1252 console rule)
        assert result.stdout.strip().isascii()

    def test_inspect_defaults_to_latest_run(self, stored_run, tmp_path, monkeypatch):
        db, _wid, rid = stored_run
        monkeypatch.chdir(tmp_path)
        result = _invoke(db, "inspect")
        assert result.exit_code == 0, result.stdout
        assert Path(result.stdout.strip()).name == f"{rid}.html"


class TestNumericHonesty:
    def test_correlogram_is_symmetric_with_unit_diagonal(self, stored_run):
        """The rendered correlations come from np.corrcoef of the regenerated
        ensemble; symmetry and the unit diagonal are asserted on the page text
        (cell values are printed at 2dp), so a transposed or shuffled grid
        cannot render identically."""
        import re

        db, _wid, rid = stored_run
        conn = connect(db)
        page = render_inspect_page(conn, rid)
        corr_section = page[page.index("Correlogram: pooled") :]
        cells = [float(v) for v in re.findall(r'class="cell">(-?\d\.\d\d)<', corr_section)]
        n = len(ASSETS)
        assert len(cells) == n * n
        import numpy as np

        grid = np.array(cells).reshape(n, n)
        assert np.allclose(np.diag(grid), 1.0)
        assert np.allclose(grid, grid.T, atol=0.011)  # 2dp rounding tolerance
