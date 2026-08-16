"""housekeeping-01/-02: the gate-merge guard's log validation and its binding
to the commit under test.

The real incidents are the test cases: a failing gate piped through tail
merged to main (EXIT: 1 with 2 failed); a wrong-directory chain produced a log
containing nothing but EXIT: 128; and (housekeeping-02) a green log stamped
against a HEAD that had moved under the running gate.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_gate", _ROOT / "scripts" / "check_gate.py")
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_log = _mod.validate_log
validate_binding = _mod.validate_binding

_SHA_A = "f498f0f" + "0" * 33
_SHA_B = "8d68b7a" + "0" * 33


def _bound_log(sha: str = _SHA_A, dirty: int = 0, body: str = "2664 passed\nEXIT: 0\n") -> str:
    return f"GATE-COMMIT: {sha}\nGATE-DIRTY: {dirty}\n{body}"


def test_a_green_log_passes():
    ok, reason = validate_log("..........\n2496 passed in 1765.33s (0:29:25)\nEXIT: 0\n")
    assert ok and "2496 passed" in reason


def test_the_red_gate_incident_is_refused():
    """2026-08-12 morning: 2 failed, EXIT: 1 - merged anyway via tail's
    exit 0. The guard says no."""
    ok, reason = validate_log("FAILED tests/x.py::t\n2 failed, 2470 passed in 1743.47s\nEXIT: 1\n")
    assert not ok and "EXIT: 1" in reason


def test_the_empty_128_incident_is_refused():
    """2026-08-12 evening: the chain died at the door; the log held only
    the exit line. Nothing ran - nothing may merge."""
    ok, _reason = validate_log("EXIT: 128\n")
    assert not ok


def test_a_log_with_failures_but_exit_zero_is_refused():
    """Belt and suspenders: even a lying exit code cannot pass failures."""
    ok, _ = validate_log("1 failed, 10 passed\nEXIT: 0\n")
    assert not ok


def test_a_log_with_no_pass_count_is_refused():
    ok, _reason = validate_log("no tests ran\nEXIT: 0\n")
    assert not ok


def test_a_bound_log_matching_head_passes():
    ok, detail = validate_binding(_bound_log(), head=_SHA_A)
    assert ok and detail == _SHA_A


def test_the_moved_head_incident_is_refused():
    """2026-08-15: the gate ran green against f498f0f; another branch was
    merged into the working branch mid-run and HEAD became 8d68b7a. The old
    code stamped rev-parse HEAD, so it certified a commit the log had never
    seen, and the hook - comparing stamp to MERGE_HEAD - agreed. Two
    never-executed tests would have reached main under a green banner."""
    ok, reason = validate_binding(_bound_log(sha=_SHA_A), head=_SHA_B)
    assert not ok
    assert "f498f0f" in reason and "8d68b7a" in reason
    assert "moved under the run" in reason


def test_an_unbound_log_is_refused():
    """A log with no GATE-COMMIT ties itself to nothing. Every gate log
    written before housekeeping-02 is in this class, deliberately: they
    cannot prove what they tested, so they cannot authorise a merge."""
    ok, reason = validate_binding("2664 passed\nEXIT: 0\n", head=_SHA_A)
    assert not ok and "no GATE-COMMIT" in reason


def test_a_dirty_tree_log_is_refused():
    """Modified tracked files mean the recorded sha names a commit that is
    not what ran. Untracked files are not counted - run_gate.py passes
    --untracked-files=no - so scratch files never block a merge."""
    ok, reason = validate_binding(_bound_log(dirty=3), head=_SHA_A)
    assert not ok and "3 tracked file(s) were modified" in reason


def test_a_log_missing_the_dirty_line_is_refused():
    """Absence is not cleanliness: a log that does not say whether the tree
    was clean cannot be treated as though it did."""
    ok, reason = validate_binding(f"GATE-COMMIT: {_SHA_A}\n2664 passed\nEXIT: 0\n", head=_SHA_A)
    assert not ok and "GATE-DIRTY" in reason


def test_run_gate_ignores_untracked_but_not_modified_files():
    """The two halves of the ruling, read off the source: tracked
    modifications are the refusal, untracked files are excluded from it."""
    text = (_ROOT / "scripts" / "run_gate.py").read_text(encoding="utf-8")
    assert "--untracked-files=no" in text
    assert "GATE-COMMIT" in text and "GATE-DIRTY" in text


def test_the_gate_command_cannot_quietly_weaken():
    """run_gate.py hardcodes the gate; a lowered --cov-fail-under or a
    dropped flag would still print EXIT: 0, which is the whole failure mode."""
    assert _mod is not None
    gate_spec = importlib.util.spec_from_file_location(
        "run_gate", _ROOT / "scripts" / "run_gate.py"
    )
    assert gate_spec is not None and gate_spec.loader is not None
    run_gate = importlib.util.module_from_spec(gate_spec)
    gate_spec.loader.exec_module(run_gate)
    assert run_gate.GATE_ARGS == [
        "pytest",
        "--cov=ah.core",
        "--cov-report=term-missing",
        "--cov-fail-under=90",
    ]


def test_the_hook_exists_and_guards_main_merges():
    """The committed hook must check MERGE_HEAD against .gate-ok on main."""
    hook = Path(__file__).resolve().parents[1] / "githooks" / "pre-commit"
    text = hook.read_text(encoding="utf-8")
    assert "MERGE_HEAD" in text
    assert ".gate-ok" in text
    assert "REFUSED" in text
