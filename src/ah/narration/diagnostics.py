"""The nine panels — the part that makes this a workbench rather than a feature.

A reader must be able to answer "is this any good?" without reading forty
slates. Two of the panels are **diagnostics on the generator, not on the
narration**, and are labelled as such wherever they are rendered:

* **policy** (DN-9 §C.6, referral N-q) — if the generated policy path is
  unquantised or reverses freely, no statement can explain it, and this is where
  that shows up rather than in the copy;
* **strain** (§D.6, referral N-v) — where prose cannot follow the numbers.

Nothing here gates anything. The vocabulary panel in particular is *measurement*
and not the leak gate: N-2 is a sealed test with a pre-registered margin, scored
by someone who did not write the template pack, and it is explicitly out of this
task's scope.
"""

from __future__ import annotations

import itertools
import math
import re
from collections import Counter
from typing import Any

import numpy as np

from ah.narration.constants import (
    BPS_PER_PP,
    DIAGNOSTIC_TOP_ROWS,
    DISPLAY_PRECISION,
    MONTHS_PER_QUARTER,
    QUARTERS_PER_YEAR,
    RECORD_PRECISION,
    SEVERITY_MAX,
)
from ah.narration.events import Event
from ah.narration.voices import RenderedSlate

__all__ = ["compute"]

_WORD = re.compile(r"[a-z]+")

#: Tokens too common to carry information about anything. A stop list for the
#: vocabulary panel only — it never touches rendered copy.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "which",
        "with",
        "this",
        "not",
        "no",
        "more",
        "than",
        "been",
    ]
)


