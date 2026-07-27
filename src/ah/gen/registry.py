"""Generator plugin registry (STEP2 §WP2.1).

Resolves a WorldSpec ``engine_defaults.generator_id`` to a concrete generator factory.
Registration is explicit; unknown ids error clearly.
"""

from __future__ import annotations

from collections.abc import Callable

from ah.core.numericworld import NumericWorld
from ah.gen.base import Generator

GeneratorFactory = Callable[[], Generator]

_REGISTRY: dict[str, GeneratorFactory] = {}


class UnknownGeneratorError(KeyError):
    """Raised when a generator_id has no registered factory."""


def register(generator_id: str, factory: GeneratorFactory) -> None:
    _REGISTRY[generator_id] = factory


def registered() -> list[str]:
    return sorted(_REGISTRY)


def snapshot() -> dict[str, GeneratorFactory]:
    """A shallow copy of the registry's current contents.

    For a caller that registers generators temporarily (a negative-control suite, a
    test fixture) and must put the registry back exactly as found: pair with
    :func:`restore`. Public so such a caller need not reach into :data:`_REGISTRY`
    directly.
    """
    return dict(_REGISTRY)


def restore(saved: dict[str, GeneratorFactory]) -> None:
    """Replace the registry's contents with ``saved`` (see :func:`snapshot`)."""
    _REGISTRY.clear()
    _REGISTRY.update(saved)


def resolve(generator_id: str) -> Generator:
    if generator_id not in _REGISTRY:
        raise UnknownGeneratorError(
            f"no generator registered for '{generator_id}'; registered: {registered()}"
        )
    return _REGISTRY[generator_id]()


def resolve_for_world(world: NumericWorld) -> Generator:
    return resolve(world.engine_defaults.generator_id)
