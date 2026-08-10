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

import ast
import dataclasses
import json
import re
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
    # WP2.3 flipped this. It was `False` through WP2.1b-WP2.2c; the assertion is updated
    # to the new truth rather than relaxed, because "is the real file sealed" is exactly
    # the fact this test exists to pin, and a sealed file that reads unsealed would be
    # the most consequential regression this repository could have.
    assert loaded.sealed is True
    # campaign-2 block additions (AM-2026-08-02-007/-008)
    assert loaded.active_blocks == ("global", "us", "fx", "valuation")
    assert set(loaded.block_thresholds) == {"global", "us", "fx", "valuation"}
    assert set(loaded.cross_block_thresholds) == {
        ("global", "us"),
        ("fx", "global"),
        ("fx", "us"),
        ("fx", "valuation"),
        ("global", "valuation"),
        ("us", "valuation"),
    }
    assert set(loaded.decisions) == {
        "R5",
        "J3",
        # WP2.3's sealed decisions -- see pre-registration.yaml's `decisions:` and
        # governance/decision-register.md's Step 2 section. S2-ENDOWMENT-WEIGHTS is the
        # re-seal's addition: RFR-9 was assigned to WP2.3 and the first seal never
        # answered it, so `endowment_proxy`'s credit_xs_hy weight is now sealed
        # explicitly as a risk budget rather than a capital share.
        "S2-NC5-EXEMPTION",
        "S2-SPREAD-FLOOR",
        "S2-NUMERAIRE-BIAS",
        "S2-ENDOWMENT-WEIGHTS",
    }
    assert loaded.decisions["R5"].status == "CLOSED-deferred"
    assert loaded.decisions["J3"].status == "CLOSED-deferred"
    assert loaded.decisions["S2-SPREAD-FLOOR"].status == "RATIFIED"


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


def test_verify_fails_when_sealed_and_lock_file_is_missing(tmp_path: Path) -> None:
    """WP2.3 re-seal, review Important 2: deleting the lock must not verify clean.

    ``verify`` used to skip the lock check entirely when the file was absent, so ``rm
    pre-registration.lock`` disarmed every hashed-source check with no error anywhere.
    """
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(prereg_path, out_path=lock_path, sealed_at="2026-01-01T00:00:00Z")

    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    prereg.verify(loaded, manifest, lock_path=lock_path)  # baseline: passes with the lock

    lock_path.unlink()
    assert loaded.sealed
    with pytest.raises(PreRegError, match="lock file is missing"):
        prereg.verify(loaded, manifest, lock_path=lock_path)


def test_verify_tolerates_missing_lock_while_unsealed(tmp_path: Path) -> None:
    """The pre-seal state is legitimate: an unsealed document has no lock yet."""
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    doc = yaml.safe_load(prereg_path.read_text(encoding="utf-8"))
    doc["sealed"] = False
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    loaded = prereg.load(prereg_path)
    assert not loaded.sealed
    prereg.verify(loaded, load_manifest(factors_path), lock_path=tmp_path / "absent.lock")


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


def test_verify_with_nonexistent_lock_path_errors_once_sealed() -> None:
    """WP2.3 re-seal, review Important 2 -- this test previously asserted the DEFECT.

    It used to require that a named-but-absent lock be skipped silently, which is what
    made ``rm pre-registration.lock`` a clean way to disarm the seal. The contract is
    now: naming a lock path for a SEALED document asserts that the lock is there.
    Passing no ``lock_path`` at all (the test above) is still the supported way to run
    the structural checks alone, so nothing lost a way to be checked.
    """
    loaded = prereg.load()
    manifest = load_manifest()
    assert loaded.sealed
    with pytest.raises(PreRegError, match="lock file is missing"):
        prereg.verify(loaded, manifest, lock_path=Path("does-not-exist.lock"))


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


def test_the_real_amendment_log_opens_with_the_d6_pre_authorization() -> None:
    """WP2.3's human gate, discharged in the log rather than asserted in prose.

    STEP2-GENERATOR-PLAN Sec.WP2.3: "merges only after the D6 workshop ratifies (or with
    provisional values pre-authorized in the amendment log)". The project owner took the
    second branch, so the log's FIRST entry must be that pre-authorization -- everything
    sealed on 2026-07-26 was sealed under it, and an entry appended later could not
    cover a seal that already happened. It must also be `post_hoc: false`: at the time
    it was written no generator, no training run and no G2 evidence existed, so there
    was nothing it could have been fitted to.

    This test also IS the amendment-log round-trip acceptance for the real file
    (Sec.WP2.3: "amendment log round-trips") -- the entry is read back through
    ``load_amendments`` from the committed bytes, payload and all.
    """
    amendments = load_amendments(REAL_AMENDMENT_LOG_PATH)
    assert amendments, "the sealed pre-registration must be covered by a pre-authorization"
    first = amendments[0]
    assert first.amendment_id == "AM-2026-07-26-001"
    assert first.type == "protocol_change"
    assert first.date == "2026-07-26"
    assert first.post_hoc is False
    assert "PRE-AUTHORIZATION OF PROVISIONAL VALUES" in first.rationale
    assert first.payload["ratifying_body"] == "D6 workshop"
    # It must NAME what is provisional -- a pre-authorization that does not say what it
    # authorizes authorizes everything.
    provisional = first.payload["what_is_provisional"]
    assert "ensemble_size.n_paths" in provisional
    assert "bootstrap_v1.mean_block_months" in provisional
    assert first.payload["what_D6_must_ratify"]


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


def _assume_every_factor_has_data(doc: dict[str, Any]) -> dict[str, Any]:
    """Blank ``reference_run``'s availability lists in a SYNTHETIC verification document.

    WP2.3 added a sealed-document check (governance/retrofit-register.md RFR-5) that
    rejects a threshold keyed to a factor or D4 strategy with no computable reference
    statistic on the campaign vintage -- three factors and three strategies, today.
    The two tests below assert a DIFFERENT property: that every metric name a suite
    emits is a well-formed, registered threshold KEY. They build a document carrying one
    entry per emitted metric name, which necessarily includes the unavailable factors'
    names, so without this the availability rule would mask the naming rule and neither
    would be tested cleanly.

    This is not a weakening: the availability rule has its own dedicated tests
    (``test_verify_rejects_a_threshold_on_a_factor_with_no_data`` and its strategy
    sibling), and the real ``pre-registration.yaml`` is verified with the real lists by
    ``test_load_and_verify_real_file_passes``.
    """
    run = dict(doc["reference_run"])
    run["missing_factors"] = []
    run["uncomputable_d4_strategies"] = []
    doc["reference_run"] = run
    return doc


