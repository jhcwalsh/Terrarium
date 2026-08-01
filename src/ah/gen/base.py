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


@dataclass(frozen=True)
class AbsentLayer:
    """An explicit, reasoned absence of a generator layer (WP2R.4).

    The generator-output contract refuses silent omission: a generator that has
    no regime path or no slow-state layer says so *here*, at construction, in
    its own words — and :func:`ah.gen.output.build_document` turns this into the
    schema's ``{"absent": true, "reason": ...}`` block. A bare ``None`` on the
    ensemble means "this generator has not adopted the output contract yet",
    and the document builder raises on it rather than inventing a reason.
    """

    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("AbsentLayer needs a non-empty reason")


@dataclass(frozen=True)
class RegimeRecord:
    """The regime path an ensemble was generated under (WP2R.4).

    ``labels``: ``(n_paths, months)`` integer codes into ``legend`` — for the
    hierarchical systems these are the operative labels (crisis windows
    overlaid), for bootstrap-v1 the historical labels of the rows each month
    was drawn from. ``mode`` records how the path arose (``semimarkov``, a
    WorldSpec regimes.mode, or a generator-specific string), verbatim from the
    run; ``ruleset_version`` names the ruleset the labels are defined against.
    """

    labels: np.ndarray
    legend: tuple[str, ...]
    mode: str
    ruleset_version: str


@dataclass(frozen=True)
class SlowStateRecord:
    """The slow-state (L1) paths an ensemble was generated under (WP2R.4).

    ``states``: ``(n_paths, months, n_states)`` in ``names`` order. ``layer``
    is ``"simulated"`` for a posterior-simulated climate layer and
    ``"frozen-posterior-mean"`` for ablation system C's frozen variant — the
    generator-output contract's enum, asserted at document time, not here.
    """

    states: np.ndarray
    names: tuple[str, ...]
    layer: str


@dataclass
class Ensemble:
    """Simulated paths, shape ``(n_paths, months, n_factors)``, with full lineage.

    ``regimes`` and ``slow_states`` are optional because not every generator
    produces them (bootstrap-v1 has no slow-state layer). The generator-output
    contract (``schemas/generator-output-v1.0.schema.json``, WP2R.4) makes the
    absence explicit-with-reason at document time; here it is simply ``None``.
    """

    paths: np.ndarray
    factor_names: list[str]
    meta: EnsembleMeta
    regimes: RegimeRecord | AbsentLayer | None = None
    slow_states: SlowStateRecord | AbsentLayer | None = None

    def __post_init__(self) -> None:
        if self.paths.ndim != 3:
            raise ValueError(f"paths must be (n_paths, months, n_factors); got {self.paths.shape}")
        if self.paths.shape[2] != len(self.factor_names):
            raise ValueError("paths last dim must match len(factor_names)")
        if isinstance(self.regimes, RegimeRecord):
            expected = self.paths.shape[:2]
            if tuple(self.regimes.labels.shape) != expected:
                raise ValueError(
                    f"regimes.labels must be (n_paths, months) {expected}; "
                    f"got {self.regimes.labels.shape}"
                )
            if not self.regimes.legend:
                raise ValueError("regimes.legend must not be empty")
        if isinstance(self.slow_states, SlowStateRecord):
            expected3 = (*self.paths.shape[:2], len(self.slow_states.names))
            if tuple(self.slow_states.states.shape) != expected3:
                raise ValueError(
                    f"slow_states.states must be (n_paths, months, n_states) {expected3}; "
                    f"got {self.slow_states.states.shape}"
                )

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
