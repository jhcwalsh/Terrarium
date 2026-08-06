"""The QA console is read-only and mock-free, and both are enforced here.

Two properties the console claims in its docstring, asserted rather than
trusted: it cannot reach a writer, and it imports no fixture. Import-graph
tests in the style of ``tests/test_leakage_guard.py`` and
``tests/test_programme_guard.py`` — the claim is structural, so the test is too.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from ah.console import cash_identity, create_app, sanity_rows
from ah.core.engine import run_path
from ah.core.numericworld import project_numeric
from ah.core.worldspec import WorldSpec

_SRC = Path(__file__).resolve().parents[1] / "src" / "ah" / "console.py"

# TestClient drives the ASGI app through ``socket.socketpair``, which
# pytest-socket blocks by default. ``enable_socket`` is the invariant's
# sanctioned loopback opt-in, applied here exactly as tests/test_serve.py does.
pytestmark = pytest.mark.enable_socket

#: Names that would let the console mutate the record it is supposed to inspect.
FORBIDDEN_NAMES = frozenset(
    {"save_world", "save_run_record", "append", "submit_score", "create_session", "record_decision"}
)
#: Modules the console must not reach at all.
FORBIDDEN_MODULES = ("ah.serve", "ah.store.sessions", "ah.store.leaderboard")


def _imports(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend((a.name, ()) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.module, tuple(a.name for a in node.names)))
    return out


class TestReadOnly:
    def test_console_imports_no_writer(self) -> None:
        for module, names in _imports(_SRC):
            for bad in FORBIDDEN_MODULES:
                assert not module.startswith(bad), f"console imports {module}, a writer surface"
            offenders = FORBIDDEN_NAMES.intersection(names)
            assert not offenders, f"console imports {sorted(offenders)} from {module}"

    def test_store_connection_is_opened_read_only(self, tmp_path: Path) -> None:
        """The driver, not discipline, refuses the write."""
        db = tmp_path / "ro.db"
        seed = sqlite3.connect(db)
        seed.execute("CREATE TABLE t (x INTEGER)")
        seed.commit()
        seed.close()

        from ah.console import _ro_conn

        conn = _ro_conn(db)
        try:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("INSERT INTO t (x) VALUES (1)")
        finally:
            conn.close()

    def test_no_fixture_is_imported(self) -> None:
        """Acceptance #2 at grep level: zero mocked content in page code."""
        text = _SRC.read_text(encoding="utf-8").lower()
        for token in ("fixtures", "mock", "sample_data", "dummy", "faker"):
            # the word may appear in prose; what must not appear is an import
            for module, names in _imports(_SRC):
                assert token not in module.lower(), f"console imports {module}"
                assert not any(token in n.lower() for n in names), f"console imports from {module}"
        assert "import" in text  # sanity: the file parsed and has imports


class TestChecksRecompute:
    """A check that cannot go red has not been shown to work (acceptance #3)."""

    def _paths(self):
        doc = {
            "engine_defaults": {"base_seed": 7, "generator_id": "toy-v0", "n_paths": 100},
            "extensions": {},
            "factor_conditions": {"equity": {"drift_annual_pct": 5.0, "vol_annual_pct": 15.0}},
            "horizon": {"quarters": 8, "start": "2027-Q1"},
            "narrative": {
                "dispatches": [
                    {"date": "2027", "headline": "one"},
                    {"date": "2028", "headline": "two"},
                    {"date": "2029", "headline": "three"},
                ],
                "language": "en",
                "lesson": "l",
                "summary": "s",
                "tagline": "t",
                "title": "T",
            },
            "provenance": {
                "author": "test",
                "created_at": "2026-01-01T00:00:00Z",
                "source": {"kind": "preset"},
            },
            "regimes": {"mode": "unconditional"},
            "spec_version": "1.2.0",
            "status": "draft",
            "structural": {"parameter_vintage": "current"},
            "world_id": "00000000-0000-4000-9000-0000000000ff",
        }
        return run_path(project_numeric(WorldSpec.model_validate(doc)), 7)

    def test_sanity_strip_is_clean_then_red_when_corrupted(self) -> None:
        from dataclasses import replace

        clean = self._paths()
        assert [r for r in sanity_rows(clean) if r[5]] == []

        rate = clean.rate.copy()
        rate[2] = 0.01  # below the engine's own floor
        assert [r for r in sanity_rows(replace(clean, rate=rate)) if r[5]] != []

    def test_cash_identity_is_zero_then_flags_a_perturbed_quarter(self) -> None:
        from dataclasses import replace

        from ah.play import START_CASH, simulate_play

        result = simulate_play(self._paths(), None)
        assert max(abs(x) for x in cash_identity(result.quarters, START_CASH)) < 1e-9

        rows = list(result.quarters)
        rows[1] = replace(rows[1], cash=rows[1].cash + 0.5)
        assert [i for i, x in enumerate(cash_identity(rows, START_CASH)) if abs(x) > 1e-6]


class TestEmptyStates:
    def test_missing_store_renders_an_honest_empty_state(self, tmp_path: Path) -> None:
        from fastapi.testclient import TestClient

        client = TestClient(create_app(tmp_path / "absent.db"))
        body = client.get("/worlds").text
        assert "Not available" in body
        assert "ah world build" in body

    def test_every_page_carries_the_watermark(self, tmp_path: Path) -> None:
        from fastapi.testclient import TestClient

        from ah.console import WATERMARK

        client = TestClient(create_app(tmp_path / "absent.db"))
        for route in ("/worlds", "/diff", "/battery/none"):
            assert WATERMARK in client.get(route).text, route
