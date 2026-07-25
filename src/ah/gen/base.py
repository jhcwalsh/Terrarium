"""Generator protocol + Ensemble container (STEP2 §WP2.1).

Every generator (bootstrap benchmark, hierarchical system) implements the same
``Generator`` protocol and returns an :class:`Ensemble` whose metadata pins exactly
what produced it — generator_id, checkpoint/config hashes, vintage id, seed, and the
conditioning record — so any ensemble is reproducible from its RunRecord.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np

from ah.core.numericworld import NumericWorld


class UnknownFactorError(ValueError):
    """Raised when :meth:`Ensemble.factor` is asked for a factor the ensemble lacks.

    Named, rather than the bare ``ValueError: 'x' is not in list`` that ``list.index``
    raises from deep inside a caller's weighted sum: the message identifies the factor
    asked for and the full set the ensemble actually carries. The likely first
    real-world trigger is ``commodities``, which the manifest declares but no Step-1
    series sources yet (see ``pre-registration.yaml``'s
    ``rationale.d4_commodities_consequence``).
    """

    def __init__(self, name: str, available: tuple[str, ...]) -> None:
        super().__init__(f"ensemble has no factor '{name}'; available factors: {list(available)}")
        self.name = name
        self.available = available


@dataclass(frozen=True)
class EnsembleMeta:
    """Metadata pinning exactly what produced an :class:`Ensemble`.

    ``active_blocks`` records which factor blocks (:class:`ah.factors.FactorManifest`)
    the ensemble was generated over, e.g. ``("global", "us")`` — so any ensemble is
    reconstructible against the block layer that produced it (WP2.1b Item 2).
    """

    generator_id: str
    vintage_id: str
    seed: int
    n_paths: int
    months: int
    checkpoint_hash: str | None = None
    config_hash: str | None = None
    conditioning: dict[str, Any] = field(default_factory=dict)
    active_blocks: tuple[str, ...] = ()


@dataclass
class Ensemble:
    """Simulated paths, shape ``(n_paths, months, n_factors)``, with full lineage."""

    paths: np.ndarray
    factor_names: list[str]
    meta: EnsembleMeta

    def __post_init__(self) -> None:
        if self.paths.ndim != 3:
            raise ValueError(f"paths must be (n_paths, months, n_factors); got {self.paths.shape}")
        if self.paths.shape[2] != len(self.factor_names):
            raise ValueError("paths last dim must match len(factor_names)")

    @property
    def n_paths(self) -> int:
        return int(self.paths.shape[0])

    @property
    def months(self) -> int:
        return int(self.paths.shape[1])

    def factor(self, name: str) -> np.ndarray:
        """The ``(n_paths, months)`` slab for one factor.

        Raises :class:`UnknownFactorError` if the ensemble does not carry ``name``.
        """
        try:
            index = self.factor_names.index(name)
        except ValueError as exc:
            raise UnknownFactorError(name, tuple(self.factor_names)) from exc
        return self.paths[:, :, index]


@runtime_checkable
class Generator(Protocol):
    generator_id: str

    def fit(self, data: Any) -> None: ...

    def sample(self, world: NumericWorld, n_paths: int, seed: int) -> Ensemble: ...
