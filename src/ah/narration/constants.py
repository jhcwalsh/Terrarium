"""Structural constants — calendar arithmetic and unit conversions only.

**Nothing here is a tunable.** A tunable is a value where a reasonable person
could pick a different one and the narration would still be correct; every such
value lives in ``voices.yaml``. The values here are facts about the calendar and
about units, and ``tests/test_narration_no_hardcoded_tunables.py`` allows
numeric literals in this module (and in :mod:`ah.narration.config`) for exactly
that reason.
"""

from __future__ import annotations

#: Calendar. The decade is 120 months = 40 quarters = 10 years (DN-9 §B.0).
MONTHS_PER_YEAR = 12
MONTHS_PER_QUARTER = 3
QUARTERS_PER_YEAR = 4

#: Unit conversions. A fraction rendered as a percentage; a percentage point
#: rendered as basis points.
PERCENT = 100.0
BPS_PER_PP = 100.0

#: The equity index is cumulated from ``equity_mkt`` monthly returns. The base
#: is a display normalisation, not a parameter: every quantity the narration
#: takes from the index (returns, drawdowns, peak distances) is scale-free, so
#: any positive base gives byte-identical events.
EQUITY_INDEX_BASE = 100.0

#: Unit conversion for the payrolls transform: one percentage point of a labour
#: force measured in millions is that many *ten-thousands* of jobs.
THOUSANDS_PER_MILLION = 1000.0

#: Rounding for display-only figures (a confidence, a prior, a dispersion). No
#: decision reads these; they are what the page prints.
DISPLAY_PRECISION = 3

#: How much of a SHA-256 to show a human, and how much of one to turn into a
#: uniform draw. Both are hash mechanics, not choices about the world.
HASH_DISPLAY_CHARS = 12
HASH_DRAW_HEX_DIGITS = 12
HEX_BASE = 16

#: Rows in each ranked diagnostics table. Presentation: the full distributions
#: are always in the panel payload and in ``manifest.json``.
DIAGNOSTIC_TOP_ROWS = 10

#: The dateline is the in-world month and is the primary time cue in the whole
#: product (DN-9 §5.1). Month 1 is January of Year 1 — the world is a decade,
#: not a dated period, so no real calendar is implied.
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

#: Rounding applied to floats before they enter ``events.jsonl`` or a manifest.
#: A serialisation precision, not a tolerance: it exists so a record written on
#: one machine is byte-identical to the same record written on another, and no
#: decision anywhere is sensitive to the sixth decimal place.
RECORD_PRECISION = 6

#: The severity grammar is 0..3 (DN-9 §3.1 "severity 0..3"). The *cut-points*
#: that map a normalised trigger onto this range are a tunable and are not here.
SEVERITY_MIN = 0
SEVERITY_MAX = 3

#: The four slate slots, one per CIO-dashboard panel (DN-9 §B.1). Order is the
#: publication order and is part of the grammar, not a preference.
SLOTS = ("POLICY", "DATA", "MARKETS", "CAPITAL")

#: Slot -> the dashboard panel it explains (DN-9 §B.1, §B.2).
PANEL_OF_SLOT = {
    "POLICY": "policy & rates",
    "DATA": "macro",
    "MARKETS": "public markets",
    "CAPITAL": "the book",
}

#: Event class -> slot. DN-9 §B.1's "draws from" column, inverted. Structural:
#: which panel a class explains is the grammar, not an editorial choice.
SLOT_OF_CLASS = {
    "E01": "POLICY",
    "E02": "DATA",
    "E03": "DATA",
    "E04": "DATA",
    "E05": "MARKETS",
    "E06": "MARKETS",
    "E07": "MARKETS",
    "E08": "MARKETS",
    "E09": "MARKETS",
    "E10": "MARKETS",
    "E11": "MARKETS",
    "E12": "CAPITAL",
    "E15": "CAPITAL",
    "E16": "CAPITAL",
    "E17": "MARKETS",
    "E18": "CAPITAL",
    "E19": "CAPITAL",
    "E21": "MARKETS",
}

#: ``kind`` per class, from ``voices.yaml``'s ``events`` block. Repeated here as
#: the structural default the loader checks the config against: DN-9 is explicit
#: that "a state class firing every period it holds is a defect, not a
#: parameter", so ``kind`` is validated, never taken as a tunable.
KIND_OF_CLASS = {
    "E01": "point",
    "E02": "point",
    "E03": "point",
    "E04": "point",
    "E05": "point",
    "E06": "point",
    "E07": "state",
    "E08": "point",
    "E09": "state",
    "E10": "state",
    "E11": "point",
    "E12": "point",
    "E15": "state",
    "E16": "state",
    "E17": "point",
    "E18": "state",
    "E19": "point",
    "E21": "point",
}

#: The L1 slow states this world's generator emits, and the DN-9 §D.2 name for
#: each. ``credit_gap`` fills DN-9's ``L`` slot (owner ruling, narr-04): DN-9
#: names the L1 state ``(pi_star, r_star, g, v, L)`` and never defines ``L``
#: beyond "the credit gap" (§D.1), which is exactly what ``credit_gap`` is.
L1_STATE_NAMES = ("pi_star", "r_star", "g", "v", "credit_gap")

#: The required input contract (task §1). Every one of these must be available
#: for 120 months or the build fails naming the series.
REQUIRED_SERIES = (
    "policy_rate",
    "cpi_yoy",
    "equity_index",
    "hy_oas",
    "curve_2s10s",
    "ust_10y",
    "regime",
    "l1_state",
)

#: Optional book series (task §1). Absent -> the CAPITAL slot is omitted and the
#: omission is stated on the artifact. Never stubbed.
OPTIONAL_SERIES = (
    "cash_pct",
    "private_weight_reported",
    "dpi_vs_plan",
    "calls",
    "distributions",
)

#: Event classes that can only fire from the optional book series.
BOOK_CLASSES = ("E12", "E15", "E16", "E17", "E18", "E19")

#: The marker emitted where a template bank has no string for a case. DN-9 /
#: task: do not improvise prose.
NO_TEMPLATE = "[[NO TEMPLATE: class={cls} sev={sev}]]"
