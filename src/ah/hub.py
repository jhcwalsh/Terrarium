"""The tools hub: one page that explains every surface and how to reach it.

Owner request 2026-08-08: "a console that allows me to access each of the
tools with an explanation." Static navigation + plain-English explanations —
this module reads one docs file and renders links; it computes nothing,
stores nothing, and writes nothing.

Run it with::

    uv run uvicorn ah.hub:app --port 8795
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

_REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_PATH = _REPO_ROOT / "docs" / "PLAIN-ENGLISH-USER-MANUAL.md"
WATERMARK = "TOOLS HUB — every surface, what it answers, how to reach it"

#: Papers and documents served at /doc/<slug>. An ALLOWLIST — the hub serves
#: exactly these files and nothing else (no path parameters into the tree).
DOCS: dict[str, tuple[str, str, str]] = {
    # slug: (repo-relative path, title, one-line description)
    "plain-english-manual": (
        "docs/PLAIN-ENGLISH-USER-MANUAL.md",
        "The plain-English manual",
        "Start here: what this platform is, what it honestly is not, and every "
        "task walked through without assuming you know a terminal.",
    ),
    "methodology": (
        "docs/METHODOLOGY.md",
        "The Terrarium Method",
        "The consolidated summary: the approach in one page, the six enforced "
        "honesty constraints, the academic lineage table, a plain-English "
        "walkthrough, and the referee-facing caveats. Sits above D-05 and P1.",
    ),
    "methodology-note": (
        "docs/D-05-methodology-note.md",
        "D-05 — Methodology note (results edition)",
        "How worlds are judged: the two batteries, the pre-registration seal, "
        "and the measured results with their provenance.",
    ),
    "preprint": (
        "docs/P1-specified-world-models-preprint.md",
        "P1 — Specified world models (preprint)",
        "The research paper: specified counterfactual worlds as a modelling "
        "object, with the empirical results section.",
    ),
    "build-summary": (
        "docs/BUILD-SUMMARY.md",
        "Build summary — what exists",
        "The system map: every capability with its status, evidence and "
        "invocation, and the known-gaps register that is the point of it.",
    ),
    "user-manual": (
        "docs/USER-MANUAL.md",
        "User manual (technical)",
        "The verified end-to-end driving manual: every command executed, real "
        "outputs shown, errata recorded.",
    ),
    "realism-register": (
        "docs/engine-realism-register.md",
        "Engine realism register",
        "Where the engine is faithful to its plans but not to an allocator's "
        "expectations: ER-1 through ER-8, open and closed, with what each fix "
        "invalidates.",
    ),
    "data-review": (
        "docs/data/DATA-REVIEW-2026-08-08.md",
        "Data review (2026-08-08)",
        "The mechanical sweep of all 70 fetched series: outliers, gaps, "
        "staleness, cross-series sanity - run before the model re-runs.",
    ),
    "desmoothing-validation": (
        "docs/data/DESMOOTHING-VALIDATION.md",
        "De-smoothing validation (private markets)",
        "Does the de-smoother actually recover risk? Per sleeve: volatility "
        "recovered, autocorrelation before and after, no-ops named, and a "
        "market-priced comparator where one exists.",
    ),
    "desmoothing-note": (
        "docs/notes/desmoothing-coefficient.md",
        "Note — the de-smoothing coefficient",
        "Plain English: what the coefficient means, why it collapses from 0.96 "
        "to 0.53 in stressed markets, and why that is the denominator effect.",
    ),
    "campaign-r1-translation": (
        "docs/data/CAMPAIGN-R1-TRANSLATION.md",
        "Campaign R1 — the twin over observed history",
        "The translation layer re-run on the AM-002 kernel and mappings: four "
        "observed windows, priors scored, the measured PM loadings as a "
        "NOT-ADOPTED diagnostic, and the cashflow tiers named as unchanged "
        "by design.",
    ),
    "campaign-r1-generator": (
        "docs/data/CAMPAIGN-R1-GENERATOR.md",
        "Campaign R1 — the generator cells on the new vintage",
        "The six campaign-2 cells re-run from the existing checkpoints against "
        "vintage 2026-08-07.5, compared cell by cell with the sealed record. "
        "Not a gate: the holdout is spent and the verdicts stand.",
    ),
    "license-registry": (
        "docs/data/LICENSE-REGISTRY.md",
        "Licence registry",
        "What needs clearing before commercial use: every registered series by "
        "licence tier, plus the four quantities the platform needs and has no "
        "licence for, each with why free data does not close it.",
    ),
    "albourne-request": (
        "docs/data/ALBOURNE-COEFFICIENT-REQUEST.md",
        "Albourne coefficient request",
        "The outgoing data request: pacing coefficients per strategy in lieu "
        "of the undelivered ALB-A/C lifecycle datasets, across all 39 sleeves "
        "of the private-markets taxonomy.",
    ),
    # The gate evidence record, in step order.
    "g0-evidence": (
        "G0-EVIDENCE.md",
        "G0 evidence — the rails",
        "Step 0's gate: WorldSpec contract, validator, deterministic engine, "
        "append-only stores and replay, each claim with its command and output.",
    ),
    "g2-evidence": (
        "G2-EVIDENCE.md",
        "G2 evidence — the promotion verdict",
        "The sealed decision rule executed on the ablation grid: PROMOTE "
        "hier-flow-v1, four SHIP-BENCHMARK verdicts, the severe test "
        "INCONCLUSIVE, and every defect in the seal itself disclosed.",
    ),
    "consolidation-evidence": (
        "CONSOLIDATION-EVIDENCE.md",
        "Consolidation evidence — contracts frozen",
        "Step 2R: the frozen contracts, the vintage handoff, and everything "
        "re-run against them before Step 3 was allowed to start.",
    ),
    "g1-evidence": (
        "G1-EVIDENCE.md",
        "G1 evidence — an honest FAIL",
        "The translation layer's 2022 end-to-end reproduction: named "
        "limitations, tier 1 beaten by tier 0, recorded as a FAIL and "
        "carried forward rather than repaired quietly.",
    ),
    "g4-evidence": (
        "governance/evidence/G4-EVIDENCE.md",
        "G4 evidence — artifacts, actors, governance",
        "Step 4's gate scored criterion by criterion: the narrative cage, "
        "tier-2 authoring, live mode, and the GenAI governance record.",
    ),
    "research-evidence": (
        "RESEARCH-EVIDENCE.md",
        "Research evidence — the consolidated record",
        "Step 5's answers to the research questions, including the one-shot "
        "holdout spend: the drawdown stayed inside the cone, terminal wealth "
        "did not, and there is no held-out data left.",
    ),
}

#: The browser surfaces. (name, url, answers, writes)
SURFACES: list[tuple[str, str, str, str]] = [
    (
        "Data console (8796)",
        "http://127.0.0.1:8796/",
        "What data is going INTO the generator? Coverage, gaps, staleness, "
        "proxy-spliced stretches, de-smoothing for privates, and the factor "
        "panel with the sealed train/validation windows shaded.",
        "reads only",
    ),
    (
        "Generator console (8797)",
        "http://127.0.0.1:8797/",
        "Watch a decade get built layer by layer - climate, seasons, weather, "
        "joinery - from the campaign checkpoints (hash-verified), and follow "
        "live campaign runs as their cell artifacts land. Nothing here is a "
        "score.",
        "reads only",
    ),
    (
        "Build console (8798)",
        "http://127.0.0.1:8798/",
        "Type a scenario in plain text and watch it compile into a world, "
        "stage by stage. Nothing is stored until you press Keep.",
        "writes ONLY when you press Keep",
    ),
    (
        "QA console (8799)",
        "http://127.0.0.1:8799/worlds",
        "What came OUT? The shelf of built worlds, their runs, battery "
        "reports, path/ensemble/cashflow views, and the diff page.",
        "reads only",
    ),
    (
        "The playable app (5173)",
        "http://127.0.0.1:5173/",
        "Play a decade against the twin. Needs the session service running "
        "on 8787 (see the commands below).",
        "scores live on the server (8787)",
    ),
]

#: The command-line tools. (command, explanation)
COMMANDS: list[tuple[str, str]] = [
    (
        "uv run ah world build --preset stagflation",
        "Make a world from a ready-made preset (also: goldilocks, deflation_bust, "
        "reflation_boom). Validates, stamps, stores; prints the world id.",
    ),
    (
        'uv run ah world build --scenario "..." --live',
        "Make a world from your own sentence via the live compiler (needs "
        "ANTHROPIC_API_KEY; the build console on 8798 is the watchable version).",
    ),
    (
        "uv run ah run --paths 1000",
        "Simulate the most recent world: 1000 alternate decades from one seed. Prints the run id.",
    ),
    (
        "uv run ah replay",
        "Re-run the latest run from its stored inputs and check the result is "
        "bit-identical. MATCH means nothing changed.",
    ),
    ("uv run ah verify", "Same check as replay, printed as True/False."),
    (
        "uv run ah inspect --out page.html",
        "A self-contained figure page for a run (fan charts, drawdowns); "
        "regenerates and re-verifies before drawing.",
    ),
    (
        "uv run ah battery",
        "The statistical checks on a run's ensemble, judged against the "
        "ratified thresholds. Exit 0 means every enforced gate passed.",
    ),
    (
        "uv run ah credibility --preset stagflation --out credibility.html",
        "The admin sanity walk: does this world's arithmetic look believable, "
        "flagged against declared bands.",
    ),
    (
        "uv run ah chronicle",
        "The append-only life story of a world: birth, runs, everything.",
    ),
    (
        "uv run ah data refresh --live",
        "Fetch fresh data from every source that is due (FRED needs "
        "FRED_API_KEY in .env). Declared gap fills are reported explicitly.",
    ),
    (
        "uv run python scripts/download_primars.py",
        "Fetch the nine Albourne private-markets return series (needs "
        "ALBOURNE_TOKEN in .env) through the standard intake path.",
    ),
    (
        "uv run ah data status",
        "One screen: current vintage, per-source freshness, QC summary.",
    ),
    (
        "uv run uvicorn ah.serve:app --port 8787",
        "Start the session service - the authority for play scoring. The app "
        "on 5173 needs this up.",
    ),
]

_CSS = """
:root { --ink:#151a1f; --mut:#5c6874; --line:#e2e6ea; --bg:#f7f8fa; --card:#fff; }
* { box-sizing:border-box; }
body { margin:0; font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
       color:var(--ink); background:var(--bg); }
.wm { background:#233246; color:#fff; font-size:11px; letter-spacing:.06em;
      padding:5px 14px; text-transform:uppercase; }
main { padding:18px; max-width:980px; margin:0 auto; }
h1 { font-size:20px; margin:12px 0 4px; }
h2 { font-size:16px; margin:22px 0 8px; border-bottom:1px solid var(--line); padding-bottom:4px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:4px;
        padding:12px 14px; margin:10px 0; }
.card b a { color:#1f4e79; text-decoration:none; font-size:15px; }
.tag { display:inline-block; padding:1px 8px; border-radius:9px; font-size:11px;
       border:1px solid var(--line); background:#eef3ee; color:#1f6b3a; margin-left:8px; }
.tag.write { background:#f6ece2; color:#8a5a1f; }
code { background:#eef1f4; padding:2px 6px; border-radius:3px; font-size:12.5px; }
.what { color:var(--mut); margin:4px 0 0; }
.prov { color:var(--mut); font-size:12px; font-style:italic; }
"""


def _e(x: Any) -> str:
    return html.escape(str(x))


def _doc_pdf(slug: str) -> Path | None:
    """The committed PDF sibling of an allowlisted document, or None. Built
    by scripts/build_doc_pdf.py; served at /pdf/<slug>."""
    entry = DOCS.get(slug)
    if entry is None:
        return None
    path = (_REPO_ROOT / entry[0]).with_suffix(".pdf")
    return path if path.exists() else None


def md_to_html(text: str, base: Path | None = None) -> str:
    """A deliberately small markdown subset -> HTML: headers, fenced code,
    tables, lists, hr, bold/italic/code/links, images, paragraphs. Consecutive
    plain lines join into one paragraph (standard markdown), so emphasis may
    wrap across source lines. Enough for this repo's documents; anything
    unrecognized renders as an escaped paragraph.

    ``base``: when given, a standalone ``![alt](name.svg)`` line whose target
    is a *sibling file* of ``base`` (no path separators, so the allowlist
    cannot be escaped) is inlined as the SVG's own markup with the alt text as
    a caption. Without ``base``, or when the file is absent, the alt text
    renders as an italic placeholder — never the raw ``![...]`` line."""
    import re

    def inline(s: str) -> str:
        s = _e(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<i>\1</i>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        return s

    out: list[str] = []
    lines = text.splitlines()
    i = 0
    in_list = False
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            block: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            out.append(f"<pre>{_e(chr(10).join(block))}</pre>")
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1]) <= set("|-: "):
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            header = [inline(c.strip()) for c in line.strip("|").split("|")]
            out.append("<table><tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [inline(c.strip()) for c in lines[i].strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        stripped = line.strip()
        if not stripped:
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
        elif stripped.startswith("#"):
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            text_part = re.sub(r"\s*\{#[^}]*\}\s*$", "", stripped.lstrip("#").strip())
            out.append(f"<h{level}>{inline(text_part)}</h{level}>")
        elif (m := re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", stripped)) is not None:
            flush_para()
            if in_list:
                out.append("</ul>")
                in_list = False
            alt, src = m.group(1), m.group(2)
            target = base / src if base is not None else None
            if (
                target is not None
                and src.endswith(".svg")
                and "/" not in src
                and "\\" not in src
                and target.is_file()
            ):
                out.append(
                    f"<figure>{target.read_text(encoding='utf-8')}"
                    f"<figcaption>{_e(alt)}</figcaption></figure>"
                )
            else:
                out.append(f"<p><i>[figure: {_e(alt)}]</i></p>")
        elif stripped in ("---", "***", "___"):
            flush_para()
            out.append("<hr>")
        elif stripped.startswith(("- ", "* ")):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(stripped[2:])}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            para.append(stripped)
        i += 1
    flush_para()
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


app = FastAPI(title="ah tools hub", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def hub() -> HTMLResponse:
    surface_cards = "".join(
        f'<div class="card"><b><a href="{_e(url)}">{_e(name)}</a></b>'
        f'<span class="tag{" write" if "Keep" in writes else ""}">{_e(writes)}</span>'
        f'<p class="what">{_e(answers)}</p></div>'
        for name, url, answers, writes in SURFACES
    )
    command_cards = "".join(
        f'<div class="card"><code>{_e(cmd)}</code><p class="what">{_e(why)}</p></div>'
        for cmd, why in COMMANDS
    )
    pdf_link = (
        ' · <a href="/manual.pdf">download as PDF</a>'
        if _doc_pdf("plain-english-manual") is not None
        else ""
    )
    manual_note = (
        f'<div class="card"><b><a href="/doc/plain-english-manual">The plain-English '
        f"manual</a></b>{pdf_link}"
        '<p class="what">Start here if you are new: what this platform is, what it '
        "honestly is not, and every task walked through without assuming you know "
        "a terminal.</p></div>"
        if MANUAL_PATH.exists()
        else '<div class="card"><p class="what">Plain-English manual not found at '
        "docs/PLAIN-ENGLISH-USER-MANUAL.md.</p></div>"
    )
    doc_cards = "".join(
        f'<div class="card"><b><a href="/doc/{_e(slug)}">{_e(title)}</a></b>'
        + (
            f' &middot; <a href="/pdf/{_e(slug)}">download as PDF</a>'
            if _doc_pdf(slug) is not None
            else ""
        )
        + f'<p class="what">{_e(blurb)}</p></div>'
        for slug, (rel, title, blurb) in DOCS.items()
        if slug != "plain-english-manual" and (_REPO_ROOT / rel).exists()
    )
    body = (
        "<h1>Every tool, and the question it answers</h1>"
        '<p class="prov">Consoles must be started before their links work - each '
        "card's command is in the list below. This hub reads allowlisted docs "
        "files and writes nothing.</p>"
        f"<h2>Start here</h2>{manual_note}"
        f"<h2>Browser surfaces</h2>{surface_cards}"
        f"<h2>Command-line tools</h2>{command_cards}"
        f"<h2>Papers &amp; documents</h2>{doc_cards}"
    )
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>ah tools hub</title>"
        f"<style>{_CSS}</style></head><body>"
        f'<div class="wm">{_e(WATERMARK)}</div><main>{body}</main></body></html>'
    )


@app.get("/manual", response_class=PlainTextResponse)
def manual() -> PlainTextResponse:
    if not MANUAL_PATH.exists():
        return PlainTextResponse("plain-English manual not found", status_code=404)
    return PlainTextResponse(MANUAL_PATH.read_text(encoding="utf-8"))


def _pdf_response(slug: str) -> FileResponse:
    path = _doc_pdf(slug)
    if path is None:
        raise HTTPException(404, "no PDF for that document; see scripts/build_doc_pdf.py")
    return FileResponse(path, media_type="application/pdf")


@app.get("/pdf/{slug}")
def doc_pdf(slug: str) -> FileResponse:
    return _pdf_response(slug)


@app.get("/manual.pdf")
def manual_pdf() -> FileResponse:
    # Alias kept for links that predate /pdf/<slug>.
    return _pdf_response("plain-english-manual")


@app.get("/methodology.pdf")
def methodology_pdf() -> FileResponse:
    # Alias kept for links that predate /pdf/<slug>.
    return _pdf_response("methodology")


_DOC_CSS = (
    "body{font:15px/1.6 Georgia,serif;color:#1a1a1a;max-width:820px;margin:0 auto;"
    "padding:28px}h1{font-size:26px}h2{font-size:20px;border-bottom:1px solid #ddd;"
    "padding-bottom:4px}pre{background:#f4f4f4;padding:10px;overflow-x:auto;"
    "font-size:12px}code{background:#f4f4f4;padding:1px 4px;font-size:13px}"
    "table{border-collapse:collapse;margin:10px 0}td,th{border:1px solid #ccc;"
    "padding:4px 9px;text-align:left;font-size:13.5px}a{color:#1f4e79}"
)


@app.get("/doc/{slug}", response_class=HTMLResponse)
def doc(slug: str) -> HTMLResponse:
    entry = DOCS.get(slug)
    if entry is None:
        raise HTTPException(404, "no such document")
    rel, title, _ = entry
    path = _REPO_ROOT / rel
    if not path.exists():
        raise HTTPException(404, f"{rel} not present in this checkout")
    body = md_to_html(path.read_text(encoding="utf-8"), base=path.parent)
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{_e(title)}</title>"
        f"<style>{_DOC_CSS}</style></head><body>"
        f'<p><a href="/">&larr; tools hub</a></p>{body}</body></html>'
    )