def test_every_monthly_metric_name_can_carry_a_sealed_threshold(tmp_path: Path) -> None:
    manifest = load_manifest()
    doc = _assume_every_factor_has_data(_load_real_doc())
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
    from ah.eval.metrics.calibration import build_calibration_suite
    from ah.eval.metrics.conditional import build_conditional_suite
    from ah.eval.metrics.economics import build_economics_suite
    from ah.eval.metrics.horizon import build_horizon_suite
    from ah.eval.metrics.memorization import build_memorization_suite
    from ah.eval.metrics.monthly import build_monthly_suite
    from ah.eval.metrics.tails import build_tails_suite
    from ah.eval.metrics.utility import build_utility_suite
    from ah.eval.reference import ReferenceStats

    manifest = load_manifest()
    reference = ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=manifest.active_blocks,
        vintage_id="v",
        n_resamples=1,
        seed=0,
        missing_factors=(),
    )
    # `thresholds.panel`/`.blocks`/`.cross_blocks` carry entries judged by every
    # reference-dependent suite, not only monthly.py's -- `produced` must be the union
    # of ALL EIGHT wired suites' own names (WP2.2 Task 5 fix pass, Minor: an earlier
    # version of this test unioned only monthly/memorization/economics/calibration --
    # four of seven -- so a real threshold judged by horizon.py, tails.py or utility.py
    # alone would have read as "inert" here purely because those three builders were
    # never called, the exact failure mode this test exists to catch, just missed for
    # its own three suites; WP2.2 Task 6 adds conditional.py as the eighth). horizon.py/
    # tails.py/utility.py's builders are safe to call against this bare, empty-history
    # `reference` -- none of them eagerly reads `historical_series` in a way that raises
    # when it is empty (build_tails_suite's `_HistoricalCache.returns` returns `None`,
    # not an error, when a strategy's legs have no historical series at all).
    # conditional.py's builder is likewise safe here: it never reads `reference` for
    # Part A, and Part B's `historical_series.get(...)` on an empty mapping returns
    # `None` (its own support-distribution NaN path), not an error.
    produced = (
        {s.name for s in build_monthly_suite(manifest, reference)}
        | {s.name for s in build_horizon_suite(manifest, reference)}
        | {s.name for s in build_tails_suite(manifest, reference)}
        | {s.name for s in build_utility_suite(manifest, reference)}
        | {s.name for s in build_memorization_suite(manifest, reference)}
        | {s.name for s in build_economics_suite(manifest, reference)}
        | {s.name for s in build_calibration_suite(manifest, reference)}
        | {s.name for s in build_conditional_suite(manifest, reference)}
    )

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


# --------------------------------------------------------------------------- #
# WP2.2 Task 3 -- the horizon-suite equivalent of the two tests directly above:
# every horizon metric name must be sealable, and every real threshold key must be
# produced by a registered metric. Same structural lesson Task 2's fix passes closed
# for `monthly`, applied to `horizon` from the start.
# --------------------------------------------------------------------------- #


def _thresholds_for_every_horizon_metric(manifest: Any) -> dict[str, Any]:
    """A ``thresholds:`` document carrying one entry per horizon metric name."""
    from ah.eval.metrics.horizon import build_horizon_suite
    from ah.eval.reference import ReferenceStats

    specs = build_horizon_suite(
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
    assert panel, "the horizon suite must contribute at least one panel-level metric"
    return {"blocks": blocks, "cross_blocks": cross, "panel": panel}


def test_every_horizon_metric_name_can_carry_a_sealed_threshold(tmp_path: Path) -> None:
    manifest = load_manifest()
    doc = _assume_every_factor_has_data(_load_real_doc())
    doc["thresholds"] = _thresholds_for_every_horizon_metric(manifest)
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)

    loaded = prereg.load(prereg_path)
    prereg.verify(loaded, load_manifest(factors_path))  # must not raise


def test_every_real_threshold_key_used_by_horizon_is_produced_by_a_registered_metric() -> None:
    """Every real ``pre-registration.yaml`` threshold key that happens to name a
    horizon-suite statistic must actually be produced by ``build_horizon_suite`` --
    the same "judges nothing, silently" check Task 2 added for `monthly`, extended to
    cover a metric registered under this task's names too. Real threshold keys today
    are all monthly-suite ones, so this test is a forward guard (it must not regress
    the day a horizon threshold is added), not evidence of a bug found now.
    """
    from ah.eval.metrics.horizon import build_horizon_suite
    from ah.eval.reference import PANEL_STATS, SINGLE_FACTOR_STATS, ReferenceStats

    manifest = load_manifest()
    specs = build_horizon_suite(
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
    horizon_stat_names = {
        stat for stat, reg in SINGLE_FACTOR_STATS.items() if reg.tier in ("1_5yr", "10yr")
    } | {stat for stat, reg in PANEL_STATS.items() if reg.tier in ("1_5yr", "10yr")}

    loaded = prereg.load()
    inert: list[str] = []
    for block, entries in loaded.block_thresholds.items():
        for key in entries:
            stat = key.split(".", 1)[-1]
            if stat in horizon_stat_names and key not in produced:
                inert.append(f"thresholds.blocks.{block}.{key}")
    for key in loaded.panel_thresholds:
        if key in horizon_stat_names and key not in produced:
            inert.append(f"thresholds.panel.{key}")

    assert not inert, f"horizon-tier threshold key(s) with no producing metric: {inert}"


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


# --------------------------------------------------------------------------- #
# WP2.2 Task 4: thresholds.strategies -- "<strategy_id>.<stat>", strategy_id a
# d4_strategies entry of THIS document, stat in ah.eval.reference.STRATEGY_STATS.
# --------------------------------------------------------------------------- #


def test_load_parses_thresholds_strategies() -> None:
    """The two example rows the real file declares (WP2.2 Task 4) round-trip."""
    loaded = prereg.load()
    assert "sixty_forty.elicitability_score" in loaded.strategy_thresholds
    assert loaded.strategy_thresholds["sixty_forty.elicitability_score"].severity == "report"


def test_verify_accepts_the_real_files_strategy_thresholds() -> None:
    """The real pre-registration.yaml's own thresholds.strategies rows verify clean --
    proven independently of test_verify_accepts_the_real_pre_registration_file (which
    covers every section at once) so a regression here is diagnosable on its own."""
    loaded = prereg.load()
    prereg.verify(loaded, load_manifest())  # must not raise


def _verify_with_strategy_threshold(tmp_path: Path, key: str) -> None:
    doc = _load_real_doc()
    doc.setdefault("thresholds", {}).setdefault("strategies", {})
    doc["thresholds"]["strategies"][key] = {"min": None, "max": 10.0, "severity": "enforce"}
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_a_strategy_id_not_in_this_documents_d4_strategies(
    tmp_path: Path,
) -> None:
    with pytest.raises(PreRegError, match="not_a_real_strategy"):
        _verify_with_strategy_threshold(tmp_path, "not_a_real_strategy.elicitability_score")


def test_verify_rejects_an_unregistered_strategy_stat(tmp_path: Path) -> None:
    with pytest.raises(PreRegError, match="not a registered strategy statistic"):
        _verify_with_strategy_threshold(tmp_path, "sixty_forty.not_a_real_stat")


def test_verify_rejects_a_malformed_strategy_threshold_key(tmp_path: Path) -> None:
    with pytest.raises(PreRegError, match="strategy threshold key"):
        _verify_with_strategy_threshold(tmp_path, "sixty_forty.elicitability_score.extra")


def test_verify_rejects_a_cross_style_strategy_threshold_key(tmp_path: Path) -> None:
    with pytest.raises(PreRegError, match="strategy threshold key"):
        _verify_with_strategy_threshold(tmp_path, "sixty_forty~carry.elicitability_score")


def test_verify_uses_this_documents_own_d4_strategies_not_the_real_repo_file(
    tmp_path: Path,
) -> None:
    """The key design choice: a strategy id is checked against THIS document's own
    ``d4_strategies:`` block, never a fresh ``ah.strategies.load_d4_strategies()`` call
    (which always reads the real repo-root file). A synthetic strategy declared only in
    this fixture must verify; one absent from it must not, even if it happens to be a
    real D4 strategy id in the actual repo file."""
    doc = _load_real_doc()
    doc["d4_strategies"]["synthetic_only"] = dict(doc["d4_strategies"]["sixty_forty"])
    doc.setdefault("thresholds", {}).setdefault("strategies", {})
    doc["thresholds"]["strategies"]["synthetic_only.elicitability_score"] = {
        "min": None,
        "max": 5.0,
        "severity": "report",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))  # must not raise


