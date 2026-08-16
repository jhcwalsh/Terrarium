"""Render hub-allowlisted markdown documents to PDF via Chrome's print engine.

Run from the repo root::

    uv run python scripts/build_doc_pdf.py                 # the default set
    uv run python scripts/build_doc_pdf.py preprint        # one slug from ah.hub.DOCS

Replaces the earlier per-document scripts (build_manual_pdf.py,
build_methodology_pdf.py). No new Python dependencies: the markdown subset
renderer lives in ah.hub (which inlines each document's sibling SVG figures)
and the PDF engine is the locally installed Chrome (headless --print-to-pdf).
The output lands next to the source with a .pdf suffix — exactly where the
hub's /pdf/<slug> route looks. Deterministic input -> stable output modulo
Chrome's PDF metadata.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.hub import _DOC_CSS, DOCS, md_to_html  # noqa: E402

#: Built when no slugs are given: the documents whose PDFs are committed.
DEFAULT_SLUGS = [
    "plain-english-manual",
    "methodology",
    "methodology-note",
    "preprint",
    "user-manual",
    "build-summary",
    "g0-evidence",
    "g2-evidence",
    "consolidation-evidence",
    "g1-evidence",
    "g4-evidence",
    "research-evidence",
    "private-markets-inflation",
]

_CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]

# Figures are full-page-width on screen; cap them for print so a figure and
# its caption stay on one page.
_PRINT_CSS = _DOC_CSS + "figure{margin:14px 0}figure svg{max-width:100%;height:auto}"


def build(slug: str, chrome: Path) -> bool:
    entry = DOCS.get(slug)
    if entry is None:
        print(f"{slug}: not in ah.hub.DOCS (known: {', '.join(DOCS)})")
        return False
    rel, title, _ = entry
    source = ROOT / rel
    if not source.exists():
        print(f"{slug}: missing {source}")
        return False
    out = source.with_suffix(".pdf")
    body = md_to_html(source.read_text(encoding="utf-8"), base=source.parent)
    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{_PRINT_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"{slug}.html"
        src.write_text(html_doc, encoding="utf-8")
        result = subprocess.run(
            [
                str(chrome),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out}",
                src.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    if not out.exists():
        print(f"{slug}: chrome exited {result.returncode}: {result.stderr[:400]}")
        return False
    print(f"{slug}: wrote {out} ({out.stat().st_size} bytes)")
    return True


def main(argv: list[str]) -> int:
    chrome = next((c for c in _CHROME_CANDIDATES if c.exists()), None)
    if chrome is None:
        print("Chrome not found; cannot render PDF")
        return 1
    slugs = argv or DEFAULT_SLUGS
    return 0 if all([build(s, chrome) for s in slugs]) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
