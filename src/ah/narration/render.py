"""``slates.html`` and ``diagnostics.html`` — the two things a human reads.

Both are self-contained, deterministic and free of anything time-dependent: no
timestamp, no run clock, no iteration over an unordered mapping. Two builds of
the same world with the same config produce byte-identical files, which is
acceptance item 2 and is tested rather than asserted.

The paper's furniture follows DN-9 §5: masthead, dateline, market strip, four
slots, the special-edition band, and compliance furniture in the footer where a
newspaper already has one. Layout state is a *rendering of revealed state*
(§5.2), keyed by the config's regime -> state map.
"""

from __future__ import annotations

import html
import json
from typing import Any

from ah.narration.constants import HASH_DISPLAY_CHARS, SEVERITY_MAX
from ah.narration.probe import PROBE_STATUS
from ah.narration.voices import RenderedSlate

__all__ = ["render_diagnostics", "render_slates"]

_CSS = """
:root{--ink:#14181d;--paper:#fdfcf8;--rule:#ded6c7;--muted:#5c6570;--accent:#8f2e26}
body{background:#f6f2e9;color:var(--ink);font-family:Georgia,'Times New Roman',serif;margin:0;padding:28px}
.page{max-width:1060px;margin:0 auto 34px;background:var(--paper);border:1px solid var(--rule);padding:26px 30px}
.mast{text-align:center;font-size:32px;letter-spacing:8px;margin:2px 0 8px}
.rule{border-top:2.4px solid var(--ink);border-bottom:.8px solid var(--ink);height:3px;margin-bottom:10px}
.dateline{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);font-style:italic;margin-bottom:14px}
.banner{background:var(--ink);color:var(--paper);text-align:center;font-size:11px;letter-spacing:5px;padding:5px;margin-bottom:10px}
.warn{background:var(--accent);color:var(--paper);padding:10px 14px;font-size:12px;letter-spacing:.4px;margin:0 auto 24px;max-width:1060px}
.slot{background:var(--ink);color:var(--paper);font-size:9.5px;letter-spacing:3px;padding:5px 12px;display:flex;justify-content:space-between}
.item{border:1px solid var(--rule);margin-bottom:16px}
.item.lead{border:1.4px solid var(--ink)}
.item h2{font-size:24px;margin:14px 16px 8px;line-height:1.14}
.item p{margin:0 16px 10px;font-size:13px}
.voice{margin:0 16px 10px;font-size:12px;color:#2b3238;border-left:2px solid var(--rule);padding-left:10px}
.voice b{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}
.chip{background:var(--accent);color:var(--paper);padding:1px 7px;font-size:8.5px;letter-spacing:1px;margin-left:5px}
.diff ins{background:#e5f0e2;text-decoration:none}
.diff del{background:#f5e2e0}
.notes{font-size:11px;color:var(--muted);border-top:1px solid var(--rule);padding-top:8px;margin-top:8px}
.foot{border-top:.8px solid var(--ink);margin-top:18px;padding-top:9px;font-size:9.5px;color:var(--muted);display:flex;justify-content:space-between}
table{border-collapse:collapse;width:100%;font-size:12px;margin:8px 0 18px}
th,td{border-bottom:1px solid var(--rule);padding:5px 8px;text-align:left}
th{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}
.panel h2{font-size:17px;margin:22px 0 2px}
.panel .sub{font-size:11px;color:var(--accent);margin:0 0 6px;font-style:italic}
.verdict{font-weight:bold}
pre{background:#f0ebe0;padding:10px;font-size:11px;overflow-x:auto}
"""

_FOOTER_LEFT = "SIMULATED WORLD · no firm, person or institution is real · not investment advice"
_FOOTER_RIGHT = "Tier-1 · deterministic · no LLM"


def _e(value: Any) -> str:
    return html.escape(str(value))


def _probe_banner(manifest: dict[str, Any]) -> str:
    if manifest["voices"]["config_status"] != PROBE_STATUS:
        return ""
    filled = len(manifest["voices"]["probe_filled_keys"])
    return (
        f"<div class='warn'><b>PROBE BUILD — NOT A DECISION.</b> {filled} open parameters were "
        "filled by the mechanical rule <i>take the first candidate listed in UNRESOLVED.md</i>. "
        "Nothing here has been ratified; every value is still an open decision. This page "
        "measures the workbench, not the world.</div>"
    )


def _capital_note(manifest: dict[str, Any]) -> str:
    if manifest["adapter"]["capital_slot"] != "omitted":
        return ""
    absent = ", ".join(manifest["adapter"]["optional_series_absent"])
    return (
        "<div class='warn'><b>CAPITAL SLOT OMITTED.</b> This world carries no book series "
        f"({_e(absent)}), so the CAPITAL slot is omitted from every slate rather than stubbed. "
        "Six event classes (E12, E15-E19) have no input and never fire.</div>"
    )


