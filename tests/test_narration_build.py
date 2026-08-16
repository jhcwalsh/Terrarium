"""End to end: the four files, determinism, and the two ways a run must fail.

Everything is synthetic. The workbench's real world needs a gitignored
campaign-2 checkpoint, so the committed suite builds its own ensemble and the
real-world run happens once, locally, and is reported.

Acceptance items 1-5 and 7-8 of the task live here; item 6 is
``test_narration_no_hardcoded_tunables.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from ah.gen.base import AbsentLayer, Ensemble, EnsembleMeta, RegimeRecord, SlowStateRecord
from ah.narration.build import (
    build_from_ensemble,
    finalise_manifest,
    load_config,
    write_events_jsonl,
    write_manifest,
)
from ah.narration.config import load_voices
from ah.narration.constants import L1_STATE_NAMES
from ah.narration.diagnostics import compute
from ah.narration.errors import MissingSeriesError, UnresolvedParameter
from ah.narration.events import uncovered_classes
from ah.narration.probe import PROBE_STATUS, render_probe_yaml
from ah.narration.render import render_diagnostics, render_slates
from ah.narration.voices.base import LlmBackend

REPO = Path(__file__).resolve().parents[1]
VOICES = REPO / "voices.yaml"
PROBE = REPO / "configs" / "voices-probe-unratified.yaml"

FACTORS = ["cpi", "equity_mkt", "equity_vol", "hy_spread", "policy_rate", "ust_10y", "ust_2y"]
MONTHS = 120
LEGEND = ("EXP", "SLOW", "REC", "CRI", "STAG", "REF")
WORLD_ID = "00000000-0000-4000-9000-0000000009ff"


def _ensemble(*, factors: list[str] | None = None, slow: object | None = None) -> Ensemble:
    """A synthetic world with a real shape: a run-up, a crisis, a recovery."""
    names = FACTORS if factors is None else factors
    rng = np.random.Generator(np.random.PCG64(9001))
    regime_codes = np.array([0] * 40 + [1] * 12 + [3] * 8 + [1] * 30 + [5] * 30, dtype=np.int64)
    drift = {0: 0.008, 1: 0.001, 3: -0.035, 5: 0.010}
    vol = {0: 0.030, 1: 0.038, 3: 0.080, 5: 0.034}
    paths = np.zeros((1, MONTHS, len(names)), dtype=np.float64)
    cpi = 1.0
    policy = 6.0
    for month in range(MONTHS):
        code = int(regime_codes[month])
        cpi *= 1.0 + 0.005 + rng.normal(0.0, 0.002)
        policy += rng.normal(0.02 if code in (0, 5) else -0.05, 0.12)
        for index, name in enumerate(names):
            if name == "cpi":
                paths[0, month, index] = cpi
            elif name == "equity_mkt":
                paths[0, month, index] = drift[code] + rng.normal(0.0, vol[code])
            elif name == "equity_vol":
                paths[0, month, index] = 14.0 + 30.0 * vol[code] + rng.normal(0.0, 2.0)
            elif name == "hy_spread":
                paths[0, month, index] = (
                    3.2 + (5.0 if code == 3 else 0.0) + abs(rng.normal(0.0, 0.4))
                )
            elif name == "policy_rate":
                paths[0, month, index] = max(0.0, policy)
            elif name == "ust_10y":
                paths[0, month, index] = max(0.0, policy + 0.9 + rng.normal(0.0, 0.15))
            else:
                paths[0, month, index] = max(0.0, policy + 0.2 + rng.normal(0.0, 0.20))
    states = np.zeros((1, MONTHS, len(L1_STATE_NAMES)), dtype=np.float64)
    states[0, :, 0] = 5.5 + rng.normal(0.0, 0.3, MONTHS)
    states[0, :, 1] = 1.2 + rng.normal(0.0, 0.2, MONTHS)
    states[0, :, 2] = 2.4 + rng.normal(0.0, 0.4, MONTHS)
    states[0, :, 3] = 0.9 + rng.normal(0.0, 0.1, MONTHS)
    states[0, :, 4] = rng.normal(0.0, 0.6, MONTHS)
    slow_states = (
        SlowStateRecord(states=states, names=L1_STATE_NAMES, layer="simulated")
        if slow is None
        else slow
    )
    return Ensemble(
        paths=paths,
        factor_names=list(names),
        meta=EnsembleMeta(
            generator_id="synthetic-for-test",
            vintage_id="test-vintage",
            seed=9001,
            n_paths=1,
            months=MONTHS,
        ),
        regimes=RegimeRecord(
            labels=regime_codes.reshape(1, MONTHS),
            legend=LEGEND,
            mode="sequence",
            ruleset_version="test",
        ),
        slow_states=slow_states,  # pyright: ignore[reportArgumentType]
    )


def _write_run(out: Path, ensemble: Ensemble, config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    result = build_from_ensemble(ensemble, config=config, world_id=WORLD_ID)
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
    out.mkdir(parents=True, exist_ok=True)
    (out / "slates.html").write_text(
        render_slates(result.rendered, manifest), encoding="utf-8", newline="\n"
    )
    (out / "diagnostics.html").write_text(
        render_diagnostics(panels, manifest), encoding="utf-8", newline="\n"
    )
    write_events_jsonl(result.events, out / "events.jsonl")
    write_manifest(manifest, out / "manifest.json")
    return manifest


# --------------------------------------------------------------------------- #


def test_build_produces_the_four_output_files(tmp_path: Path):
    out = tmp_path / "run"
    _write_run(out, _ensemble(), PROBE)
    for name in ("slates.html", "diagnostics.html", "events.jsonl", "manifest.json"):
        assert (out / name).exists() and (out / name).stat().st_size > 0


def test_identical_world_and_config_give_byte_identical_output(tmp_path: Path):
    """Acceptance 2. Tested, not asserted."""
    first, second = tmp_path / "a", tmp_path / "b"
    _write_run(first, _ensemble(), PROBE)
    _write_run(second, _ensemble(), PROBE)
    for name in ("slates.html", "events.jsonl"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()


def test_output_is_identical_across_PROCESSES_not_just_within_one(tmp_path: Path):
    """The in-process determinism test above passed while the build was NOT
    deterministic, and this is the test that caught it.

    ``Counter.most_common`` breaks ties by insertion order; insertion order in
    the vocabulary panel came from iterating a ``set`` of tokens, whose order
    depends on the interpreter's hash seed. Two runs in one pytest process share
    a seed, so they agreed; two runs of the CLI did not, and
    ``diagnostics.html`` and ``manifest.json`` differed between them. Fixed by
    ranking on ``(-count, key)``. Inverted and kept: it now fails if the defect
    returns.
    """
    here = str(Path(__file__).parent)
    script = (
        f"import sys; sys.path.insert(0, {here!r})\n"
        "from test_narration_build import _ensemble, _write_run, PROBE\n"
        "from pathlib import Path\n"
        "_write_run(Path(sys.argv[1]), _ensemble(), PROBE)\n"
    )
    outputs = []
    for index, seed in enumerate(("0", "1")):
        target = tmp_path / f"run{index}"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        subprocess.run(
            [sys.executable, "-c", script, str(target)],
            check=True,
            cwd=str(REPO),
            env=env,
        )
        outputs.append(target)
    for name in ("slates.html", "diagnostics.html", "events.jsonl", "manifest.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes(), name


def test_changing_one_config_value_changes_the_output_and_the_hash(tmp_path: Path):
    """Acceptance 3."""
    document = yaml.safe_load(PROBE.read_text(encoding="utf-8"))
    document["severity"]["cuts"] = [1.25, 2.25, 3.25]
    tweaked = tmp_path / "tweaked.yaml"
    tweaked.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")

    base, changed = tmp_path / "base", tmp_path / "changed"
    manifest_a = _write_run(base, _ensemble(), PROBE)
    manifest_b = _write_run(changed, _ensemble(), tweaked)
    assert manifest_a["voices"]["hash"] != manifest_b["voices"]["hash"]
    assert (base / "events.jsonl").read_bytes() != (changed / "events.jsonl").read_bytes()


def test_a_world_without_the_book_builds_and_states_the_omission(tmp_path: Path):
    """Acceptance 4. Omitted, never stubbed, and said out loud on the artifact."""
    out = tmp_path / "run"
    manifest = _write_run(out, _ensemble(), PROBE)
    assert manifest["adapter"]["capital_slot"] == "omitted"
    slates = (out / "slates.html").read_text(encoding="utf-8")
    assert "CAPITAL SLOT OMITTED" in slates
    events = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert not [e for e in events if e["slot"] == "CAPITAL"]


def test_a_world_missing_a_required_series_fails_naming_it(tmp_path: Path):
    """Acceptance 5."""
    without = [f for f in FACTORS if f != "hy_spread"]
    with pytest.raises(MissingSeriesError, match="hy_oas"):
        _write_run(tmp_path / "run", _ensemble(factors=without), PROBE)

    with pytest.raises(MissingSeriesError, match="l1_state"):
        _write_run(
            tmp_path / "run2",
            _ensemble(slow=AbsentLayer(reason="no climate layer here")),
            PROBE,
        )


def test_the_shipped_config_fails_the_run_with_the_unresolved_list(tmp_path: Path):
    """Acceptance 6, first half: a run does not proceed on a default."""
    with pytest.raises(UnresolvedParameter) as excinfo:
        _write_run(tmp_path / "run", _ensemble(), VOICES)
    message = str(excinfo.value)
    assert "severity.cuts" in message
    assert "UNRESOLVED.md" in message
    assert len(excinfo.value.keys) > 40


def test_every_announcement_in_events_jsonl_carries_panel_and_delta(tmp_path: Path):
    """Acceptance 8."""
    out = tmp_path / "run"
    _write_run(out, _ensemble(), PROBE)
    rows = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert rows
    for row in rows:
        assert row["panel"]
        assert row["delta"] and row["delta"]["label"]


def test_diagnostics_renders_nine_panels_with_the_severity_verdict(tmp_path: Path):
    """Acceptance 9."""
    out = tmp_path / "run"
    manifest = _write_run(out, _ensemble(), PROBE)
    panels = manifest["diagnostics"]
    assert set(panels) == {
        "severity",
        "slot_contest",
        "repetition",
        "vocabulary",
        "chips",
        "policy",
        "strain",
        "coverage",
        "columnists",
    }
    page = (out / "diagnostics.html").read_text(encoding="utf-8")
    for index in range(1, 10):
        assert f"<h2>{index} · " in page
    assert "severity-3 events this decade" in page
    assert "reversal frequency" in page.lower()


def test_the_probe_config_is_the_registry_rendered_and_is_labelled_unratified():
    """The probe is generated by rule and says so on every artifact it touches."""
    assert PROBE.read_text(encoding="utf-8") == render_probe_yaml(load_voices(VOICES))
    document = yaml.safe_load(PROBE.read_text(encoding="utf-8"))
    assert document["config_status"] == PROBE_STATUS


def test_a_probe_build_stamps_the_warning_on_the_manifest_and_both_pages(tmp_path: Path):
    out = tmp_path / "run"
    manifest = _write_run(out, _ensemble(), PROBE)
    assert manifest["voices"]["config_status"] == PROBE_STATUS
    assert "RATIFIED BY NOBODY" in manifest["WARNING"]
    for name in ("slates.html", "diagnostics.html"):
        assert "PROBE BUILD" in (out / name).read_text(encoding="utf-8")


def test_the_llm_backend_is_an_interface_that_raises():
    """A task non-goal, stated as code rather than as a comment."""
    with pytest.raises(NotImplementedError, match="llm backend"):
        LlmBackend("ferrers").render(None, {})  # pyright: ignore[reportArgumentType]


def test_the_manifest_stamps_everything_a_rerun_would_need(tmp_path: Path):
    manifest = _write_run(tmp_path / "run", _ensemble(), PROBE)
    assert manifest["world_id"] == WORLD_ID
    assert manifest["voices"]["hash"]
    assert set(manifest["templates"]) == {"events", "fomc", "columnists", "economist"}
    assert manifest["adapter_version"] and manifest["narration_version"]
    names = {entry["name"] for entry in manifest["derived_observable_register"]}
    assert names == {"unemployment", "payrolls_change", "headline_cpi", "growth_print"}
    assert manifest["unresolved"]["open_parameters_total"] > 0
