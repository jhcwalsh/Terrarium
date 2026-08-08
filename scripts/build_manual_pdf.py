"""Render docs/PLAIN-ENGLISH-USER-MANUAL.md to PDF via Chrome's print engine.

Run from the repo root:  uv run python scripts/build_manual_pdf.py

No new Python dependencies: the markdown subset renderer lives in ah.hub and
the PDF engine is the locally installed Chrome (headless --print-to-pdf).
Deterministic input -> stable output modulo Chrome's PDF metadata.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ah.hub import _DOC_CSS, MANUAL_PATH, MANUAL_PDF_PATH, md_to_html  # noqa: E402

_CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]


def main() -> int:
    if not MANUAL_PATH.exists():
        print(f"missing {MANUAL_PATH}")
        return 1
    chrome = next((c for c in _CHROME_CANDIDATES if c.exists()), None)
    if chrome is None:
        print("Chrome not found; cannot render PDF")
        return 1
    body = md_to_html(MANUAL_PATH.read_text(encoding="utf-8"))
    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>The Plain-English Manual</title><style>{_DOC_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "manual.html"
        src.write_text(html_doc, encoding="utf-8")
        result = subprocess.run(
            [
                str(chrome),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={MANUAL_PDF_PATH}",
                src.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    if not MANUAL_PDF_PATH.exists():
        print(f"chrome exited {result.returncode}: {result.stderr[:400]}")
        return 1
    print(f"wrote {MANUAL_PDF_PATH} ({MANUAL_PDF_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
