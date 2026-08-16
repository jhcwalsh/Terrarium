"""housekeeping-01/-02: the gate-merge guard's log validation and its binding
to the commit under test.

The real incidents are the test cases: a failing gate piped through tail
merged to main (EXIT: 1 with 2 failed); a wrong-directory chain produced a log
containing nothing but EXIT: 128; and (housekeeping-02) a green log stamped
against a HEAD that had moved under the running gate.
"""

from __future__ import annotations

import importlib.util
import subprocess
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
    """The committed hook must check MERGE_HEAD against .gate-ok on main.

    INVERTED (housekeeping-03) and kept, per the repo rule that a test which
    catches a defect is inverted rather than deleted. It used to read
    githooks/pre-commit and passed for three days while the guard never ran,
    because it asserted the file MENTIONED the right things rather than that
    the hook DID anything. It now reads the hook that actually fires, and the
    real proof is the merges run below. A grep over a hook is not a test of a
    hook.
    """
    hooks = Path(__file__).resolve().parents[1] / "githooks"
    text = (hooks / "commit-msg").read_text(encoding="utf-8")
    assert "MERGE_HEAD" in text
    assert ".gate-ok" in text
    assert "REFUSED" in text
    # and the guard must NOT be duplicated into pre-commit: on the conflicted
    # route both hooks run, and the first to see the stamp consumes it
    assert "REFUSED" not in (hooks / "pre-commit").read_text(encoding="utf-8")


# ------------------------------------------------- the hooks, actually run
#
# housekeeping-03. `git merge` fires pre-merge-commit, NOT pre-commit, and git
# does not fall back. From 2026-08-12 to 2026-08-15 only pre-commit existed,
# so the guard never blocked a merge into main - proven by running it, after
# three days of a grep-based test reporting green.


def test_the_hooks_are_committed_executable():
    """Git records the exec bit in the index, and a hook without it is
    SILENTLY skipped on Linux and macOS - the same guard-never-fires bug in a
    fresh clone. Windows ignores the bit and runs hooks anyway, which is why
    this could not be caught by using the repo here. Both hooks were committed
    100644 until housekeeping-03 noticed.
    """
    out = subprocess.run(
        ["git", "ls-files", "-s", "githooks/"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    modes = {line.split("\t")[1]: line.split()[0] for line in out.splitlines() if line.strip()}
    assert modes, "no hooks are tracked at all"
    for path, mode in modes.items():
        assert mode == "100755", f"{path} is committed {mode}; a non-executable hook never runs"


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway repo wired to THIS repository's real githooks directory."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check)

    run("init", "-q", "-b", "main", ".")
    run("config", "user.email", "gate@test")
    run("config", "user.name", "gate test")
    # the shipped hooks, by absolute path - the artifact under test
    run("config", "core.hooksPath", str(_ROOT / "githooks"))

    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-qm", "base", "--no-verify")
    run("checkout", "-qb", "feat")
    (repo / "g.txt").write_text("feat\n", encoding="utf-8")
    run("add", "g.txt")
    run("commit", "-qm", "feat", "--no-verify")
    run("checkout", "-q", "main")
    return repo


def _merge(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "merge", "--no-ff", "feat", "-m", "merge feat"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_merge_into_main_is_actually_refused_without_a_stamp(tmp_path: Path):
    """The test that was missing. Not "the hook file says REFUSED" - an actual
    merge into main, actually refused, by the actually-installed hooks."""
    repo = _scratch_repo(tmp_path)
    before = _head(repo)
    result = _merge(repo)
    assert result.returncode != 0, "the merge was allowed through with no gate stamp"
    assert "REFUSED" in result.stdout + result.stderr
    assert _head(repo) == before, "a merge commit was created despite the refusal"


def test_a_merge_into_main_is_refused_when_the_stamp_is_for_another_commit(tmp_path: Path):
    """The stamp binds ONE commit. A stamp for anything else is not a key."""
    repo = _scratch_repo(tmp_path)
    (repo / ".gate-ok").write_text("0" * 40 + "\n", encoding="utf-8")
    before = _head(repo)
    result = _merge(repo)
    assert result.returncode != 0
    assert "REFUSED" in result.stdout + result.stderr
    assert _head(repo) == before


def test_a_merge_into_main_succeeds_with_the_right_stamp_and_consumes_it(tmp_path: Path):
    """And the guard must not be merely obstructive: the correct stamp opens
    it exactly once, then is consumed so it cannot authorise a second merge."""
    repo = _scratch_repo(tmp_path)
    feat = subprocess.run(
        ["git", "rev-parse", "feat"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / ".gate-ok").write_text(feat + "\n", encoding="utf-8")
    before = _head(repo)

    result = _merge(repo)
    assert result.returncode == 0, f"the correct stamp was rejected: {result.stderr}"
    assert _head(repo) != before, "no merge commit was created"
    assert not (repo / ".gate-ok").exists(), "the stamp must be one-shot"


def test_an_ordinary_commit_on_main_is_not_blocked(tmp_path: Path):
    """The guard fires on merges into main, not on commits. commit-msg runs
    for every commit, so a guard written carelessly there would block the
    owner's direct commits to main - which happen routinely."""
    repo = _scratch_repo(tmp_path)
    (repo / "h.txt").write_text("direct\n", encoding="utf-8")
    subprocess.run(["git", "add", "h.txt"], cwd=repo, check=True, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", "a direct commit on main"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"an ordinary commit was blocked: {result.stderr}"


def test_the_conflicted_merge_route_is_guarded_too(tmp_path: Path):
    """The second route to a merge commit: the merge conflicts, git stops
    without committing, and `git commit` finishes it. MERGE_HEAD is still set,
    so the guard must apply there as well - and must not have been consumed by
    an earlier hook on the same commit."""
    repo = _scratch_repo(tmp_path)

    def run(*args: str, check: bool = True):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check)

    # make feat and main touch the same file so the merge cannot auto-resolve
    run("checkout", "-q", "feat")
    (repo / "f.txt").write_text("feat side\n", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-qm", "feat edits f", "--no-verify")
    run("checkout", "-q", "main")
    (repo / "f.txt").write_text("main side\n", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-qm", "main edits f", "--no-verify")

    conflicted = _merge(repo)
    assert conflicted.returncode != 0, "expected a conflict"
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    run("add", "f.txt")
    before = _head(repo)

    finish = run("commit", "-m", "finish the merge", check=False)
    assert finish.returncode != 0, "the conflicted route completed with no stamp"
    assert "REFUSED" in finish.stdout + finish.stderr
    assert _head(repo) == before
