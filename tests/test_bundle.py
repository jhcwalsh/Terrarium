"""su-eng-01 acceptance: the world bundle (DN-3 W2 contract, v0.1)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from ah.artifacts.live import verify_tape
from ah.bundle import MAX_COMPRESSED_BYTES, BundleError, build_bundle, write_bundle
from ah.cli import app
from ah.core.engine import ASSETS, REPORTED_SLEEVES
from ah.store.db import connect

RUNNER = CliRunner()


def _invoke(db: Path, *args: str):
    return RUNNER.invoke(app, ["--db", str(db), *args])


@pytest.fixture(scope="module")
def stored_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bundle")
    db = tmp / "ah.db"
    assert _invoke(db, "world", "build", "--preset", "stagflation").exit_code == 0
    run = _invoke(db, "run", "--paths", "50")
    assert run.exit_code == 0
    return db, run.stdout.strip()


class TestContract:
    def test_sections_and_provenance(self, stored_run):
        db, rid = stored_run
        doc = build_bundle(connect(db), rid)
        assert doc["bundle_version"] == "world-bundle-0.6"
        # toy worlds carry no factor-lineage sections (generated worlds only)
        assert "factors" not in doc
        assert "credibility" not in doc
        for section in ("meta", "revealed", "bands", "summary", "feed"):
            assert section in doc, section
        meta = doc["meta"]
        assert meta["run_id"] == rid
        assert meta["digest_verified"] is True
        assert meta["decision_stamps"]["twin_definition"] == "policy"
        # every asset gets a five-quantile fan of the right length, on the
        # GROWTH-OF-1 scale (regression, found live: percent returns
        # compounded as decimals render empty/negative cones)
        months = meta["months"]
        for asset in ASSETS:
            fan = doc["bands"][asset]
            assert set(fan) == {"p5", "p25", "p50", "p75", "p95"}
            assert all(len(v) == months for v in fan.values())
            for m in range(months):
                column = [fan[q][m] for q in ("p5", "p25", "p50", "p75", "p95")]
                assert column == sorted(column), f"{asset} quantiles cross at {m}"
                assert column[0] > 0, f"{asset} p5 non-positive at {m} (percent bug)"
            assert 0.05 < fan["p50"][-1] < 20, f"{asset} median terminal off-scale"
        # the numeric tape carries assets then reported columns, sealed at t0
        order = doc["revealed"]["series_order"]
        assert order == [*ASSETS, *(f"{s}_reported" for s in REPORTED_SLEEVES)]
        assert len(order) == 13  # ER-14 close-out: 9 assets + 4 reported sleeves
        tape = np.array(doc["revealed"]["tape"], dtype=np.float64)
        assert tape.shape == (months, len(order))
        assert verify_tape(tape, doc["revealed"]["tape_seal"])
        # windows + episodes + chronicle present
        assert doc["summary"]["decision_months"]
        assert doc["summary"]["episodes"]
        assert doc["feed"]["chronicle"]
        # v0.2: the tier-1 wire rides in the bundle, every item in-horizon
        artifacts = doc["feed"]["artifacts"]
        assert artifacts and all(0 <= a["month"] < months for a in artifacts)
        assert {a["type"] for a in artifacts} >= {
            "cb_statement",
            "release_page",
            "quarterly_statement",
        }

    def test_twin_ledger_rides_along(self, stored_run):
        """0.4 carries the HOLD-COURSE TWIN's cashflows, not the player's.

        The twin never acts, so its ledger is decision-independent and stays
        honestly pre-authorable (PD-4). The player's own ledger depends on what
        they did and comes from the session service instead.
        """
        db, rid = stored_run
        doc = build_bundle(connect(db), rid)
        assert "private" not in doc
        led = doc["twin_ledger"]
        n = len(led["quarter_months"])
        assert n == doc["meta"]["months"] // 3
        for key in (
            "calls",
            "distributions",
            "nav_true",
            "nav_reported",
            "cash",
            "unfunded",
            "private_weight_true",
        ):
            assert len(led[key]) == n, key
        assert led["quarter_months"] == [q * 3 + 2 for q in range(n)]
        assert all(c >= 0.0 for c in led["cash"])

    def test_build_is_deterministic(self, stored_run):
        db, rid = stored_run
        a = build_bundle(connect(db), rid)
        b = build_bundle(connect(db), rid)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_tampered_digest_is_loud_not_pretty(self, tmp_path):
        db = tmp_path / "t.db"
        assert _invoke(db, "world", "build", "--preset", "stagflation").exit_code == 0
        run = _invoke(db, "run", "--paths", "8")
        rid = run.stdout.strip()
        conn = connect(db)
        conn.execute(
            "UPDATE run_records SET outputs_digest = ? WHERE run_id = ?",
            ("sha256:" + "0" * 64, rid),
        )
        conn.commit()
        doc = build_bundle(conn, rid)
        assert doc["meta"]["digest_verified"] is False

    def test_missing_run_refused(self, stored_run):
        db, _rid = stored_run
        with pytest.raises(BundleError, match="no run_record"):
            build_bundle(connect(db), "nope")


class TestSizeAndCli:
    def test_under_the_w2_budget_and_gzip_deterministic(self, stored_run, tmp_path):
        db, rid = stored_run
        doc = build_bundle(connect(db), rid)
        p1, p2 = tmp_path / "a.gz", tmp_path / "b.gz"
        s1 = write_bundle(doc, p1)
        s2 = write_bundle(doc, p2)
        assert s1 == s2 and s1 < MAX_COMPRESSED_BYTES
        assert p1.read_bytes() == p2.read_bytes()  # mtime=0: byte-identical archives
        loaded = json.loads(gzip.decompress(p1.read_bytes()))
        assert loaded["meta"]["run_id"] == rid

    def test_generated_bundle_carries_factor_lineage(self, tmp_path, monkeypatch):
        """su-gen-02 acceptance: a generated world's bundle carries the 16
        factor names with units and per-factor proxy shares (incl. the
        HAR/VXO split), the campaign credibility pointers, a tape over the
        generated asset order, and it verifies. The catalog read is behind
        the ``factor_lineage`` seam (OD-4: the real build requires data/;
        tests inject)."""
        import ah.bundle as bundle_mod
        import ah.gen.bootstrap as bs
        from ah.gen import registry
        from ah.port.adapter import GEN_ASSETS
        from conftest import make_synthetic_source_16

        fake_lineage = {
            "vintage_id": "test-vintage",
            "units": {n: "test-units" for n in bs.FACTOR_SET},
            "proxy_shares": {
                n: {"n_months": 72, "n_proxy": 0, "share": 0.0, "by_rule": {}}
                for n in bs.FACTOR_SET
            },
        }
        monkeypatch.setattr(bundle_mod, "factor_lineage", lambda vintage_id: fake_lineage)

        saved = registry.snapshot()
        registry.register("bootstrap-v1", lambda: bs.BootstrapV1(make_synthetic_source_16()))
        try:
            db = tmp_path / "gen.db"
            assert _invoke(db, "world", "build", "--preset", "stagflation_1974").exit_code == 0
            run = _invoke(db, "run", "--paths", "8")
            assert run.exit_code == 0, run.output
            rid = run.stdout.strip().splitlines()[-1]
            doc = build_bundle(connect(db), rid)
        finally:
            registry.restore(saved)

        assert doc["bundle_version"] == "world-bundle-0.6"
        assert doc["meta"]["digest_verified"] is True
        order = doc["revealed"]["series_order"]
        assert order == [*GEN_ASSETS, *(f"{s}_reported" for s in REPORTED_SLEEVES)]
        assert len(order) == 12  # ER-14 close-out: 8 generated assets + 4 reported sleeves
        assert set(doc["bands"]) == set(GEN_ASSETS)
        tape = np.array(doc["revealed"]["tape"], dtype=np.float64)
        assert verify_tape(tape, doc["revealed"]["tape_seal"])
        factors = doc["factors"]
        assert set(factors["names"]) == set(bs.FACTOR_SET)
        assert factors["vintage_id"] == "test-vintage"
        assert set(factors["proxy_shares"]) == set(bs.FACTOR_SET)
        cred = doc["credibility"]
        assert cred["verdict"] == "SHIP-BENCHMARK"
        assert cred["generator_id"] == "bootstrap-v1"
        assert "severe" in cred
        # sp-04: episodes are the REALIZED regime path, not the authored wish
        episodes = doc["summary"]["episodes"]
        assert episodes
        names = {"expansion", "recession", "reflation", "slowdown", "crisis", "stagflation"}
        horizon_q = doc["meta"]["months"] // 3
        for seg in episodes:
            assert seg["regime"] in names
            assert 0 <= seg["from_quarter"] <= seg["to_quarter"] < horizon_q
        assert episodes[0]["from_quarter"] == 0
        assert episodes[-1]["to_quarter"] == horizon_q - 1
        # the new sections carry their own integrity digest
        assert doc["meta"]["sections_seal"].startswith("sha256:")

    def test_committed_fixture_bundles_verify_in_this_suite(self):
        """The 'both suites verify it' acceptance, python half: the committed
        fixtures load, name a supported version, and their seals verify."""
        fixtures = Path(__file__).resolve().parents[1] / "app" / "fixtures"
        for name, expect_factors in (("toy.bundle.gz", False), ("gen.bundle.gz", True)):
            raw = gzip.decompress((fixtures / name).read_bytes())
            doc = json.loads(raw)
            assert doc["bundle_version"] == "world-bundle-0.6", name
            tape = np.array(doc["revealed"]["tape"], dtype=np.float64)
            assert verify_tape(tape, doc["revealed"]["tape_seal"]), name
            assert ("factors" in doc) is expect_factors, name

    def test_generated_fixture_wire_is_prewritten_and_sane(self):
        """su-gen-04 (PD-4): tier-1 artifacts ride the GENERATED bundle,
        authored at build over spliced-history paths — every expected type
        present, in-horizon, with values on their proper scales (percent
        inflation from the source-space YoY channel, bp spreads from the
        percent->bp conversion). Pins the plan's Task 4 acceptance."""
        fixtures = Path(__file__).resolve().parents[1] / "app" / "fixtures"
        doc = json.loads(gzip.decompress((fixtures / "gen.bundle.gz").read_bytes()))
        months = doc["meta"]["months"]
        arts = doc["feed"]["artifacts"]
        types = {a["type"] for a in arts}
        assert {"cb_statement", "release_page", "quarterly_statement", "newspaper"} <= types
        assert all(0 <= a["month"] < months for a in arts)
        # one release page per month, each carrying both wired rows with units
        pages = [a for a in arts if a["type"] == "release_page"]
        assert len(pages) == months
        for a in pages:
            rows = {r["series"]: r["value"] for r in a["payload"]["rows"]}
            assert rows["CPI inflation"].endswith("%")
            assert rows["High yield spread"].endswith("bp")
            spread_bp = float(rows["High yield spread"].removesuffix("bp"))
            assert 100 <= spread_bp <= 1100  # the panel's real range, in bp not %
        # central bank statements quote a percent-scale policy rate
        cb = next(a for a in arts if a["type"] == "cb_statement")
        first_line = cb["payload"]["lines"][0]
        assert "policy rate" in first_line and "%" in first_line

    def test_cli_builds_where_told(self, stored_run, tmp_path):
        db, rid = stored_run
        out = tmp_path / "world.bundle.gz"
        result = _invoke(db, "bundle", rid, "--out", str(out))
        assert result.exit_code == 0, result.stdout
        assert out.exists()
        assert result.stdout.strip().isascii()


def test_nothing_imports_the_retired_pacing_shim():
    """The retired pacing module was a display-only miniature of what
    ah.play now does properly. Two ledgers computed different ways is the
    drift this deletion exists to prevent.

    Anchored on import syntax (``from ... import`` / ``import ...``) rather
    than a bare substring, so it catches a real regression without ever
    self-matching prose or comments that merely name the retired module --
    this docstring included.
    """
    import subprocess

    root = Path(__file__).resolve().parents[1]
    hits = subprocess.run(
        [
            "git",
            "grep",
            "-E",
            "-l",
            r"^\s*(from ah\.pacing import|import ah\.pacing)\b",
            "--",
            "src",
            "tests",
            "app/src",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert hits.stdout.strip() == "", hits.stdout
