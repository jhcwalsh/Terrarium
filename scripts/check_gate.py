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

Usage, on the branch, after the gate:

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


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_gate.py <gate-log>")
        return 2
    log = Path(argv[1])
    if not log.exists():
        print(f"REFUSED: {log} does not exist")
        return 1
    ok, reason = validate_log(log.read_text(encoding="utf-8", errors="replace"))
    if not ok:
        print(f"REFUSED: {reason}")
        return 1
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    Path(".gate-ok").write_text(head + "\n", encoding="utf-8")
    print(f"GATE OK ({reason}) - .gate-ok stamped for {head[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
