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


def test_md_to_html_strips_header_anchors():
    out = md_to_html("## The two hardest questions {#hardest-questions}")
    assert out == "<h2>The two hardest questions</h2>"  # pandoc-style anchor never renders


def test_md_to_html_joins_wrapped_paragraphs():
    out = md_to_html("*An italic caption\nwrapped across lines.*\n\nNext paragraph.")
    assert "<i>An italic caption wrapped across lines.</i>" in out  # emphasis survives the wrap
    assert out.count("<p>") == 2  # blank line still separates paragraphs
    assert "*" not in out  # no literal asterisks leak


def test_md_to_html_inlines_sibling_svg_figures(tmp_path):
    (tmp_path / "fig.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    md = "![The figure](fig.svg)\n\n![Gone](missing.svg)\n\n![Escape](../fig.svg)"
    out = md_to_html(md, base=tmp_path)
    assert "<svg" in out and "<figcaption>The figure</figcaption>" in out
    assert "[figure: Gone]" in out and "[figure: Escape]" in out  # absent + traversal fall back
    assert "![" not in out  # the raw markdown never leaks
    assert "<svg" not in md_to_html(md)  # no base, no filesystem access


def test_methodology_doc_serves_with_inlined_figures():
    c = TestClient(app)
    r = c.get("/doc/methodology")
    assert r.status_code == 200
    assert "Terrarium Method" in r.text
    assert r.text.count("<figure>") == 2  # both exhibits inlined, not ![...] text


def test_pdf_routes_serve_only_committed_pdfs():
    c = TestClient(app)
    assert c.get("/pdf/no-such-doc").status_code == 404
    served = 0
    for slug in DOCS:
        r = c.get(f"/pdf/{slug}")
        assert r.status_code in (200, 404)  # 404 only when no PDF sibling is committed
        if r.status_code == 200:
            served += 1
            assert r.headers["content-type"] == "application/pdf"
    assert served >= 4  # the manual, the method, D-05 and P1 PDFs are committed
    for alias in ("/manual.pdf", "/methodology.pdf"):  # links that predate /pdf/<slug>
        assert c.get(alias).status_code == 200


def test_hub_is_static_no_write_call_sites():
    import inspect

    import ah.hub as hub

    src = inspect.getsource(hub)
    for needle in ("save_", "INSERT", "write_observations(", "to_parquet(", "open("):
        assert needle not in src or needle == "open("  # only read_text is used
    assert ".write_text(" not in src and "mkdir(" not in src
