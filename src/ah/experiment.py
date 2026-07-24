"""Local-first experiment tracking (STEP2 §1, §WP2.1).

Each experiment records its config, config hash, git SHA, seed, and vintage under
``experiments/<exp_id>/`` — no external service. The config hash is deterministic
(canonical JSON) so identical configs produce identical hashes, and it is pinned into
the RunRecord for reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ah.core.digest import canonical_json


def config_hash(config: dict[str, Any]) -> str:
    return "cfg:" + hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()[:16]


def git_sha(default: str = "unknown") -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return out.stdout.strip() or default
    except Exception:
        return default


@dataclass(frozen=True)
class ExperimentMeta:
    exp_id: str
    config_hash: str
    git_sha: str
    seed: int
    vintage_id: str
    created_at: str


class ExperimentStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, exp_id: str) -> Path:
        return self.root / exp_id

    def create(
        self, exp_id: str, config: dict[str, Any], *, seed: int, vintage_id: str, created_at: str
    ) -> ExperimentMeta:
        d = self._dir(exp_id)
        d.mkdir(parents=True, exist_ok=True)
        meta = ExperimentMeta(exp_id, config_hash(config), git_sha(), seed, vintage_id, created_at)
        (d / "config.json").write_text(canonical_json(config), encoding="utf-8")
        (d / "meta.json").write_text(
            json.dumps(asdict(meta), indent=2, sort_keys=True), encoding="utf-8"
        )
        return meta

    def exists(self, exp_id: str) -> bool:
        return (self._dir(exp_id) / "meta.json").exists()

    def load(self, exp_id: str) -> tuple[ExperimentMeta, dict[str, Any]]:
        d = self._dir(exp_id)
        meta = ExperimentMeta(**json.loads((d / "meta.json").read_text(encoding="utf-8")))
        config = json.loads((d / "config.json").read_text(encoding="utf-8"))
        return meta, config

    def list(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "meta.json").exists())

    def record_metrics(self, exp_id: str, metrics: dict[str, Any]) -> None:
        (self._dir(exp_id) / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
        )

    def diff(self, exp_a: str, exp_b: str) -> dict[str, tuple[Any, Any]]:
        _, a = self.load(exp_a)
        _, b = self.load(exp_b)
        keys = set(a) | set(b)
        return {k: (a.get(k), b.get(k)) for k in sorted(keys) if a.get(k) != b.get(k)}
