"""The gate-merge guard's key-cutter (housekeeping-01).

Validates a gate log (full-suite pytest output ending in an ``EXIT: N``
line) and, when it is genuinely green, stamps ``.gate-ok`` with the current
HEAD sha. The committed pre-commit hook (``githooks/pre-commit``) refuses a
merge into main unless ``.gate-ok`` matches the branch being merged — one
guard, two incidents behind it:

* 2026-08-12 morning: ``tail gate.log && git merge`` — tail exits 0
  whatever the log SAYS, so a failing gate (EXIT: 1, 2 failed) merged and
  pushed to main.
* 2026-08-12 evening: a chained commit ran from the wrong directory and
  produced a log containing nothing but ``EXIT: 128`` — no tests ran at all.
* 2026-08-15: a gate ran green against ``f498f0f``; another branch was merged
  into the working branch mid-run; HEAD became ``8d68b7a``. This script
  stamped from ``git rev-parse HEAD``, so it would have certified ``8d68b7a``
  on a log that never saw it — and the hook, comparing stamp to MERGE_HEAD,
  would have agreed. The chain verified *stamp → merged commit* and never
  *log → commit*. Closed by housekeeping-02: the log now carries the sha it
  ran against (``scripts/run_gate.py`` writes it BEFORE pytest starts), this
  script refuses any log whose sha is missing or is not HEAD, and ``.gate-ok``
  is stamped **from the log** rather than from ambient state.

Usage, on the branch:

    uv run python scripts/run_gate.py gate-<wp>.log     # writes GATE-COMMIT
    uv run python scripts/check_gate.py gate-<wp>.log
    git checkout main && git merge --no-ff <branch> ...   # hook verifies

One-shot: the hook consumes ``.gate-ok`` on a successful merge.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def validate_log(text: str) -> tuple[bool, str]:
    """(ok, reason). Green means: EXIT: 0, a positive pass count, no fails."""
    exits = re.findall(r"^EXIT: (\d+)\s*$", text, flags=re.MULTILINE)
    if not exits:
        return False, "no EXIT line - the gate never finished (or never ran)"
    if exits[-1] != "0":
        return False, f"EXIT: {exits[-1]} - the gate did not pass"
    summary = re.search(r"(\d+) passed", text)
    if not summary or int(summary.group(1)) == 0:
        return False, "no positive pass count - nothing was actually tested"
    failed = re.search(r"(\d+) failed", text)
    if failed and int(failed.group(1)) > 0:
        return False, f"{failed.group(1)} failed - the gate did not pass"
    return True, f"{summary.group(1)} passed, EXIT: 0"


def log_commit(text: str) -> str | None:
    """The sha the gate ran against, or None if the log does not carry one."""
    match = re.search(r"^GATE-COMMIT: ([0-9a-f]{40})\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else None


def log_dirty(text: str) -> int | None:
    """Tracked-file modifications recorded at gate start, or None if absent."""
    match = re.search(r"^GATE-DIRTY: (\d+)\s*$", text, flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def validate_binding(text: str, head: str) -> tuple[bool, str]:
    """(ok, reason). Does this log describe the commit now at HEAD?

    Three ways to fail, in the order they matter. The log names no commit, so
    nothing ties it to any state of the tree. The log names a DIFFERENT commit
    from HEAD -- the 2026-08-15 incident, where HEAD moved under a running
    gate. Or the tree was dirty when it ran, so the sha names a commit that is
    not what was tested.
    """
    sha = log_commit(text)
    if sha is None:
        return False, (
            "no GATE-COMMIT line - the log is not bound to any commit. "
            "Re-run via: uv run python scripts/run_gate.py <gate-log>"
        )
    if sha != head:
        return False, (
            f"the gate tested {sha[:12]} but HEAD is {head[:12]} - the branch "
            f"moved under the run. Re-run the gate on the branch tip."
        )
    dirty = log_dirty(text)
    if dirty is None:
        return False, "no GATE-DIRTY line - cannot tell whether the tree was clean"
    if dirty != 0:
        return False, (
            f"{dirty} tracked file(s) were modified when the gate ran - "
            f"{sha[:12]} does not describe what was tested"
        )
    return True, sha


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_gate.py <gate-log>")
        return 2
    log = Path(argv[1])
    if not log.exists():
        print(f"REFUSED: {log} does not exist")
        return 1
    text = log.read_text(encoding="utf-8", errors="replace")
    ok, reason = validate_log(text)
    if not ok:
        print(f"REFUSED: {reason}")
        return 1
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    bound, detail = validate_binding(text, head)
    if not bound:
        print(f"REFUSED: {detail}")
        return 1
    # Stamped from the LOG's sha, not from rev-parse: the stamp derives from
    # the evidence. validate_binding has already proved the two agree.
    Path(".gate-ok").write_text(detail + "\n", encoding="utf-8")
    print(f"GATE OK ({reason}) - .gate-ok stamped for {detail[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
