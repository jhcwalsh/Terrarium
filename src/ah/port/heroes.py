"""Hero funds (WP3.10) — named individual funds whose numbers are real.

Splits a cohort into 3-5 synthetic individual funds (``n_funds = 1`` each),
dispersion-drawn per the platform seed rule, with the RECONCILIATION INVARIANT
the plan demands: every numeric field of the heroes sums exactly to the parent
cohort's — manager letters and gating events need real arithmetic behind them
(Step 4's numeric-fidelity gate), and a hero whose numbers don't add up to the
cohort is fiction of the wrong kind.

Names are supplied by the caller; binding them to the World Bible cast is
Step 4's job, deliberately not this module's.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ah.port.cohort import ClosedEndCohort

SEED_STRIDE = 7919


class HeroError(ValueError):
    """A split that cannot reconcile, or bad inputs."""


def split_cohort(
    cohort_document: dict[str, Any],
    *,
    names: tuple[str, ...],
    seed: int,
    dispersion_sigma: float = 0.35,
) -> list[dict[str, Any]]:
    """The cohort's state, split into one document per hero fund.

    Weights are log-normal draws (path ``k`` on ``PCG64(seed + 7919 k)``),
    normalized to sum to one, so every extensive field splits exactly and the
    reconciliation test is an identity rather than an approximation. Each hero
    carries ``n_funds = 1``, its own ``dispersion_draw`` (the quantile of its
    weight among the draws — larger funds are not automatically better funds,
    but the draw feeds WP3.4's dispersion machinery), and its name.
    """
    if not 3 <= len(names) <= 5:
        raise HeroError("the plan asks for 3-5 hero funds per world")
    if len(set(names)) != len(names):
        raise HeroError("hero names must be distinct")
    if dispersion_sigma <= 0.0:
        raise HeroError("dispersion_sigma must be positive")

    parent = ClosedEndCohort.from_document(cohort_document)  # validates the contract
    raw = np.array(
        [
            float(
                np.random.Generator(np.random.PCG64(seed + SEED_STRIDE * k)).lognormal(
                    0.0, dispersion_sigma
                )
            )
            for k in range(len(names))
        ]
    )
    weights = raw / raw.sum()
    quantiles = raw.argsort().argsort() / max(1, len(names) - 1)

    extensive_paths = (
        ("commitment", "committed"),
        ("commitment", "paid_in"),
        ("commitment", "unfunded"),
        ("commitment", "recallable_balance"),
        ("commitment", "cumulative_recycled"),
        ("value", "nav_true"),
        ("value", "nav_reported"),
        ("value", "cumulative_distributions"),
        ("flows", "calls"),
        ("flows", "distributions_income"),
        ("flows", "distributions_capital"),
        ("flows", "nav_growth"),
        ("flows", "fees_paid"),
        ("flows", "carry_crystallized"),
    )

    heroes: list[dict[str, Any]] = []
    for k, name in enumerate(names):
        doc = parent.to_document()
        doc["identity"] = {
            **doc["identity"],
            "n_funds": 1,
            "fund_name": name,
            "cohort_id": f"{doc['identity']['cohort_id']}-hero{k}",
        }
        doc["parameters"] = {**doc["parameters"], "dispersion_draw": float(quantiles[k])}
        for section, fieldname in extensive_paths:
            doc[section] = {
                **doc[section],
                fieldname: cohort_document[section][fieldname] * float(weights[k]),
            }
        ClosedEndCohort.from_document(doc)  # every hero is contract-valid
        heroes.append(doc)
    return heroes


def reconcile(
    cohort_document: dict[str, Any], hero_documents: list[dict[str, Any]], *, atol: float = 1e-9
) -> None:
    """Raise unless every extensive field of the heroes sums to the parent's."""
    for section in ("commitment", "value", "flows"):
        for fieldname, parent_value in cohort_document[section].items():
            total = sum(h[section][fieldname] for h in hero_documents)
            if abs(total - parent_value) > atol:
                raise HeroError(
                    f"{section}.{fieldname}: heroes sum to {total}, parent has "
                    f"{parent_value} — the numbers behind the letters must add up"
                )
