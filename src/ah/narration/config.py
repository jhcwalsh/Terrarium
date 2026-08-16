"""Loading ``voices.yaml`` — the only place a tunable value may enter the layer.

Two rules, both enforced here rather than by convention:

1. **``UNRESOLVED`` is a sentinel, not a placeholder.** :meth:`VoicesConfig.get`
   raises on it. :func:`preflight` reads the whole registry
   (:mod:`ah.narration.params`) before any work starts, so the run fails with
   *every* key it would have needed rather than one key per re-run.
2. **There are no defaults.** :meth:`VoicesConfig.get` has no ``default``
   argument. A key absent from the file is an error naming the key, exactly as
   an unresolved one is.

Every read is recorded, so the manifest can stamp what the build actually
consumed and ``compare`` can attribute an output difference to a config key.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ah.narration.constants import KIND_OF_CLASS
from ah.narration.errors import NarrationError, UnresolvedParameter
from ah.narration.params import keys_for

__all__ = ["UNRESOLVED", "VoicesConfig", "load_voices"]

#: The sentinel. A string, so it survives a YAML round-trip unchanged and is
#: visible in a diff.
UNRESOLVED = "UNRESOLVED"

#: Where the open list lives, quoted in the failure message.
UNRESOLVED_DOC = "src/ah/narration/UNRESOLVED.md"


class ConfigError(NarrationError):
    """A structural problem with ``voices.yaml`` — a missing or malformed key."""


@dataclass
class VoicesConfig:
    """A loaded ``voices.yaml``, plus the record of what was read from it."""

    raw: dict[str, Any]
    path: Path
    reads: dict[str, Any] = field(default_factory=dict)

    # -- access ------------------------------------------------------------
    def _walk(self, key: str) -> Any:
        node: Any = self.raw
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise ConfigError(
                    f"voices.yaml ({self.path}) has no key '{key}'. "
                    "The narration layer has no defaults: add the key with the value "
                    f"UNRESOLVED and describe it in {UNRESOLVED_DOC}."
                )
            node = node[part]
        return node

    def has(self, key: str) -> bool:
        """True if the key exists at all (resolved or not)."""
        try:
            self._walk(key)
        except ConfigError:
            return False
        return True

    def is_unresolved(self, key: str) -> bool:
        """True if the key exists and still carries the sentinel."""
        return self._walk(key) == UNRESOLVED

    def get(self, key: str) -> Any:
        """The value at ``key``, recorded as a read.

        Raises :class:`~ah.narration.errors.UnresolvedParameter` if the value is
        the sentinel. There is deliberately no ``default``.
        """
        value = self._walk(key)
        if value == UNRESOLVED:
            raise UnresolvedParameter(
                [key], config_path=str(self.path), unresolved_doc=UNRESOLVED_DOC
            )
        self.reads[key] = value
        return value

    # -- lineage -----------------------------------------------------------
    def canonical(self) -> str:
        """The file's content as canonical JSON — the thing that is hashed."""
        return json.dumps(self.raw, sort_keys=True, separators=(",", ":"), default=str)

    def hash(self) -> str:
        """SHA-256 over the canonical form. Any value change moves this."""
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def unresolved_keys(self) -> tuple[str, ...]:
        """Every key in the file still carrying the sentinel, dotted, sorted."""
        found: list[str] = []

        def walk(node: Any, prefix: str) -> None:
            if isinstance(node, dict):
                for name, child in node.items():
                    walk(child, f"{prefix}.{name}" if prefix else str(name))
            elif node == UNRESOLVED:
                found.append(prefix)

        walk(self.raw, "")
        return tuple(sorted(found))

    def event_classes(self) -> tuple[str, ...]:
        """The classes declared in the file, in file order.

        ``kind`` is validated against :data:`~ah.narration.constants.KIND_OF_CLASS`
        rather than trusted: DN-9 is explicit that point-versus-state is
        structural, so a config that reclassifies a state class as a point class
        is a defect and not a configuration.
        """
        events = self.raw.get("events")
        if not isinstance(events, dict):
            raise ConfigError(f"voices.yaml ({self.path}) has no 'events' block")
        for cls, block in events.items():
            kind = block.get("kind") if isinstance(block, dict) else None
            expected = KIND_OF_CLASS.get(cls)
            if expected is None:
                raise ConfigError(f"voices.yaml declares unknown event class '{cls}'")
            if kind != expected:
                raise ConfigError(
                    f"voices.yaml declares {cls} as kind '{kind}'; the grammar fixes it as "
                    f"'{expected}'. Point-versus-state is structural (DN-9 §3.2): a state "
                    "class firing every period it holds is a defect, not a parameter."
                )
        return tuple(events)


def load_voices(path: str | Path) -> VoicesConfig:
    """Parse ``voices.yaml``. Does not resolve anything — see :func:`preflight`."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"voices config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError(f"voices config {path} did not parse to a mapping")
    config = VoicesConfig(raw=raw, path=path)
    config.event_classes()
    return config


def preflight(config: VoicesConfig, *, book_available: bool) -> None:
    """Fail once, with the whole list, before any narration work begins.

    Reads the open-parameter registry rather than the file: a key the registry
    knows about but the file has never heard of is just as unresolved, and this
    is where that is caught.
    """
    missing: list[str] = []
    for key in keys_for(book_available=book_available):
        if not config.has(key) or config.is_unresolved(key):
            missing.append(key)
    if missing:
        raise UnresolvedParameter(
            missing, config_path=str(config.path), unresolved_doc=UNRESOLVED_DOC
        )
