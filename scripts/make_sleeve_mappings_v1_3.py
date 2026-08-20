"""Make sleeve-mappings v1.3 (AM-2026-08-19-001 -- D-ER16-1, chosen-realistic,
ruled 2026-08-19).

One row moves, and it moves to CHOSEN coefficients, not measured ones: the
generated plane's ``pm_buyout``

* ``loadings.equity_mkt``  0.8362 -> 1.2 -- DN-5's own buyout prior 1.1-1.3
  ("levered beta", Instructions/DN5-factor-sleeve-mapping.md), mid-range;
* ``alpha_quarterly``  0.019441 -> 0.007399 -- 3%/yr, the mid-range of the
  marks-free cashflow/PME literature's 2-4%/yr net buyout outperformance,
  expressed under the sealed convention (the adapter applies alpha/3 per
  month): 3 * (1.03**(1/12) - 1) = 0.00739881, rounded to the artifact's
  six-decimal style. COMPUTED below and asserted, never typed in;
* ``r2_train_val`` -> null with ``r2_note`` -- a chosen row has no fit R2
  (the v1.0 precedent for unusable cells, pm_direct_lending's r2_note form);
* a ``chosen:`` provenance block recording the ratification, the replaced
  measured values, both anchors, and the trigger.

Why: ER-16 (docs/engine-realism-register.md) + the Route-C measurement
(docs/superpowers/specs/2026-08-19-pe-desmooth-c-measurement.md). The
measured row was fitted on an appraisal index whose GFC was never recorded
(worst GFC quarter -15.01%); the state-dependent de-smoother deepens the
reconstructed GFC only -26% -> -29%, the refit beta does not rise, the alpha
rises, and the D-preview finds no asymmetry -- no internal refit is
supportable, so the owner ruled chosen coefficients with external anchors.

Everything else -- every other sleeve, every other field of the pm_buyout
row, every top-level block -- is byte-identical to sealed
``mappings/sleeve-mappings-v1.2.yaml``, which is opened read-only and never
written. This script imports NOTHING from the sealed estimator scripts
(their machinery is inside pre-registration-g3.lock); it needs none of it --
this is a declared override, not a fit. Three hard assertions guard the
output: (a) the alpha derivation/rounding, (b) a deep-diff of v1.3 vs v1.2
contains ONLY the declared changes, (c) v1.2's bytes are unchanged after the
run (and the yaml round-trip is byte-faithful, so "unchanged" means
byte-for-byte, not merely value-equal).

Deterministic: no RNG, no catalog, no network; ASCII console.

Usage:
  uv run python scripts/make_sleeve_mappings_v1_3.py
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
V12_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.2.yaml"
OUT_PATH = _REPO_ROOT / "mappings" / "sleeve-mappings-v1.3.yaml"

AMENDMENT_ID = "AM-2026-08-19-001"
RATIFICATION = "D-ER16-1"
RULING_DATE = "2026-08-19"

# The chosen values (D-ER16-1, owner-ratified 2026-08-19).
CHOSEN_EQUITY_MKT = 1.2
ALPHA_ANNUAL = 0.03
ALPHA_QUARTERLY = 0.007399  # asserted against the derivation below, never trusted

# The measured values being replaced (sealed v1.2's pm_buyout row) -- the
# script refuses if v1.2 does not carry exactly these, so a drifted input
# cannot be silently overridden.
REPLACED = {"alpha_quarterly": 0.019441, "equity_mkt": 0.8362}

R2_NOTE = "chosen coefficients (D-ER16-1); not a fit"

CHOSEN_BLOCK: dict[str, Any] = {
    "ratification": RATIFICATION,
    "date": RULING_DATE,
    "replaced": dict(REPLACED),
    "anchors": {
        "beta": "DN-5 buyout prior 1.1-1.3 ('levered beta', "
        "Instructions/DN5-factor-sleeve-mapping.md); 1.2 chosen mid-range",
        "alpha": "cashflow/PME literature places net buyout outperformance at "
        "roughly 2-4%/yr (marks-free evidence); 3%/yr chosen mid-range",
    },
    "trigger": "ER-16 + the Route-C measurement "
    "(2026-08-19-pe-desmooth-c-measurement.md): the measured row is fitted on "
    "an appraisal index whose GFC was never recorded; no internal refit is "
    "supportable.",
    "route_note": "route: sum-beta(4) retained; the application semantics "
    "(whole sum applied contemporaneously at monthly frequency by the "
    "adapter) are unchanged; 1.2 is the SUM the adapter applies.",
}

HEADER = (
    "# mappings/sleeve-mappings-v1.3.yaml - scripts/make_sleeve_mappings_v1_3.py\n"
    "# AM-2026-08-19-001 (D-ER16-1, chosen-realistic, ruled 2026-08-19):\n"
    "# pm_buyout moves to CHOSEN coefficients - equity_mkt 1.2 (DN-5\n"
    "# levered-beta prior 1.1-1.3, mid-range), alpha_quarterly 0.007399\n"
    "# (3%/yr under the sealed alpha/3-per-month convention); r2_train_val\n"
    "# null (a chosen row has no fit R2). Trigger: ER-16 + the Route-C\n"
    "# measurement (2026-08-19-pe-desmooth-c-measurement.md). Everything\n"
    "# else is byte-identical to sleeve-mappings-v1.2.yaml (read-only).\n"
)


def chosen_alpha_quarterly() -> float:
    """Assertion (a): the alpha is DERIVED, not invented.

    The sealed convention applies ``alpha_quarterly / 3`` per month, so an
    alpha_quarterly of x compounds to ``(1 + x/3)**12 - 1`` a year. For that
    to equal 3%/yr: ``x = 3 * (1.03**(1/12) - 1) = 0.00739881``, rounded to
    the artifact's six-decimal style.
    """
    exact = 3.0 * ((1.0 + ALPHA_ANNUAL) ** (1.0 / 12.0) - 1.0)
    rounded = round(exact, 6)
    if rounded != ALPHA_QUARTERLY:
        raise SystemExit(
            f"alpha derivation broke: 3*((1+{ALPHA_ANNUAL})**(1/12)-1) = {exact!r} "
            f"rounds to {rounded!r}, not the declared {ALPHA_QUARTERLY!r}"
        )
    return rounded


def deep_diff(a: object, b: object, path: str = "") -> dict[str, tuple[object, object]]:
    """Every leaf-level difference between two loaded documents, as
    ``{dotted.path: (old, new)}`` with ``'<absent>'`` marking added/removed."""
    diffs: dict[str, tuple[object, object]] = {}
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            sub = f"{path}.{key}" if path else str(key)
            if key not in a:
                diffs[sub] = ("<absent>", b[key])
            elif key not in b:
                diffs[sub] = (a[key], "<absent>")
            else:
                diffs.update(deep_diff(a[key], b[key], sub))
    elif a != b:
        diffs[path] = (a, b)
    return diffs


def _rebuilt_row(row: dict[str, Any], alpha_q: float) -> dict[str, Any]:
    """The pm_buyout row with EXACTLY the declared overrides, key order
    preserved; ``r2_note`` lands beside ``r2_train_val`` (the
    pm_direct_lending layout) and ``chosen`` closes the row."""
    for field, expected in REPLACED.items():
        found = row["loadings"][field] if field == "equity_mkt" else row[field]
        if found != expected:
            raise SystemExit(
                f"v1.2 pm_buyout.{field} is {found!r}, expected {expected!r} -- "
                "refusing to override a row that is not the sealed one this "
                "ruling replaced"
            )
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key == "alpha_quarterly":
            out[key] = alpha_q
        elif key == "loadings":
            out[key] = {**value, "equity_mkt": CHOSEN_EQUITY_MKT}
        elif key == "r2_train_val":
            out[key] = None
            out["r2_note"] = R2_NOTE
        else:
            out[key] = value
    out["chosen"] = copy.deepcopy(CHOSEN_BLOCK)
    return out


def build() -> str:
    """The full v1.3 file text. Pure: reads v1.2, writes nothing."""
    original_bytes = V12_PATH.read_bytes()
    text = original_bytes.decode("utf-8")
    doc = yaml.safe_load(text)

    # Round-trip fidelity: v1.2's body (after its comment header) must be
    # byte-identical under load->dump, or "unchanged" below would only mean
    # value-equal and the byte-for-byte claim in the header would be false.
    lines = text.split("\n")
    n_header = 0
    while lines[n_header].startswith("#"):
        n_header += 1
    body = "\n".join(lines[n_header:])
    if yaml.safe_dump(doc, sort_keys=False, allow_unicode=False) != body:
        raise SystemExit(
            "v1.2 does not round-trip byte-identically through "
            "yaml.safe_dump(sort_keys=False, allow_unicode=False) -- the "
            "byte-for-byte inheritance claim would be false; stopping"
        )

    alpha_q = chosen_alpha_quarterly()
    new_doc = copy.deepcopy(doc)
    new_doc["pm_sleeves"]["pm_buyout"] = _rebuilt_row(new_doc["pm_sleeves"]["pm_buyout"], alpha_q)

    # Assertion (b): the deep-diff is EXACTLY the declared change set.
    expected_diff: dict[str, tuple[object, object]] = {
        "pm_sleeves.pm_buyout.alpha_quarterly": (REPLACED["alpha_quarterly"], alpha_q),
        "pm_sleeves.pm_buyout.loadings.equity_mkt": (
            REPLACED["equity_mkt"],
            CHOSEN_EQUITY_MKT,
        ),
        "pm_sleeves.pm_buyout.r2_train_val": (0.269, None),
        "pm_sleeves.pm_buyout.r2_note": ("<absent>", R2_NOTE),
        "pm_sleeves.pm_buyout.chosen": ("<absent>", CHOSEN_BLOCK),
    }
    diff = deep_diff(doc, new_doc)
    if diff != expected_diff:
        unexpected = sorted(set(diff) ^ set(expected_diff)) or sorted(
            k for k in diff if diff[k] != expected_diff.get(k)
        )
        raise SystemExit(
            "deep-diff of v1.3 vs v1.2 is not exactly the declared change set; "
            f"unexpected/missing paths: {unexpected}"
        )

    # Assertion (c): v1.2 was never written.
    if V12_PATH.read_bytes() != original_bytes:
        raise SystemExit("v1.2 bytes changed during the run -- this must never happen")

    return HEADER + yaml.safe_dump(new_doc, sort_keys=False, allow_unicode=False)


def main() -> None:
    OUT_PATH.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH.name} (pm_buyout -> chosen, {RATIFICATION}, {AMENDMENT_ID})")


if __name__ == "__main__":
    main()
