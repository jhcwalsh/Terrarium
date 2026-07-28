"""WP2.8 tuning tests — the sealed protocol is machine-checked, not remembered."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ah.experiment import config_hash
from ah.gen.blocks import data as bd
from ah.gen.blocks import diffusion as df
from ah.gen.blocks import train as tr
from ah.gen.blocks import tuning as tu
from joinery_common import make_climate_artifact, make_source

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def protocol():
    doc = yaml.safe_load((_REPO_ROOT / "pre-registration.yaml").read_text(encoding="utf-8"))
    return doc["tuning_protocol"]


class TestSealedConstants:
    """The in-code protocol constants must equal the SEALED YAML values."""

    def test_trial_budget_matches_the_seal(self, protocol):
        assert tu.TRIAL_BUDGET == int(protocol["trial_budget_per_system"]) == 40

    def test_selection_lambda_matches_the_seal_and_is_pinned(self, protocol):
        assert tr.SELECTION_LAMBDA == float(protocol["selection_lambda"]) == 1.0

    def test_search_surface_is_validation_folds_only(self, protocol):
        assert protocol["search_surface"] == "validation_folds_only"


def _entries(n_completed: int, budget_extra: int = 0, n_folds: int = 3):
    entries = [{"event": "search_header", "seed": 1}]
    for i in range(n_completed + budget_extra):
        h = f"cfg:{i:016d}"
        entries.append(
            {
                "event": "trial_started",
                "trial": i,
                "config": {"lr": 1e-4 * (i + 1), "eval_nfe": 31},
                "config_hash": h,
                "git_sha": "abc1234",
                "seed": 100 + i,
            }
        )
        if i < n_completed:
            entries.append(
                {
                    "event": "trial_completed",
                    "trial": i,
                    "config_hash": h,
                    "seed": 100 + i,
                    "per_fold_gen": [1.0 + 0.1 * i, 1.1 + 0.1 * i, 0.9 + 0.1 * i],
                    "per_fold_aux": [0.5, 0.5, 0.5],
                    "gen_term": 1.0 + 0.1 * i,
                    "aux_term": 0.5,
                    "s_value": 1.5 + 0.1 * i,
                    "eval_nfe": 31,
                }
            )
        else:
            entries.append({"event": "trial_crashed", "trial": i, "config_hash": h, "error": "x"})
    return entries


class TestLogValidation:
    def test_valid_log_passes(self):
        tu.validate_log(_entries(3), n_folds=3)

    def test_crashed_trials_count_against_budget(self):
        entries = _entries(38, budget_extra=2)  # 40 started, 2 crashed
        tu.validate_log(entries, n_folds=3)
        assert len(tu.distinct_started_hashes(entries)) == 40
        over = _entries(39, budget_extra=2)  # 41 started
        with pytest.raises(tu.TuningError, match="sealed budget"):
            tu.validate_log(over, n_folds=3)

    def test_incomplete_fold_scores_invalidate_selection(self):
        entries = _entries(2)
        entries[2]["per_fold_gen"] = [1.0, 1.1]  # only 2 of 3 folds
        with pytest.raises(tu.TuningError, match="incomplete log invalidates selection"):
            tu.select_config(entries, n_folds=3)

    def test_completed_without_started_is_invalid(self):
        entries = _entries(1)
        entries.append(
            {
                "event": "trial_completed",
                "trial": 99,
                "config_hash": "cfg:ghost",
                "seed": 1,
                "per_fold_gen": [1, 1, 1],
                "per_fold_aux": [0, 0, 0],
                "s_value": 1.0,
                "eval_nfe": 9,
            }
        )
        with pytest.raises(tu.TuningError, match="never logged as started"):
            tu.validate_log(entries, n_folds=3)

    def test_missing_git_sha_is_invalid(self):
        entries = _entries(1)
        del entries[1]["git_sha"]
        with pytest.raises(tu.TuningError, match="git_sha"):
            tu.validate_log(entries, n_folds=3)


class TestSelection:
    def test_selects_min_s_and_reports_both_terms_separately(self):
        entries = _entries(4)
        sel = tu.select_config(entries, n_folds=3)
        assert sel["config_hash"] == "cfg:0000000000000000"
        # BOTH terms present, separately, with the pinned lambda (sealed consequence).
        assert sel["gen_term"] == pytest.approx(1.0)
        assert sel["aux_term"] == pytest.approx(0.5)
        assert sel["selection_lambda"] == 1.0
        assert sel["s_value"] == pytest.approx(1.5)
        assert sel["n_trials_started"] == 4
        assert sel["trial_budget"] == 40

    def test_s_is_recomputed_from_fold_scores_not_trusted(self):
        entries = _entries(2)
        entries[2]["s_value"] = -999.0  # tampered scalar on the worse trial...
        entries[2]["per_fold_gen"] = [2.0, 2.0, 2.0]  # ...but folds say it is worse
        sel = tu.select_config(entries, n_folds=3)
        assert sel["config_hash"] == "cfg:0000000000000001"

    def test_exact_ties_break_by_lower_nfe(self):
        entries = _entries(2)
        for e in entries:
            if e["event"] == "trial_completed":
                e["per_fold_gen"] = [1.0, 1.0, 1.0]
                e["per_fold_aux"] = [0.5, 0.5, 0.5]
        entries[4]["eval_nfe"] = 9  # second trial, same S, cheaper sampling
        sel = tu.select_config(entries, n_folds=3)
        assert sel["config_hash"] == "cfg:0000000000000001"
        assert sel["eval_nfe"] == 9

    def test_no_completed_trial_is_reported_not_extended(self):
        entries = _entries(0, budget_extra=3)  # 3 started, all crashed
        with pytest.raises(tu.TuningError, match="reported as such"):
            tu.select_config(entries, n_folds=3)


class TestSearchSpaceFile:
    def test_committed_search_space_loads_and_names_real_fields(self):
        space, budget, sha = tu.load_search_space(
            _REPO_ROOT / "configs" / "wp28-diffusion-search-v1.yaml"
        )
        assert len(sha) == 64
        for key in (
            "lr",
            "d_model",
            "n_layers",
            "lambda_tail",
            "p_mean",
            "p_std",
            "dropout",
            "ema_decay",
            "cond_noise_std",
            "eval_nfe",
        ):
            assert key in space and len(space[key]) >= 2, key
        assert budget["trial_max_steps"] >= 500
        assert budget["n_trials"] <= tu.TRIAL_BUDGET

    def test_config_sampling_is_deterministic_and_deduplicated(self):
        space, _budget, _sha = tu.load_search_space(
            _REPO_ROOT / "configs" / "wp28-diffusion-search-v1.yaml"
        )
        a = tu.sample_trial_configs(space, 10, seed=5)
        b = tu.sample_trial_configs(space, 10, seed=5)
        assert [c.as_dict() for c in a] == [c.as_dict() for c in b]
        hashes = {config_hash(c.as_dict()) for c in a}
        assert len(hashes) == 10


class TestRealTuningLog:
    """The sealed 'tuning log complete and within budget' acceptance is
    MACHINE-CHECKED here against the actual campaign search record. The
    experiment store is local-first (gitignored), so the log is validated from
    whichever copy is present: experiments/ (the store) or artifacts/wp28 (the
    committed evidence copy); skip only when neither exists."""

    def _log_path(self):
        for p in (
            _REPO_ROOT / "experiments" / "l3a-diffusion-tuning-v1" / "tuning-log.jsonl",
            _REPO_ROOT / "artifacts" / "wp28" / "tuning-log.jsonl",
        ):
            if p.exists():
                return p
        return None

    def test_campaign_tuning_log_is_complete_and_within_budget(self):
        path = self._log_path()
        if path is None:
            pytest.skip("no campaign tuning log present (pre-search checkout)")
        entries = tu.read_log(path)
        header = entries[0]
        assert header["event"] == "search_header"
        assert header["selection_lambda"] == tr.SELECTION_LAMBDA == 1.0
        assert len(header["search_space_sha256"]) == 64
        n_folds = int(header["n_folds"])
        tu.validate_log(entries, n_folds=n_folds)
        assert len(tu.distinct_started_hashes(entries)) <= tu.TRIAL_BUDGET
        # once a selection is recorded, it must match a re-run of the sealed rule
        # (before that the search is in progress and only log completeness binds)
        recorded = [e for e in entries if e.get("event") == "selected"]
        if recorded:
            sel = tu.select_config(entries, n_folds=n_folds)
            assert recorded[-1]["config_hash"] == sel["config_hash"]
            assert recorded[-1]["s_value"] == pytest.approx(sel["s_value"])
            assert recorded[-1]["gen_term"] == pytest.approx(sel["gen_term"])
            assert recorded[-1]["aux_term"] == pytest.approx(sel["aux_term"])


class TestEndToEndSearch:
    def test_short_search_logs_everything_and_selects(self, tmp_path, tmp_path_factory):
        source = make_source(n_rows=240)
        climate = make_climate_artifact(
            tmp_path_factory.mktemp("clim-tune"), t_months=480, state_noise=0.05
        )
        dataset = bd.build_dataset(source, climate, validation_start_date="2005-01-01")
        configs = [
            df.DiffusionConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=5, lambda_tail=0.0),
            df.DiffusionConfig(d_model=32, n_layers=1, n_heads=2, eval_nfe=5, lambda_tail=0.1),
        ]
        entries = tu.run_search(
            dataset,
            configs,
            exp_dir=tmp_path,
            seed=3,
            trial_max_steps=6,
            trial_eval_every=6,
            trial_patience=5,
            device="cpu",
            n_rep_eval=1,
            space_sha256="deadbeef",
        )
        events = [e["event"] for e in entries]
        assert events[0] == "search_header"
        assert events.count("trial_started") == 2
        assert events.count("trial_completed") == 2
        sel = tu.select_config(entries, n_folds=3)
        tu.mark_selected(tmp_path, sel)
        again = tu.selection_from_log_dir(tmp_path, n_folds=3)
        assert again["config_hash"] == sel["config_hash"]
        # re-running the same configs spends no extra budget (already started)
        entries2 = tu.run_search(
            dataset,
            configs,
            exp_dir=tmp_path,
            seed=3,
            trial_max_steps=6,
            trial_eval_every=6,
            trial_patience=5,
            device="cpu",
            n_rep_eval=1,
        )
        assert len(tu.distinct_started_hashes(entries2)) == 2
