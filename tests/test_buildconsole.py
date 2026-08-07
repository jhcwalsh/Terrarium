"""Tests for the scenario build console (WP-B). All offline; live path never imported.

``enable_socket`` is the same sanctioned opt-in ``test_serve.py`` uses: the
TestClient's event loop needs an in-process socketpair on Windows, which
pytest-socket blocks by default. No test here touches the network — the live
compiler path is never imported.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ah.buildconsole import Attempt, create_app, ledger_html, run_stages

pytestmark = pytest.mark.enable_socket


def _client(tmp_path, fixtures_dir=None):
    app = create_app(
        db_path=tmp_path / "test.db",
        fixtures_dir=fixtures_dir or tmp_path / "fixtures",
        synchronous=True,
    )
    return TestClient(app)


GOOD = "the long stagflation"  # slug: the-long-stagflation


def _write_fixture(tmp_path, name, doc):
    d = tmp_path / "fixtures"
    d.mkdir(exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    return d


def _good_doc():
    # reuse a real committed KNOWN-GOOD compiler fixture (the adversarial-*
    # families are deliberately clamped/rejected; valid-scenario-* are clean)
    src = Path(__file__).resolve().parents[1] / "fixtures" / "compiler"
    return json.loads(sorted(src.glob("valid-scenario-*.json"))[0].read_text(encoding="utf-8"))


def test_run_stages_all_ok():
    doc = _good_doc()
    att = Attempt(
        attempt_id="a1",
        scenario_text=GOOD,
        live=False,
        created_at="2026-08-06T00:00:00+00:00",
        stages=[],
    )
    run_stages(att, fetch_text=lambda s: json.dumps(doc))
    assert att.done
    assert [s.name for s in att.stages] == ["prompt", "model", "extract", "validate", "stamp"]
    assert all(s.status == "ok" for s in att.stages)
    assert att.stamped is not None and "world_id" in att.stamped


def test_run_stages_rejection_is_first_class():
    att = Attempt(
        attempt_id="a2",
        scenario_text="x",
        live=False,
        created_at="2026-08-06T00:00:00+00:00",
        stages=[],
    )
    run_stages(att, fetch_text=lambda s: json.dumps({"schema_version": "1.0.0"}))
    assert att.done and att.stamped is None
    validate_stage = next(s for s in att.stages if s.name == "validate")
    assert validate_stage.status == "fail"
    assert validate_stage.payload  # evidence preserved
    assert not any(s.name == "stamp" for s in att.stages)  # later stages not run


def test_ledger_html_marks_failures():
    att = Attempt(
        attempt_id="a3",
        scenario_text="x",
        live=False,
        created_at="2026-08-06T00:00:00+00:00",
        stages=[],
    )
    run_stages(att, fetch_text=lambda s: "not json at all")
    out = ledger_html(att)
    assert 'class="bad"' in out and "extract" in out


def test_compose_page_renders(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "BUILD SURFACE" in r.text  # watermark
    assert "WRITES ONLY ON KEEP" in r.text
    assert "<textarea" in r.text


def test_compile_flow_fixture_green(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    c = _client(tmp_path, fixtures_dir=fixtures)
    r = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False)
    assert r.status_code == 303
    page = c.get(r.headers["location"]).text
    for stage in ("prompt", "model", "extract", "validate", "stamp"):
        assert stage in page
    assert "world_id" in page
    assert "Keep" in page  # done state offers keep
    assert "http-equiv" not in page  # done -> no meta refresh


def test_watching_page_polls_until_done(tmp_path):
    # non-synchronous app: the page must render mid-compile with a refresh tag
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    app = create_app(db_path=tmp_path / "t.db", fixtures_dir=fixtures, synchronous=False)
    c = TestClient(app)
    r = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False)
    aid = r.headers["location"].rsplit("/", 1)[1]
    with app.state.lock:
        thread = app.state.attempts[aid]._thread
    thread.join(timeout=30)
    assert "Keep" in c.get(f"/attempt/{aid}").text


def test_unknown_attempt_404(tmp_path):
    c = _client(tmp_path)
    assert c.get("/attempt/nope").status_code == 404
