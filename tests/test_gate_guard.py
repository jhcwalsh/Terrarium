"""housekeeping-01: the gate-merge guard's log validation.

The two real incidents are the test cases: a failing gate piped through
tail merged to main (EXIT: 1 with 2 failed), and a wrong-directory chain
produced a log containing nothing but EXIT: 128.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_gate", _ROOT / "scripts" / "check_gate.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate_log = _mod.validate_log


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


def test_the_hook_exists_and_guards_main_merges():
    """The committed hook must check MERGE_HEAD against .gate-ok on main."""
    hook = Path(__file__).resolve().parents[1] / "githooks" / "pre-commit"
    text = hook.read_text(encoding="utf-8")
    assert "MERGE_HEAD" in text
    assert ".gate-ok" in text
    assert "REFUSED" in text
