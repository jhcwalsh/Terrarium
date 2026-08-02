"""The Tier-2 consistency gate (WP4.4) — G1-G9, run in order, frozen split.

The blocking split is FROZEN (G4-pre, AM-2026-08-02-002): G1-G5 and G8
block; G6 is advisory in v1; G7 blocks on its own terms; G9 blocks
publication through the chronicle record's own refusals. A blocked draft
returns to the author queue with the violation attached — the pipeline
(author.py) owns the two-retries-then-fallback rule.

v1 scope, stated not hidden: G3's screening is the keyword rules; the
spec's leak-checker PROMPT over the draft is v1.1 (needs a second model
call), recorded here and in the WP record. G6 warns "not evaluated"
unless past artifacts are supplied — an advisory that pretends to check
would be worse than one that says it did not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ah.artifacts.render import WATERMARK_BANNER, WATERMARK_FOOTER

#: Implementation lineage for the SEALED rules. The G4-pre freeze covers the
#: rule definitions, thresholds and blocking split (ARTIFACT-AUTHORING.md,
#: hashed) — this constant versions the heuristics that IMPLEMENT them.
#: 1.0.1: run-1 false-positive fixes (salutations are not entities; 'gate'
#: only as redemption-gating; wider hedge lexicon), each aligning the code
#: to the sealed rule's meaning, re-measured by a fresh full live run.
#: 1.0.2: run-2 fixes — market/asset-class terms are not entities; G2 gains
#: a modality guard (an outlook is not an event claim); G5's rating rule
#: relaxed to the SPEC's actual sentence (vocabulary constrained, >=1 rating
#: present — 'exactly one' was stricter than sealed text); proper-noun scan
#: no longer glues across newlines. note@1.1 (sentence-case titles) is the
#: companion prompt-side fix, version-bumped per the frozen rule.
#: 1.0.3: run-6 false-positive fixes - sentence-starting relative/interrogative
#: adverbs join the stopwords ("Where Grimshaw" is the allowed entity plus an
#: adverb, not a new firm); the hedge lexicon covers ordinary cautious prose
#: ("watching closely", "holding steady" - the sealed rule demands hedging
#: PRESENT, not one narrow vocabulary); market-expectation phrasings
#: ("pricing in rate cuts") are expectations, not event claims (G2).
#: 1.0.4: run-7 fixes - G2's default pattern narrows to EVENT phrasings
#: (the sealed rule polices named events; "default risk remains contained"
#: is a state assessment, not an event claim - surfaced when the @1.2
#: exemplar primed the word into every draft); "net asset value index"
#: joins the finance phrases. "The Federal Reserve" flagged by G4 is a
#: TRUE positive (real institutions at role level only) and stays.
#: 1.0.5: run-8 fix - sentence-starting prepositions join the stopwords
#: ("At Stonebeck, we..." is an allowed entity plus a preposition).
#: 1.0.6: run-10 fix - document furniture ("Quarterly Letter", "Annual
#: Report") is not an entity reference.
GATE_IMPL_VERSION = "gate-impl/1.0.6"

RATINGS = ("overweight", "neutral", "underweight", "no_rating")
_PROMISE_PATTERNS = (
    r"\bwill (?:return|deliver|achieve|outperform)\b",
    r"\bguarantee[sd]?\b",
    r"\bassured returns?\b",
)
_ADVICE_PATTERNS = (r"\byou should (?:buy|sell|invest|redeem)\b", r"\bwe recommend you\b")
_HEDGE_WORDS = (
    "may",
    "could",
    "expect",
    "believe",
    "likely",
    "risk",
    "uncertain",
    "prudent",
    "cautious",
    "cautiously",
    "monitor",
    "watchful",
    "remain",
    "depend",
    "subject to",
    "no assurance",
    # the caution family reads as hedged outlook too (1.0.2)
    "downside",
    "headwind",
    "pressure",
    "vulnerab",
    "fragil",
    "stress",
    # ordinary cautious-outlook prose is hedging too (1.0.3)
    "watch",
    "patien",
    "disciplin",
    "steady",
    "humble",
    "time will tell",
    "hard to know",
    "no promises",
)
# G2 polices EVENT CLAIMS, not vocabulary: 'gate' counts only as the
# redemption-gating event, not the common noun/metaphor (run-1 fix).
_EVENT_PATTERNS = {
    "redemption gating": r"\bgat(?:e[sd]?|ing)\b[^.]{0,40}\bredemptions?\b"
    r"|\bredemptions?\b[^.]{0,40}\bgat(?:e[sd]?|ing)\b",
    "default": r"\bdefaults?\s+(?:rose|rise|spiked|surged|climbed|jumped|hit|swept)\b"
    r"|\bdefaulted\b|\b(?:entered|filed for)\s+default\b",
    "rate cut": r"\brate cuts?\b",
    "rate hike": r"\brate hikes?\b",
    "bear market": r"\bbear market\b",
}
_EVENT_STEMS = {
    "redemption gating": ("gate", "gating", "gated"),
    "default": ("default",),
    "rate cut": ("rate cut", "cut"),
    "rate hike": ("rate hike", "hike"),
    "bear market": ("bear",),
}
# numbers the gate polices: percentages, bps, and thousand-separated decimals
_NUMBER_RE = re.compile(r"[+-]?\d[\d,]*\.\d+%?|[+-]?\d[\d,]*%|\b\d[\d,]*\s?bps\b")
_FUTURE_Q_RE = re.compile(r"\bQ(\d{1,2})\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_PROPER_RE = re.compile(r"\b([A-Z][a-z]+(?:[ ]+(?:&[ ]+)?[A-Z][a-z]+)+)\b")
#: A hypothetical or outlook mention is not an event claim (1.0.2): an event
#: match preceded nearby by a modal marker is exempt from G2.
_MODAL_GUARD = re.compile(
    r"\b(?:may|might|could|would|if|should|expect(?:ed|ations?)?|potential|risk of|were"
    r"|pric(?:e[sd]?|ing) in|anticipat)\b[^.]{0,60}$"
)
# Letter furniture: salutations and sign-offs are prose conventions, not
# entity references (run-1's dominant false positive, 18/30). Lines opening
# with these words are exempt from G4's proper-noun scan; the entities on
# such a line are still caught anywhere else they appear.
_SALUTATION_RE = re.compile(
    r"^(?:Dear|To|Sincerely|Regards|Best|Warm|Respectfully|Yours|Onward)\b.*$",
    re.MULTILINE,
)
_COMMON_PHRASES = {
    "limited partners",
    "general partner",
    "general partners",
    "investment committee",
    "board of trustees",
    "annual meeting",
    # markets and asset classes are subjects, not entities (1.0.2)
    "private credit",
    "private equity",
    "public markets",
    "public equities",
    "high yield",
    "investment grade",
    "direct lending",
    "real estate",
    "fixed income",
    "fair value",
    "net asset value",
    "net asset value index",
    # document furniture is not an entity reference (1.0.6)
    "quarterly letter", "quarterly statement", "annual report",
    "annual letter", "investor letter", "board pack",
}
_TITLE_STOPWORDS = {
    "The",
    "A",
    "An",
    "In",
    "On",
    "Of",
    "For",
    "And",
    "But",
    "Our",
    "We",
    "This",
    "That",
    "These",
    "Those",
    "Your",
    "Their",
    "Its",
    # sentence-starting relative/interrogative adverbs (1.0.3)
    "Where",
    "When",
    "While",
    "What",
    "Why",
    "How",
    "If",
    "As",
    "Since",
    "Though",
    "Although",
    "Unlike",
    "Should",
    "Whether",
    # sentence-starting prepositions (1.0.5)
    "At",
    "From",
    "With",
    "By",
    "Under",
    "Across",
    "Beyond",
    "Against",
    "Within",
    "Between",
    "After",
    "Before",
    "During",
    "Here",
}


@dataclass
class GateReport:
    passed: list[str] = field(default_factory=list)
    violations: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.violations)


def _fail(report: GateReport, rule: str, message: str) -> None:
    report.violations.append({"rule": rule, "message": message})


def run_gate(
    draft: str,
    payload: dict[str, Any],
    *,
    allowed_entities: list[str],
    generic_allowlist: list[str],
    is_note: bool = False,
    past_artifacts: list[str] | None = None,
    fog: dict[str, Any] | None = None,
    rendered: str | None = None,
) -> GateReport:
    """G1-G8 over a draft (G9 is the chronicle record's own refusals).

    ``rendered``: the framed artifact, if already rendered — G8 checks the
    marking there; when None, G8 checks that rendering is still ahead and
    records a warning so the caller cannot forget.
    """
    report = GateReport()
    claims = payload["checkable_claims_table"]
    dateline_quarter = int(payload["dateline_quarter"])
    dateline_year = int(str(payload["dateline"])[:4])

    # G1 — numeric fidelity: every policed number matches a claims value
    claim_values = set(claims.values())
    bad_numbers = [
        m.group(0)
        for m in _NUMBER_RE.finditer(draft)
        if not any(m.group(0) in v or v in m.group(0) for v in claim_values)
    ]
    if bad_numbers:
        _fail(
            report,
            "G1",
            f"numbers not in the claims table (copied, never derived): {bad_numbers}",
        )
    else:
        report.passed.append("G1")

    # G2 — event fidelity: named event CLAIMS must be substantiated by newsflow
    extracts = " ".join(payload.get("chronicle_extracts", [])).lower()
    arc = " ".join(payload.get("arc_beats_to_date", [])).lower()
    facts = " ".join(str(v) for v in payload.get("fund_facts", {}).values()).lower()
    substantiation = f"{extracts} {arc} {facts}"
    lower_draft = draft.lower()

    def _claimed(pattern: str) -> bool:
        """An event MATCH is a claim only if not under a modal guard (1.0.2)."""
        for m in re.finditer(pattern, lower_draft):
            if not _MODAL_GUARD.search(lower_draft[: m.start()]):
                return True
        return False

    unsub = [
        event
        for event, pattern in _EVENT_PATTERNS.items()
        if _claimed(pattern) and not any(stem in substantiation for stem in _EVENT_STEMS[event])
    ]
    if unsub:
        _fail(report, "G2", f"events with no chronicle substantiation: {unsub}")
    else:
        report.passed.append("G2")

    # G3 — dateline causality (keyword rules; leak-checker prompt is v1.1)
    future_qs = [
        f"Q{m.group(1)}" for m in _FUTURE_Q_RE.finditer(draft) if int(m.group(1)) > dateline_quarter
    ]
    future_years = [m.group(1) for m in _YEAR_RE.finditer(draft) if int(m.group(1)) > dateline_year]
    if future_qs or future_years:
        _fail(report, "G3", f"references beyond the dateline: {future_qs + future_years}")
    else:
        report.passed.append("G3")

    # G4 — closed entity world: unknown proper nouns block. Salutation and
    # sign-off lines are prose furniture, not entity references (1.0.1).
    scannable = _SALUTATION_RE.sub("", draft)
    allowed_lower = {a.lower() for a in allowed_entities} | {g.lower() for g in generic_allowlist}
    unknown = []
    for m in _PROPER_RE.finditer(scannable):
        candidate = m.group(1)
        words = candidate.split()
        trimmed = " ".join(w for w in words if w not in _TITLE_STOPWORDS)
        if not trimmed or len(trimmed.split()) < 2:
            continue
        if trimmed.lower() in _COMMON_PHRASES:
            continue
        if not any(trimmed.lower() in a or a in trimmed.lower() for a in allowed_lower):
            unknown.append(candidate)
    if unknown:
        _fail(report, "G4", f"proper nouns outside the closed world: {sorted(set(unknown))}")
    else:
        report.passed.append("G4")

    # G5 — vocabulary and compliance
    g5_bad: list[str] = []
    lower = draft.lower()
    for pattern in _PROMISE_PATTERNS:
        if re.search(pattern, lower):
            g5_bad.append(f"performance promise: /{pattern}/")
    for pattern in _ADVICE_PATTERNS:
        if re.search(pattern, lower):
            g5_bad.append(f"advice imperative: /{pattern}/")
    if is_note:
        # the SEALED sentence constrains the VOCABULARY and requires a rating;
        # mentioning a prior rating ('downgrade from neutral to underweight')
        # is legitimate prose (1.0.2)
        found = [r for r in RATINGS if re.search(rf"\b{r}\b", lower)]
        if not found:
            g5_bad.append(f"a note carries a rating from {RATINGS}; none found")
    if not any(w in lower for w in _HEDGE_WORDS):
        g5_bad.append("no hedging language anywhere in the draft")
    if g5_bad:
        _fail(report, "G5", "; ".join(g5_bad))
    else:
        report.passed.append("G5")

    # G6 — continuity: ADVISORY in v1 (frozen split), blocking from v1.1
    if past_artifacts:
        report.warnings.append(
            {"rule": "G6", "message": "continuity check v1 is advisory; reviewed, not blocking"}
        )
    else:
        report.warnings.append(
            {"rule": "G6", "message": "not evaluated: no past artifacts supplied (advisory in v1)"}
        )

    # G7 — fog discipline
    if fog is not None:
        g7_bad = []
        if not any(marker in lower for marker in ("unconfirmed", "people familiar")):
            g7_bad.append("fog artifact missing its in-world uncertainty marker")
        if not fog.get("resolver_scheduled", False):
            g7_bad.append("no resolver artifact scheduled inside the declared window")
        if g7_bad:
            _fail(report, "G7", "; ".join(g7_bad))
        else:
            report.passed.append("G7")

    # G8 — marking, checked on the rendered artifact
    if rendered is None:
        report.warnings.append(
            {"rule": "G8", "message": "not yet rendered; export() must apply marking last"}
        )
    elif WATERMARK_BANNER in rendered and WATERMARK_FOOTER in rendered:
        report.passed.append("G8")
    else:
        _fail(report, "G8", "rendered artifact is missing the simulated-world marking")

    return report
