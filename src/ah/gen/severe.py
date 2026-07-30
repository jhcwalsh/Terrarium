"""WP2.11 severe test — the fitting-sample exclusion, as one shared span object.

The sealed ``severe_test_protocol`` (``pre-registration.yaml``) reads, verbatim:

    Exclude the 1970s (1970-01-01 to 1979-12-31 inclusive) from the fitting
    sample. Refit L1 and L2 and RETRAIN L3 with the FROZEN architectures and
    hyperparameters of the primary runs -- refit/retrain only, NO fresh
    hyperparameter search on the reduced sample, no architecture change, no
    early-stopping-criterion change. Regenerate from the 1965 climate state and
    compare 1966-1984 behaviour through the horizon tier.

"Exclude" has to be given a concrete meaning per layer, because the three layers
read the fitting sample in three different shapes. The meanings are decided
here, once, and the same :data:`SEVERE_TEST_EXCLUSION` object drives all three.

**L1 (climate) -- MASK, do not delete.** The Kalman filter already carries an
observation ``mask`` (:class:`ah.gen.climate.model.KFData`), and a masked month
contributes no likelihood term and no state update while the state still
*evolves* through the gap (see ``_filter_step``: every update is multiplied by
the mask). Deleting rows instead would splice 1969-12 directly onto 1980-01 and
make the transition across the gap a single month's worth of process noise
covering ten years -- which would corrupt the very thing the test needs, a
1965 state estimate embedded in a coherent state path. Masking is the honest
state-space reading of "unobserved". Exclusion is BY DATE, not by index: the
annual JST channels land on July (and ``a_r10`` on December), so an index rule
would miss or over-catch them.

**L2 (regimes) -- SEGMENT, with the existing censoring convention.** The label
history is one contiguous monthly run and the spell decomposition depends on
contiguity, so the exclusion splits it into two observation SEGMENTS (pre-1970,
post-1979) and each segment is treated exactly as the primary fit treats the
whole sample: its first spell is dropped (left-truncated, its start unobserved)
and its last spell is right-censored (a survival term, not a pmf term).
Transitions are counted only at spell boundaries INTERIOR to a segment, so no
transition is ever invented across the gap. This is the "something better" the
straddling-spell problem asks for: a spell running into the excluded decade is
*genuinely* right-censored and a spell running out of it *genuinely* has an
unobserved start, so both are handled by machinery the primary fit already has
rather than by a new rule. It is also the cheapest correct option -- dropping
straddlers outright would discard two spells' worth of partial information that
the censoring term can legitimately use.

**L3 (blocks) -- DROP ANY BLOCK WHOSE WINDOW INTERSECTS.** Not merely the blocks
that START inside the decade: an L-month block starting in 1969-06 still
*contains* 1970 months, and training on it would be training on excluded data.
:meth:`ExclusionSpan.window_intersects` implements the window rule.

NOTE, recorded here because it is the single most consequential fact about the
L3 leg of this test: the L3 training panel is the
:class:`~ah.gen.bootstrap.BootstrapSource` panel, whose span is the sealed
``block_draw_span`` 1990-01..2020-12 -- which does not intersect the 1970s at
all. So the window rule drops ZERO blocks, for the same structural reason the
sealed ``benchmark_exception`` says ``bootstrap-v1`` cannot run this test. The
L3 retrain is nonetheless NOT a no-op, because the block conditioning vectors
carry L1's posterior-mean slow states (``ah.gen.blocks.data._conditioning_rows``)
and L1 has been refit; the conditioning changes, and with it the train-only
``c_mean``/``c_std``. Both facts are measured and reported rather than assumed.

This module is in ``ah.gen`` and therefore never imports ``ah.eval``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "SEVERE_TEST_EXCLUSION",
    "SEVERE_TEST_S0_DATE",
    "ExclusionSpan",
    "contains_or_false",
    "segments_outside",
]

#: The sealed regeneration start: "regenerate from the 1965 climate state".
#: January 1965, so the compared 1966-1984 window opens in the first full year.
SEVERE_TEST_S0_DATE = "1965-01-01"


@dataclass(frozen=True)
class ExclusionSpan:
    """A half-open ``[start, end_exclusive)`` month span removed from a fit.

    Stored half-open because every date grid in this repo is half-open, while the
    sealed protocol states the decade with an INCLUSIVE end (1979-12-31); the two
    agree on months and :attr:`label` prints the sealed form.
    """

    start: str
    end_exclusive: str

    def __post_init__(self) -> None:
        if pd.Timestamp(self.end_exclusive) <= pd.Timestamp(self.start):
            raise ValueError(
                f"exclusion span {self.start}..{self.end_exclusive} is empty or inverted; "
                f"end_exclusive must be strictly after start"
            )

    @property
    def label(self) -> str:
        """The sealed inclusive-end form, for reports."""
        last = pd.Timestamp(self.end_exclusive) - pd.Timedelta(days=1)
        return f"{self.start}..{last.date()}"

    def contains(self, dates: pd.DatetimeIndex) -> np.ndarray:
        """Boolean mask: which of ``dates`` fall inside the excluded span."""
        idx = pd.DatetimeIndex(dates)
        lo = pd.Timestamp(self.start)
        hi = pd.Timestamp(self.end_exclusive)
        return np.asarray((idx >= lo) & (idx < hi), dtype=bool)

    def intersects(self, start: str | pd.Timestamp, end_exclusive: str | pd.Timestamp) -> bool:
        """Does the half-open window ``[start, end_exclusive)`` overlap the span?"""
        return bool(
            pd.Timestamp(start) < pd.Timestamp(self.end_exclusive)
            and pd.Timestamp(end_exclusive) > pd.Timestamp(self.start)
        )

    def window_intersects(self, starts: pd.DatetimeIndex, months: int) -> np.ndarray:
        """L3's block rule: True where ``[start, start+months)`` touches the span.

        Any overlap drops the block -- a block that merely ENDS inside the decade
        still trains on excluded months.
        """
        if months < 1:
            raise ValueError("months must be >= 1")
        idx = pd.DatetimeIndex(starts)
        ends = idx + pd.DateOffset(months=months)  # exclusive
        lo = pd.Timestamp(self.start)
        hi = pd.Timestamp(self.end_exclusive)
        return np.asarray((idx < hi) & (pd.DatetimeIndex(ends) > lo), dtype=bool)


#: The sealed span: the 1970s, inclusive of 1979-12.
SEVERE_TEST_EXCLUSION = ExclusionSpan(start="1970-01-01", end_exclusive="1980-01-01")


def contains_or_false(span: ExclusionSpan | None, dates: pd.DatetimeIndex) -> np.ndarray:
    """:meth:`ExclusionSpan.contains`, or an all-False mask when ``span`` is None.

    The primary (full-sample) path passes ``None`` everywhere, so every call site
    can be written once and the primary behaviour is the identity by construction.
    """
    if span is None:
        return np.zeros(len(pd.DatetimeIndex(dates)), dtype=bool)
    return span.contains(dates)


def segments_outside(dates: pd.DatetimeIndex, span: ExclusionSpan | None) -> list[tuple[int, int]]:
    """Maximal contiguous ``[lo, hi)`` index runs of ``dates`` outside ``span``.

    ``span=None`` returns the single whole-range segment, so the primary path is
    unchanged. Empty runs are never emitted; a fully excluded grid returns ``[]``.
    """
    idx = pd.DatetimeIndex(dates)
    if span is None:
        return [(0, len(idx))] if len(idx) else []
    inside = span.contains(idx)
    segments: list[tuple[int, int]] = []
    lo: int | None = None
    for i, bad in enumerate(inside):
        if bad:
            if lo is not None:
                segments.append((lo, i))
                lo = None
        elif lo is None:
            lo = i
    if lo is not None:
        segments.append((lo, len(idx)))
    return segments
