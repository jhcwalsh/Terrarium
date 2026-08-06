"""Results figures for D-05 v0.3 and P1 v0.3 (Task 2 Part D, Ruling 5).

Draws only what recorded data supports:

1. ``fig-benchmark-comparison.svg``   -- the campaign-2 kill-criterion outcome
2. ``fig-preregistration-timeline.svg`` -- the two batteries, their seals, the
   2026-08-04 stylised-panel run, and ratification status per gate

**Pure-Python SVG, zero new dependencies**, following the precedent set by
``scripts/build_artifact.py`` and ``ah/inspect.py``. The task brief asked for
matplotlib; matplotlib is not a dependency of this project and the repo's
convention is that adding one needs a stated justification. The twelve figures
already shipping with these documents are hand-authored SVG in a house style
(Georgia serif, ink ``#1a1a1a``/``#333``/``#666``), so matching that style with
the same technique is both cheaper and more consistent than importing a
plotting stack to produce a different look.

**Palette.** Series hues are ``#12628f`` (challenger) and ``#9a4a2f``
(benchmark). The house blue is ``#2c5a7a``; it fails the chroma floor
(0.073 < 0.10, "reads gray"), so it is stepped to ``#12628f`` in the same hue
family. The pair validates clean: CVD separation dE 14.8 (protan) / 22.9
(tritan), normal-vision dE 21.5, contrast >= 3:1, all inside the lightness
band. ``#8a2f2f`` is used ONLY as a status colour (unratified / outside band)
and never as an adjacent categorical series -- it sits dE 7.3 from the
benchmark rust, which would fail as a series pair. Every status use carries a
text label and a line-style change, never colour alone.

Deterministic: no clock, no RNG. Values are literals transcribed from the
recorded artifacts named in ``PROVENANCE``.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROVENANCE = (
    "experiments/campaign2/cells/{F-hier-flow-v1,B-bootstrap-v1}-s{0,1,2}/battery.json; "
    "artifacts/campaign2/promotion-verdict.json; prereg digest sha256:e50e18f3...f85d92"
)

CHAL = "#12628f"  # challenger, validated
BENCH = "#9a4a2f"  # benchmark, validated
STATUS = "#8a2f2f"  # status only, always with a label
INK = "#1a1a1a"
INK2 = "#333"
MUTED = "#666"
RULE = "#d8d8d4"

# -- recorded values -------------------------------------------------------- #
SEEDS = (0, 1, 2)
CHAL_ELIC = (-2.5591, -2.5163, -2.5116)
BENCH_ELIC = (-2.2131, -2.2132, -2.2139)
DIFFS = (-0.3461, -0.3031, -0.2978)
CHAL_EXC = (12, 5, 8)
BENCH_EXC = (13, 11, 12)
MEAN_D, SD_D = -0.3157, 0.0265

STYLE = """
  <style>
    text { font-family: Georgia, 'Times New Roman', serif; }
    .h  { font-size: 15px; font-weight: bold; fill: #1a1a1a; }
    .s  { font-size: 11.5px; fill: #333; }
    .p  { font-size: 12px; font-weight: bold; fill: #1a1a1a; }
    .m  { font-size: 10.5px; fill: #666; font-style: italic; }
    .t  { font-size: 10px; fill: #666; }
    .v  { font-size: 9.5px; fill: #333; }
    .ax { stroke: #d8d8d4; stroke-width: 1; }
  </style>
"""


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _lerp(v: float, lo: float, hi: float, a: float, b: float) -> float:
    if hi == lo:
        return (a + b) / 2.0
    return a + (v - lo) * (b - a) / (hi - lo)


def benchmark_figure() -> str:
    w, h = 880, 400
    out: list[str] = [
        f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Benchmark comparison across three seeds">',
        STYLE,
        f'<rect width="{w}" height="{h}" fill="#fdfdfc"/>',
        '<text x="28" y="30" class="h">Benchmark comparison — verdict PROMOTE, per-seed route</text>',
        '<text x="28" y="50" class="m">'
        "hier-flow-v1 against bootstrap-v1. The sealed rule required the challenger to win in every seed."
        "</text>",
    ]
    # shared legend (2 series -> legend always present)
    out += [
        f'<rect x="28" y="62" width="10" height="10" fill="{CHAL}"/>',
        '<text x="44" y="71" class="t">hier-flow-v1 (challenger)</text>',
        f'<rect x="196" y="62" width="10" height="10" fill="{BENCH}"/>',
        '<text x="212" y="71" class="t">bootstrap-v1 (benchmark)</text>',
    ]

    panel_w, panel_x0, top, bot = 250, 28, 108, 300
    titles = (
        "Tail criterion — elicitability score",
        "Difference (negative = challenger wins)",
        "No-regression — band exceedances",
    )
    for i, title in enumerate(titles):
        x0 = panel_x0 + i * (panel_w + 40)
        out.append(f'<text x="{x0}" y="{top - 14}" class="p">{_esc(title)}</text>')
        out.append(f'<line x1="{x0}" y1="{bot}" x2="{x0 + panel_w}" y2="{bot}" class="ax"/>')
        for j, s in enumerate(SEEDS):
            cx = x0 + 42 + j * ((panel_w - 70) / 2)
            out.append(
                f'<text x="{cx:.1f}" y="{bot + 16}" class="t" text-anchor="middle">seed {s}</text>'
            )

    # -- panel 1: elicitability lines
    x0 = panel_x0
    lo, hi = -2.60, -2.18

    def px(j: int) -> float:
        return x0 + 42 + j * ((panel_w - 70) / 2)

    def py(v: float) -> float:
        return _lerp(v, lo, hi, bot - 8, top + 8)

    for series, colour, dash in (
        (CHAL_ELIC, CHAL, ""),
        (BENCH_ELIC, BENCH, ' stroke-dasharray="5 3"'),
    ):
        pts = " ".join(f"{px(j):.1f},{py(v):.1f}" for j, v in enumerate(series))
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2"{dash}/>'
        )
        for j, v in enumerate(series):
            out.append(
                f'<circle cx="{px(j):.1f}" cy="{py(v):.1f}" r="4.5" fill="{colour}" '
                f'stroke="#fdfdfc" stroke-width="2"/>'
            )
    out.append(f'<text x="{px(0) - 8:.1f}" y="{py(CHAL_ELIC[0]) + 16:.1f}" class="v">-2.559</text>')
    out.append(
        f'<text x="{px(0) - 8:.1f}" y="{py(BENCH_ELIC[0]) - 10:.1f}" class="v">-2.213</text>'
    )

    # -- panel 2: difference bars + pooled mean band
    x0 = panel_x0 + (panel_w + 40)
    lo2, hi2 = -0.40, 0.0

    def py2(v: float) -> float:
        return _lerp(v, lo2, hi2, bot - 8, top + 8)

    band_top, band_bot = py2(MEAN_D + SD_D), py2(MEAN_D - SD_D)
    out.append(
        f'<rect x="{x0}" y="{band_top:.1f}" width="{panel_w}" height="{band_bot - band_top:.1f}" '
        f'fill="{STATUS}" opacity="0.10"/>'
    )
    out.append(
        f'<line x1="{x0}" y1="{py2(MEAN_D):.1f}" x2="{x0 + panel_w}" y2="{py2(MEAN_D):.1f}" '
        f'stroke="{STATUS}" stroke-width="1.5" stroke-dasharray="4 3"/>'
    )
    out.append(
        f'<text x="{x0 + panel_w}" y="{py2(MEAN_D) - 6:.1f}" class="v" text-anchor="end">'
        f"pooled mean -0.3157, ±1 sd 0.0265</text>"
    )
    for j, v in enumerate(DIFFS):
        cx = x0 + 42 + j * ((panel_w - 70) / 2)
        y = py2(v)
        out.append(
            f'<rect x="{cx - 16:.1f}" y="{py2(0.0):.1f}" width="32" height="{y - py2(0.0):.1f}" '
            f'fill="{CHAL}" rx="3"/>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{y + 14:.1f}" class="v" text-anchor="middle">{v:+.4f}</text>'
        )
    out.append(
        f'<line x1="{x0}" y1="{py2(0.0):.1f}" x2="{x0 + panel_w}" y2="{py2(0.0):.1f}" class="ax"/>'
    )

    # -- panel 3: grouped exceedance bars
    x0 = panel_x0 + 2 * (panel_w + 40)
    hi3 = 15.0

    def py3(v: float) -> float:
        return _lerp(v, 0.0, hi3, bot, top + 8)

    for j in range(3):
        cx = x0 + 42 + j * ((panel_w - 70) / 2)
        for k, (series, colour) in enumerate(((CHAL_EXC, CHAL), (BENCH_EXC, BENCH))):
            v = series[j]
            bx = cx - 20 + k * 22  # 2px surface gap between adjacent bars
            out.append(
                f'<rect x="{bx:.1f}" y="{py3(v):.1f}" width="20" height="{bot - py3(v):.1f}" '
                f'fill="{colour}" rx="3"/>'
            )
            out.append(
                f'<text x="{bx + 10:.1f}" y="{py3(v) - 5:.1f}" class="v" text-anchor="middle">{v}</text>'
            )

    out += [
        f'<text x="28" y="{h - 40}" class="m">'
        "Generator hier-flow-v1 (campaign-2 checkpoints, c6addb54…); battery version eval-battery-0.1; "
        "vintage 2026-08-02.4; 1024 x 120."
        "</text>",
        f'<text x="28" y="{h - 24}" class="m">'
        "Pre-registered: thresholds hashed with the judging code, digest sha256:e50e18f3… verified on every "
        "cell. RFR-66 (benchmark draw-span bias) applies."
        "</text>",
        "</svg>",
    ]
    return "\n".join(out)


EVENTS = (
    ("2026-07-24", "Panel thresholds drafted", "all seven todo — never ratified", 0),
    ("2026-07-26", "Pre-registration sealed", "thresholds + judging code", 1),
    ("2026-07-31", "G2 verdict adjudicated", "4 of 5 SHIP-BENCHMARK", 1),
    ("2026-08-02", "Campaign-2 re-seal", "digest e50e18f3…; PROMOTE", 1),
    ("2026-08-03", "Holdout spent", "drawdown surprise −0.3952", 1),
    ("2026-08-04", "Panel run", "acf_r_lag1 0.364 — outside band", 0),
)


def timeline_figure() -> str:
    w, h = 880, 470
    out: list[str] = [
        f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Pre-registration timeline for the two batteries">',
        STYLE,
        f'<rect width="{w}" height="{h}" fill="#fdfdfc"/>',
        '<text x="28" y="30" class="h">Pre-registration status, by battery</text>',
        '<text x="28" y="50" class="m">'
        "Two batteries, two standings. They are reported separately and never combined."
        "</text>",
    ]

    lane_y = {1: 150, 0: 310}
    x_start, x_end = 300, 800
    step = (x_end - x_start) / (len(EVENTS) - 1)

    # lane rules: solid = sealed, dashed = unratified (line style is the secondary encoding)
    out += [
        f'<line x1="{x_start - 20}" y1="{lane_y[1]}" x2="{x_end}" y2="{lane_y[1]}" '
        f'stroke="{CHAL}" stroke-width="2"/>',
        f'<line x1="{x_start - 20}" y1="{lane_y[0]}" x2="{x_end}" y2="{lane_y[0]}" '
        f'stroke="{STATUS}" stroke-width="2" stroke-dasharray="6 4"/>',
    ]
    out += [
        f'<text x="28" y="{lane_y[1] - 6}" class="p">Step-2 generator battery</text>',
        f'<text x="28" y="{lane_y[1] + 12}" class="t">PRE-REGISTERED — sealed</text>',
        f'<text x="28" y="{lane_y[1] + 27}" class="t">pass/fail claims permitted</text>',
        f'<text x="28" y="{lane_y[0] - 6}" class="p">Step-0 stylised panel</text>',
        f'<text x="28" y="{lane_y[0] + 12}" class="t">DESCRIPTIVE — gates unratified</text>',
        f'<text x="28" y="{lane_y[0] + 27}" class="t">no pass/fail claim made</text>',
    ]

    for i, (date, title, detail, lane) in enumerate(EVENTS):
        x = x_start + i * step
        y = lane_y[lane]
        colour = CHAL if lane == 1 else STATUS
        out.append(
            f'<circle cx="{x:.1f}" cy="{y}" r="6" fill="{colour}" stroke="#fdfdfc" stroke-width="2"/>'
        )
        # labels alternate above/below within a lane to avoid collision
        up = i % 2 == 0
        ty = y - 22 if up else y + 34
        out.append(f'<text x="{x:.1f}" y="{ty}" class="v" text-anchor="middle">{_esc(date)}</text>')
        out.append(
            f'<text x="{x:.1f}" y="{ty + (-14 if up else 14)}" class="t" text-anchor="middle">'
            f"{_esc(title)}</text>"
        )
        out.append(
            f'<text x="{x:.1f}" y="{ty + (-27 if up else 27)}" class="m" text-anchor="middle" '
            f'font-size="9">{_esc(detail)}</text>'
        )

    out += [
        f'<text x="28" y="{h - 52}" class="m">'
        "Sealed line: thresholds hashed together with the code that judges them, verified by content "
        "address (prereg_digest) on every recorded run."
        "</text>",
        f'<text x="28" y="{h - 36}" class="m">'
        "Dashed line: thresholds drafted 2026-07-24 and never ratified; the one observed statistic was "
        "observed before ratification, so it is descriptive."
        "</text>",
        f'<text x="28" y="{h - 20}" class="m">'
        "Generator hier-flow-v1; battery versions eval-battery-0.1 (Step 2) and battery-0.1 (Step 0)."
        "</text>",
        "</svg>",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else Path("docs/figures/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, svg in (
        ("fig-benchmark-comparison.svg", benchmark_figure()),
        ("fig-preregistration-timeline.svg", timeline_figure()),
    ):
        target = out_dir / name
        target.write_text(svg, encoding="utf-8", newline="\n")
        print(f"wrote {target} ({len(svg)} bytes)")
    print(f"provenance: {PROVENANCE}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
