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
import shutil
from pathlib import Path
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
    doc = _load_real_doc()
    del doc["thresholds"]["blocks"]["us"]
    doc["thresholds"]["blocks"]["uk"] = {
        "bank_rate.mean": {"min": -1.0, "max": 1.0, "severity": "report"}
    }
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    with pytest.raises(PreRegError) as excinfo:
        prereg.verify(loaded, manifest)
    message = str(excinfo.value)
    assert "'us'" in message
    assert "'uk'" in message


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


def test_verify_passes_when_conventions_pre_classifies_a_not_yet_active_block(
    tmp_path: Path,
) -> None:
    # apply_block_addition's fixture (test 10) relies on this: a conventions block may
    # classify factors of a block that isn't active *yet* without verify() rejecting
    # the file for it -- only "active factor left unclassified" and "factor classified
    # as both" are hard errors.
    doc = _load_real_doc()
    doc["conventions"]["level_factors"] = [*doc["conventions"]["level_factors"], "bank_rate"]
    prereg_path, factors_path = _write_doc_and_factors(tmp_path, doc)
    loaded = prereg.load(prereg_path)
    manifest = load_manifest(factors_path)
    prereg.verify(loaded, manifest)  # must not raise


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
# 11, 12. amendment log: append-only, round-trip
# --------------------------------------------------------------------------- #


def _amendment(amendment_id: str, **overrides: Any) -> Amendment:
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


def test_load_amendments_rejects_duplicate_ids(tmp_path: Path) -> None:
    log_path = tmp_path / "amendment-log.yaml"
    log_path.write_text(_AMENDMENT_LOG_HEADER, encoding="utf-8")
    append_amendment(log_path, _amendment("DUP"))
    append_amendment(log_path, _amendment("DUP"))
    with pytest.raises(PreRegError, match="DUP"):
        load_amendments(log_path)


def test_append_amendment_requires_existing_log(tmp_path: Path) -> None:
    with pytest.raises(PreRegError):
        append_amendment(tmp_path / "does-not-exist.yaml", _amendment("A1"))


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
    p = tmp_path / filename
    p.write_text(
        "factor_blocks:\n"
        "  alpha: [a1]\n"
        "  beta: [b1]\n"
        "  gamma: [g1]\n"
        f"active_blocks: [{', '.join(active)}]\n",
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

    # Conventions classify all three blocks' factors from the start -- a conventions
    # block declared ahead of a block's activation is not itself a verify() failure
    # (see test_verify_passes_when_conventions_pre_classifies_a_not_yet_active_block);
    # only leaving an *active* factor unclassified, or double-classifying one, is.
    doc = {
        "schema_version": "1.0",
        "sealed": False,
        "campaign_vintage_id": "test",
        "factor_manifest": "factors_before.yaml",
        "active_blocks": ["alpha", "beta"],
        "conventions": {
            "percent_to_decimal": 0.01,
            "months_per_year": 12.0,
            "return_bearing_factors": ["a1", "b1", "g1"],
            "level_factors": [],
            "rebalance_cadences": ["monthly"],
            "static_weights_composition": "test fixture",
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

    prereg_after = apply_block_addition(prereg_before, manifest_after, amendment)

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
            "return_bearing_factors": ["a1", "b1", "g1"],
            "level_factors": [],
            "rebalance_cadences": ["monthly"],
            "static_weights_composition": "test fixture",
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
    with pytest.raises(PreRegError, match="beta"):
        apply_block_addition(prereg_before, manifest_after, amendment)


# --------------------------------------------------------------------------- #
# structural sanity
# --------------------------------------------------------------------------- #


def test_dataclasses_are_frozen() -> None:
    th = Threshold(min=0.0, max=1.0, severity="report")
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        th.min = 5.0  # type: ignore[misc]

    dec = Decision(decision_id="X", status="CLOSED-deferred", consequence="text")
    with pytest.raises(Exception):  # noqa: B017
        dec.status = "OPEN"  # type: ignore[misc]

    pr = prereg.load()
    with pytest.raises(Exception):  # noqa: B017
        pr.sealed = True  # type: ignore[misc]

    amendment = _amendment("A")
    with pytest.raises(Exception):  # noqa: B017
        amendment.post_hoc = False  # type: ignore[misc]


def test_preregistration_is_a_dataclass_instance() -> None:
    assert isinstance(prereg.load(), PreRegistration)
