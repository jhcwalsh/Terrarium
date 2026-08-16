"""The tweak loop.

::

    python -m ah.narration build --world <preset path or name> --voices voices.yaml --out runs/<id>
    python -m ah.narration compare runs/<a> runs/<b>
    python -m ah.narration probe --voices voices.yaml --out <path>

Editing ``voices.yaml`` and re-running is the only step needed to change a
voice. ``build`` on the shipped config **fails** with the unresolved list — that
is the correct behaviour, not a bug, and ``probe`` exists so the workbench can
still be measured while the list is open.

Argparse rather than Typer: the repo's Typer CLIs carry a documented constraint
about ``from __future__ import annotations``, and this entry point has no reason
to join that surface. It is a workbench tool, not part of ``ah``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ah.narration.build import (
    build_from_ensemble,
    finalise_manifest,
    load_config,
    load_world_ensemble,
    write_events_jsonl,
    write_manifest,
)
from ah.narration.constants import HASH_DISPLAY_CHARS
from ah.narration.diagnostics import compute
from ah.narration.errors import MissingSeriesError, UnresolvedParameter
from ah.narration.events import uncovered_classes
from ah.narration.probe import write_probe
from ah.narration.render import render_diagnostics, render_slates

__all__ = ["main", "run_build"]

_PRESETS = Path(__file__).resolve().parent.parent / "presets"


def _resolve_world(name: str) -> Path:
    candidate = Path(name)
    if candidate.exists():
        return candidate
    preset = _PRESETS / f"{name}.json"
    if preset.exists():
        return preset
    raise SystemExit(f"no world at '{name}' and no preset named '{name}' in {_PRESETS}")


def run_build(world: str, voices: str, out: str) -> dict[str, Any]:
    """Build one world and write the four files. Returns the manifest."""
    spec_path = _resolve_world(world)
    config = load_config(voices)
    numeric, ensemble = load_world_ensemble(spec_path)
    result = build_from_ensemble(ensemble, config=config, world_id=numeric.world_id)

    panels = compute(
        events=result.events,
        slates=result.slates,
        rendered=result.rendered,
        world=result.world,
        strain_log=result.strain_log,
        columnist_calls=result.columnist_calls,
        target_band=list(config.get("severity.target_sev3_band")),
        ngram_n=int(config.get("diagnostics.repetition_ngram_n")),
        min_slots=result.slate_params.min_slots,
        hit_rate_target=list(config.get("voices.columnists.hit_rate_target")),
        columnist_horizon_months=int(config.get("diagnostics.columnist_horizon_months")),
        uncovered=uncovered_classes(result.events, book_available=result.world.book_available),
    )
    manifest = finalise_manifest(result.manifest, config, panels)

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "slates.html").write_text(
        render_slates(result.rendered, manifest), encoding="utf-8", newline="\n"
    )
    (out_dir / "diagnostics.html").write_text(
        render_diagnostics(panels, manifest), encoding="utf-8", newline="\n"
    )
    write_events_jsonl(result.events, out_dir / "events.jsonl")
    write_manifest(manifest, out_dir / "manifest.json")
    return manifest


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    else:
        out[prefix] = node
    return out


def run_compare(left: str, right: str) -> int:
    """Manifest + diagnostics delta between two runs."""
    a = json.loads((Path(left) / "manifest.json").read_text(encoding="utf-8"))
    b = json.loads((Path(right) / "manifest.json").read_text(encoding="utf-8"))
    flat_a, flat_b = _flatten(a), _flatten(b)

    keys = sorted(set(flat_a) | set(flat_b))
    config_changes = [
        key for key in keys if key.startswith("voices.") and flat_a.get(key) != flat_b.get(key)
    ]
    downstream = [
        key for key in keys if not key.startswith("voices.") and flat_a.get(key) != flat_b.get(key)
    ]

    print(f"comparing {left} -> {right}")
    print(
        f"  voices hash: {a['voices']['hash'][:HASH_DISPLAY_CHARS]} -> {b['voices']['hash'][:HASH_DISPLAY_CHARS]}"
    )
    print(f"\n  CONFIG DIFFERENCES ({len(config_changes)}):")
    for key in config_changes:
        print(f"    {key}: {flat_a.get(key)!r} -> {flat_b.get(key)!r}")
    print(f"\n  DOWNSTREAM EFFECTS ({len(downstream)}):")
    for key in downstream:
        print(f"    {key}: {flat_a.get(key)!r} -> {flat_b.get(key)!r}")
    if not config_changes and not downstream:
        print("    none - the two runs are identical")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ah.narration", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="render one world's decade")
    build.add_argument("--world", required=True, help="preset name or path to a WorldSpec json")
    build.add_argument("--voices", required=True, help="path to voices.yaml")
    build.add_argument("--out", required=True, help="output directory")

    compare = sub.add_parser("compare", help="manifest + diagnostics delta between two runs")
    compare.add_argument("left")
    compare.add_argument("right")

    probe = sub.add_parser("probe", help="generate the unratified probe config")
    probe.add_argument("--voices", required=True)
    probe.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    if args.command == "compare":
        return run_compare(args.left, args.right)
    if args.command == "probe":
        path = write_probe(load_config(args.voices), args.out)
        print(f"wrote {path} - UNRATIFIED, every value is candidates[0] from UNRESOLVED.md")
        return 0

    try:
        manifest = run_build(args.world, args.voices, args.out)
    except UnresolvedParameter as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except MissingSeriesError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    counts = manifest["counts"]
    print(
        f"wrote {args.out}: {counts['events']} events, {counts['slates']} slates, "
        f"{counts['announcements']} announcements, {counts['severity_3']} severity-3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
