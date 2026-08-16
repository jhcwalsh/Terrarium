"""Run the CI gate and bind its log to the commit it actually tested
(housekeeping-02).

``scripts/check_gate.py`` verifies a gate log and stamps ``.gate-ok``; the
committed ``githooks/commit-msg`` hook then refuses a merge into main unless that stamp
matches the commit being merged. That chain had a missing link. The hook
compared the stamp to ``MERGE_HEAD`` (sound), but ``check_gate.py`` minted the
stamp from ``git rev-parse HEAD`` at stamp time -- ambient state, with nothing
tying it to what the log had tested. So *stamp -> merged commit* was verified
and *log -> commit* never was.

The incident, 2026-08-15: a gate ran green against ``f498f0f``; the owner
merged another branch into the working branch while it ran; HEAD became
``8d68b7a``. Stamping would have certified ``8d68b7a`` on a log that never saw
it, the hook would have matched stamp to MERGE_HEAD and passed, and a 96-line
preset plus 15 lines of never-executed tests would have reached main under a
green banner. Caught by comparing HEAD by hand, which is exactly the kind of
vigilance a mechanical guard is supposed to retire.

This script closes it by making the log self-describing. It records the sha
**before** pytest starts, so a HEAD that moves mid-run leaves the log naming
the commit it really tested, and ``check_gate.py`` refuses the mismatch.

Usage:

    uv run python scripts/run_gate.py gate-<wp>.log
    uv run python scripts/check_gate.py gate-<wp>.log
    git checkout main && git merge --no-ff <branch>

Refuses to start when tracked files are modified: the sha would name a commit
that is not what ran. Untracked files are ignored -- they are not part of the
tested state.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

#: The CI gate, verbatim. Hardcoded so the gate cannot quietly drift from the
#: command CLAUDE.md documents -- a weaker gate that still says "EXIT: 0" is
#: the failure mode this whole guard exists to prevent.
GATE_ARGS = [
    "pytest",
    "--cov=ah.core",
    "--cov-report=term-missing",
    "--cov-fail-under=90",
]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def modified_tracked_files() -> list[str]:
    """Tracked files with staged or unstaged modifications.

    ``--untracked-files=no`` is the whole point: untracked files (scratch
    logs, unfiled drops) are not part of the state under test, but a modified
    tracked file means the recorded sha describes something other than what
    ran.
    """
    out = _git("status", "--porcelain", "--untracked-files=no")
    return [line[3:] for line in out.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: run_gate.py <gate-log>")
        return 2
    log = Path(argv[1])

    dirty = modified_tracked_files()
    if dirty:
        print("REFUSED: tracked files are modified; the gate would certify a")
        print("commit that is not what ran. Commit or stash first:")
        for path in dirty[:10]:
            print(f"  {path}")
        if len(dirty) > 10:
            print(f"  ... and {len(dirty) - 10} more")
        return 1

    head = _git("rev-parse", "HEAD")
    print(f"gate starting against {head[:12]} -> {log}")

    with log.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"GATE-COMMIT: {head}\n")
        handle.write("GATE-DIRTY: 0\n")
        handle.flush()
        completed = subprocess.run(
            ["uv", "run", *GATE_ARGS], stdout=handle, stderr=subprocess.STDOUT
        )
        handle.write(f"EXIT: {completed.returncode}\n")

    print(f"gate finished, EXIT: {completed.returncode}")
    print(f"next: uv run python scripts/check_gate.py {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
