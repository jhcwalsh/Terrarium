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
        log_dir=tmp_path / "log",  # never the repo's real data/buildconsole
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
    # "envelope" joined the ledger in WP-A (carried through on the fixture path)
    assert [s.name for s in att.stages] == [
        "prompt",
        "model",
        "extract",
        "envelope",
        "validate",
        "stamp",
    ]
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
    app = create_app(
        db_path=tmp_path / "t.db",
        fixtures_dir=fixtures,
        synchronous=False,
        log_dir=tmp_path / "log",  # never the repo's real data/buildconsole
    )
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


def _kept_client(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    c = _client(tmp_path, fixtures_dir=fixtures)
    loc = c.post("/compile", data={"scenario": GOOD}, follow_redirects=False).headers["location"]
    return c, loc.rsplit("/", 1)[1]


def test_keep_stores_world_and_birth(tmp_path):
    from ah.store import chronicle as chronicle_store
    from ah.store.db import connect

    c, aid = _kept_client(tmp_path)
    r = c.post(f"/attempt/{aid}/keep", data={}, follow_redirects=False)
    assert r.status_code == 200
    conn = connect(tmp_path / "test.db")
    rows = conn.execute("SELECT world_id FROM worlds").fetchall()
    assert len(rows) == 1
    events = chronicle_store.read(conn, rows[0]["world_id"])
    assert [e["type"] for e in events] == ["birth"]


def test_keep_with_run_records_a_run(tmp_path):
    from ah.store.db import connect

    c, aid = _kept_client(tmp_path)
    c.post(f"/attempt/{aid}/keep", data={"run": "on", "seed": "42", "n_paths": "16"})
    conn = connect(tmp_path / "test.db")
    runs = conn.execute("SELECT n_paths, seed FROM run_records").fetchall()
    assert [(r["n_paths"], r["seed"]) for r in runs] == [(16, 42)]


def test_keep_twice_is_rejected(tmp_path):
    c, aid = _kept_client(tmp_path)
    c.post(f"/attempt/{aid}/keep", data={})
    r = c.post(f"/attempt/{aid}/keep", data={})
    assert r.status_code == 409


def test_compile_alone_stores_nothing(tmp_path):
    """The dry-run guarantee, tested from the outside: no keep, no rows."""
    from ah.store.db import connect

    _c, _aid = _kept_client(tmp_path)  # compiled, never kept
    conn = connect(tmp_path / "test.db")
    assert conn.execute("SELECT COUNT(*) AS n FROM worlds").fetchone()["n"] == 0


def test_attempt_log_records_failures_too(tmp_path):
    app = create_app(
        db_path=tmp_path / "t.db",
        fixtures_dir=tmp_path / "none",
        synchronous=True,
        log_dir=tmp_path / "log",
    )
    c = TestClient(app)
    c.post("/compile", data={"scenario": "no such fixture"})
    lines = (tmp_path / "log" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["scenario_text"] == "no such fixture"
    assert rec["stages"][-1]["status"] == "fail"  # model stage: missing fixture
    assert "no fixture" in rec["stages"][-1]["payload"]


def test_recent_attempts_on_compose_page(tmp_path):
    fixtures = _write_fixture(tmp_path, "the-long-stagflation", _good_doc())
    app = create_app(
        db_path=tmp_path / "t.db",
        fixtures_dir=fixtures,
        synchronous=True,
        log_dir=tmp_path / "log",
    )
    c = TestClient(app)
    c.post("/compile", data={"scenario": GOOD})
    assert GOOD in c.get("/").text


def test_only_keep_handler_writes_to_store():
    """Guard: the module's sole store-writing call sites live inside keep_post.

    Same technique as the narrative-blindness scan: assert on source text so a
    future edit that adds a second write path fails loudly here.
    """
    import inspect

    import ah.buildconsole as bc

    src = inspect.getsource(bc)
    keep_src = src[src.index("async def keep_post") :]
    for needle in ("save_world(", "save_run_record(", "chronicle_store.append("):
        assert src.count(needle) == keep_src.count(needle), (
            f"{needle} called outside keep_post — the console's write "
            "guarantee is 'nothing persists except through Keep'"
        )


def test_live_attempt_gets_envelope_stage(tmp_path):
    """Simulated live: fetch returns a six-block body with model-invented keys;
    the envelope stage must stamp identity before validation."""
    body = {
        k: v
        for k, v in _good_doc().items()
        if k
        in ("narrative", "horizon", "regimes", "factor_conditions", "structural", "engine_defaults")
    }
    body["meta"] = {"model": "invented"}
    att = Attempt(
        attempt_id="a9",
        scenario_text="x",
        live=True,
        created_at="2026-08-06T00:00:00+00:00",
        stages=[],
    )
    run_stages(att, fetch_text=lambda s: json.dumps(body))
    names = [s.name for s in att.stages]
    assert names == ["prompt", "model", "extract", "envelope", "validate", "stamp"]
    assert att.stamped is not None
    assert att.stamped["provenance"]["source"]["kind"] == "compiler"


def test_fixture_attempt_envelope_stage_is_carried(tmp_path):
    att = Attempt(
        attempt_id="a10",
        scenario_text="x",
        live=False,
        created_at="2026-08-06T00:00:00+00:00",
        stages=[],
    )
    run_stages(att, fetch_text=lambda s: json.dumps(_good_doc()))
    env = next(s for s in att.stages if s.name == "envelope")
    assert env.status == "ok" and "fixture" in env.detail