def _diff_html(diff: list[dict[str, str]]) -> str:
    if not diff:
        return ""
    parts = []
    for change in diff:
        if change["removed"]:
            parts.append(f"<del>{_e(change['removed'])}</del>")
        if change["added"]:
            parts.append(f"<ins>{_e(change['added'])}</ins>")
    return (
        "<div class='voice diff'><b>Changes from the previous statement</b><br>"
        + " ".join(parts)
        + "</div>"
    )


def render_slates(rendered: list[RenderedSlate], manifest: dict[str, Any]) -> str:
    """All forty slates, readable end to end in one scroll."""
    out: list[str] = [
        "<meta charset='utf-8'>",
        "<title>THE WIRE — the decade</title>",
        f"<style>{_CSS}</style>",
        _probe_banner(manifest),
        _capital_note(manifest),
    ]
    for slate in rendered:
        meta = slate.slate
        out.append("<div class='page'>")
        out.append("<div class='mast'>THE WIRE</div><div class='rule'></div>")
        if meta.special:
            out.append("<div class='banner'>SPECIAL EDITION</div>")
        out.append(
            f"<div class='dateline'><span>{_e(slate.dateline)} · Year {meta.year}, "
            f"Quarter {meta.quarter_of_year}</span>"
            f"<span>slate {meta.quarter:02d}/40 · layout: {_e(slate.layout_state)}</span></div>"
        )
        lead = meta.lead
        for item in slate.items:
            is_lead = lead is not None and item.announcement is lead
            classes = "item lead" if is_lead else "item"
            announcement = item.announcement
            out.append(f"<div class='{classes}'>")
            out.append(
                f"<div class='slot'><span>{_e(announcement.slot)} · {_e(announcement.panel)} · "
                f"sev {announcement.event.severity} · {_e(announcement.delta['label'])}</span>"
                f"<span>{''.join(f'<span class=chip>{_e(c)}</span>' for c in item.report.chips)}"
                "</span></div>"
            )
            out.append(f"<h2>{_e(item.report.headline)}</h2>")
            for paragraph in item.report.body:
                out.append(f"<p>{_e(paragraph)}</p>")
            for artifact in item.voices:
                out.append(f"<div class='voice'><b>{_e(artifact.headline)}</b><br>")
                out.append("<br>".join(_e(line) for line in artifact.body))
                out.append("</div>")
                if artifact.extras.get("statement_diff"):
                    out.append(_diff_html(artifact.extras["statement_diff"]))
                if artifact.extras.get("rule_monitor"):
                    out.append(
                        "<div class='voice'><b>Why they moved — rule monitor</b><br>"
                        f"{_e(artifact.extras['rule_monitor'])}</div>"
                    )
            if announcement.also_this_quarter:
                also = "; ".join(
                    f"{_e(other.cls)} m{other.month} ({_e(other.delta['label'])})"
                    for other in announcement.also_this_quarter
                )
                out.append(f"<div class='notes'>Also this quarter: {also}</div>")
            out.append("</div>")
        if slate.notes:
            out.append(
                "<div class='notes'>" + "<br>".join(_e(note) for note in slate.notes) + "</div>"
            )
        out.append(
            f"<div class='foot'><span>{_FOOTER_LEFT}</span><span>{_FOOTER_RIGHT}</span></div>"
        )
        out.append("</div>")
    return "\n".join(out) + "\n"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def render_diagnostics(panels: dict[str, Any], manifest: dict[str, Any]) -> str:
    """The nine panels. Two of them are diagnostics on the generator."""
    out: list[str] = [
        "<meta charset='utf-8'>",
        "<title>THE WIRE — diagnostics</title>",
        f"<style>{_CSS}</style>",
        _probe_banner(manifest),
        _capital_note(manifest),
        "<div class='page'>",
        "<div class='mast'>DIAGNOSTICS</div><div class='rule'></div>",
        f"<div class='dateline'><span>world {_e(manifest['world_id'])} · "
        f"generator {_e(manifest['generator']['generator_id'])} · "
        f"seed {_e(manifest['generator']['seed'])}</span>"
        f"<span>voices {_e(manifest['voices']['hash'][:HASH_DISPLAY_CHARS])} · "
        f"narration {_e(manifest['narration_version'])}</span></div>",
    ]

    severity = panels["severity"]
    verdict = "IN BAND" if severity["in_band"] else "OUT OF BAND"
    out.append("<div class='panel'><h2>1 · Severity calibration</h2>")
    out.append(
        f"<p class='verdict'>{severity['severity_3_count']} severity-3 events this decade "
        f"against a configured target band of {severity['target_band']} — {verdict}.</p>"
    )
    out.append(
        _table(
            ["severity", "events"],
            [[k, v] for k, v in sorted(severity["histogram"].items())],
        )
    )
    out.append(
        _table(
            ["class", "sev 0", "sev 1", "sev 2", "sev 3"],
            [
                [cls]
                + [
                    counts.get(level, counts.get(str(level), 0))
                    for level in range(SEVERITY_MAX + 1)
                ]
                for cls, counts in sorted(severity["by_class"].items())
            ],
        )
    )
    out.append("</div>")

    contest = panels["slot_contest"]
    out.append("<div class='panel'><h2>2 · Slot contest</h2>")
    for slot, rows in sorted(contest["winners"].items()):
        out.append(f"<h3>{_e(slot)}</h3>")
        out.append(_table(["class", "slots won"], [[cls, count] for cls, count in rows]))
    out.append(
        _table(
            ["announcements per slate", "slates"],
            [[k, v] for k, v in sorted(contest["slate_sizes"].items())],
        )
    )
    out.append("</div>")

    repetition = panels["repetition"]
    out.append(f"<div class='panel'><h2>3 · Repetition ({repetition['n']}-grams)</h2>")
    out.append(
        f"<p>{repetition['distinct_ngrams']} distinct of {repetition['total_ngrams']} total.</p>"
    )
    out.append(
        _table(
            ["phrase", "count"],
            [[row["phrase"], row["count"]] for row in repetition["top"]],
        )
    )
    out.append("</div>")

    vocabulary = panels["vocabulary"]
    out.append("<div class='panel'><h2>4 · Vocabulary -> regime</h2>")
    out.append(f"<p class='sub'>{_e(vocabulary['note'])}</p>")
    out.append(f"<p>Mean MI over the measured vocabulary: {vocabulary['mean_mi_bits']} bits.</p>")
    out.append(
        _table(
            ["word", "MI (bits)"],
            [[row["word"], row["mi_bits"]] for row in vocabulary["top"]],
        )
    )
    out.append("</div>")

    chips = panels["chips"]
    out.append("<div class='panel'><h2>5 · Verdict chips</h2>")
    out.append(_table(["chip", "count"], [[r["chip"], r["count"]] for r in chips["top"]]))
    out.append("</div>")

    policy = panels["policy"]
    out.append("<div class='panel'><h2>6 · Policy diagnostics</h2>")
    out.append(f"<p class='sub'>{_e(policy['subtitle'])}</p>")
    out.append(
        f"<p class='verdict'>Meeting-to-meeting reversal frequency: "
        f"{policy['reversal_frequency']} ({policy['reversals']} reversals across "
        f"{policy['moves']} moves in {policy['meetings']} meetings).</p>"
    )
    out.append(
        _table(
            ["|step| (bp)", "meetings"],
            [[k, v] for k, v in sorted(policy["step_histogram"].items())],
        )
    )
    out.append(f"<pre>epsilon, bp: {_e(json.dumps(policy['epsilon_bp'], sort_keys=True))}</pre>")
    out.append("</div>")

    strain = panels["strain"]
    out.append("<div class='panel'><h2>7 · Rationale strain</h2>")
    out.append(f"<p class='sub'>{_e(strain['subtitle'])}</p>")
    out.append(
        f"<p>mean {strain['mean']} · max {strain['max']} over {strain['count']} meetings.</p>"
    )
    out.append(
        _table(
            ["month", "strain", "state", "epsilon", "contradictions"],
            [
                [row["month"], row["strain"], row["state"], row["epsilon"], row["contradictions"]]
                for row in strain["top"]
            ],
        )
    )
    out.append("</div>")

    coverage = panels["coverage"]
    out.append("<div class='panel'><h2>8 · Coverage</h2>")
    out.append(
        f"<p>Classes that never fired: {_e(', '.join(coverage['classes_never_fired']) or 'none')}."
        f"<br>Slates below {coverage['min_slots']} slots: "
        f"{len(coverage['slates_below_minimum'])}."
        f"<br>[[NO TEMPLATE]] markers emitted: {coverage['no_template_markers']}.</p>"
    )
    out.append(
        _table(
            ["slot", "times omitted"],
            [[k, v] for k, v in sorted(coverage["omitted_slots"].items())],
        )
    )
    out.append("</div>")

    columnists = panels["columnists"]
    out.append("<div class='panel'><h2>9 · Columnists</h2>")
    out.append(
        f"<p>Target hit-rate band {columnists['hit_rate_target']}; mean dispersion "
        f"{columnists['mean_dispersion']}. Deferred to Tier-2: "
        f"{_e(', '.join(columnists['deferred']) or 'none')}.</p>"
    )
    out.append(
        _table(
            ["columnist", "calls", "hit rate", "in target band"],
            [
                [row["name"], row["calls"], row["hit_rate"], row["in_target_band"]]
                for row in columnists["records"]
            ],
        )
    )
    out.append("</div>")

    out.append(
        f"<div class='foot'><span>{_FOOTER_LEFT}</span><span>{_FOOTER_RIGHT}</span></div></div>"
    )
    return "\n".join(out) + "\n"
