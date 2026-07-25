"""WP2.1b Task 4 acceptance: block-nested thresholds, seal/verify, block_addition.

This task builds the pre-registration seal machinery (Instructions/WP2.1b-PRE-SEAL-
PATCH.md Item 2, Definition of done item 4) -- it does not seal anything for real.
The tests therefore exercise ``ah.eval.prereg.seal()`` only in dry-run form or against
throwaway ``tmp_path`` copies of the real files, never mutating the committed
``pre-registration.yaml`` / ``factors.yaml`` / ``governance/amendment-log.yaml``.

Layout: block/cross-block coverage (tests 1-5), the ``conventions`` closure that is
this task's most emphasized finding (the "extra" tests after test 5 -- see
``ah.eval.prereg``'s module docstring for why a missing/misspelled ``conventions:``
block would otherwise silently disable enforcement in the very file the seal hashes),
threshold sanity, dry-run seal + verify against a lock (tests 6-9, 13), the amendment
log (tests 11-12), and the ``block_addition`` round trip (test 10).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import yaml

from ah.core.digest import canonical_json
from ah.eval import prereg
from ah.eval.prereg import (
    AMENDMENT_TYPES,
    Amendment,
    Decision,
    PreRegError,
    PreRegistration,
    Threshold,
    append_amendment,
    apply_block_addition,
    load_amendments,
)
from ah.factors import load_manifest

ROOT = Path(__file__).resolve().parents[1]
REAL_PREREG_PATH = ROOT / "pre-registration.yaml"
REAL_FACTORS_PATH = ROOT / "factors.yaml"
REAL_AMENDMENT_LOG_PATH = ROOT / "governance" / "amendment-log.yaml"

_AMENDMENT_LOG_HEADER = "# amendment log fixture\n\namendments:\n"


# --------------------------------------------------------------------------- #
# fixture helpers
# --------------------------------------------------------------------------- #


def _load_real_doc() -> dict[str, Any]:
    text = REAL_PREREG_PATH.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    assert isinstance(doc, dict)
    return doc


def _write_doc_and_factors(
    tmp_path: Path, doc: dict[str, Any], *, factors_src: Path = REAL_FACTORS_PATH
) -> tuple[Path, Path]:
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    factors_path = tmp_path / "factors.yaml"
    shutil.copy(factors_src, factors_path)
    return prereg_path, factors_path


def _copy_real_prereg_and_factors(tmp_path: Path) -> tuple[Path, Path]:
    prereg_path = tmp_path / "pre-registration.yaml"
    factors_path = tmp_path / "factors.yaml"
    shutil.copy(REAL_PREREG_PATH, prereg_path)
    shutil.copy(REAL_FACTORS_PATH, factors_path)
    return prereg_path, factors_path


def _threshold_dict(mapping: Any) -> dict[str, Any]:
    return {k: dataclasses.asdict(v) for k, v in mapping.items()}


# --------------------------------------------------------------------------- #
# 1. real file load + verify
# --------------------------------------------------------------------------- #


def test_load_and_verify_real_file_passes() -> None:
    loaded = prereg.load()
    manifest = load_manifest()
    prereg.verify(loaded, manifest)  # must not raise


def test_load_real_file_explicit_path() -> None:
    loaded = prereg.load(REAL_PREREG_PATH)
    assert loaded.sealed is False
    assert loaded.active_blocks == ("global", "us")
    assert set(loaded.block_thresholds) == {"global", "us"}
    assert set(loaded.cross_block_thresholds) == {("global", "us")}
    assert set(loaded.decisions) == {"R5", "J3"}
    assert loaded.decisions["R5"].status == "CLOSED-deferred"
    assert loaded.decisions["J3"].status == "CLOSED-deferred"


def test_decision_consequence_text_is_verbatim() -> None:
    loaded = prereg.load(REAL_PREREG_PATH)
    assert loaded.decisions["R5"].consequence == (
        "Institutions with material unhedged foreign-currency exposure are out of "
        "scope for v1. Adding FX later requires a block_addition amendment and "
        "retraining the generator, since cross-block correlation cannot be added to "
        "trained weights."
    )
    assert loaded.decisions["J3"].consequence == (
        "UK-domiciled institution twins are blocked until a block_addition "
        "amendment; the InstitutionProfile interface accommodates them without "
        "rework. Same retraining consequence applies."
    )


# --------------------------------------------------------------------------- #
# 2-5. block / cross-block coverage
# --------------------------------------------------------------------------- #


def test_verify_fails_when_active_block_missing_thresholds(tmp_path: Path) -> None:
    doc = _load_real_doc()
    del doc["thresholds"]["blocks"]["us"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"'us'"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_threshold_references_inactive_block(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["blocks"]["uk"] = {
        "bank_rate.mean": {"min": -1.0, "max": 1.0, "severity": "report"}
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"'uk'"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_cross_block_entry_missing(tmp_path: Path) -> None:
    doc = _load_real_doc()
    del doc["thresholds"]["cross_blocks"]["global|us"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"\('global', 'us'\)"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_cross_block_references_inactive_block(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["cross_blocks"]["global|uk"] = {
        "equity_mkt~bank_rate.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"'uk'"):
        prereg.verify(loaded, manifest)


def test_verify_reports_all_failures_at_once(tmp_path: Path) -> None:
    # One fault from the *first* section verify() runs (the conventions closure) and
    # one from the *last* (threshold sanity), so this discriminates against a
    # section-level early return, not merely against per-error short-circuiting
    # inside one loop.
    doc = _load_real_doc()
    doc["conventions"]["return_bearing_factors"] = [
        f for f in doc["conventions"]["return_bearing_factors"] if f != "smb"
    ]
    doc["thresholds"]["blocks"]["global"]["equity_mkt.skew"]["severity"] = "bogus"
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError) as excinfo:
        prereg.verify(loaded, manifest)
    message = str(excinfo.value)
    assert "smb" in message
    assert "severity" in message


# --------------------------------------------------------------------------- #
# the conventions-block hole (closed by verify(), not by ah.strategies)
# --------------------------------------------------------------------------- #


def test_verify_fails_when_conventions_block_missing(tmp_path: Path) -> None:
    doc = _load_real_doc()
    del doc["conventions"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="conventions"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_conventions_missing_required_key(tmp_path: Path) -> None:
    doc = _load_real_doc()
    del doc["conventions"]["rebalance_cadences"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="rebalance_cadences"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_conventions_classifies_factor_in_both(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["conventions"]["level_factors"] = [*doc["conventions"]["level_factors"], "equity_mkt"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="equity_mkt"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_conventions_leaves_active_factor_unclassified(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["conventions"]["return_bearing_factors"] = [
        f for f in doc["conventions"]["return_bearing_factors"] if f != "smb"
    ]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="smb"):
        prereg.verify(loaded, manifest)


def test_verify_rejects_empty_conventions_list(tmp_path: Path) -> None:
    # ah.strategies._require_string_set rejects an empty return_bearing_factors /
    # level_factors list; verify() must too, or it green-lights a file
    # load_conventions() would raise on (final branch review, fix 3).
    doc = _load_real_doc()
    doc["conventions"]["level_factors"] = []
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"conventions\.level_factors.*non-empty"):
        prereg.verify(loaded, manifest)


def test_verify_rejects_non_string_entry_in_conventions_list(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["conventions"]["return_bearing_factors"] = [
        *doc["conventions"]["return_bearing_factors"],
        123,
    ]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"conventions\.return_bearing_factors.*non-string"):
        prereg.verify(loaded, manifest)


def test_verify_rejects_duplicate_entry_in_conventions_list(tmp_path: Path) -> None:
    doc = _load_real_doc()
    first = doc["conventions"]["level_factors"][0]
    doc["conventions"]["level_factors"] = [*doc["conventions"]["level_factors"], first]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"conventions\.level_factors.*more than once"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_conventions_classifies_a_non_active_factor(tmp_path: Path) -> None:
    # `ah.strategies._validate_conventions` rejects a conventions block that classifies
    # a factor outside the active set ("must cover exactly the active factor set, no
    # more"). verify()'s stated purpose is closing divergences with that loader, so it
    # rejects it too. This replaces an earlier test that asserted the divergence as
    # intended behaviour -- see the fix report, finding 6.
    doc = _load_real_doc()
    doc["conventions"]["level_factors"] = [*doc["conventions"]["level_factors"], "bank_rate"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="bank_rate"):
        prereg.verify(loaded, manifest)


# --------------------------------------------------------------------------- #
# threshold sanity
# --------------------------------------------------------------------------- #


def test_verify_fails_on_invalid_severity(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["blocks"]["global"]["equity_mkt.skew"]["severity"] = "bogus"
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="severity"):
        prereg.verify(loaded, manifest)


def test_verify_fails_when_min_greater_than_max(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["blocks"]["global"]["equity_mkt.skew"] = {
        "min": 5.0,
        "max": 1.0,
        "severity": "enforce",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="min"):
        prereg.verify(loaded, manifest)


# --------------------------------------------------------------------------- #
# threshold KEY validity -- the sealed naming rule pre-registration.yaml states
# ("<factor>.<stat>" / "<factorA>~<factorB>.<stat>"), enforced against the manifest
# and ah.eval.reference's registered statistic tables.
# --------------------------------------------------------------------------- #


def _verify_with_block_threshold(tmp_path: Path, block: str, key: str) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["blocks"][block][key] = {"min": -1.0, "max": 1.0, "severity": "enforce"}
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def _verify_with_cross_block_threshold(tmp_path: Path, pair_key: str, key: str) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["cross_blocks"][pair_key][key] = {
        "min": -1.0,
        "max": 1.0,
        "severity": "enforce",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_malformed_block_threshold_key(tmp_path: Path) -> None:
    with pytest.raises(PreRegError, match=r"equity_mkt\.skew\.extra"):
        _verify_with_block_threshold(tmp_path, "global", "equity_mkt.skew.extra")


def test_verify_rejects_block_threshold_naming_another_blocks_factor(tmp_path: Path) -> None:
    # policy_rate is a `us` factor; a threshold for it nested under `global` judges
    # nothing, because reference.compute_reference keys it under `us`.
    with pytest.raises(PreRegError, match="policy_rate"):
        _verify_with_block_threshold(tmp_path, "global", "policy_rate.mean")


def test_verify_rejects_unknown_single_factor_stat(tmp_path: Path) -> None:
    # The exact hole the review named: a sealed `enforce` threshold on a statistic
    # that does not exist judges nothing, silently, forever.
    with pytest.raises(PreRegError, match="bogus"):
        _verify_with_block_threshold(tmp_path, "global", "equity_mkt.bogus")


def test_verify_rejects_cross_block_key_with_factors_from_wrong_blocks(tmp_path: Path) -> None:
    # Both factors are real and both blocks are active, but `smb` and `equity_mkt` are
    # both `global` -- so this is not a cross-block statistic at all.
    with pytest.raises(PreRegError, match="smb"):
        _verify_with_cross_block_threshold(tmp_path, "global|us", "equity_mkt~smb.correlation")


def test_verify_rejects_cross_block_key_with_reversed_block_order(tmp_path: Path) -> None:
    # The pair key is sorted, and reference.py keys "<factor from pair[0]>~<factor
    # from pair[1]>"; the reversed form names a statistic nothing computes.
    with pytest.raises(PreRegError, match="ust_10y~equity_mkt"):
        _verify_with_cross_block_threshold(tmp_path, "global|us", "ust_10y~equity_mkt.correlation")


def test_verify_rejects_unknown_cross_block_stat(tmp_path: Path) -> None:
    with pytest.raises(PreRegError, match="bogus"):
        _verify_with_cross_block_threshold(tmp_path, "global|us", "equity_mkt~ust_10y.bogus")


def test_verify_rejects_malformed_cross_block_key(tmp_path: Path) -> None:
    with pytest.raises(PreRegError, match=r"equity_mkt\.correlation"):
        _verify_with_cross_block_threshold(tmp_path, "global|us", "equity_mkt.correlation")


# --------------------------------------------------------------------------- #
# document-level checks: schema_version and the decisions block (finding 9)
# --------------------------------------------------------------------------- #


def test_verify_rejects_unknown_schema_version(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["schema_version"] = "2.0"
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match="schema_version"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_missing_schema_version(tmp_path: Path) -> None:
    doc = _load_real_doc()
    del doc["schema_version"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match="schema_version"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_misspelled_decisions_block(tmp_path: Path) -> None:
    # A `decisons:` typo would silently drop R5 and J3 from the sealed file.
    doc = _load_real_doc()
    doc["decisons"] = doc.pop("decisions")
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match="decisions"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


# --------------------------------------------------------------------------- #
# 6, 7, 8, 9, 13. dry-run seal + verify against a lock
# --------------------------------------------------------------------------- #


def test_dry_run_seal_then_verify_passes(tmp_path: Path) -> None:
    unused_lock = tmp_path / "unused.lock"
    digest = prereg.seal(
        REAL_PREREG_PATH,
        out_path=unused_lock,
        sealed_at="2026-01-01T00:00:00Z",
        dry_run=True,
    )
    assert digest.startswith("sha256:")
    assert not unused_lock.exists()  # dry run must not write

    lock_path = tmp_path / "pre-registration.lock"
    digest2 = prereg.seal(
        REAL_PREREG_PATH,
        out_path=lock_path,
        sealed_at="2026-01-01T00:00:00Z",
        dry_run=False,
    )
    assert digest2 == digest
    assert lock_path.exists()

    loaded = prereg.load()
    manifest = load_manifest()
    prereg.verify(loaded, manifest, lock_path=lock_path)  # must not raise


def test_verify_fails_against_stale_lock_after_prereg_mutation(tmp_path: Path) -> None:
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(prereg_path, out_path=lock_path, sealed_at="2026-01-01T00:00:00Z")

    with prereg_path.open("a", encoding="utf-8") as f:
        f.write("# one mutated byte\n")

    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="digest"):
        prereg.verify(loaded, manifest, lock_path=lock_path)


def test_verify_fails_against_stale_lock_after_judged_source_mutation(tmp_path: Path) -> None:
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    judged = tmp_path / "fake_metric_module.py"
    judged.write_text(
        "# judged source fixture\ndef compute() -> int:\n    return 1\n", encoding="utf-8"
    )
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(
        prereg_path,
        out_path=lock_path,
        judged_sources=[judged],
        sealed_at="2026-01-01T00:00:00Z",
    )

    with judged.open("a", encoding="utf-8") as f:
        f.write("# mutated after sealing\n")

    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match="digest"):
        prereg.verify(loaded, manifest, lock_path=lock_path)


def test_seal_is_deterministic(tmp_path: Path) -> None:
    prereg_path, _factors_path = _copy_real_prereg_and_factors(tmp_path)
    judged = tmp_path / "fake_metric_module.py"
    judged.write_text("# fixture\n", encoding="utf-8")

    digest_a = prereg.seal(
        prereg_path,
        out_path=tmp_path / "a.lock",
        judged_sources=[judged],
        sealed_at="2026-01-01T00:00:00Z",
        dry_run=True,
    )
    digest_b = prereg.seal(
        prereg_path,
        out_path=tmp_path / "b.lock",
        judged_sources=[judged],
        sealed_at="2099-12-31T23:59:59Z",  # different sealed_at, same content
        dry_run=True,
    )
    assert digest_a == digest_b


def test_seal_requires_explicit_sealed_at(tmp_path: Path) -> None:
    prereg_path, _ = _copy_real_prereg_and_factors(tmp_path)
    with pytest.raises(TypeError):
        prereg.seal(prereg_path, out_path=tmp_path / "x.lock", dry_run=True)  # type: ignore[call-arg]


def test_verify_without_lock_path_skips_lock_check(tmp_path: Path) -> None:
    # No lock_path given at all -> no digest check, structural checks still run.
    loaded = prereg.load()
    manifest = load_manifest()
    prereg.verify(loaded, manifest)  # no lock_path kwarg; must not raise


def test_verify_with_nonexistent_lock_path_skips_lock_check() -> None:
    loaded = prereg.load()
    manifest = load_manifest()
    prereg.verify(loaded, manifest, lock_path=Path("does-not-exist.lock"))  # must not raise


# --------------------------------------------------------------------------- #
# the sealed digest must not be a function of the checkout's absolute path
# (a committed lock has to verify in CI, in a reviewer's clone, and under WSL2)
# --------------------------------------------------------------------------- #


def _seed_checkout(directory: Path) -> Path:
    """A throwaway 'checkout': the real prereg + factors + one judged source."""
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL_PREREG_PATH, directory / "pre-registration.yaml")
    shutil.copy(REAL_FACTORS_PATH, directory / "factors.yaml")
    (directory / "judged.py").write_text("# judged source fixture\n", encoding="utf-8")
    return directory / "pre-registration.yaml"


def test_seal_digest_is_independent_of_the_checkout_path(tmp_path: Path) -> None:
    prereg_a = _seed_checkout(tmp_path / "checkout_a")
    prereg_b = _seed_checkout(tmp_path / "checkout_b")

    digest_a = prereg.seal(
        prereg_a,
        out_path=tmp_path / "a.lock",
        judged_sources=[prereg_a.parent / "judged.py"],
        sealed_at="2026-01-01T00:00:00Z",
        dry_run=True,
    )
    digest_b = prereg.seal(
        prereg_b,
        out_path=tmp_path / "b.lock",
        judged_sources=[prereg_b.parent / "judged.py"],
        sealed_at="2026-01-01T00:00:00Z",
        dry_run=True,
    )
    assert digest_a == digest_b


def test_lock_hashed_files_are_relative_forward_slashed_paths(tmp_path: Path) -> None:
    # A lock sealed on Windows must verify on Linux: no drive letter, no backslash,
    # no absolute path, no '..' escape out of the root it is resolved against.
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(REAL_PREREG_PATH, out_path=lock_path, sealed_at="2026-01-01T00:00:00Z")
    hashed = json.loads(lock_path.read_text(encoding="utf-8"))["hashed_files"]
    assert hashed
    for entry in hashed:
        assert "\\" not in entry, entry
        assert ":" not in entry, entry
        assert not entry.startswith(("/", "..")), entry
        assert not Path(entry).is_absolute(), entry


def test_verify_resolves_a_lock_read_from_an_unrelated_directory(tmp_path: Path) -> None:
    # Stand-in for "sealed in one checkout, verified in another": the lock's paths are
    # resolved against the repository root, not against wherever the lock happens to sit.
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(REAL_PREREG_PATH, out_path=lock_path, sealed_at="2026-01-01T00:00:00Z")
    elsewhere = tmp_path / "elsewhere" / "nested"
    elsewhere.mkdir(parents=True)
    moved = elsewhere / "pre-registration.lock"
    moved.write_text(lock_path.read_text(encoding="utf-8"), encoding="utf-8")

    prereg.verify(prereg.load(), load_manifest(), lock_path=moved)  # must not raise


# --------------------------------------------------------------------------- #
# the default judged-source set is real, non-empty, and recorded in the lock
# --------------------------------------------------------------------------- #

# Decision 0: the seal covers *every* module that can influence a pass/fail verdict --
# including ah/splits.py, which hardcodes the train/validation/holdout boundaries that
# define what "the reference data" means (final branch review, fix 1).
_EXPECTED_JUDGED_SOURCES = frozenset(
    {
        "src/ah/eval/g2.py",
        "src/ah/eval/reference.py",
        "src/ah/eval/prereg.py",
        "src/ah/eval/battery.py",
        "src/ah/eval/panel.py",
        "src/ah/strategies.py",
        "src/ah/factors.py",
        "src/ah/splits.py",
        "src/ah/battery/report.py",
        "src/ah/battery/stylized.py",
    }
)


def test_default_judged_sources_covers_every_judging_module() -> None:
    sources = prereg._default_judged_sources()
    assert sources, "the default judged-source set must never be empty"
    relative = {p.resolve().relative_to(ROOT).as_posix() for p in sources}
    assert relative >= _EXPECTED_JUDGED_SOURCES
    # plus every enforce-tier metric module that exists yet
    assert "src/ah/eval/metrics/tails.py" in relative
    assert all(p.exists() for p in sources)


def test_lock_records_hashed_files_and_sealed_at(tmp_path: Path) -> None:
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(REAL_PREREG_PATH, out_path=lock_path, sealed_at="2026-03-04T05:06:07Z")
    doc = json.loads(lock_path.read_text(encoding="utf-8"))

    assert doc["sealed_at"] == "2026-03-04T05:06:07Z"
    assert doc["digest"].startswith("sha256:")
    hashed = set(doc["hashed_files"])
    assert "pre-registration.yaml" in hashed
    assert "factors.yaml" in hashed
    assert hashed >= _EXPECTED_JUDGED_SOURCES
    assert doc["prereg_path"] == "pre-registration.yaml"


# --------------------------------------------------------------------------- #
# the lock is bound to the pre-registration it was sealed for
# --------------------------------------------------------------------------- #


def test_verify_rejects_a_lock_sealed_for_a_different_preregistration(tmp_path: Path) -> None:
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(prereg_path, out_path=lock_path, sealed_at="2026-01-01T00:00:00Z")

    # A *different* pre-registration file -- byte-identical content, different
    # identity. The digest still matches; the binding is what must reject it.
    other_path = tmp_path / "other-pre-registration.yaml"
    other_path.write_text(prereg_path.read_text(encoding="utf-8"), encoding="utf-8")

    loaded_other = prereg.load(other_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError, match=r"other-pre-registration\.yaml"):
        prereg.verify(loaded_other, manifest, lock_path=lock_path)


def test_verify_accepts_the_lock_sealed_for_this_preregistration(tmp_path: Path) -> None:
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(prereg_path, out_path=lock_path, sealed_at="2026-01-01T00:00:00Z")
    prereg.verify(prereg.load(prereg_path), load_manifest(factors_path), lock_path=lock_path)


# --------------------------------------------------------------------------- #
# unreadable judged source -> PreRegError naming the file (never a bare OSError
# or UnicodeDecodeError escaping seal()/verify())
# --------------------------------------------------------------------------- #


def test_seal_wraps_undecodable_file_in_prereg_error(tmp_path: Path) -> None:
    prereg_path, _ = _copy_real_prereg_and_factors(tmp_path)
    binary = tmp_path / "not_utf8.py"
    binary.write_bytes(b"\xff\xfe\x00garbage\x80\x81")
    with pytest.raises(PreRegError, match=r"not_utf8\.py"):
        prereg.seal(
            prereg_path,
            out_path=tmp_path / "x.lock",
            judged_sources=[binary],
            sealed_at="2026-01-01T00:00:00Z",
            dry_run=True,
        )


def test_verify_wraps_undecodable_hashed_file_in_prereg_error(tmp_path: Path) -> None:
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    judged = tmp_path / "judged.py"
    judged.write_text("# judged source fixture\n", encoding="utf-8")
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(
        prereg_path,
        out_path=lock_path,
        judged_sources=[judged],
        sealed_at="2026-01-01T00:00:00Z",
    )
    judged.write_bytes(b"\xff\xfe\x00garbage\x80\x81")

    with pytest.raises(PreRegError, match=r"judged\.py"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path), lock_path=lock_path)


# --------------------------------------------------------------------------- #
# 11, 12. amendment log: append-only, round-trip
# --------------------------------------------------------------------------- #


def _amendment(amendment_id: str = "A1", **overrides: Any) -> Amendment:
    fields: dict[str, Any] = {
        "amendment_id": amendment_id,
        "type": "correction",
        "date": "2026-01-01",
        "rationale": "fixture amendment",
        "post_hoc": True,
    }
    fields.update(overrides)
    return Amendment(**fields)


def test_amendment_types_constant_matches_governance_doc() -> None:
    assert {
        "threshold_change",
        "protocol_change",
        "block_addition",
        "correction",
    } == AMENDMENT_TYPES


def test_real_amendment_log_documents_block_addition_property() -> None:
    text = REAL_AMENDMENT_LOG_PATH.read_text(encoding="utf-8")
    assert "block_addition" in text
    assert "additive" in text
    assert "byte-identical" in text
    assert "not a re-seal" in text
    doc = yaml.safe_load(text)
    assert doc.get("amendments") in (None, [])


def test_append_amendment_leaves_prior_entries_byte_identical(tmp_path: Path) -> None:
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(_AMENDMENT_LOG_HEADER, encoding="utf-8")

    append_amendment(log_path, _amendment("A1"))
    before = log_path.read_bytes()

    append_amendment(log_path, _amendment("A2", type="threshold_change"))
    after = log_path.read_bytes()

    assert after[: len(before)] == before
    assert len(after) > len(before)


def test_load_amendments_round_trips_appended_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(_AMENDMENT_LOG_HEADER, encoding="utf-8")

    a1 = _amendment("A1")
    a2 = _amendment("A2", type="protocol_change", post_hoc=False)
    append_amendment(log_path, a1)
    append_amendment(log_path, a2)

    loaded = load_amendments(log_path)
    assert loaded == (a1, a2)


def test_load_amendments_on_fresh_log_is_empty(tmp_path: Path) -> None:
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(_AMENDMENT_LOG_HEADER, encoding="utf-8")
    assert load_amendments(log_path) == ()


_DUPLICATE_ENTRY = (
    "- amendment_id: DUP\n"
    "  type: correction\n"
    "  date: '2026-01-01'\n"
    "  rationale: fixture amendment\n"
    "  post_hoc: true\n"
)


def test_load_amendments_rejects_duplicate_ids(tmp_path: Path) -> None:
    # Defence in depth: the duplicate is now rejected at *write* time (see
    # test_append_amendment_rejects_duplicate_id), so this log has to be hand-written
    # rather than manufactured through append_amendment -- which previously produced a
    # log that could never be read again. See the fix report, finding 4.
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(
        _AMENDMENT_LOG_HEADER + _DUPLICATE_ENTRY + _DUPLICATE_ENTRY, encoding="utf-8"
    )
    with pytest.raises(PreRegError, match="DUP"):
        load_amendments(log_path)


def test_append_amendment_requires_existing_log(tmp_path: Path) -> None:
    with pytest.raises(PreRegError):
        append_amendment(tmp_path / "does-not-exist.yaml", _amendment("A1"))


# --------------------------------------------------------------------------- #
# append-time validation: the log is append-only, so a bad entry is permanent
# --------------------------------------------------------------------------- #


def _fresh_log(tmp_path: Path) -> Path:
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(_AMENDMENT_LOG_HEADER, encoding="utf-8")
    return log_path


def test_append_amendment_rejects_unknown_type(tmp_path: Path) -> None:
    log_path = _fresh_log(tmp_path)
    before = log_path.read_bytes()
    with pytest.raises(PreRegError, match="made_up"):
        append_amendment(log_path, _amendment("A1", type="made_up"))
    assert log_path.read_bytes() == before  # nothing was written


@pytest.mark.parametrize("field", ["amendment_id", "date", "rationale"])
def test_append_amendment_rejects_empty_required_field(tmp_path: Path, field: str) -> None:
    log_path = _fresh_log(tmp_path)
    before = log_path.read_bytes()
    fields: dict[str, Any] = {"amendment_id": "A1", field: ""}
    with pytest.raises(PreRegError, match=field):
        append_amendment(log_path, _amendment(**fields))
    assert log_path.read_bytes() == before


def test_append_amendment_rejects_non_boolean_post_hoc(tmp_path: Path) -> None:
    log_path = _fresh_log(tmp_path)
    with pytest.raises(PreRegError, match="post_hoc"):
        append_amendment(log_path, _amendment("A1", post_hoc="yes"))


def test_append_amendment_rejects_duplicate_id(tmp_path: Path) -> None:
    log_path = _fresh_log(tmp_path)
    append_amendment(log_path, _amendment("DUP"))
    before = log_path.read_bytes()
    with pytest.raises(PreRegError, match="DUP"):
        append_amendment(log_path, _amendment("DUP", type="threshold_change"))
    assert log_path.read_bytes() == before
    assert load_amendments(log_path) == (_amendment("DUP"),)  # log still readable


def test_amendment_with_unknown_type_rejected(tmp_path: Path) -> None:
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(
        _AMENDMENT_LOG_HEADER
        + "- amendment_id: BAD\n  type: made_up\n  date: '2026-01-01'\n  rationale: x\n  post_hoc: true\n",
        encoding="utf-8",
    )
    with pytest.raises(PreRegError, match="made_up"):
        load_amendments(log_path)


# --------------------------------------------------------------------------- #
# 10. block_addition round trip
# --------------------------------------------------------------------------- #


def _write_synthetic_factors(tmp_path: Path, filename: str, active: list[str]) -> Path:
    # alpha carries a second factor, a1_lvl, classified `level` below -- so the
    # conventions fixture has a genuinely non-empty, valid level_factors list rather
    # than the `[]` a prior version of this fixture used (which ah.strategies would
    # reject as empty; see the module docstring's "hole this task closes" / final
    # branch review fix 3). a1_lvl is otherwise unused (no derived_series, no
    # strategy weight), which is fine -- verify() does not require every factor to
    # be used in a D4 strategy.
    p = tmp_path / filename
    p.write_text(
        "factor_blocks:\n"
        "  alpha: [a1, a1_lvl]\n"
        "  beta: [b1]\n"
        "  gamma: [g1]\n"
        f"active_blocks: [{', '.join(active)}]\n"
        "factor_sources:\n"
        "  a1: {kind: unavailable, reason: fixture}\n"
        "  a1_lvl: {kind: unavailable, reason: fixture}\n"
        "  b1: {kind: unavailable, reason: fixture}\n"
        "  g1: {kind: unavailable, reason: fixture}\n",
        encoding="utf-8",
    )
    return p


def test_block_addition_round_trip(tmp_path: Path) -> None:
    before_path = _write_synthetic_factors(tmp_path, "factors_before.yaml", ["alpha", "beta"])
    after_path = _write_synthetic_factors(
        tmp_path, "factors_after.yaml", ["alpha", "beta", "gamma"]
    )
    manifest_before = load_manifest(before_path)
    manifest_after = load_manifest(after_path)
    assert manifest_after.active_blocks == ("alpha", "beta", "gamma")

    # Conventions classify exactly the *active* factor set, as `ah.strategies`
    # requires -- `g1` is deliberately absent here and is added below, by hand, as
    # part of the block addition itself.
    doc = {
        "schema_version": "1.0",
        "sealed": False,
        "campaign_vintage_id": "test",
        "factor_manifest": "factors_before.yaml",
        "active_blocks": ["alpha", "beta"],
        "conventions": {
            "percent_to_decimal": 0.01,
            "months_per_year": 12.0,
            "return_bearing_factors": ["a1", "b1"],
            "level_factors": ["a1_lvl"],
            "rebalance_cadences": ["monthly"],
            "static_weights_composition": "test fixture",
            # Required by verify() since the WP2.2 Task 1 fix pass (Critical 3): the
            # sealed numeraire must be declared, so a block addition cannot land a
            # pre-registration that has quietly dropped it.
            "numeraire": "total_return",
            "numeraire_zero_cost_legs": [],
        },
        "thresholds": {
            "blocks": {
                "alpha": {"a1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
                "beta": {"b1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
            },
            "cross_blocks": {
                "alpha|beta": {
                    "a1~b1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
            },
        },
        "decisions": {},
    }
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    prereg_before = prereg.load(prereg_path)
    prereg.verify(prereg_before, manifest_before)  # sanity: baseline is valid

    amendment = Amendment(
        amendment_id="AMEND-GAMMA",
        type="block_addition",
        date="2026-02-01",
        rationale="fixture: activate gamma block",
        post_hoc=True,
        payload={
            "block": "gamma",
            "block_thresholds": {
                "g1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"},
            },
            "cross_block_thresholds": {
                "alpha|gamma": {
                    "a1~g1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
                "beta|gamma": {
                    "b1~g1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
            },
        },
    )

    merged = apply_block_addition(prereg_before, manifest_after, amendment)

    # apply_block_addition merges thresholds only; a real block addition is also a
    # hand edit to `conventions:` in pre-registration.yaml, classifying the new
    # block's factors. Until that edit lands, verify() correctly refuses the result --
    # `g1` is active and unclassified.
    with pytest.raises(PreRegError, match="g1"):
        prereg.verify(merged, manifest_after)

    raw_after = dict(merged.raw)
    conventions_after = dict(raw_after["conventions"])
    conventions_after["return_bearing_factors"] = [
        *conventions_after["return_bearing_factors"],
        "g1",
    ]
    raw_after["conventions"] = conventions_after
    prereg_after = dataclasses.replace(merged, raw=MappingProxyType(raw_after))

    # the amendment validates: the merged result verifies cleanly against manifest_after
    prereg.verify(prereg_after, manifest_after)

    assert prereg_after.active_blocks == ("alpha", "beta", "gamma")
    assert ("alpha", "gamma") in prereg_after.cross_block_thresholds
    assert ("beta", "gamma") in prereg_after.cross_block_thresholds
    assert "gamma" in prereg_after.block_thresholds

    # the original two blocks' (and their pair's) thresholds are byte-identical
    # before and after, via canonical-JSON serialization -- the patch's acceptance
    # criterion for a block addition.
    for block in ("alpha", "beta"):
        before_json = canonical_json(_threshold_dict(prereg_before.block_thresholds[block]))
        after_json = canonical_json(_threshold_dict(prereg_after.block_thresholds[block]))
        assert before_json == after_json
    before_pair_json = canonical_json(
        _threshold_dict(prereg_before.cross_block_thresholds[("alpha", "beta")])
    )
    after_pair_json = canonical_json(
        _threshold_dict(prereg_after.cross_block_thresholds[("alpha", "beta")])
    )
    assert before_pair_json == after_pair_json


def test_apply_block_addition_rejects_non_block_addition_amendment() -> None:
    loaded = prereg.load()
    manifest = load_manifest()
    bad = _amendment("X", type="correction")
    with pytest.raises(PreRegError, match="block_addition"):
        apply_block_addition(loaded, manifest, bad)


def test_apply_block_addition_rejects_missing_new_pair(tmp_path: Path) -> None:
    _write_synthetic_factors(tmp_path, "factors_before.yaml", ["alpha", "beta"])
    after_path = _write_synthetic_factors(
        tmp_path, "factors_after.yaml", ["alpha", "beta", "gamma"]
    )
    manifest_after = load_manifest(after_path)
    doc = {
        "schema_version": "1.0",
        "sealed": False,
        "campaign_vintage_id": "test",
        "factor_manifest": "factors_before.yaml",
        "active_blocks": ["alpha", "beta"],
        "conventions": {
            "percent_to_decimal": 0.01,
            "months_per_year": 12.0,
            "return_bearing_factors": ["a1", "b1"],
            "level_factors": ["a1_lvl"],
            "rebalance_cadences": ["monthly"],
            "static_weights_composition": "test fixture",
            # Required by verify() since the WP2.2 Task 1 fix pass (Critical 3): the
            # sealed numeraire must be declared, so a block addition cannot land a
            # pre-registration that has quietly dropped it.
            "numeraire": "total_return",
            "numeraire_zero_cost_legs": [],
        },
        "thresholds": {
            "blocks": {
                "alpha": {"a1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
                "beta": {"b1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
            },
            "cross_blocks": {
                "alpha|beta": {
                    "a1~b1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
            },
        },
        "decisions": {},
    }
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    prereg_before = prereg.load(prereg_path)

    amendment = Amendment(
        amendment_id="AMEND-INCOMPLETE",
        type="block_addition",
        date="2026-02-01",
        rationale="fixture: missing beta|gamma pair",
        post_hoc=True,
        payload={
            "block": "gamma",
            "block_thresholds": {"g1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
            "cross_block_thresholds": {
                "alpha|gamma": {
                    "a1~g1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
                # beta|gamma deliberately omitted
            },
        },
    )
    with pytest.raises(
        PreRegError, match=r"missing cross-block thresholds for new pair\(s\).*'beta', 'gamma'"
    ):
        apply_block_addition(prereg_before, manifest_after, amendment)


# --------------------------------------------------------------------------- #
# structural sanity
# --------------------------------------------------------------------------- #


def test_dataclasses_are_frozen() -> None:
    th = Threshold(min=0.0, max=1.0, severity="report")
    with pytest.raises(dataclasses.FrozenInstanceError):
        th.min = 5.0  # type: ignore[misc]

    dec = Decision(decision_id="X", status="CLOSED-deferred", consequence="text")
    with pytest.raises(dataclasses.FrozenInstanceError):
        dec.status = "OPEN"  # type: ignore[misc]

    pr = prereg.load()
    with pytest.raises(dataclasses.FrozenInstanceError):
        pr.sealed = True  # type: ignore[misc]

    amendment = _amendment("A")
    with pytest.raises(dataclasses.FrozenInstanceError):
        amendment.post_hoc = False  # type: ignore[misc]


def test_preregistration_is_a_dataclass_instance() -> None:
    assert isinstance(prereg.load(), PreRegistration)


# --------------------------------------------------------------------------- #
# WP2.2 Task 2 fix pass -- Critical 2: every monthly metric name must be sealable
#
# `verify()` rejects a threshold key whose `<stat>` is not a registered
# reference statistic, and `run_battery` calls `verify()` unconditionally once
# `sealed: true` lands. A monthly metric whose name no registry knows therefore
# cannot carry a threshold at all -- and an entry authored under such a name
# would break every battery run, not merely the seal. These tests are the proof
# that the monthly suite's own names are all sealable.
# --------------------------------------------------------------------------- #


def _block_of(manifest: Any, factor: str) -> str:
    for block in manifest.active_blocks:
        if factor in manifest.blocks[block]:
            return block
    raise AssertionError(f"factor {factor!r} is in no active block")


def _thresholds_for_every_monthly_metric(manifest: Any) -> dict[str, Any]:
    """A ``thresholds:`` document carrying one entry per monthly metric name."""
    from ah.eval.metrics.monthly import build_monthly_suite
    from ah.eval.reference import ReferenceStats

    specs = build_monthly_suite(
        manifest,
        ReferenceStats(
            blocks={},
            cross_blocks={},
            active_blocks=manifest.active_blocks,
            vintage_id="v",
            n_resamples=1,
            seed=0,
            missing_factors=(),
        ),
    )
    blocks: dict[str, dict[str, Any]] = {b: {} for b in manifest.active_blocks}
    cross: dict[str, dict[str, Any]] = {f"{a}|{b}": {} for a, b in manifest.cross_block_pairs()}
    panel: dict[str, Any] = {}
    entry = {"min": None, "max": None, "severity": "report"}
    for spec in specs:
        if "." not in spec.name:
            panel[spec.name] = dict(entry)
        elif "~" in spec.name:
            factors = spec.name.split(".", 1)[0]
            fa, fb = factors.split("~")
            pair = tuple(sorted((_block_of(manifest, fa), _block_of(manifest, fb))))
            cross[f"{pair[0]}|{pair[1]}"][spec.name] = dict(entry)
        else:
            factor = spec.name.split(".", 1)[0]
            blocks[_block_of(manifest, factor)][spec.name] = dict(entry)
    assert panel, "the monthly suite must contribute at least one panel-level metric"
    return {"blocks": blocks, "cross_blocks": cross, "panel": panel}


def test_every_monthly_metric_name_can_carry_a_sealed_threshold(tmp_path: Path) -> None:
    manifest = load_manifest()
    doc = _load_real_doc()
    doc["thresholds"] = _thresholds_for_every_monthly_metric(manifest)
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)

    loaded = prereg.load(prereg_path)
    prereg.verify(loaded, load_manifest(factors_path))  # must not raise


def test_every_real_threshold_key_is_produced_by_a_registered_metric() -> None:
    """Minor 3 (WP2.2 Task 2 fix pass 2). The mirror of the test above: `verify()`
    validates a threshold key's `<stat>` against the *reference* registries
    (`SINGLE_FACTOR_STATS`/`CROSS_BLOCK_STATS`/`PANEL_STATS`), not against what any
    metric suite actually *emits* -- so a threshold can be well-formed and registered,
    and still be judged by nothing: no `MetricResult` is ever produced under that name,
    so an `enforce` bound on it can never fail (or ever run) at all. `mean`/`std`
    (`SINGLE_FACTOR_STATS`) and `correlation` (`CROSS_BLOCK_STATS`) are registered
    reference statistics -- a historical band gets computed for them -- but no monthly
    metric computes an ensemble-side value under those names, since `build_monthly_suite`
    never emits a bare `.mean`/`.std` spec or a bare `.correlation` cross-block spec
    (only `.crisis_corr_lift`). This is exactly the "judges nothing, silently" failure
    `_check_block_threshold_key` exists to prevent, one level up: a key can be
    well-formed and still be inert.
    """
    from ah.eval.metrics.monthly import build_monthly_suite
    from ah.eval.reference import ReferenceStats

    manifest = load_manifest()
    specs = build_monthly_suite(
        manifest,
        ReferenceStats(
            blocks={},
            cross_blocks={},
            active_blocks=manifest.active_blocks,
            vintage_id="v",
            n_resamples=1,
            seed=0,
            missing_factors=(),
        ),
    )
    produced = {s.name for s in specs}

    loaded = prereg.load()
    inert: list[str] = []
    for block, entries in loaded.block_thresholds.items():
        for key in entries:
            if key not in produced:
                inert.append(f"thresholds.blocks.{block}.{key}")
    for pair, entries in loaded.cross_block_thresholds.items():
        for key in entries:
            if key not in produced:
                inert.append(f"thresholds.cross_blocks.{pair[0]}|{pair[1]}.{key}")
    for key in loaded.panel_thresholds:
        if key not in produced:
            inert.append(f"thresholds.panel.{key}")

    assert not inert, f"threshold key(s) with no producing metric (judge nothing): {inert}"


def test_verify_rejects_an_unregistered_panel_threshold_key(tmp_path: Path) -> None:
    doc = _load_real_doc()
    doc["thresholds"]["panel"] = {
        "not_a_registered_panel_statistic": {"min": 0.0, "max": 1.0, "severity": "enforce"}
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    with pytest.raises(PreRegError, match="not a registered panel statistic"):
        prereg.verify(loaded, load_manifest(factors_path))


def test_verify_rejects_a_factor_scoped_panel_threshold_key(tmp_path: Path) -> None:
    """A panel statistic is whole-panel by definition; a factor-scoped key under it
    would name a statistic nothing computes."""
    doc = _load_real_doc()
    doc["thresholds"]["panel"] = {
        "equity_mkt.cross_block_corr_matrix_distance": {
            "min": 0.0,
            "max": 1.0,
            "severity": "report",
        }
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    with pytest.raises(PreRegError, match="panel threshold key"):
        prereg.verify(loaded, load_manifest(factors_path))


def test_block_addition_carries_panel_thresholds_through_unchanged(tmp_path: Path) -> None:
    """`block_addition` is additive over blocks and pairs; a panel statistic is not
    block-scoped at all, so it must survive the merge byte-identically -- otherwise
    activating a block would silently drop the sealed panel threshold."""
    _write_synthetic_factors(tmp_path, "factors_before.yaml", ["alpha", "beta"])
    after_path = _write_synthetic_factors(
        tmp_path, "factors_after.yaml", ["alpha", "beta", "gamma"]
    )
    doc = {
        "schema_version": "1.0",
        "sealed": False,
        "campaign_vintage_id": "test",
        "factor_manifest": "factors_before.yaml",
        "active_blocks": ["alpha", "beta"],
        "conventions": {
            "percent_to_decimal": 0.01,
            "months_per_year": 12.0,
            "return_bearing_factors": ["a1", "b1"],
            "level_factors": ["a1_lvl"],
            "rebalance_cadences": ["monthly"],
            "static_weights_composition": "test fixture",
            "numeraire": "total_return",
            "numeraire_zero_cost_legs": [],
        },
        "thresholds": {
            "blocks": {
                "alpha": {"a1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
                "beta": {"b1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
            },
            "cross_blocks": {
                "alpha|beta": {
                    "a1~b1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
            },
            "panel": {
                "cross_block_corr_matrix_distance": {
                    "min": 0.0,
                    "max": 2.0,
                    "severity": "report",
                }
            },
        },
        "decisions": {},
    }
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    before = prereg.load(prereg_path)
    assert "cross_block_corr_matrix_distance" in before.panel_thresholds

    amendment = Amendment(
        amendment_id="AMEND-GAMMA-PANEL",
        type="block_addition",
        date="2026-02-01",
        rationale="fixture: activate gamma block",
        post_hoc=True,
        payload={
            "block": "gamma",
            "block_thresholds": {"g1.mean": {"min": -1.0, "max": 1.0, "severity": "enforce"}},
            "cross_block_thresholds": {
                "alpha|gamma": {
                    "a1~g1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
                "beta|gamma": {
                    "b1~g1.correlation": {"min": -1.0, "max": 1.0, "severity": "report"}
                },
            },
        },
    )
    merged = apply_block_addition(before, load_manifest(after_path), amendment)

    assert merged.panel_thresholds == before.panel_thresholds
    assert canonical_json(_threshold_dict(merged.panel_thresholds)) == canonical_json(
        _threshold_dict(before.panel_thresholds)
    )


def test_default_judged_sources_pins_every_existing_metric_suite() -> None:
    """The seal join is a fixed name list, and `_default_judged_sources()` silently
    skips a suite path that does not exist -- so a rename or move of a metric suite
    module would shrink the seal with no test failure. Asserting the *string* is in
    `_METRIC_SUITE_NAMES` does not catch that; asserting the file resolves into the
    judged set does.
    """
    resolved = {p.resolve() for p in prereg._default_judged_sources()}
    metrics_dir = ROOT / "src" / "ah" / "eval" / "metrics"
    on_disk = {p.resolve() for p in metrics_dir.glob("*.py") if p.name != "__init__.py"}
    assert on_disk, "expected at least one metric suite module on disk"
    missing = sorted(str(p.relative_to(ROOT)) for p in on_disk - resolved)
    assert not missing, (
        f"metric suite module(s) {missing} exist on disk but are outside the sealed "
        f"judged-source set -- add them to ah.eval.prereg._METRIC_SUITE_NAMES"
    )