def _ranked(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    """``most_common`` with the tie order pinned.

    ``Counter.most_common`` breaks ties by INSERTION order, and insertion order
    here comes from iterating sets of tokens — whose order varies with the
    interpreter's hash seed, i.e. between processes. That made two identical
    builds produce different ``diagnostics.html`` files. Sorting on
    ``(-count, key)`` makes the ranking a property of the data.
    """
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _tokens(text: str) -> list[str]:
    return [word for word in _WORD.findall(text.lower()) if word not in _STOPWORDS]


def _mutual_information(present: list[bool], labels: list[str]) -> float:
    """MI in bits between "this token appears in the slate" and the L2 label."""
    n = len(labels)
    if n == 0:
        return 0.0
    joint = Counter(zip(present, labels, strict=True))
    p_token = Counter(present)
    p_label = Counter(labels)
    total = 0.0
    for (token, label), count in joint.items():
        p_xy = count / n
        p_x = p_token[token] / n
        p_y = p_label[label] / n
        if p_xy > 0.0:
            total += p_xy * math.log2(p_xy / (p_x * p_y))
    return total


def compute(
    *,
    events: list[Event],
    slates: list[Any],
    rendered: list[RenderedSlate],
    world: Any,
    strain_log: list[dict[str, Any]],
    columnist_calls: list[dict[str, Any]],
    target_band: list[float],
    ngram_n: int,
    min_slots: int,
    hit_rate_target: list[float],
    uncovered: tuple[str, ...],
) -> dict[str, Any]:
    """Every panel's payload, as plain data. Rendering is :mod:`render`'s job."""
    panels: dict[str, Any] = {}

    # 1 -- severity calibration
    histogram = Counter(event.severity for event in events)
    sev3 = histogram.get(SEVERITY_MAX, 0)
    low, high = float(target_band[0]), float(target_band[1])
    panels["severity"] = {
        "title": "Severity calibration",
        "histogram": {str(k): histogram.get(k, 0) for k in range(SEVERITY_MAX + 1)},
        "severity_3_count": sev3,
        "target_band": [low, high],
        "in_band": low <= sev3 <= high,
        "by_class": {
            cls: dict(Counter(e.severity for e in events if e.cls == cls))
            for cls in sorted({e.cls for e in events})
        },
    }

    # 2 -- slot contest
    winners = Counter(
        (announcement.slot, announcement.event.cls)
        for slate in slates
        for announcement in slate.announcements
    )
    by_slot: dict[str, list[tuple[str, int]]] = {}
    for (slot, cls), count in winners.items():
        by_slot.setdefault(slot, []).append((cls, count))
    panels["slot_contest"] = {
        "title": "Slot contest",
        "winners": {
            slot: sorted(rows, key=lambda row: (-row[1], row[0])) for slot, rows in by_slot.items()
        },
        "slate_sizes": dict(Counter(len(slate.announcements) for slate in slates)),
    }

    # 3 -- repetition
    corpus = [text for slate in rendered for item in slate.items for text in item.texts()]
    ngrams: Counter[str] = Counter()
    for text in corpus:
        words = _tokens(text)
        for start in range(len(words) - ngram_n + 1):
            ngrams[" ".join(words[start : start + ngram_n])] += 1
    panels["repetition"] = {
        "title": "Repetition",
        "n": ngram_n,
        "top": [
            {"phrase": phrase, "count": count}
            for phrase, count in _ranked(ngrams, DIAGNOSTIC_TOP_ROWS)
        ],
        "distinct_ngrams": len(ngrams),
        "total_ngrams": sum(ngrams.values()),
    }

    # 4 -- vocabulary -> regime (measurement, not a gate)
    labels = [world.regime[slate.slate.months[-1] - 1] for slate in rendered]
    slate_text = [
        " ".join(text for item in slate.items for text in item.texts()) for slate in rendered
    ]
    vocabulary = Counter(word for text in slate_text for word in sorted(set(_tokens(text))))
    rows = []
    for word, _ in _ranked(vocabulary, DIAGNOSTIC_TOP_ROWS * 4):
        present = [word in set(_tokens(text)) for text in slate_text]
        rows.append(
            {"word": word, "mi_bits": round(_mutual_information(present, labels), RECORD_PRECISION)}
        )
    rows.sort(key=lambda row: (-float(row["mi_bits"]), str(row["word"])))
    panels["vocabulary"] = {
        "title": "Vocabulary -> regime",
        "note": "Measurement, not a gate. N-2 is a sealed test scored by someone else.",
        "top": rows[:DIAGNOSTIC_TOP_ROWS],
        "mean_mi_bits": round(
            float(np.mean([float(row["mi_bits"]) for row in rows])) if rows else 0.0,
            RECORD_PRECISION,
        ),
        "regimes_present": sorted(set(labels)),
    }

    # 5 -- verdict chips
    chips = Counter(
        chip
        for slate in rendered
        for item in slate.items
        for artifact in (item.report, *item.voices)
        for chip in artifact.chips
    )
    panels["chips"] = {
        "title": "Verdict chips",
        "top": [
            {"chip": chip, "count": count} for chip, count in _ranked(chips, DIAGNOSTIC_TOP_ROWS)
        ],
        "distinct": len(chips),
    }

    # 6 -- policy diagnostics (ON THE GENERATOR)
    policy_events = [event for event in events if event.cls == "E01"]
    moves_bp = [float(event.delta["value"]) for event in policy_events]
    non_zero = [move for move in moves_bp if move != 0.0]
    reversals = sum(1 for first, second in itertools.pairwise(non_zero) if first * second < 0.0)
    epsilons = [float(event.trigger_values["epsilon"]) * BPS_PER_PP for event in policy_events]
    panels["policy"] = {
        "title": "Policy diagnostics",
        "subtitle": "A diagnostic on the GENERATOR, not on the narration (DN-9 §C.6, N-q)",
        "meetings": len(policy_events),
        "moves": len(non_zero),
        "reversals": reversals,
        "reversal_frequency": round(reversals / len(non_zero), RECORD_PRECISION)
        if non_zero
        else 0.0,
        "step_histogram": dict(sorted(Counter(round(abs(move)) for move in non_zero).items())),
        "epsilon_bp": {
            "mean": round(float(np.mean(epsilons)), DISPLAY_PRECISION) if epsilons else 0.0,
            "sd": round(float(np.std(epsilons)), DISPLAY_PRECISION) if epsilons else 0.0,
            "min": round(float(np.min(epsilons)), DISPLAY_PRECISION) if epsilons else 0.0,
            "max": round(float(np.max(epsilons)), DISPLAY_PRECISION) if epsilons else 0.0,
        },
    }

    # 7 -- strain (ON THE GENERATOR)
    strains = [float(entry["strain"]) for entry in strain_log]
    panels["strain"] = {
        "title": "Rationale strain",
        "subtitle": "Also a diagnostic on the GENERATOR (DN-9 §D.6, N-v)",
        "count": len(strains),
        "mean": round(float(np.mean(strains)), RECORD_PRECISION) if strains else 0.0,
        "max": round(float(np.max(strains)), RECORD_PRECISION) if strains else 0.0,
        "top": sorted(strain_log, key=lambda e: -float(e["strain"]))[:DIAGNOSTIC_TOP_ROWS],
        "states": dict(Counter(str(entry["state"]) for entry in strain_log)),
    }

    # 8 -- coverage
    markers = sum(
        1
        for slate in rendered
        for item in slate.items
        for artifact in (item.report, *item.voices)
        if artifact.missing_template
    )
    panels["coverage"] = {
        "title": "Coverage",
        "classes_never_fired": list(uncovered),
        "slates_below_minimum": [
            slate.quarter for slate in slates if len(slate.announcements) < min_slots
        ],
        "min_slots": min_slots,
        "no_template_markers": markers,
        "omitted_slots": dict(Counter(slot for slate in slates for slot in slate.omitted_slots)),
    }

    # 9 -- columnists
    equity = world.series["equity_index"]
    horizon = MONTHS_PER_QUARTER * QUARTERS_PER_YEAR
    scored: Counter[str] = Counter()
    right: Counter[str] = Counter()
    for call in columnist_calls:
        month = int(call["month"])
        if month + horizon > len(equity):
            continue
        realised = 1 if equity[month + horizon - 1] > equity[month - 1] else -1
        scored[str(call["name"])] += 1
        if realised == int(call["call"]):
            right[str(call["name"])] += 1
    dispersions = [
        artifact.extras["dispersion"]
        for slate in rendered
        for item in slate.items
        for artifact in item.voices
        if artifact.voice == "columnists" and artifact.extras.get("dispersion") is not None
    ]
    panels["columnists"] = {
        "title": "Columnists",
        "hit_rate_target": [float(hit_rate_target[0]), float(hit_rate_target[1])],
        "records": [
            {
                "name": name,
                "calls": scored[name],
                "hit_rate": round(right[name] / scored[name], DISPLAY_PRECISION)
                if scored[name]
                else None,
                "in_target_band": (
                    float(hit_rate_target[0])
                    <= right[name] / scored[name]
                    <= float(hit_rate_target[1])
                    if scored[name]
                    else None
                ),
            }
            for name in sorted(scored)
        ],
        "mean_dispersion": round(float(np.mean(dispersions)), DISPLAY_PRECISION)
        if dispersions
        else None,
        "deferred": sorted(
            {
                name
                for slate in rendered
                for item in slate.items
                for artifact in item.voices
                for name in artifact.extras.get("deferred", [])
            }
        ),
    }
    return panels
