"""WP2.1 acceptance: experiment store + config hashing."""

from __future__ import annotations

from pathlib import Path

from ah.experiment import ExperimentStore, config_hash, git_sha

NOW = "2026-07-24T00:00:00"


def test_config_hash_is_deterministic_and_order_independent() -> None:
    a = config_hash({"lr": 0.001, "layers": 4})
    b = config_hash({"layers": 4, "lr": 0.001})  # key order should not matter
    assert a == b
    assert config_hash({"lr": 0.002, "layers": 4}) != a


def test_create_load_list(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path)
    cfg = {"model": "diffusion", "seed": 0, "lr": 3e-4}
    meta = store.create("exp-001", cfg, seed=7, vintage_id="2026-07-24", created_at=NOW)
    assert meta.config_hash == config_hash(cfg)
    assert meta.seed == 7
    assert store.list() == ["exp-001"]
    m2, c2 = store.load("exp-001")
    assert m2 == meta
    assert c2 == cfg


def test_diff(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path)
    store.create("a", {"lr": 1e-3, "depth": 4}, seed=1, vintage_id="v", created_at=NOW)
    store.create("b", {"lr": 2e-3, "depth": 4}, seed=1, vintage_id="v", created_at=NOW)
    diff = store.diff("a", "b")
    assert diff == {"lr": (1e-3, 2e-3)}


def test_metrics_record(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path)
    store.create("a", {"x": 1}, seed=1, vintage_id="v", created_at=NOW)
    store.record_metrics("a", {"loss": 0.42})
    assert (tmp_path / "a" / "metrics.json").exists()


def test_git_sha_is_a_string() -> None:
    assert isinstance(git_sha(), str)
