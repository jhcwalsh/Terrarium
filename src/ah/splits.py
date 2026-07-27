"""Train / validation / holdout splits with a leakage guard (STEP2 §WP2.1).

Leakage is the whole game (STEP2 §6). The holdout is reachable only through a
:class:`FinalEvaluationToken` that is *constructed only in* ``ah.eval.g2`` — training
and tuning code paths cannot mint one, and an import-graph test proves the gen/train
modules never import ``ah.eval.g2``. Reference statistics (WP2.2) and normalization
(WP2.5/2.8) are computed on train+validation only; this module is the single door to
the data by split.

Split dates here are **sealed**, not provisional: WP2.3 froze them in
``pre-registration.yaml``'s ``splits:`` block on 2026-07-26, that document is normative
if the two ever disagree, and ``ah.eval.prereg.verify`` compares this module's
:data:`SPLITS` against it on every battery invocation (RFR-6). Moving a boundary is a
dated amendment plus a re-seal, not an edit. The holdout is the final ~5 years and is
spent exactly once (WP2.11).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Split:
    name: str
    start: str  # inclusive, YYYY-MM-DD
    end: str  # exclusive, YYYY-MM-DD


# The sealed campaign splits (pre-registration.yaml `splits:`, WP2.3, 2026-07-26).
# Holdout = final ~5 years. Claims-sweep correction: this comment read "Provisional
# campaign splits (sealed for real in WP2.3)" after WP2.3 had sealed them.
TRAIN = Split("train", "1871-01-01", "2011-01-01")
VALIDATION = Split("validation", "2011-01-01", "2021-01-01")
HOLDOUT = Split("holdout", "2021-01-01", "2026-08-01")
SPLITS: dict[str, Split] = {s.name: s for s in (TRAIN, VALIDATION, HOLDOUT)}
# The reference/normalization surface — never the holdout.
TRAIN_VAL = ("train", "validation")


class HoldoutAccessError(RuntimeError):
    """Raised when the holdout is requested without a FinalEvaluationToken."""


@dataclass(frozen=True)
class FinalEvaluationToken:
    """Proof-of-purpose for touching the holdout. Mint ONLY via ``ah.eval.g2``.

    The class lives here so callers can type against it, but the only sanctioned
    constructor is ``ah.eval.g2.final_evaluation_token()``; the import-graph test
    (``tests/test_leakage_guard.py``) proves training modules never import that module.
    """

    purpose: str = "final-evaluation"


Reader = Callable[[str], pd.DataFrame]


class DataAccess:
    """The single door to campaign data, gated by split.

    ``reader(series_id)`` returns a full ``(date, value)`` frame (e.g. a catalog read
    pinned to the campaign vintage). ``frame(series_id, split)`` returns only the rows
    inside that split's span; the holdout additionally requires a token.
    """

    def __init__(self, reader: Reader) -> None:
        self._reader = reader

    def frame(
        self, series_id: str, split: str, *, token: FinalEvaluationToken | None = None
    ) -> pd.DataFrame:
        if split not in SPLITS:
            raise KeyError(f"unknown split '{split}'; known: {list(SPLITS)}")
        if split == "holdout" and not isinstance(token, FinalEvaluationToken):
            raise HoldoutAccessError(
                "holdout access requires a FinalEvaluationToken minted in ah.eval.g2 "
                "(final-evaluation only, spent once in WP2.11)"
            )
        span = SPLITS[split]
        df = self._reader(series_id)
        d = df.assign(date=pd.to_datetime(df["date"]))
        mask = (d["date"] >= pd.Timestamp(span.start)) & (d["date"] < pd.Timestamp(span.end))
        return d.loc[mask].reset_index(drop=True)

    def train_val(self, series_id: str) -> pd.DataFrame:
        """The reference/normalization surface: train + validation, holdout excluded."""
        frames = [self.frame(series_id, s) for s in TRAIN_VAL]
        return pd.concat(frames, ignore_index=True).sort_values(by="date", ignore_index=True)
