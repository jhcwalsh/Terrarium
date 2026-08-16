"""The unratified probe config — how a workbench with 50 open parameters is run.

**This module takes no decisions and neither does the file it writes.**

The workbench's shipped config is ``voices.yaml``, in which every tunable is
``UNRESOLVED``; a build against it fails with the list, which is the correct
behaviour and the task's headline requirement. But a workbench that can only
fail has told nobody whether the severity cut-points produce four severity-3
events or forty — and that measurement is the other half of what the task asks
for (acceptance 9: nine panels rendered on a real world).

So the build can be pointed at a **probe config**, generated here by a single
mechanical rule:

    every UNRESOLVED key takes ``params.PARAMETERS[key].candidates[0]``

`candidates[0]` is not a recommendation and the registry says so — it is the
first value DN-9 or the skeleton's own comments raise. The rule is stated,
auditable, reversible, and deliberately dumb, because the failure this task
exists to prevent is a *silently* chosen threshold becoming canon. Every value
the probe uses is still listed as open in ``UNRESOLVED.md``, the generated file
carries the banner below on every read, and the manifest and both HTML artifacts
stamp ``config_status: PROBE-UNRATIFIED``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ah.narration.config import UNRESOLVED, VoicesConfig
from ah.narration.params import by_key

__all__ = ["BANNER", "PROBE_STATUS", "RATIFIED_STATUS", "probe_document", "render_probe_yaml"]

PROBE_STATUS = "PROBE-UNRATIFIED"
RATIFIED_STATUS = "RATIFIED"

BANNER = """\
# =========================================================================
# GENERATED — DO NOT HAND-EDIT, DO NOT TREAT AS A DECISION
# =========================================================================
# This file is `voices.yaml` with every UNRESOLVED key replaced by the FIRST
# CANDIDATE listed for it in src/ah/narration/UNRESOLVED.md, by the mechanical
# rule in src/ah/narration/probe.py. It exists so the workbench can be RUN and
# MEASURED while its parameters are open.
#
# NOTHING IN HERE HAS BEEN RATIFIED. `candidates[0]` is the first value DN-9 or
# the voices.yaml skeleton raises, not a recommendation and not a ranking.
# Every key below is still an open decision in UNRESOLVED.md.
#
# Regenerate:  python -m ah.narration probe --voices voices.yaml --out <path>
# =========================================================================
"""


def _fill(node: Any, prefix: str, registry: dict[str, Any], filled: list[str]) -> Any:
    if isinstance(node, dict):
        return {
            name: _fill(child, f"{prefix}.{name}" if prefix else str(name), registry, filled)
            for name, child in node.items()
        }
    if node == UNRESOLVED:
        param = registry.get(prefix)
        if param is None:
            raise KeyError(
                f"voices.yaml carries UNRESOLVED key '{prefix}' with no entry in "
                "ah.narration.params — every open key must be described in UNRESOLVED.md "
                "before it can be probed."
            )
        filled.append(prefix)
        return param.candidates[0]
    return node


def probe_document(config: VoicesConfig) -> tuple[dict[str, Any], list[str]]:
    """``(document, filled_keys)`` — the probe form of ``config``."""
    filled: list[str] = []
    document = _fill(config.raw, "", by_key(), filled)
    document["config_status"] = PROBE_STATUS
    document["probe_filled_keys"] = sorted(filled)
    return document, sorted(filled)


def render_probe_yaml(config: VoicesConfig) -> str:
    """The probe config as YAML text, banner included."""
    document, _ = probe_document(config)
    body = yaml.safe_dump(document, sort_keys=True, allow_unicode=True, default_flow_style=False)
    return BANNER + body


def write_probe(config: VoicesConfig, out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_probe_yaml(config), encoding="utf-8", newline="\n")
    return out
