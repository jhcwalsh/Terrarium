"""Tests for the scenario build console (WP-B). All offline; live path never imported.

``enable_socket`` is the same sanctioned opt-in ``test_serve.py`` uses: the
TestClient's event loop needs an in-process socketpair on Windows, which
pytest-socket blocks by default. No test here touches the network — the live
compiler path is never imported.
"""

import pytest
from fastapi.testclient import TestClient

from ah.buildconsole import create_app

pytestmark = pytest.mark.enable_socket


def _client(tmp_path, fixtures_dir=None):
    app = create_app(
        db_path=tmp_path / "test.db",
        fixtures_dir=fixtures_dir or tmp_path / "fixtures",
        synchronous=True,
    )
    return TestClient(app)


def test_compose_page_renders(tmp_path):
    c = _client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "BUILD SURFACE" in r.text  # watermark
    assert "WRITES ONLY ON KEEP" in r.text
    assert "<textarea" in r.text
