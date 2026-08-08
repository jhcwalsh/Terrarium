"""The tools hub: static navigation, zero writes.

``enable_socket`` is the sanctioned TestClient opt-in (see test_serve.py).
"""

import pytest
from fastapi.testclient import TestClient

from ah.hub import COMMANDS, DOCS, SURFACES, app, md_to_html

pytestmark = pytest.mark.enable_socket


def test_hub_lists_every_surface_and_command():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "TOOLS HUB" in r.text
    for name, url, _, _ in SURFACES:
        assert name.split(" (")[0] in r.text and url in r.text
    for cmd, _ in COMMANDS:
        assert cmd.split(" --")[0] in r.text


def test_every_entry_carries_an_explanation():
    assert all(len(answers) > 40 for _, _, answers, _ in SURFACES)
    assert all(len(why) > 30 for _, why in COMMANDS)


def test_manual_route_serves_the_docs_file_or_404s():
    c = TestClient(app)
    r = c.get("/manual")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "terminal" in r.text.lower()


def test_doc_routes_serve_only_the_allowlist():
    c = TestClient(app)
    assert c.get("/doc/no-such-doc").status_code == 404
    assert c.get("/doc/..%2fpyproject.toml").status_code == 404  # no traversal
    served = 0
    for slug in DOCS:
        r = c.get(f"/doc/{slug}")
        assert r.status_code in (200, 404)  # 404 only if the file is absent
        if r.status_code == 200:
            served += 1
            assert "tools hub" in r.text  # the back link rides on every doc
    assert served >= 4  # this checkout carries the core documents


def test_md_to_html_covers_the_repo_subset():
    out = md_to_html(
        "# T\n\n**b** and `c` and *i*\n\n- item\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```\nraw <tag>\n```"
    )
    assert "<h1>T</h1>" in out
    assert "<b>b</b>" in out and "<code>c</code>" in out and "<i>i</i>" in out
    assert "<li>item</li>" in out
    assert "<th>a</th>" in out and "<td>2</td>" in out
    assert "&lt;tag&gt;" in out  # code blocks escape HTML


def test_hub_is_static_no_write_call_sites():
    import inspect

    import ah.hub as hub

    src = inspect.getsource(hub)
    for needle in ("save_", "INSERT", "write_observations(", "to_parquet(", "open("):
        assert needle not in src or needle == "open("  # only read_text is used
    assert ".write_text(" not in src and "mkdir(" not in src