def test_block_addition_carries_strategy_thresholds_through_unchanged(tmp_path: Path) -> None:
    """Symmetric with the panel-threshold guarantee below: a strategy statistic is not
    block-scoped either, so a block_addition amendment must not touch it. Mirrors
    ``test_block_addition_carries_panel_thresholds_through_unchanged``'s synthetic
    alpha/beta/gamma fixture, with a ``d4_strategies``/``thresholds.strategies``
    section added."""
    from ah.eval.prereg import Amendment, apply_block_addition

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
        "d4_strategies": {
            "test_strategy": {
                "kind": "static_weights",
                "rebalance": "monthly",
                "lookback": None,
                "rule": None,
                "weights": {"a1": 1.0},
                "params": {},
                "notes": "fixture",
            }
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
            "panel": {},
            "strategies": {
                "test_strategy.var_95": {"min": 0.0, "max": 1.0, "severity": "report"},
            },
        },
        "decisions": {},
    }
    prereg_path = tmp_path / "pre-registration.yaml"
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    before = prereg.load(prereg_path)
    assert "test_strategy.var_95" in before.strategy_thresholds

    amendment = Amendment(
        amendment_id="AMEND-GAMMA-STRATEGY",
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

    assert merged.strategy_thresholds == before.strategy_thresholds
    assert canonical_json(_threshold_dict(merged.strategy_thresholds)) == canonical_json(
        _threshold_dict(before.strategy_thresholds)
    )


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


# --------------------------------------------------------------------------- #
# WP2.2 Task 3 fix pass 1 (Important 4): a band is meaningless without the estimator
# that produced it, so every registered statistic must carry a sealed prose definition
# -- and the rule must be machine-checked, not remembered.
# --------------------------------------------------------------------------- #


def test_every_registered_statistic_has_an_estimator_definition() -> None:
    """Both directions. A statistic missing from
    ``prereg.ESTIMATOR_CONVENTION_KEYS`` fails (nobody said which block defines it), and
    so does one whose named block is absent from ``pre-registration.yaml`` (the block
    was named but never written). Task 3 originally shipped eight estimators with
    neither, leaving the constants that change the numbers -- VARIANCE_RATIO_MIN_SUMS,
    DRAWDOWN_MIN_EPISODES, LONG_INFLATION_MIN_RUN_MONTHS, the 120-month decade window,
    nominal-not-real -- reconstructible only from ``reference.py``."""
    real = prereg.load(ROOT / "pre-registration.yaml")
    assert prereg.missing_estimator_definitions(real) == ()


def test_estimator_convention_table_names_no_statistic_that_does_not_exist() -> None:
    """The reverse guard: a renamed or dropped statistic must not leave a stale row
    pointing at nothing, which would make the check above pass vacuously for it."""
    from ah.eval.reference import (
        CROSS_BLOCK_STATS,
        PANEL_STATS,
        SINGLE_FACTOR_STATS,
        STRATEGY_STATS,
    )

    registered = {*SINGLE_FACTOR_STATS, *CROSS_BLOCK_STATS, *PANEL_STATS, *STRATEGY_STATS}
    stale = sorted(set(prereg.ESTIMATOR_CONVENTION_KEYS) - registered)
    assert not stale, f"ESTIMATOR_CONVENTION_KEYS names unregistered statistic(s): {stale}"


# --------------------------------------------------------------------------- #
# WP2.3 -- the seal itself.
#
# STEP2-GENERATOR-PLAN Sec.WP2.3's acceptance is two sentences: "modified YAML or
# modified enforce-metric code with a stale lock fails loudly; amendment log
# round-trips." Both halves are asserted here (the log's round trip against the real
# committed file is `test_the_real_amendment_log_opens_with_the_d6_pre_authorization`
# above), together with the four sealed-document checks WP2.3 added to `verify()`.
# --------------------------------------------------------------------------- #

REAL_LOCK_PATH = ROOT / "pre-registration.lock"


def test_the_committed_lock_verifies_against_the_committed_tree() -> None:
    """The seal is real: the lock in the repository matches the files in the repository.

    This is the test that fails the moment ANY hashed file changes without a re-seal --
    every metric suite, ``reference.py``, ``battery.py``, ``prereg.py`` itself,
    ``splits.py``, ``strategies.py``, ``factors.py``, ``derive.py``, the battery report
    modules, the authored conditional worlds, ``factors.yaml``, and
    ``pre-registration.yaml``. That is the one-way door working, not a brittle test: the
    remedy is an amendment plus a re-seal, and the procedure is stated in
    ``pre-registration.yaml``'s header.
    """
    loaded = prereg.load(REAL_PREREG_PATH)
    prereg.verify(loaded, load_manifest(), lock_path=REAL_LOCK_PATH)  # must not raise


def test_the_lock_records_what_it_hashed() -> None:
    lock = json.loads(REAL_LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["digest"].startswith("sha256:")
    assert lock["prereg_path"] == "pre-registration.yaml"
    hashed = set(lock["hashed_files"])
    # The document, the factor namespace, the judging code, and the sealed input data.
    assert "pre-registration.yaml" in hashed
    assert "factors.yaml" in hashed
    assert "src/ah/eval/g2.py" in hashed
    assert "src/ah/eval/reference.py" in hashed
    assert "src/ah/eval/prereg.py" in hashed
    assert "src/ah/splits.py" in hashed
    assert "src/ah/eval/metrics/monthly.py" in hashed
    # WP2.3's two seal-scope decisions (pre-registration.yaml's `seal_scope:` block).
    assert "src/ah/data/derive.py" in hashed
    assert "src/ah/battery/thresholds.yaml" in hashed
    # CAMPAIGN-2: splice.py JOINED the seal (seal_scope.splice_py: SEALED --
    # RFR-50's re-entry condition fired; its PINNED_FITS now shape sealed bands).
    assert "src/ah/data/splice.py" in hashed
    assert any(p.startswith("fixtures/worlds/conditional/") for p in hashed)


def _sealed_copy(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A tmp copy of the real pre-registration/factors, with a freshly written lock."""
    prereg_path, factors_path = _copy_real_prereg_and_factors(tmp_path)
    lock_path = tmp_path / "pre-registration.lock"
    prereg.seal(prereg_path, out_path=lock_path, sealed_at="2026-07-26")
    return prereg_path, factors_path, lock_path


def test_a_modified_yaml_with_a_stale_lock_fails_loudly(tmp_path: Path) -> None:
    """Acceptance, half one: MODIFIED YAML + stale lock must fail.

    The edit is a real one a threshold author might make -- widening an enforce bound --
    not a whitespace change, so this proves the digest is over content that matters.
    """
    prereg_path, factors_path, lock_path = _sealed_copy(tmp_path)
    loaded = prereg.load(prereg_path)
    prereg.verify(loaded, load_manifest(factors_path), lock_path=lock_path)  # baseline

    doc = yaml.safe_load(prereg_path.read_text(encoding="utf-8"))
    doc["thresholds"]["panel"]["moment_band_exceedance_fraction"]["max"] = 0.9
    prereg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    reloaded = prereg.load(prereg_path)
    with pytest.raises(PreRegError, match="does not match sealed digest"):
        prereg.verify(reloaded, load_manifest(factors_path), lock_path=lock_path)


def test_modified_enforce_metric_code_with_a_stale_lock_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance, half two, and THE HALF THAT IS EASY TO GET WRONG.

    A seal over thresholds alone is worthless: the same YAML judged by different code is
    a different criterion. STEP2-GENERATOR-PLAN Sec.WP2.3 therefore requires the
    ENFORCE-METRIC IMPLEMENTATIONS inside the digest, and CLAUDE.md states the invariant
    as "thresholds AND the code that judges them".

    So this test seals over a COPIED source tree, edits the module that implements the
    three ``*_band_exceedance_fraction`` enforce gates -- ``ah/eval/metrics/monthly.py``,
    real judging code, not a stand-in -- and asserts verification then fails. Nothing
    about the YAML changes.
    """
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "src", repo / "src")
    shutil.copytree(ROOT / "fixtures", repo / "fixtures")
    shutil.copy(REAL_PREREG_PATH, repo / "pre-registration.yaml")
    shutil.copy(REAL_FACTORS_PATH, repo / "factors.yaml")
    monkeypatch.setattr(prereg, "_REPO_ROOT", repo)

    prereg_path = repo / "pre-registration.yaml"
    lock_path = repo / "pre-registration.lock"
    prereg.seal(prereg_path, out_path=lock_path, sealed_at="2026-07-26")
    loaded = prereg.load(prereg_path)
    prereg.verify(loaded, load_manifest(repo / "factors.yaml"), lock_path=lock_path)

    gate_module = repo / "src" / "ah" / "eval" / "metrics" / "monthly.py"
    assert "band_exceedance" in gate_module.read_text(encoding="utf-8")
    gate_module.write_text(
        gate_module.read_text(encoding="utf-8") + "\n# an edit to enforce-metric code\n",
        encoding="utf-8",
    )

    with pytest.raises(PreRegError, match="does not match sealed digest"):
        prereg.verify(loaded, load_manifest(repo / "factors.yaml"), lock_path=lock_path)


def test_sealed_splits_match_the_code(tmp_path: Path) -> None:
    """RFR-6. The sealed boundaries and ``ah.splits`` must be identical, and a
    divergence must name itself rather than surfacing as an opaque lock violation."""
    from ah.splits import SPLITS

    doc = _load_real_doc()
    assert {name: (s["start"], s["end"]) for name, s in doc["splits"].items()} == {
        name: (s.start, s.end) for name, s in SPLITS.items()
    }

    doc["splits"]["validation"]["end"] = "2022-01-01"
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match=r"does not match ah\.splits\.SPLITS"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_a_threshold_on_a_factor_with_no_data(tmp_path: Path) -> None:
    """RFR-5, closed. A threshold on a factor with no train+validation data judges
    nothing, silently, forever -- and at ENFORCE, under THE ONE NaN RULE, it fails every
    run forever, reading in the artifact as a real generator defect.

    RE-TARGETED AT THE RE-SEAL, and the reason is the finding. This test used to name
    ``policy_rate``, which was in ``missing_factors`` only because campaign vintage
    2026-07-24 predated ``fred.FEDFUNDS``'s registration -- a stale snapshot, not a data
    gap. On 2026-07-26.1 that factor has 798 train+validation months and a real sealed
    band, so it is no longer an example of anything. ``hy_spread`` is the durable one:
    FRED serves ~3 licensed years of it and all of them fall inside the holdout, so no
    refresh will ever give it a train+validation sample. The check is unchanged; only
    the factor it is demonstrated on has moved to one that is genuinely absent.
    """
    doc = _load_real_doc()
    # CAMPAIGN-2: hy_spread left missing_factors (the pinned splice restored it --
    # the "no refresh will ever" sentence above was true of refreshes and the
    # splice is not one). commodities is now the sole, durable demonstration
    # factor: declared unavailable, no candidate series free (RFR-8).
    assert "commodities" in doc["reference_run"]["missing_factors"]
    doc["thresholds"]["blocks"]["global"]["commodities.excess_kurtosis"] = {
        "min": -2.0,
        "max": 50.0,
        "severity": "enforce",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match="no computable reference statistic"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_a_threshold_on_an_uncomputable_d4_strategy(tmp_path: Path) -> None:
    """The strategy-scoped half of RFR-5.

    RE-TARGETED AT THE RE-SEAL for the same reason as the factor-scoped test above: this
    used to name ``carry``, whose funding leg derives from ``policy_rate`` and which the
    campaign-vintage move made computable (it now carries four sealed thresholds).
    ``endowment_proxy`` is the durable example -- it is blocked twice over, by
    ``commodities`` (unsourced) and independently by ``hy_spread`` via ``credit_xs_hy``,
    so sourcing either one alone would not restore it.
    """
    doc = _load_real_doc()
    assert "endowment_proxy" in doc["reference_run"]["uncomputable_d4_strategies"]
    doc["thresholds"]["strategies"]["endowment_proxy.var_95"] = {
        "min": 0.0,
        "max": 1.0,
        "severity": "report",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match="uncomputable_d4_strategies"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_rejects_enforce_on_a_structurally_unavailable_statistic(tmp_path: Path) -> None:
    """A NaN ``enforce`` metric fails EVERY run forever. The status was visible on the
    MetricSpec before WP2.3, but nothing stopped a threshold being sealed on it."""
    doc = _load_real_doc()
    doc["thresholds"]["blocks"]["global"]["equity_mkt.ergodicity_gap"] = {
        "min": None,
        "max": 1.0,
        "severity": "enforce",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    with pytest.raises(PreRegError, match="structurally_unavailable"):
        prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))


def test_verify_allows_report_on_a_structurally_unavailable_statistic(tmp_path: Path) -> None:
    """The rule is about ENFORCE, not about the name: an unavailable statistic may still
    carry a reported bound, and sealing the name is what makes it amendable later."""
    doc = _load_real_doc()
    doc["thresholds"]["blocks"]["global"]["equity_mkt.ergodicity_gap"] = {
        "min": None,
        "max": 1.0,
        "severity": "report",
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    prereg.verify(prereg.load(prereg_path), load_manifest(factors_path))  # must not raise


def test_the_sealed_unavailable_list_matches_what_the_suites_actually_mark() -> None:
    """Both directions, against a REAL suite registration.

    ``verify()`` reads the sealed list rather than importing the suites (it cannot --
    they import ``ah.eval.battery``, which imports ``prereg``), and the sealed file must
    be reconstructible on its own. That makes this test the only thing tying the sealed
    list to reality: a statistic the platform marks unavailable but the file omits could
    then be sealed at enforce, and a name in the file the platform actually computes
    would bar an enforce bound for no reason.
    """
    from ah.eval import battery as battery_mod
    from ah.eval.reference import ReferenceStats

    manifest = load_manifest()
    reference = ReferenceStats(
        blocks={},
        cross_blocks={},
        active_blocks=manifest.active_blocks,
        vintage_id="v",
        n_resamples=1,
        seed=0,
        missing_factors=(),
    )
    marked: set[str] = set()
    for module_name, builder_name in battery_mod._REFERENCE_DEPENDENT_SUITE_BUILDERS.values():
        module = __import__(module_name, fromlist=[builder_name])
        for spec in getattr(module, builder_name)(manifest, reference):
            if spec.status == battery_mod.STRUCTURALLY_UNAVAILABLE:
                marked.add(spec.name.rsplit(".", 1)[-1])

    sealed = set(_load_real_doc()["structurally_unavailable_statistics"])
    assert marked == sealed, (
        f"marked-but-unsealed: {sorted(marked - sealed)}; "
        f"sealed-but-not-marked: {sorted(sealed - marked)}"
    )


def test_verify_checks_the_sealed_ensemble_size() -> None:
    """The owner's decision: the gate bounds are calibrated at ONE ensemble size, and a
    criterion-bearing run at any other size means something different by an amount
    nobody has measured. The check is OPTIONAL by design -- a small diagnostic run must
    stay runnable (the negative-control suite runs at 16 paths) -- so
    ``BatteryReport.criterion_bearing`` and ``ah/eval/g2.py`` are the hard gate, and
    this is the check they call."""
    loaded = prereg.load(REAL_PREREG_PATH)
    manifest = load_manifest()
    size = loaded.raw["ensemble_size"]
    prereg.verify(
        loaded,
        manifest,
        ensemble_n_paths=size["n_paths"],
        ensemble_months=size["months"],
    )  # must not raise
    with pytest.raises(PreRegError, match="the sealed criterion size"):
        prereg.verify(loaded, manifest, ensemble_n_paths=16)
    with pytest.raises(PreRegError, match="sealed criterion length"):
        prereg.verify(loaded, manifest, ensemble_months=60)


def test_the_reference_run_script_agrees_with_the_sealed_parameters() -> None:
    """Every historical band in the sealed file came from ONE run of
    ``scripts/compute_campaign_reference.py``. If that script's defaults and the sealed
    ``reference_run:`` block drift apart, "reproduce with this command" stops being
    true -- and ``data/`` is gitignored, so that command is the only reproduction path a
    reader without the catalog has."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_campaign_reference", ROOT / "scripts" / "compute_campaign_reference.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    doc = _load_real_doc()
    run = doc["reference_run"]
    assert run["vintage_id"] == module.CAMPAIGN_VINTAGE_ID
    assert run["seed"] == module.REFERENCE_SEED
    assert run["n_resamples"] == module.N_RESAMPLES
    assert run["level"] == module.LEVEL
    assert run["block_length"] == module.BLOCK_LENGTH
    assert run["resample_length"] == module.RESAMPLE_LENGTH
    # The replicate length IS the sealed criterion path length -- that equality is what
    # makes every length-matched band comparable to the ensemble it judges.
    assert doc["ensemble_size"]["months"] == module.RESAMPLE_LENGTH
    assert run["vintage_id"] == doc["campaign_vintage_id"]


# --------------------------------------------------------------------------- #
# WP2.3 re-seal -- the multi-seed rule's tail tier (review Critical 1)
# --------------------------------------------------------------------------- #


def test_the_sealed_tail_tier_is_a_suite_because_no_tail_TIER_exists() -> None:
    """The re-seal defines "the tail tier" as the ``tails`` SUITE, not a horizon tier.

    That phrasing is not stylistic: ``ah.eval.battery.TIERS`` has no ``tail`` member and
    every ``ah.eval.metrics.tails`` spec is registered ``tier="monthly"``, so the first
    seal's promotion rule named something nothing could resolve. If a later work package
    ever adds a real ``tail`` tier, this test fails and the sealed wording must be
    revisited by amendment rather than silently reinterpreted.
    """
    from ah.eval.battery import TIERS

    assert "tail" not in TIERS
    assert "tails" not in TIERS

    doc = _load_real_doc()
    rule = doc["multi_seed_decision_rule"]
    assert "tail_tier_definition" in rule
    assert "beats_definition" in rule
    assert 'suite == "tails"' in rule["tail_tier_definition"]


def test_the_sealed_tail_tier_definition_matches_the_registered_statistics() -> None:
    """The sealed definition enumerates the tail suite's two families by name. Those
    names come from ``ah.eval.reference``'s registries, which are what
    ``ah.eval.metrics.tails.build_tails_suite`` builds its specs from -- so the sealed
    words and the emitted metrics cannot drift without this failing."""
    from ah.eval.reference import CROSS_BLOCK_STATS, STRATEGY_STATS

    doc = _load_real_doc()
    definition = doc["multi_seed_decision_rule"]["tail_tier_definition"]

    # Family (a): every registered D4 strategy statistic, and there are eleven.
    assert len(STRATEGY_STATS) == 11
    assert "eleven names" in definition
    for stat in ("var_95", "es_95", "var_99", "es_99", "elicitability_score"):
        assert stat in STRATEGY_STATS
        assert stat in definition
    for prefix in (
        "kupiec_pof",
        "christoffersen_independence",
        "christoffersen_conditional_coverage",
    ):
        assert f"{prefix}_lr_1path" in STRATEGY_STATS
        assert f"{prefix}_chi2_tail_1path" in STRATEGY_STATS
        assert prefix in definition

    # Family (b): the two cross-block tail-dependence statistics.
    for stat in ("tail_dependence_lower", "tail_dependence_upper"):
        assert stat in CROSS_BLOCK_STATS
        assert stat in definition

    # The comparison set is defined by subtraction from the sealed lists, so both must
    # be present and the subtraction must be non-empty (otherwise clause (1) of the
    # promotion rule compares nothing).
    strategy_ids = set(doc["d4_strategies"])
    uncomputable = set(doc["reference_run"]["uncomputable_d4_strategies"])
    assert uncomputable < strategy_ids
    assert strategy_ids - uncomputable


def test_the_sealed_beats_definition_names_a_directional_registered_statistic() -> None:
    """ "Beats" is defined on ``elicitability_score`` -- the only directional scalar in
    the suite. If that name ever leaves ``STRATEGY_STATS`` the promotion rule's objective
    becomes uncomputable, which is the failure this pins."""
    from ah.eval.reference import STRATEGY_STATS

    doc = _load_real_doc()
    beats = doc["multi_seed_decision_rule"]["beats_definition"]
    assert "elicitability_score" in STRATEGY_STATS
    assert "elicitability_score" in beats
    # The three properties that make the clause executable rather than rhetorical.
    assert "STRICTLY LOWER" in beats
    assert "ddof=1" in beats
    assert "NaN" in beats


def test_the_benchmark_draw_span_bias_is_sealed_and_names_its_direction() -> None:
    """Review Critical 2: the benchmark's 1990-2020 draw span biases the head-to-head
    TOWARD promotion, and that must be inside the hash rather than in a report."""
    doc = _load_real_doc()
    bias = doc["multi_seed_decision_rule"]["benchmark_draw_span_bias"]
    assert "TOWARD PROMOTION" in bias
    span = doc["bootstrap_v1"]["block_draw_span"]
    assert str(span["start"]) in bias or "1990-2020" in bias
    # HISTORY: sealed as equity_vol at G2 (the claim was checkable, not narrative).
    # AM-2026-08-09-002 (span-53 ratification) moved the span to 1953-04 and the
    # binding factor to ust_2y (the GS1/GS3 donor floor); the amended consequence
    # prose records the G2-era text verbatim as history.
    assert doc["bootstrap_v1"]["block_draw_span_binding_factor"] == "ust_2y"
    assert doc["bootstrap_v1"]["block_draw_span"]["months"] == 813
    assert "AM-2026-08-09-002" in doc["bootstrap_v1"]["block_draw_span_consequence"]


def test_the_tuning_selection_lambda_is_pinned_to_a_number() -> None:
    """Review Important 5: the first seal referred to "the config's own sealed lambda"
    and sealed no lambda anywhere, which pinned nothing and would have let each trial
    carry its own weighting."""
    doc = _load_real_doc()
    tuning = doc["tuning_protocol"]
    assert isinstance(tuning["selection_lambda"], (int, float))
    assert "selection_lambda" in tuning["selection_criterion"]


def test_the_mc_error_grid_is_sealed_and_brackets_the_sealed_ensemble_size() -> None:
    """Review Important 3: the MC-error grid that justifies ``ensemble_size.n_paths``
    used to live in the UNSEALED decision register, and the sealed size (1000) was not
    one of the sizes it measured (1024). Both are now inside the hash, and the sealed
    size must be a MEASURED point of the grid, not an interpolation between two."""
    doc = _load_real_doc()
    size = doc["ensemble_size"]
    grid = size["mc_error_grid"]
    assert str(size["n_paths"]) in {str(k) for k in grid["rows"]}
    assert size["n_paths"] == max(int(k) for k in grid["rows"])


def test_the_mc_error_grid_script_agrees_with_the_sealed_grid() -> None:
    """``scripts/measure_mc_error_grid.py`` is the sealed grid's provenance script; its
    measured sizes and generator parameters must match what the file seals."""
    import importlib.util
    import sys

    scripts_dir = ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "_mc_error_grid", scripts_dir / "measure_mc_error_grid.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts_dir))

    doc = _load_real_doc()
    grid = doc["ensemble_size"]["mc_error_grid"]
    assert sorted(int(k) for k in grid["rows"]) == sorted(module.N_PATHS_GRID)
    assert grid["mean_block_months"] == module.MEAN_BLOCK_MONTHS
    assert grid["mean_block_months"] == doc["bootstrap_v1"]["mean_block_months"]
    assert doc["ensemble_size"]["months"] == module.MONTHS


def test_the_block_length_window_script_agrees_with_the_sealed_vintage() -> None:
    """``scripts/measure_block_length_window.py`` is the provenance script for
    ``bootstrap_v1.block_length_derivation``; it must read the sealed campaign vintage
    and the sealed reference-run parameters, or the quoted window is a window over
    different data."""
    import importlib.util
    import sys

    scripts_dir = ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "_block_length_window", scripts_dir / "measure_block_length_window.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts_dir))

    doc = _load_real_doc()
    assert doc["campaign_vintage_id"] == module.CAMPAIGN_VINTAGE_ID
    assert doc["reference_run"]["seed"] == module.REFERENCE_SEED
    assert doc["bootstrap_v1"]["mean_block_months"] in module.BLOCK_LENGTHS


# --------------------------------------------------------------------------- #
# WP2.3 final pass -- the four sealed-text fixes closing the re-seal review
# --------------------------------------------------------------------------- #


def test_the_sealed_splice_scope_rests_on_the_true_premise() -> None:
    """The seal keeps ``ah/data/splice.py`` OUTSIDE the hash, and that conclusion is
    unchanged and independently demonstrated -- but the sealed justification used to
    rest on a premise that the campaign-vintage move made false.

    It read "policy_rate and hy_spread appear in reference_run.missing_factors precisely
    BECAUSE the backfills are absent". ``policy_rate`` is NOT in ``missing_factors`` on
    vintage 2026-07-26.1: it is present, and what demonstrates its backfill is unapplied
    is its START DATE (``fred.FEDFUNDS``'s own 1954-07, not ``fred.TB3MS``'s 1934-01).
    The correct wording already existed in ``ah/eval/prereg.py`` and ``factors.yaml``;
    this pins it into the sealed block too, in both directions.
    """
    doc = _load_real_doc()
    missing = doc["reference_run"]["missing_factors"]
    assert "policy_rate" not in missing
    # CAMPAIGN-2: hy_spread left missing_factors -- the hy_oas_pre1996 rule is
    # applied at the read surface with a pinned fit, which is exactly the
    # consequence clause the WP2.3 reasoning predicted. The premise this test
    # pins is therefore the NEW one, in both directions: the factor resolves,
    # splice.py is INSIDE the hash, and the pinned constants exist.
    assert "hy_spread" not in missing
    assert missing == ["commodities"]

    assert doc["seal_scope"]["splice_py"] == "SEALED"
    assert "SEALED AT CAMPAIGN-2" in doc["seal_scope"]["splice_py_reason"]
    superseded = doc["seal_scope"]["splice_py_superseded_wp23_reason"]
    # The superseded WP2.3 reasoning survives verbatim, corrections included --
    # a reader can still see why it was out and what was said would bring it in.
    assert 'previously read "policy_rate and hy_spread appear in' in superseded
    assert "fedfunds_pre1954" in superseded and "NEITHER backfill" in superseded
    assert "splice.py joins the seal" in superseded

    from ah.eval.prereg import _REQUIRED_JUDGED_SOURCES

    assert ("src", "ah", "data", "splice.py") in _REQUIRED_JUDGED_SOURCES
    from ah.data.splice import PINNED_FITS

    assert "hy_oas_pre1996" in PINNED_FITS


def test_the_sealed_beats_clause_two_discloses_that_no_strategy_band_exists() -> None:
    """Clause (ii) is scoped to usable REFERENCE bands, and no strategy statistic has
    one -- ``RegisteredStrategyStat`` carries no ``fn``, by construction. So clause (ii)
    can only ever count the cross-block tail-dependence family, and "NO TAIL-BAND
    REGRESSION over comparison-set metrics" must not be read as covering
    ``var_95``/``es_95``/``es_99``. Disclosure, not a behaviour change: the clause is
    unchanged and still deterministic.
    """
    import dataclasses as _dc

    from ah.eval.reference import STRATEGY_STATS

    # The structural fact the disclosure rests on, asserted rather than described.
    assert STRATEGY_STATS
    for name, registered in STRATEGY_STATS.items():
        assert not hasattr(registered, "fn"), name
    assert {f.name for f in _dc.fields(next(iter(STRATEGY_STATS.values())))} == {"tier"}

    beats = _load_real_doc()["multi_seed_decision_rule"]["beats_definition"]
    assert "tail_dependence_lower/upper" in beats
    assert "ZERO strategy-level metrics" in beats
    # The alternative is named for the record, and named as NOT taken.
    assert "thresholds.strategies" in beats


def test_the_sealed_lambda_invariance_argument_states_its_own_limit() -> None:
    """``selection_lambda`` stays 1.0 and is never re-fitted. What changed is the
    REASON: the objectives are incommensurable across arms (D runs an ELBO sampler and
    an exact-likelihood sampler), so a fixed lambda gives the D4 auxiliary a different
    EFFECTIVE weight per arm. Invariance is invariance of the RULE, not of the weight.
    """
    doc = _load_real_doc()
    tuning = doc["tuning_protocol"]
    assert tuning["selection_lambda"] == 1.0  # unchanged; this pass re-words, not re-fits
    criterion = tuning["selection_criterion"]
    assert "DIFFERENT QUANTITY" in criterion
    assert "EFFECTIVE" in criterion
    # The two samplers whose objectives are not on one scale are a sealed fact.
    assert "hier-diffusion-v1" in doc["ablation_systems"]["D"]["description"]
    assert "hier-flow-v1" in doc["ablation_systems"]["D"]["description"]
    # The obligation this puts on WP2.8.
    assert "WP2.8" in criterion


def test_the_sealed_criterion_bearing_sentence_describes_a_check_that_exists() -> None:
    """A sealed file must not claim a check it does not have. The sentence named three
    conditions -- sealed size, sealed campaign_vintage_id, verified prereg+lock -- and
    ``ah.eval.battery`` compared only the size. The code was extended rather than the
    sentence weakened; this asserts both halves against the live implementation.
    """
    from ah.eval.battery import criterion_bearing_for

    doc = _load_real_doc()
    sentence = doc["multi_seed_decision_rule"]["criterion_bearing_runs_only"]
    assert "campaign_vintage_id" in sentence
    assert "ensemble.meta.vintage_id" in sentence
    # The g2.py refusal is still a REQUIREMENT, not a description -- unchanged.
    assert "does not exist yet" in sentence

    loaded = prereg.load(REAL_PREREG_PATH)
    size = loaded.raw["ensemble_size"]

    def _ensemble(vintage_id: str) -> Any:
        import numpy as np

        from ah.gen.base import Ensemble, EnsembleMeta

        return Ensemble(
            paths=np.zeros((size["n_paths"], size["months"], 1)),
            factor_names=["g1"],
            meta=EnsembleMeta(
                generator_id="test",
                vintage_id=vintage_id,
                seed=0,
                n_paths=size["n_paths"],
                months=size["months"],
            ),
        )

    assert criterion_bearing_for(_ensemble(loaded.raw["campaign_vintage_id"]), loaded) is True
    assert criterion_bearing_for(_ensemble("2026-07-24"), loaded) is False


# --------------------------------------------------------------------------- #
# The claims sweep (2026-07-26): `claims_with_tests` -- the standing check that makes
# a sealed sentence describing a check answerable to the code.
#
# Background, because it is the whole reason these tests exist. Two sealed sentences
# were false about the implementation and both survived multiple review passes:
# `seal_scope.splice_py_reason` (asserted `policy_rate` is in `missing_factors`; it is
# not) and `multi_seed_decision_rule.criterion_bearing_runs_only` (named three
# conditions; `battery.py` compared two quantities and nothing else). Each was fixed
# with its own test. The CLASS was not -- nothing made prose answerable to code in
# general -- and the claims-sweep pass found seven more instances.
# `claims_with_tests` is the registry; these three tests are what make it bind.
# --------------------------------------------------------------------------- #

_MIN_ANCHOR_CHARS = 40


def _claims_registry() -> dict[str, Any]:
    registry = _load_real_doc()["claims_with_tests"]
    assert isinstance(registry, dict)
    return registry


def _prereg_lines() -> list[str]:
    return REAL_PREREG_PATH.read_text(encoding="utf-8").splitlines()


def _registry_region(lines: list[str]) -> set[int]:
    """1-based line numbers of the ``claims_with_tests`` block *and its own banner*.

    The registry quotes every anchor verbatim and its own prose necessarily contains
    trigger phrases, so it is excluded from both the anchor search and the completeness
    scan -- otherwise the registry would have to register itself and every anchor would
    match twice by construction.
    """
    key = next(i for i, line in enumerate(lines, 1) if line.startswith("claims_with_tests:"))
    start = key
    while start - 2 >= 0 and lines[start - 2].startswith("#"):
        start -= 1
    end = next(i for i, line in enumerate(lines, 1) if i > key and re.match(r"^[a-z_]+:", line))
    return set(range(start, end))


def _defined_test_functions(path: Path) -> set[str]:
    """Every ``def test_*`` defined at any level of ``path``, read by AST.

    AST rather than import: this stays a cheap textual check that cannot be satisfied
    by a name that only exists at runtime, and cannot fail because some unrelated
    module-level import in the target file broke.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def test_every_sealed_claim_is_pinned_by_a_test_that_exists() -> None:
    """Guarantee (1) of ``claims_with_tests``: every ``pinned_by`` entry resolves.

    A claim cannot be "pinned" by a test somebody renamed or deleted -- which is
    exactly how a registry rots into decoration. This checks that the file exists and
    the function is defined in it; it deliberately does NOT check that the test asserts
    what the sentence says, and the sealed block states that limit as (b).

    An empty ``pinned_by`` is legal only with a non-``pinned`` ``status``, so "this
    claim has no test" is a sealed, visible declaration rather than an empty list
    nobody notices.
    """
    registry = _claims_registry()
    claims = registry["claims"]
    assert claims, "claims_with_tests.claims must not be empty"

    cache: dict[Path, set[str]] = {}
    problems: list[str] = []
    for claim_id, claim in claims.items():
        for field in ("claim", "covers", "pinned_by", "status"):
            assert field in claim, f"{claim_id}: missing '{field}'"
        assert isinstance(claim["claim"], str) and claim["claim"].strip(), claim_id
        assert claim["covers"], f"{claim_id}: must anchor at least one sealed line"
        pinned = claim["pinned_by"] or []
        status = claim["status"]
        if not pinned:
            if status == "pinned":
                problems.append(f"{claim_id}: status 'pinned' with an empty pinned_by")
            continue
        if status != "pinned":
            problems.append(f"{claim_id}: status {status!r} but names {len(pinned)} test(s)")
        for ref in pinned:
            if "::" not in ref:
                problems.append(f"{claim_id}: '{ref}' is not '<file>::<test>'")
                continue
            rel, func = ref.split("::", 1)
            path = ROOT / rel
            if not path.exists():
                problems.append(f"{claim_id}: '{ref}' names a file that does not exist")
                continue
            if path not in cache:
                cache[path] = _defined_test_functions(path)
            if func not in cache[path]:
                problems.append(f"{claim_id}: '{ref}' names a test not defined in {rel}")
    assert not problems, "claims_with_tests.pinned_by does not resolve:\n" + "\n".join(problems)


def test_every_sealed_claim_anchor_still_matches_its_sentence() -> None:
    """Guarantee (2): every ``covers`` / ``not_a_code_claim`` anchor still matches the
    sealed text, on a line the detector flags, and is long enough not to be vague.

    This is what makes re-wording a claim-bearing line BREAK the suite rather than
    silently orphan its registration. Anchors need not be unique -- two sections
    legitimately quote one test name verbatim -- but every line an anchor matches must
    itself carry a trigger phrase, so a generic anchor cannot be stretched over
    ordinary prose.
    """
    registry = _claims_registry()
    lines = _prereg_lines()
    region = _registry_region(lines)
    triggers = registry["trigger_phrases"]
    assert triggers, "the sealed detector must declare at least one trigger phrase"

    anchors: list[tuple[str, str]] = [
        (claim_id, anchor)
        for claim_id, claim in registry["claims"].items()
        for anchor in claim["covers"]
    ]
    anchors += [("<not_a_code_claim>", e["anchor"]) for e in registry["not_a_code_claim"]]

    problems: list[str] = []
    for owner, anchor in anchors:
        if len(anchor) < _MIN_ANCHOR_CHARS:
            problems.append(f"{owner}: anchor is under {_MIN_ANCHOR_CHARS} chars: {anchor!r}")
        hits = [i for i, line in enumerate(lines, 1) if i not in region and anchor in line]
        if not hits:
            problems.append(f"{owner}: anchor no longer matches the sealed text: {anchor[:70]!r}")
            continue
        for hit in hits:
            if not any(t in lines[hit - 1] for t in triggers):
                problems.append(
                    f"{owner}: anchor matches line {hit}, which carries no trigger phrase: "
                    f"{anchor[:70]!r}"
                )
    assert not problems, "claims_with_tests anchors are stale:\n" + "\n".join(problems)


def test_no_claim_shaped_sentence_is_unregistered() -> None:
    """Guarantee (3), the completeness half -- the one that would have caught both prior
    escapes at the moment they were written.

    Every line of ``pre-registration.yaml`` carrying a sealed trigger phrase must be
    covered by exactly one registered claim, or listed in ``not_a_code_claim`` with a
    stated reason. A new sentence of the form "verify() rejects X" therefore fails this
    test until someone either points it at a test or declares, inside the seal, that it
    is not a claim about the code.

    Its limit, restated here so a pass is not over-read: this is a KEYWORD detector,
    not a reader. A claim phrased with none of the sealed trigger phrases is invisible
    to it. ``trigger_phrases`` is itself sealed, so blinding the detector moves the lock
    digest and needs a dated amendment.
    """
    registry = _claims_registry()
    lines = _prereg_lines()
    region = _registry_region(lines)
    triggers = registry["trigger_phrases"]

    owner_of: dict[int, list[str]] = {}
    all_anchors = [
        (claim_id, anchor)
        for claim_id, claim in registry["claims"].items()
        for anchor in claim["covers"]
    ] + [("<not_a_code_claim>", e["anchor"]) for e in registry["not_a_code_claim"]]
    for owner, anchor in all_anchors:
        for i, line in enumerate(lines, 1):
            if i not in region and anchor in line:
                owner_of.setdefault(i, []).append(owner)

    unregistered = [
        f"  line {i}: {line.strip()[:120]}"
        for i, line in enumerate(lines, 1)
        if i not in region and any(t in line for t in triggers) and i not in owner_of
    ]
    assert not unregistered, (
        "these sealed lines look like claims about the code but are not registered in "
        "claims_with_tests -- point each at the test that pins it, or add it to "
        "not_a_code_claim with a reason:\n" + "\n".join(unregistered)
    )

    doubly_owned = [
        f"  line {i}: owned by {sorted(owners)}"
        for i, owners in owner_of.items()
        if len(owners) > 1
    ]
    assert not doubly_owned, (
        "a claim-bearing line is registered by more than one claim, so which test pins "
        "it is ambiguous:\n" + "\n".join(doubly_owned)
    )

    for entry in registry["not_a_code_claim"]:
        assert isinstance(entry.get("reason"), str) and entry["reason"].strip(), (
            f"not_a_code_claim entry {entry.get('anchor')!r} must state a reason"
        )


# --------------------------------------------------------------------------- #
# The pin tests the claims sweep found missing -- each is named by a
# `claims_with_tests` entry above.
# --------------------------------------------------------------------------- #


def test_verify_rejects_active_blocks_that_disagree_with_the_manifest(tmp_path: Path) -> None:
    """``active_blocks``'s sealed comment says verify() "checks this exactly against the
    live FactorManifest". Nothing asserted it: every existing coverage test moves the
    THRESHOLDS, not the declared block list, so a document declaring
    ``active_blocks: [global]`` against a two-block manifest was untested.
    """
    doc = _load_real_doc()
    doc["active_blocks"] = ["global"]
    prereg_path, _ = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    with pytest.raises(PreRegError, match="active_blocks"):
        prereg.verify(loaded, load_manifest())


def test_the_sealed_seal_scope_accounts_for_every_hashed_file() -> None:
    """``seal_scope`` calls this file's header and ``ah.eval.prereg``'s module docstring
    the full accounting of what is hashed. Two hashed files -- ``_pooling.py`` and
    ``negative_controls.py`` -- were named in neither, so a reader could not reconstruct
    the sealed set from the two documents that claim to state it. The SEAL was never
    short (both are in ``_REQUIRED_JUDGED_SOURCES`` and in the lock); the accounting of
    it was.
    """
    lock = json.loads((ROOT / "pre-registration.lock").read_text(encoding="utf-8"))
    accounting = (
        REAL_PREREG_PATH.read_text(encoding="utf-8")
        + "\n"
        + (ROOT / "src" / "ah" / "eval" / "prereg.py").read_text(encoding="utf-8")
    )

    suite_stems = set(prereg._METRIC_SUITE_NAMES)
    unaccounted: list[str] = []
    for rel in lock["hashed_files"]:
        # The eight authored conditional worlds are accounted for as a directory glob,
        # which is exactly how the sealed estimator names them too.
        if rel.startswith("fixtures/worlds/conditional/"):
            if "fixtures/worlds/conditional" not in accounting:
                unaccounted.append(rel)
            continue
        # A metric SUITE is accounted for collectively: both accountings say "the
        # metric suites under src/ah/eval/metrics/, and the fixed name list is
        # ah.eval.prereg._METRIC_SUITE_NAMES", so membership of that tuple IS the
        # accounting for it. Anything else under eval/metrics/ -- `_pooling.py` -- must
        # be named outright, which is the whole point of the note that a helper beside
        # the suites joins the seal only by being named.
        if rel.startswith("src/ah/eval/metrics/") and Path(rel).stem in suite_stems:
            continue
        if Path(rel).name not in accounting:
            unaccounted.append(rel)
    assert not unaccounted, (
        "pre-registration.lock hashes files that neither the sealed document's header "
        f"nor ah.eval.prereg's module docstring names: {unaccounted}"
    )


def test_the_sealed_length_matching_exception_count_is_the_registered_count() -> None:
    """``conventions.estimator_length_matching`` said THREE registered statistics depart
    from length matching, and then named four. Four registration records carry the flag.
    Counted against the live registries, in both directions.
    """
    from ah.eval.reference import CROSS_BLOCK_STATS, SINGLE_FACTOR_STATS

    unmatched = {
        name
        for registry in (SINGLE_FACTOR_STATS, CROSS_BLOCK_STATS)
        for name, stat in registry.items()
        if not getattr(stat, "length_matched", True)
    }
    assert unmatched == {
        "lost_decade_frequency",
        "long_inflation_era_frequency",
        "tail_dependence_lower",
        "tail_dependence_upper",
    }

    text = " ".join(_load_real_doc()["conventions"]["estimator_length_matching"].split())
    assert "FOUR REGISTERED STATISTICS DEPART FROM IT" in text
    assert "THREE REGISTERED STATISTICS DEPART FROM IT" not in text
    for name in unmatched:
        assert name in text, name


def test_the_sealed_panel_section_states_its_own_size() -> None:
    """The thresholds header said ``cross_block_corr_matrix_distance`` "is the one entry
    today" for the panel section. True when WP2.2 Task 4 wrote it, false by the time it
    was sealed: Tasks 5 and 6 registered dozens more into ``PANEL_STATS``. The corrected
    sentence states two counts; both are checked here rather than left to rot again.
    """
    from ah.eval.reference import PANEL_STATS

    loaded = prereg.load(REAL_PREREG_PATH)
    text = REAL_PREREG_PATH.read_text(encoding="utf-8")
    assert f"PANEL_STATS, which today holds {len(PANEL_STATS)} names" in text
    assert f"this section seals {len(loaded.panel_thresholds)}" in text
    assert "cross_block_corr_matrix_distance" in loaded.panel_thresholds
