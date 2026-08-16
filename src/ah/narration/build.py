"""The build: config -> adapter -> events -> slates -> voices -> four files.

This module is where ``voices.yaml`` is turned into resolved parameter objects,
and it is the **only** place that happens. Every module downstream takes values,
not a config — so "no tunable is hardcoded" is a property of one file rather
than a habit spread over ten.

Order matters. :func:`preflight` runs before any work, so a run with unresolved
parameters fails with the whole list rather than after twenty minutes of
rendering. The book series are checked first, because whether they exist decides
which parameters the run genuinely needs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ah.gen.base import Ensemble
from ah.narration import ADAPTER_VERSION, NARRATION_VERSION
from ah.narration.adapters.world import WorldSeries, build_world_series
from ah.narration.anchor import AnchorParams
from ah.narration.config import VoicesConfig, load_voices, preflight
from ah.narration.constants import BOOK_CLASSES, RECORD_PRECISION
from ah.narration.errors import NarrationError
from ah.narration.events import ConsensusParams, Event, EventParams, detect
from ah.narration.params import PARAMETERS
from ah.narration.probe import PROBE_STATUS, RATIFIED_STATUS
from ah.narration.slate import Slate, SlateParams, build_slates
from ah.narration.voices import (
    ColumnistsParams,
    ColumnistsVoice,
    EconomistParams,
    EconomistVoice,
    FomcParams,
    FomcVoice,
    Newsroom,
    RenderedSlate,
    TemplateBank,
    filtered_r_star,
)

__all__ = [
    "BuildResult",
    "build_from_ensemble",
    "finalise_manifest",
    "load_world_ensemble",
]

_BANK_NAMES = ("events", "fomc", "columnists", "economist")

#: E08 at or above this severity counts as credit stress for the quarter, which
#: is what lets the Committee reach for its financial-conditions sentence. Not a
#: tunable: it is the top of the severity grammar minus the top band, i.e. "the
#: paper called it serious", and it moves with severity.cuts rather than
#: independently of them.
_CREDIT_STRESS_SEVERITY = 2


@dataclass(frozen=True)
class BuildResult:
    world: WorldSeries
    events: list[Event]
    slates: list[Slate]
    rendered: list[RenderedSlate]
    manifest: dict[str, Any]
    strain_log: list[dict[str, Any]]
    columnist_calls: list[dict[str, Any]]
    config: VoicesConfig
    event_params: EventParams
    slate_params: SlateParams


# --------------------------------------------------------------------------- #
# config -> resolved parameters
# --------------------------------------------------------------------------- #


def adapter_params(config: VoicesConfig) -> dict[str, Any]:
    return {
        "cpi_yoy_warmup": config.get("adapter.cpi_yoy_warmup"),
        "headline_cpi": config.get("derived_observables.headline_cpi.params"),
        "unemployment": config.get("derived_observables.unemployment.params"),
        "payrolls_change": config.get("derived_observables.payrolls_change.params"),
        "growth_print": config.get("derived_observables.growth_print.params"),
    }


def event_params(config: VoicesConfig, *, book_available: bool) -> EventParams:
    classes = [cls for cls in config.event_classes() if book_available or cls not in BOOK_CLASSES]
    thresholds: dict[str, Any] = {}
    for cls in classes:
        if cls == "E10":
            continue
        if config.raw["events"][cls].get("threshold") is None:
            continue
        thresholds[cls] = config.get(f"events.{cls}.threshold")
    return EventParams(
        cuts=tuple(config.get("severity.cuts")),  # pyright: ignore[reportArgumentType]
        class_scale=dict(config.get("severity.class_scale")),
        hard_overrides=dict(config.raw["severity"]["hard_overrides"]),
        z_window_months=int(config.get("severity.z_window_months")),
        thresholds=thresholds,
        milestones=tuple(config.get("events.E10.milestones")),
        meeting_months=tuple(config.get("voices.fomc.meeting_months")),
        anchor=AnchorParams(
            rho=float(config.get("voices.fomc.anchor.rho")),
            quantise_bp=float(config.get("voices.fomc.anchor.quantise_bp")),
            phi_pi=float(config.get("voices.fomc.anchor.phi_pi")),
            phi_c=float(config.get("voices.fomc.anchor.phi_c")),
            cycle_source=str(config.get("voices.fomc.anchor.cycle_source")),
        ),
        consensus=ConsensusParams(
            persistence_weight=float(config.get("consensus.persistence_weight")),
            bias=float(config.get("consensus.bias")),
            dispersion=float(config.get("consensus.dispersion")),
            n_forecasters=int(config.get("consensus.n_forecasters")),
        ),
        book_available=book_available,
    )


def slate_params(config: VoicesConfig, *, book_available: bool) -> SlateParams:
    return SlateParams(
        contest_rule=str(config.get("slate.contest_rule")),
        tie_break=str(config.get("slate.tie_break")),
        min_slots=int(config.get("slate.min_slots")),
        capital_drop_rule=(str(config.get("slate.capital_drop_rule")) if book_available else None),
        special_edition_severity=int(config.raw["slate"]["special_edition_severity"]),
        capital_absent_message=str(config.raw["slate"]["capital_absent_message"]),
        book_available=book_available,
    )


def _banks() -> dict[str, TemplateBank]:
    return {name: TemplateBank.load(name) for name in _BANK_NAMES}


def _bank_hashes() -> dict[str, str]:
    from ah.narration.voices.base import TEMPLATES_DIR

    out: dict[str, str] = {}
    for name in _BANK_NAMES:
        text = (TEMPLATES_DIR / f"{name}.yaml").read_bytes()
        out[name] = hashlib.sha256(text).hexdigest()
    return out


def _newsroom(config: VoicesConfig, banks: dict[str, TemplateBank], *, world_id: str, seed: int):
    fomc = FomcVoice(
        banks["fomc"],
        banks["events"],
        FomcParams(
            backend=str(config.raw["voices"]["fomc"]["backend"]),
            committee_size=int(config.get("voices.fomc.dissent.committee_size")),
            prior_spread=float(config.get("voices.fomc.dissent.prior_spread")),
            dissent_threshold=float(config.get("voices.fomc.dissent.threshold")),
            may_not_speak_to=tuple(
                config.raw["voices"]["fomc"]["mandate_boundary"]["may_not_speak_to"]
            ),
            base_seed=seed,
        ),
    )
    columnists = ColumnistsVoice(
        banks["columnists"],
        ColumnistsParams(
            backend=str(config.raw["voices"]["columnists"]["backend"]),
            count=int(config.get("voices.columnists.count")),
            consensus_lag_months=int(config.get("voices.columnists.consensus_lag_months")),
            dispersion_model=str(config.get("voices.columnists.dispersion")),
            hit_rate_target=tuple(config.get("voices.columnists.hit_rate_target")),
            outlier_backend=str(config.raw["voices"]["columnists"]["outlier_backend"]),
        ),
    )
    economist = EconomistVoice(
        banks["economist"],
        EconomistParams(
            backend=str(config.raw["voices"]["economist"]["backend"]),
            name=str(config.raw["voices"]["economist"]["name"]),
            stickiness_meetings=int(config.get("voices.economist.stickiness_meetings")),
            confidence_start=float(config.get("voices.economist.confidence_start")),
            confidence_decay=float(
                config.get("voices.economist.confidence_decay_per_contradiction")
            ),
            capitulation_floor=float(config.get("voices.economist.capitulation_floor")),
            risk_book_size=int(config.get("voices.economist.risk_book_size")),
            risk_materialisation_rate=float(
                config.get("voices.economist.risk_materialisation_rate")
            ),
            filtered_state=str(config.get("voices.economist.filtered_state")),
            strain_weights=dict(config.get("voices.economist.strain_weights")),
        ),
    )
    return Newsroom(
        events_bank=banks["events"],
        fomc=fomc,
        columnists=columnists,
        economist=economist,
        cross_firing=dict(config.get("style.vocabulary_cross_firing")),
        layout_states=dict(config.get("style.layout_states")),
        world_id=world_id,
    )


# --------------------------------------------------------------------------- #
# the build
# --------------------------------------------------------------------------- #


def load_world_ensemble(spec_path: str | Path, *, n_paths: int = 1) -> tuple[Any, Ensemble]:
    """Compile a preset and sample it. Needs the generator's pinned checkpoint.

    Kept out of :func:`build_from_ensemble` deliberately: the checkpoint is a
    gitignored campaign-2 artifact, so every committed test builds its ensemble
    in-test and only the local real-world run comes through here.
    """
    import ah.gen.blocks.flow  # noqa: F401  (registers hier-flow-v1)
    from ah.core.loader import load_worldspec
    from ah.core.numericworld import project_numeric
    from ah.gen import registry

    document = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    spec = load_worldspec(document)
    numeric = project_numeric(spec)
    generator = registry.resolve(numeric.engine_defaults.generator_id)
    seed = numeric.engine_defaults.base_seed
    if seed is None:
        raise NarrationError(
            f"{spec_path} declares no engine_defaults.base_seed; the workbench narrates one "
            "named path and will not invent a seed for it."
        )
    ensemble = generator.sample(numeric, n_paths, int(seed))
    return numeric, ensemble


def build_from_ensemble(
    ensemble: Ensemble,
    *,
    config: VoicesConfig,
    world_id: str,
    path_index: int = 0,
) -> BuildResult:
    """Everything from a sampled ensemble to a rendered decade, in memory."""
    book_available = False  # decided by the adapter below; needed before preflight
    probe_keys = config.raw.get("probe_filled_keys", [])
    status = str(config.raw.get("config_status", RATIFIED_STATUS))
    preflight(config, book_available=book_available)

    world = build_world_series(ensemble, path_index=path_index, params=adapter_params(config))
    if world.book_available != book_available:
        raise NarrationError(
            "the adapter found book series after the pre-flight ran without them; re-run "
            "pre-flight with book_available=True"
        )

    e_params = event_params(config, book_available=world.book_available)
    events = detect(world, e_params)
    s_params = slate_params(config, book_available=world.book_available)
    slates = build_slates(events, s_params, months=world.months)

    banks = _banks()
    newsroom = _newsroom(config, banks, world_id=world_id, seed=int(ensemble.meta.seed))

    severity_by_month: dict[int, int] = {}
    for event in events:
        severity_by_month[event.month] = max(severity_by_month.get(event.month, 0), event.severity)
    credit_stress = {
        event.month
        for event in events
        if event.cls == "E08" and event.severity >= _CREDIT_STRESS_SEVERITY
    }
    r_star_hat = filtered_r_star(
        world.series["policy_rate"],
        world.series["cpi_yoy"],
        str(config.get("voices.economist.filtered_state")),
    )
    rendered = newsroom.render(
        slates,
        regime=world.regime,
        severity_by_month=severity_by_month,
        r_star_hat=r_star_hat,
        unemployment=world.series["unemployment"],
        credit_stress_months=credit_stress,
    )

    calls: list[dict[str, Any]] = []
    for slate in rendered:
        for item in slate.items:
            for artifact in item.voices:
                calls.extend(artifact.extras.get("calls", []))

    manifest = {
        "world_id": world_id,
        "narration_version": NARRATION_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "generator": {
            "generator_id": ensemble.meta.generator_id,
            "vintage_id": ensemble.meta.vintage_id,
            "seed": int(ensemble.meta.seed),
            "checkpoint_hash": ensemble.meta.checkpoint_hash,
            "months": int(ensemble.months),
            "path_index": path_index,
        },
        "voices": {
            "path": str(config.path),
            "version": config.raw.get("version"),
            "hash": config.hash(),
            "config_status": status,
            "probe_filled_keys": list(probe_keys),
        },
        "templates": _bank_hashes(),
        "template_status": {name: bank.status for name, bank in banks.items()},
        "adapter": {
            "mapping_notes": list(world.mapping_notes),
            "warmup_months": world.warmup_months,
            "extras": list(world.extras),
            "optional_series_absent": list(world.absent_optional),
            "capital_slot": "omitted" if not world.book_available else "present",
        },
        "derived_observable_register": [dict(entry) for entry in world.derived_register],
        "unresolved": {
            "open_parameters_total": len(PARAMETERS),
            "still_unresolved_in_config": len(config.unresolved_keys()),
            "resolved_by_probe": len(probe_keys),
            "document": "src/ah/narration/UNRESOLVED.md",
        },
        "counts": {
            "events": len(events),
            "slates": len(slates),
            "announcements": sum(len(s.announcements) for s in slates),
            "severity_3": sum(1 for e in events if e.severity == 3),
        },
    }
    if status == PROBE_STATUS:
        manifest["WARNING"] = (
            "This build ran against a PROBE config. Every value it used for an open parameter "
            "is candidates[0] from UNRESOLVED.md, chosen by a mechanical rule and RATIFIED BY "
            "NOBODY. The numbers below measure the workbench, not a decision."
        )

    return BuildResult(
        world=world,
        events=events,
        slates=slates,
        rendered=rendered,
        manifest=manifest,
        strain_log=list(newsroom.economist.strain_log),
        columnist_calls=calls,
        config=config,
        event_params=e_params,
        slate_params=s_params,
    )


def finalise_manifest(
    manifest: dict[str, Any], config: VoicesConfig, panels: dict[str, Any]
) -> dict[str, Any]:
    """Attach the diagnostics and EVERY RESOLVED VALUE THE BUILD ACTUALLY READ.

    The resolved block is what makes ``compare`` able to name the parameter that
    changed rather than only the hash that moved. It is the config's own record
    of what was consumed, so a key nothing read never appears -- which is itself
    informative when a parameter turns out to be dead.
    """
    out = dict(manifest)
    out["voices"] = {**out["voices"], "resolved": dict(sorted(config.reads.items()))}
    out["diagnostics"] = panels
    return out


def write_events_jsonl(events: list[Event], path: Path) -> None:
    """One JSON object per line, sorted, with stable key order and no timestamps."""
    lines = [
        json.dumps(event.as_record(), sort_keys=True, separators=(",", ":")) for event in events
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=_json_safe) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        return round(float(value), RECORD_PRECISION)
    if isinstance(value, (np.integer, int)):
        return int(value)
    raise TypeError(f"{type(value)!r} is not JSON-serialisable")


def load_config(path: str | Path) -> VoicesConfig:
    return load_voices(path)
