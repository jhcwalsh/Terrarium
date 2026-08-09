"""Render docs/METHODOLOGY.md to PDF via Chrome's print engine.

Run from the repo root:  uv run python scripts/build_methodology_pdf.py

No new Python dependencies: the markdown subset renderer lives in ah.hub
(which inlines the document's sibling SVG figures) and the PDF engine is the
locally installed Chrome (headless --print-to-pdf). Deterministic input ->
stable output modulo Chrome's PDF metadata.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.hub import _DOC_CSS, METHODOLOGY_PDF_PATH, md_to_html  # noqa: E402

SOURCE = ROOT / "docs" / "METHODOLOGY.md"

_CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]

# Figures are full-page-width on screen; cap them for print so a figure and
# its caption stay on one page.
_PRINT_CSS = _DOC_CSS + "figure{margin:14px 0}figure svg{max-width:100%;height:auto}"


def main() -> int:
    if not SOURCE.exists():
        print(f"missing {SOURCE}")
        return 1
    chrome = next((c for c in _CHROME_CANDIDATES if c.exists()), None)
    if chrome is None:
        print("Chrome not found; cannot render PDF")
        return 1
    body = md_to_html(SOURCE.read_text(encoding="utf-8"), base=SOURCE.parent)
    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>The Terrarium Method</title><style>{_PRINT_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "methodology.html"
        src.write_text(html_doc, encoding="utf-8")
        result = subprocess.run(
            [
                str(chrome),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={METHODOLOGY_PDF_PATH}",
                src.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    if not METHODOLOGY_PDF_PATH.exists():
        print(f"chrome exited {result.returncode}: {result.stderr[:400]}")
        return 1
    print(f"wrote {METHODOLOGY_PDF_PATH} ({METHODOLOGY_PDF_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
