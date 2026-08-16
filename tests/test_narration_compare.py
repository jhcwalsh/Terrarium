"""Acceptance 10: ``compare`` reports the changed value and its downstream effects.

The tweak loop is the deliverable, and ``compare`` is the half of it that says
what a change *did*. A diff that only reported "the hash moved" would be useless;
one that reported every byte of two HTML files would be unreadable. It reports
the config keys that differ and the manifest/diagnostics numbers that moved.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ah.narration.cli import run_compare
from test_narration_build import PROBE, _ensemble, _write_run


def test_compare_names_the_changed_value_and_what_it_moved(tmp_path: Path, capsys):
    document = yaml.safe_load(PROBE.read_text(encoding="utf-8"))
    document["severity"]["cuts"] = [1.25, 2.25, 3.25]
    tweaked = tmp_path / "tweaked.yaml"
    tweaked.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")

    left, right = tmp_path / "a", tmp_path / "b"
    _write_run(left, _ensemble(), PROBE)
    _write_run(right, _ensemble(), tweaked)

    assert run_compare(str(left), str(right)) == 0
    out = capsys.readouterr().out
    assert "CONFIG DIFFERENCES" in out
    assert "voices.hash" in out
    # the CHANGED VALUE itself is named, not merely the hash that moved
    assert "voices.resolved.severity.cuts" in out
    assert "DOWNSTREAM EFFECTS" in out
    # the severity cut-points move the severity-3 count, which is the number the
    # calibration panel is judged against
    assert "counts.severity_3" in out
    assert "diagnostics.severity.severity_3_count" in out


def test_compare_on_two_identical_runs_reports_nothing(tmp_path: Path, capsys):
    left, right = tmp_path / "a", tmp_path / "b"
    _write_run(left, _ensemble(), PROBE)
    _write_run(right, _ensemble(), PROBE)
    run_compare(str(left), str(right))
    assert "the two runs are identical" in capsys.readouterr().out
