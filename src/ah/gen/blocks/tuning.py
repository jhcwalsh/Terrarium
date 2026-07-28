"""WP2.8 tuning — the forking-paths record (SEALED: pre-registration
``tuning_protocol``, binding on this module).

- ``search_surface: validation_folds_only`` — every score in this module is a
  validation-fold score from :func:`ah.gen.blocks.train.evaluate_fold_scores`;
  the holdout is unreachable (token minted only in ``ah.eval.g2``, which this
  package never imports) and nothing here reads a negative control or an
  enforce-tier threshold.
- ``trial_budget_per_system: 40`` (:data:`TRIAL_BUDGET`, asserted equal to the
  sealed YAML by test), counted as DISTINCT CONFIG HASHES logged to the
  experiment store INCLUDING abandoned/crashed runs: a trial is logged as
  ``trial_started`` BEFORE its first training step, so a crash still spends
  budget — otherwise "restart it and don't count it" is an unbounded search.
  Exhausting the budget without a satisfactory config is reported as such,
  never extended here (an extension is a dated amendment).
- Every trial logs config hash, git SHA, seed, and per-fold validation scores
  to ``experiments/<exp_id>/``; :func:`validate_log` is the machine check —
  an incomplete log makes :func:`select_config` raise, invalidating selection.
- Selection: the final config minimizes the SEALED closed form
  ``S = mean_folds(generative_objective) + selection_lambda *
  mean_folds(D4_tail_elicitability_auxiliary)`` with ``selection_lambda`` =
  :data:`ah.gen.blocks.train.SELECTION_LAMBDA` = 1.0 PINNED (never read off
  trials; DN-1.1's lambda_tail is a different, searchable quantity). Ties break by
  lower sampling NFE. The sealed binding consequence: BOTH terms of S are
  reported separately, with their scales, wherever a selection is reported.

The search space itself lives in a YAML file whose SHA-256 is recorded in the
log before the first trial runs, so "stated in advance" is machine-checkable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ah.experiment import config_hash, git_sha
from ah.gen.blocks import data as bd
from ah.gen.blocks.diffusion import DiffusionConfig
from ah.gen.blocks.train import SELECTION_LAMBDA, TrainResult, train_diffusion

__all__ = [
    "TRIAL_BUDGET",
    "TuningError",
    "load_search_space",
    "read_log",
    "run_search",
    "sample_trial_configs",
    "select_config",
    "validate_log",
]

#: Sealed ``tuning_protocol.trial_budget_per_system`` (asserted by test).
TRIAL_BUDGET = 40

LOG_NAME = "tuning-log.jsonl"


class TuningError(RuntimeError):
    """A tuning-protocol violation — never caught and continued past."""


def load_search_space(path: str | Path) -> tuple[dict[str, list[Any]], dict[str, Any], str]:
    """Read the committed search-space YAML; returns (space, budget, file sha256).

    ``search_space`` maps DiffusionConfig field -> list of candidate values;
    ``budget`` carries the trial-cap parameters (max steps per trial etc.). The
    file's SHA-256 goes into the log header — the search space cannot be edited
    after the fact without the log showing it.
    """
    path = Path(path)
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    space = doc["search_space"]
    budget = doc["trial_budget_params"]
    unknown = sorted(set(space) - set(DiffusionConfig.__dataclass_fields__))
    if unknown:
        raise TuningError(f"search space names unknown DiffusionConfig fields: {unknown}")
    return space, budget, hashlib.sha256(raw).hexdigest()


def sample_trial_configs(
    space: dict[str, list[Any]], n_trials: int, seed: int
) -> list[DiffusionConfig]:
    """Deterministic random search: uniform independent draws, de-duplicated."""
    rng = np.random.Generator(np.random.PCG64(seed))
    keys = sorted(space)
    configs: list[DiffusionConfig] = []
    seen: set[str] = set()
    attempts = 0
    while len(configs) < n_trials:
        attempts += 1
        if attempts > 200 * n_trials:
            raise TuningError("search space too small to draw the requested distinct trials")
        choice = {k: space[k][int(rng.integers(len(space[k])))] for k in keys}
        config = DiffusionConfig(**choice)
        h = config_hash(config.as_dict())
        if h in seen:
            continue
        seen.add(h)
        configs.append(config)
    return configs


def _append(log_path: Path, entry: dict[str, Any]) -> None:
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def read_log(log_path: str | Path) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def distinct_started_hashes(entries: list[dict[str, Any]]) -> set[str]:
    return {e["config_hash"] for e in entries if e.get("event") == "trial_started"}


def run_search(
    dataset: bd.BlockDataset,
    configs: list[DiffusionConfig],
    *,
    exp_dir: str | Path,
    seed: int,
    trial_max_steps: int,
    trial_eval_every: int,
    trial_patience: int,
    device: str = "cpu",
    n_rep_eval: int = 8,
    space_sha256: str = "",
    log: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Run trials under the sealed budget; every trial logged, crashes included.

    Idempotent-ish by config hash: a config already STARTED in the log is not
    restarted (its budget is already spent). Returns the full log entries.
    """
    exp_dir = Path(exp_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)
    log_path = exp_dir / LOG_NAME
    entries = read_log(log_path)
    if not entries:
        _append(
            log_path,
            {
                "event": "search_header",
                "search_space_sha256": space_sha256,
                "git_sha": git_sha(),
                "seed": seed,
                "selection_lambda": SELECTION_LAMBDA,
                "trial_budget": TRIAL_BUDGET,
                "n_folds": len(dataset.fold_indices),
                "trial_max_steps": trial_max_steps,
            },
        )

    for i, config in enumerate(configs):
        h = config_hash(config.as_dict())
        entries = read_log(log_path)
        started = distinct_started_hashes(entries)
        if h in started:
            continue
        if len(started) >= TRIAL_BUDGET:
            _append(
                log_path,
                {
                    "event": "budget_exhausted",
                    "message": (
                        f"sealed budget of {TRIAL_BUDGET} distinct started configs "
                        f"reached; remaining candidates NOT run (an extension is a "
                        f"dated amendment, not a restart)"
                    ),
                },
            )
            break
        trial_seed = seed + 1000 * (len(started) + 1)
        _append(
            log_path,
            {
                "event": "trial_started",
                "trial": i,
                "config": config.as_dict(),
                "config_hash": h,
                "git_sha": git_sha(),
                "seed": trial_seed,
            },
        )
        if log is not None:
            log(f"trial {i} start  {h}  (started so far: {len(started) + 1}/{TRIAL_BUDGET})")
        try:
            result: TrainResult = train_diffusion(
                dataset,
                config,
                seed=trial_seed,
                max_steps=trial_max_steps,
                eval_every=trial_eval_every,
                patience=trial_patience,
                device=device,
                n_rep_eval=n_rep_eval,
            )
        except Exception as exc:  # a crashed trial still spent its budget
            _append(
                log_path,
                {
                    "event": "trial_crashed",
                    "trial": i,
                    "config_hash": h,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            if log is not None:
                log(f"trial {i} CRASHED: {type(exc).__name__}: {exc}")
            continue
        _append(
            log_path,
            {
                "event": "trial_completed",
                "trial": i,
                "config_hash": h,
                "seed": trial_seed,
                "per_fold_gen": result.per_fold_gen,
                "per_fold_aux": result.per_fold_aux,
                "gen_term": result.best_gen_term,
                "aux_term": result.best_aux_term,
                "s_value": result.best_s,
                "eval_nfe": int(config.eval_nfe),
                "best_step": result.best_step,
                "steps_run": result.steps_run,
                "stopped_early": result.stopped_early,
                "checkpoint_hash": result.checkpoint_hash,
            },
        )
        if log is not None:
            log(
                f"trial {i} done  S={result.best_s:.4f} "
                f"(gen {result.best_gen_term:.4f} aux {result.best_aux_term:.4f})"
            )
    return read_log(log_path)


def validate_log(entries: list[dict[str, Any]], *, n_folds: int) -> None:
    """The machine check the sealed protocol requires; raises TuningError.

    Complete = every started trial carries config hash, git SHA and seed; every
    completed trial carries per-fold scores for every fold; distinct started
    hashes within budget; every completed/crashed trial was started.
    """
    started: dict[str, dict[str, Any]] = {}
    for e in entries:
        event = e.get("event")
        if event == "trial_started":
            for key in ("config_hash", "git_sha", "seed", "config"):
                if key not in e:
                    raise TuningError(f"trial_started entry missing '{key}': {e}")
            started[e["config_hash"]] = e
        elif event in ("trial_completed", "trial_crashed"):
            if e.get("config_hash") not in started:
                raise TuningError(f"{event} for a config never logged as started: {e}")
            if event == "trial_completed":
                for key in ("per_fold_gen", "per_fold_aux", "s_value", "eval_nfe", "seed"):
                    if key not in e:
                        raise TuningError(f"trial_completed entry missing '{key}': {e}")
                if len(e["per_fold_gen"]) != n_folds or len(e["per_fold_aux"]) != n_folds:
                    raise TuningError(
                        f"trial {e.get('trial')} logged "
                        f"{len(e['per_fold_gen'])}/{len(e['per_fold_aux'])} fold scores; "
                        f"{n_folds} folds required — incomplete log invalidates selection"
                    )
    if len(started) > TRIAL_BUDGET:
        raise TuningError(f"{len(started)} distinct configs started > sealed budget {TRIAL_BUDGET}")
    if not started:
        raise TuningError("empty tuning log — nothing to select from")


def select_config(entries: list[dict[str, Any]], *, n_folds: int) -> dict[str, Any]:
    """Apply the SEALED selection criterion to a validated log.

    S is recomputed from the logged per-fold scores (mean over folds), never
    trusted from the stored scalar; ``selection_lambda`` is the pinned 1.0.
    Exact ties break by lower ``eval_nfe``, then by config hash (deterministic).
    Returns the selection record with BOTH terms separately (sealed consequence).
    """
    validate_log(entries, n_folds=n_folds)
    completed = [e for e in entries if e.get("event") == "trial_completed"]
    if not completed:
        raise TuningError(
            "no trial completed inside the sealed budget: reported as such; "
            "selection is impossible without a dated amendment"
        )

    def key(e: dict[str, Any]) -> tuple[float, int, str]:
        gen = float(np.mean(e["per_fold_gen"]))
        aux = float(np.mean(e["per_fold_aux"]))
        return (gen + SELECTION_LAMBDA * aux, int(e["eval_nfe"]), e["config_hash"])

    best = min(completed, key=key)
    gen = float(np.mean(best["per_fold_gen"]))
    aux = float(np.mean(best["per_fold_aux"]))
    started = next(
        e
        for e in entries
        if e.get("event") == "trial_started" and e["config_hash"] == best["config_hash"]
    )
    return {
        "event": "selected",
        "config_hash": best["config_hash"],
        "config": started["config"],
        "seed": best["seed"],
        "s_value": gen + SELECTION_LAMBDA * aux,
        "gen_term": gen,
        "aux_term": aux,
        "selection_lambda": SELECTION_LAMBDA,
        "eval_nfe": int(best["eval_nfe"]),
        "n_trials_started": len(distinct_started_hashes(entries)),
        "n_trials_completed": len(completed),
        "trial_budget": TRIAL_BUDGET,
    }


def mark_selected(exp_dir: str | Path, selection: dict[str, Any]) -> None:
    """Append the selection record to the log (the final forking-paths entry)."""
    _append(Path(exp_dir) / LOG_NAME, selection)


def selection_from_log_dir(exp_dir: str | Path, *, n_folds: int) -> dict[str, Any]:
    entries = read_log(Path(exp_dir) / LOG_NAME)
    return select_config(entries, n_folds=n_folds)
