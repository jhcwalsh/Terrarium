"""The narrative-blind projection of a WorldSpec.

The engine (WP0.4) and institution simulator (WP0.5) consume a ``NumericWorld``,
never a ``WorldSpec``. ``NumericWorld`` structurally omits ``narrative`` (and
``provenance``): there is no attribute to read, so the narrative-blindness
guarantee ("no engine component may read the narrative object", WORLDSPEC.md §1)
holds by construction, not by convention. A companion test
(``tests/test_narrative_blindness.py``) additionally scans the engine/institution
source for any reference to ``narrative`` as a belt-and-suspenders guard.
"""

from __future__ import annotations

from dataclasses import dataclass

from ah.core.worldspec import (
    EngineDefaults,
    FactorConditions,
    Horizon,
    Regimes,
    Structural,
    WorldSpec,
)


@dataclass(frozen=True)
class NumericWorld:
    """Everything the engine may see — and nothing it may not.

    Deliberately excludes ``narrative`` and ``provenance``. ``world_id`` and
    ``spec_version`` are carried for lineage/labelling only.
    """

    world_id: str
    spec_version: str
    horizon: Horizon
    regimes: Regimes
    factor_conditions: FactorConditions
    structural: Structural
    engine_defaults: EngineDefaults


def project_numeric(world: WorldSpec) -> NumericWorld:
    """Project a validated WorldSpec down to its engine-visible fields."""
    return NumericWorld(
        world_id=world.world_id,
        spec_version=world.spec_version,
        horizon=world.horizon,
        regimes=world.regimes,
        factor_conditions=world.factor_conditions,
        structural=world.structural,
        engine_defaults=world.engine_defaults,
    )
