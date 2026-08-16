"""Seal the spine02 bars (Task 12 -- spine-conditioned compiler pilot, round
two). This is the re-run's PRE-REGISTRATION: after this commit, only
measurement is allowed. COMMIT-ORDER: this commit lands BEFORE any Task-13
ensemble is drawn.

Writes docs/superpowers/specs/spine02-prereg.json:

- ``b2``, ``b3``, ``b4``: copied VERBATIM from the round-one seal
  (docs/superpowers/specs/spine-pilot-prereg.json). The Task-11 review left
  these three bars unchanged -- only B1, B5 and B6 were respecified -- so
  they are loaded from the round-one JSON and re-emitted as-is here, never
  hand-retyped (a hand-retype could silently drift a digit; loading the
  object is what "verbatim" means).
- ``b1_v2``, ``b5_v2``, ``b6_v2``: the Task-11-respecified v2 judge bars.
  See scripts/spine_pilot_report.py's judge_b1_v2 / judge_b5_v2 / judge_b6_v2
  for what each field is read for. Some fields are DOCUMENTATION ONLY: b1_v2's
  ``lag_months`` (the judge hardcodes the 0..2-month scan itself) and b5_v2's
  ``method`` / ``alpha`` / ``z`` / ``per_quadrant`` (the judge computes its
  own z via the same literal and does not read these back) are sealed for the
  record, matching round-one's own convention of sealing values a judge
  doesn't literally consume (e.g. round-one b5's ``min_cell_months``).
  b5_v2's ``panel_rates`` and ``zero_rate_convention`` are carried verbatim
  from round-one's ``b5`` block. b6_v2's ``panel_base_rate`` is computed here
  as an exact ``149 / 813`` float division (the panel's curve-inversion
  coverage, disclosed in round-one's ``b6.base_rate_disclosure``) rather than
  hand-typed.
- ``sensitivity_seeds``: carried verbatim from the round-one seal.
- ``round_one_record``: pointers back to the round-one seal file, its two
  distinct commits (the pre-registration commit and the measured-state
  commit -- see ``ROUND_ONE_PREREG_COMMIT``/``ROUND_ONE_MEASURED_STATE_COMMIT``
  below for why they differ), and its verdicts document, so this JSON is
  self-locating without forcing a reader back through git log.
- ``hashes``: over the CURRENT working tree. Unlike round-one's seal (which
  bound files as they stood AT its own sealed commit -- spine-02 has been
  editing this tree freely since Task 10, under its own authority, up to this
  point), this round's tree IS the sealed state: this seal is the commit at
  which that editing stops and only measurement is authorized.

Deterministic: no randomness is drawn, no network is touched, and no wall
clock is read -- ``sealed_at_utc`` is derived from git HEAD's own commit
metadata, same convention as scripts/spine_pilot_seal.py.

Run ONCE; commit the JSON in the SAME commit as this script and the tests
that check it, per CLAUDE.md's pre-registration invariant (thresholds and the
code that judges them are hashed together before any measurement run).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND_ONE_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine-pilot-prereg.json"
OUT_PATH = _REPO_ROOT / "docs" / "superpowers" / "specs" / "spine02-prereg.json"

#: Round one has TWO commits that matter, and they are not the same thing:
#: the pre-registration itself (the seal commit b97450a, completed by the
#: amendment commit c9bd036 -- see spine-pilot-prereg.json's own
#: sealed_at_utc "as of HEAD commit" note) versus the tree state the
#: round-one GATE actually certified and later measured against (233b70d,
#: spine-01's post-measurement gated tip). Sealing only one of the two under
#: a single generic "sealed_commit" key erases that distinction; both are
#: recorded here under names that say which is which.
ROUND_ONE_PREREG_COMMIT = "c9bd03621424becf24dcb603ac7ef725ff9a53ab"
ROUND_ONE_MEASURED_STATE_COMMIT = "233b70d30157e2e06e80e447f410c03afc5d1f68"
ROUND_ONE_VERDICTS_PATH = "docs/superpowers/specs/2026-08-15-spine-pilot-results.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    round_one = json.loads(ROUND_ONE_PATH.read_text(encoding="utf-8"))

    committer_date = _git("log", "-1", "--format=%cI")
    head_sha = _git("rev-parse", "HEAD")

    seal_script = Path(__file__)
    hashed_paths = {
        "src/ah/gen/spine.py": _REPO_ROOT / "src" / "ah" / "gen" / "spine.py",
        "src/ah/gen/stress.py": _REPO_ROOT / "src" / "ah" / "gen" / "stress.py",
        "src/ah/gen/bootstrap.py": _REPO_ROOT / "src" / "ah" / "gen" / "bootstrap.py",
        "src/ah/gen/regimes/semimarkov.py": (
            _REPO_ROOT / "src" / "ah" / "gen" / "regimes" / "semimarkov.py"
        ),
        "src/ah/gen/climate/model.py": (_REPO_ROOT / "src" / "ah" / "gen" / "climate" / "model.py"),
        "src/ah/gen/climate/simulate.py": (
            _REPO_ROOT / "src" / "ah" / "gen" / "climate" / "simulate.py"
        ),
        "scripts/spine_pilot_report.py": _REPO_ROOT / "scripts" / "spine_pilot_report.py",
        "scripts/spine_pilot_b3.py": _REPO_ROOT / "scripts" / "spine_pilot_b3.py",
        "src/ah/presets/spine_pilot.json": (
            _REPO_ROOT / "src" / "ah" / "presets" / "spine_pilot.json"
        ),
        "scripts/spine02_seal.py": seal_script,
    }

    sealed = {
        "sealed_at_utc": f"{committer_date} (as of HEAD commit {head_sha})",
        "b2": round_one["b2"],
        "b3": round_one["b3"],
        "b4": round_one["b4"],
        "b1_v2": {
            "min_sign_fraction": 0.90,
            "lag_months": [0, 2],
        },
        "b5_v2": {
            "panel_rates": round_one["b5"]["panel_rates"],
            "method": "aggregate-binomial-normal-approx-cc",
            "alpha": 0.05,
            "z": 1.959963984540054,
            "per_quadrant": "disclosure-only",
            "zero_rate_convention": round_one["b5"]["zero_rate_convention"],
        },
        "b6_v2": {
            "k_months": 12,
            "panel_base_rate": 149 / 813,
            "rel_tolerance": 0.5,
            "panel_conditional_onset_rate": 0.2214765100671141,
            "panel_unconditional_onset_rate": 0.07731305449936629,
            "conditioning": "per-decade quantile-matched to the panel inversion base rate",
        },
        "sensitivity_seeds": round_one["sensitivity_seeds"],
        "round_one_record": {
            "seal": "docs/superpowers/specs/spine-pilot-prereg.json",
            "prereg_commit": ROUND_ONE_PREREG_COMMIT,
            "measured_state_commit": ROUND_ONE_MEASURED_STATE_COMMIT,
            "verdicts": ROUND_ONE_VERDICTS_PATH,
        },
        "hashes": {rel: _sha256(p) for rel, p in hashed_paths.items()},
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(
        f"b6_v2.panel_base_rate = {sealed['b6_v2']['panel_base_rate']!r} "
        f"(149 / 813 = {149 / 813!r})"
    )
    print(f"b2/b3/b4 carried verbatim from {ROUND_ONE_PATH}")


if __name__ == "__main__":
    main()
