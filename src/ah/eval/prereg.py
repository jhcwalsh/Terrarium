"""The pre-registration seal machinery: block-nested thresholds, seal/verify,
the amendment log, and ``block_addition`` (WP2.1b Item 2 / Task 4).

WP2.3 seals the pre-registration: thresholds **and the code that judges them** are
hashed together before any training run, and after that every change is a dated,
post-hoc-flagged amendment logged in ``governance/amendment-log.yaml``. This module
builds that machinery -- with the block structure from Task 1 (``ah.factors``) already
wired through it -- so the seal freezes the right shape. **Nothing in WP2.1b actually
seals**: ``pre-registration.yaml``'s ``sealed`` flag stays ``false`` here; a dry-run
``seal()`` + ``verify()`` is the acceptance bar (Instructions/WP2.1b-PRE-SEAL-PATCH.md
Definition of done, item 4). WP2.3 is the one PR allowed to flip ``sealed: true``.

Layout
------
- :func:`load` parses ``pre-registration.yaml`` into a :class:`PreRegistration`.
- :func:`verify` checks a loaded pre-registration against a :class:`~ah.factors.FactorManifest`
  (block coverage, cross-block coverage, threshold sanity, and -- the hole this task
  closes, see below) -- and, if given a lock file, that the sealed digest still matches
  the files on disk.
- :func:`seal` computes (and, unless ``dry_run``, writes) the digest that WP2.3 will
  freeze: canonically, the pre-registration YAML, the factor manifest YAML it
  references, and the source text of every "judged" evaluation module.
- :func:`load_amendments` / :func:`append_amendment` read/extend
  ``governance/amendment-log.yaml``, which is append-only by construction (appends use
  file-append mode, so prior bytes are provably untouched).
- :func:`apply_block_addition` merges a ``block_addition`` amendment's new thresholds
  into a :class:`PreRegistration`, leaving every pre-existing block's and pair's
  thresholds byte-identical -- additive, not a re-seal (see
  ``governance/amendment-log.yaml``'s header).

The hole this task closes
--------------------------
``ah.strategies.load_conventions`` treats a *missing* ``conventions:`` block as "no
structured conventions declared" rather than an error -- a deliberate concession so
minimal hand-written test fixtures (that predate the block) keep loading. That
concession is safe everywhere it was made *except* here: this is the file the seal
hashes, so a deleted or misspelled ``conventons:`` key would silently disable the
level-factor/return-factor classification the loader would otherwise enforce, and
:mod:`ah.strategies` has no top-level unknown-key check that would catch the typo.
:func:`verify` therefore re-checks, unconditionally: the ``conventions`` block is
present; it declares every key :func:`ah.strategies.load_conventions` reads
(``percent_to_decimal``, ``months_per_year``, ``return_bearing_factors``,
``level_factors``, ``rebalance_cadences``, ``static_weights_composition``); and
``return_bearing_factors``/``level_factors`` together classify every active factor in
the given manifest, with none in both. This check reads ``PreRegistration.raw``
directly -- it does not call :mod:`ah.strategies` (which would re-read the file from a
path this module is not guaranteed to have, e.g. after :func:`apply_block_addition`
produces an in-memory-only result) and does not require every non-active factor to be
*absent* from the classification (an amendment's fixture may pre-declare a not-yet-
active block's factors; see :func:`apply_block_addition`'s docstring).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from ah.core.digest import canonical_json
from ah.factors import FactorManifest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PREREG_PATH = _REPO_ROOT / "pre-registration.yaml"

# The eight WP2.2 metric suites (STEP2-GENERATOR-PLAN Sec.WP2.2); only some exist yet
# (see `ah.eval.reference`'s module docstring). `g2.py` is always a judged source: it
# is the sanctioned holdout-token mint and the G2 decision rule.
_METRIC_SUITE_NAMES = (
    "monthly",
    "horizon",
    "tails",
    "utility",
    "memorization",
    "economics",
    "conditional",
    "calibration",
)


class PreRegError(RuntimeError):
    """Raised when a pre-registration fails to load, verify, or seal."""


# --------------------------------------------------------------------------- #
# public data types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Threshold:
    """One acceptance band: ``value in [min, max]`` (either bound may be absent)."""

    min: float | None
    max: float | None
    severity: str  # "enforce" | "report"


@dataclass(frozen=True)
class Decision:
    """One entry of ``pre-registration.yaml``'s ``decisions:`` block (Item 3, R5/J3)."""

    decision_id: str
    status: str
    consequence: str


@dataclass(frozen=True)
class PreRegistration:
    """The parsed ``pre-registration.yaml``.

    ``block_thresholds`` and ``cross_block_thresholds`` are the structured, validated
    view of the ``thresholds:`` YAML block; ``raw`` is the full parsed document (used by
    :func:`verify`'s ``conventions`` check, which this module implements independently
    of :mod:`ah.strategies` -- see the module docstring).
    """

    sealed: bool
    active_blocks: tuple[str, ...]
    block_thresholds: Mapping[str, Mapping[str, Threshold]]
    cross_block_thresholds: Mapping[tuple[str, str], Mapping[str, Threshold]]
    decisions: Mapping[str, Decision]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class Amendment:
    """One entry of ``governance/amendment-log.yaml``.

    ``type`` is one of :data:`AMENDMENT_TYPES`. ``date`` is supplied by the caller --
    never ``date.today()`` (the repo's no-clock-reads invariant; see
    ``ah.eval.prereg``'s callers, never this module, for where "today" would come
    from). ``payload`` carries type-specific data; for ``block_addition`` it is
    ``{"block": <id>, "block_thresholds": {...}, "cross_block_thresholds": {...}}``,
    each sub-mapping shaped like ``pre-registration.yaml``'s own ``thresholds.blocks.*``
    / ``thresholds.cross_blocks.*`` (see :func:`apply_block_addition`).
    """

    amendment_id: str
    type: str
    date: str
    rationale: str
    post_hoc: bool
    payload: Mapping[str, Any] = MappingProxyType({})


AMENDMENT_TYPES: frozenset[str] = frozenset(
    {"threshold_change", "protocol_change", "block_addition", "correction"}
)


# --------------------------------------------------------------------------- #
# small parsing helpers (shared by load() and apply_block_addition())
# --------------------------------------------------------------------------- #

_THRESHOLD_KEYS = frozenset({"min", "max", "severity"})
_DECISION_KEYS = frozenset({"status", "consequence"})
_AMENDMENT_KEYS = frozenset({"amendment_id", "type", "date", "rationale", "post_hoc", "payload"})
_REQUIRED_CONVENTIONS_KEYS = (
    "percent_to_decimal",
    "months_per_year",
    "return_bearing_factors",
    "level_factors",
    "rebalance_cadences",
    "static_weights_composition",
)


def _require_mapping(value: object, what: str, source: Path) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise PreRegError(f"{source}: {what} must be a mapping, got {type(value).__name__}")
    return value


def _parse_optional_number(value: object, what: str, source: Path) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreRegError(f"{source}: {what} must be numeric or null, got {value!r}")
    return float(value)


def _parse_threshold_map(raw: object, what: str, source: Path) -> dict[str, Threshold]:
    raw_map = _require_mapping(raw, what, source)
    out: dict[str, Threshold] = {}
    for key, entry in raw_map.items():
        if not isinstance(key, str) or not key:
            raise PreRegError(f"{source}: {what} has a non-string/empty key {key!r}")
        entry_map = _require_mapping(entry, f"{what}.{key}", source)
        unknown = sorted(k for k in entry_map if k not in _THRESHOLD_KEYS)
        if unknown:
            raise PreRegError(f"{source}: {what}.{key} has unknown key(s) {unknown}")
        min_v = _parse_optional_number(entry_map.get("min"), f"{what}.{key}.min", source)
        max_v = _parse_optional_number(entry_map.get("max"), f"{what}.{key}.max", source)
        severity = entry_map.get("severity")
        if not isinstance(severity, str) or not severity:
            raise PreRegError(f"{source}: {what}.{key}.severity must be a non-empty string")
        out[key] = Threshold(min=min_v, max=max_v, severity=severity)
    return out


def _parse_pair_key(key: object, source: Path) -> tuple[str, str]:
    if not isinstance(key, str) or key.count("|") != 1:
        raise PreRegError(f"{source}: cross-block key {key!r} must be 'blockA|blockB'")
    parts = key.split("|")
    if not all(parts):
        raise PreRegError(f"{source}: cross-block key {key!r} must name two non-empty blocks")
    a, b = sorted(parts)
    return (a, b)


def _parse_decision(raw: object, decision_id: object, source: Path) -> Decision:
    if not isinstance(decision_id, str) or not decision_id:
        raise PreRegError(f"{source}: decisions has a non-string/empty id {decision_id!r}")
    entry_map = _require_mapping(raw, f"decisions.{decision_id}", source)
    unknown = sorted(k for k in entry_map if k not in _DECISION_KEYS)
    if unknown:
        raise PreRegError(f"{source}: decisions.{decision_id} has unknown key(s) {unknown}")
    status = entry_map.get("status")
    consequence = entry_map.get("consequence")
    if not isinstance(status, str) or not status:
        raise PreRegError(f"{source}: decisions.{decision_id}.status must be a non-empty string")
    if not isinstance(consequence, str) or not consequence:
        raise PreRegError(
            f"{source}: decisions.{decision_id}.consequence must be a non-empty string"
        )
    return Decision(decision_id=decision_id, status=status, consequence=consequence)


def _require_string_tuple(value: object, what: str, source: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise PreRegError(f"{source}: '{what}' must be a non-empty list of non-empty strings")
    return tuple(value)


# --------------------------------------------------------------------------- #
# load()
# --------------------------------------------------------------------------- #


def load(path: Path | None = None) -> PreRegistration:
    """Parse ``pre-registration.yaml`` (defaulting to the repo root) into a :class:`PreRegistration`.

    Structural validation only -- consistency against a :class:`~ah.factors.FactorManifest`
    (block/pair coverage, the ``conventions`` closure) is :func:`verify`'s job, not
    this function's, so a caller can load a pre-registration and choose which
    manifest to verify it against (e.g. the post-``block_addition`` manifest).
    """
    resolved = (path if path is not None else _DEFAULT_PREREG_PATH).resolve()
    if not resolved.exists():
        raise PreRegError(f"{resolved}: not found")
    doc = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise PreRegError(f"{resolved}: top level must be a mapping")

    sealed = doc.get("sealed", False)
    if not isinstance(sealed, bool):
        raise PreRegError(f"{resolved}: 'sealed' must be a boolean, got {sealed!r}")

    active_blocks = _require_string_tuple(doc.get("active_blocks"), "active_blocks", resolved)

    thresholds_doc = doc.get("thresholds") or {}
    if not isinstance(thresholds_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds' must be a mapping")

    blocks_doc = thresholds_doc.get("blocks") or {}
    if not isinstance(blocks_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds.blocks' must be a mapping")
    block_thresholds: dict[str, Mapping[str, Threshold]] = {}
    for block_id, entries in blocks_doc.items():
        if not isinstance(block_id, str) or not block_id:
            raise PreRegError(
                f"{resolved}: thresholds.blocks has a non-string/empty key {block_id!r}"
            )
        block_thresholds[block_id] = MappingProxyType(
            _parse_threshold_map(entries, f"thresholds.blocks.{block_id}", resolved)
        )

    cross_doc = thresholds_doc.get("cross_blocks") or {}
    if not isinstance(cross_doc, dict):
        raise PreRegError(f"{resolved}: 'thresholds.cross_blocks' must be a mapping")
    cross_block_thresholds: dict[tuple[str, str], Mapping[str, Threshold]] = {}
    for pair_key, entries in cross_doc.items():
        pair = _parse_pair_key(pair_key, resolved)
        cross_block_thresholds[pair] = MappingProxyType(
            _parse_threshold_map(entries, f"thresholds.cross_blocks.{pair_key}", resolved)
        )

    decisions_doc = doc.get("decisions") or {}
    if not isinstance(decisions_doc, dict):
        raise PreRegError(f"{resolved}: 'decisions' must be a mapping")
    decisions: dict[str, Decision] = {
        decision_id: _parse_decision(entry, decision_id, resolved)
        for decision_id, entry in decisions_doc.items()
    }

    return PreRegistration(
        sealed=sealed,
        active_blocks=active_blocks,
        block_thresholds=MappingProxyType(block_thresholds),
        cross_block_thresholds=MappingProxyType(cross_block_thresholds),
        decisions=MappingProxyType(decisions),
        raw=MappingProxyType(doc),
    )


# --------------------------------------------------------------------------- #
# verify()
# --------------------------------------------------------------------------- #


def _check_conventions(raw: Mapping[str, Any], manifest: FactorManifest, errors: list[str]) -> None:
    """The hole-closing check -- see the module docstring."""
    conventions = raw.get("conventions")
    if not isinstance(conventions, dict):
        errors.append("pre-registration is missing the 'conventions' block")
        return

    missing_keys = sorted(k for k in _REQUIRED_CONVENTIONS_KEYS if k not in conventions)
    if missing_keys:
        errors.append(f"conventions block is missing required key(s) {missing_keys}")

    return_bearing = conventions.get("return_bearing_factors")
    level = conventions.get("level_factors")
    if not isinstance(return_bearing, list) or not isinstance(level, list):
        errors.append(
            "conventions.return_bearing_factors and conventions.level_factors must both be lists"
        )
        return

    rb_set = set(return_bearing)
    lv_set = set(level)
    overlap = sorted(rb_set & lv_set)
    if overlap:
        errors.append(
            f"conventions.return_bearing_factors and conventions.level_factors both "
            f"classify {overlap}; a factor must be exactly one"
        )
    active = set(manifest.active_factors())
    unclassified = sorted(active - (rb_set | lv_set))
    if unclassified:
        errors.append(
            f"conventions does not classify active factor(s) {unclassified} as "
            f"return_bearing_factors or level_factors"
        )


def _check_threshold_sanity(th: Threshold, label: str, errors: list[str]) -> None:
    if th.severity not in ("enforce", "report"):
        errors.append(f"{label}: severity must be 'enforce' or 'report', got {th.severity!r}")
    if th.min is not None and th.max is not None and th.min > th.max:
        errors.append(f"{label}: min ({th.min}) > max ({th.max})")


def _hash_files(paths: Iterable[Path]) -> tuple[str, list[str]]:
    """Canonical SHA-256 over the current text content of every path in ``paths``.

    Reuses :func:`ah.core.digest.canonical_json` for the serialization (sorted keys,
    compact, deterministic) and ``hashlib.sha256`` for the digest itself -- the same
    primitive :func:`ah.core.digest.sha256_of_arrays` wraps, so this is not a second
    hashing scheme, just that module's canonicalize-then-hash pattern applied to file
    text instead of float arrays (``digest.py`` has no generic text-file hasher to
    call directly). Returns ``(digest, resolved_path_strings)``; the resolved list is
    sorted, so hashing is independent of the order ``paths`` was given in.
    """
    resolved = sorted({str(Path(p).resolve()) for p in paths})
    contents = {p: Path(p).read_text(encoding="utf-8") for p in resolved}
    digest_hex = (
        "sha256:" + hashlib.sha256(canonical_json({"files": contents}).encode("utf-8")).hexdigest()
    )
    return digest_hex, resolved


def _verify_lock(lock_path: Path, errors: list[str]) -> None:
    try:
        lock_doc = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{lock_path}: could not read/parse lock file ({exc})")
        return
    if not isinstance(lock_doc, dict):
        errors.append(f"{lock_path}: lock file must contain a JSON object")
        return
    hashed_files = lock_doc.get("hashed_files")
    stored_digest = lock_doc.get("digest")
    if not isinstance(hashed_files, list) or not isinstance(stored_digest, str):
        errors.append(f"{lock_path}: malformed lock file (missing 'hashed_files' or 'digest')")
        return
    paths = [Path(p) for p in hashed_files]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        errors.append(f"{lock_path}: hashed file(s) no longer exist: {missing}")
        return
    recomputed_digest, _ = _hash_files(paths)
    if recomputed_digest != stored_digest:
        errors.append(
            f"{lock_path}: recomputed digest {recomputed_digest} does not match sealed "
            f"digest {stored_digest} -- a hashed file changed since sealing"
        )


def verify(
    prereg: PreRegistration, manifest: FactorManifest, *, lock_path: Path | None = None
) -> None:
    """Check ``prereg`` against ``manifest``; raise :class:`PreRegError` listing every failure.

    Checks (Instructions/WP2.1b-PRE-SEAL-PATCH.md Item 2, plus the conventions closure
    documented in this module's docstring):

    - the ``conventions`` block is present and complete, and
      ``return_bearing_factors``/``level_factors`` together classify every active
      factor with none in both;
    - ``prereg.active_blocks == manifest.active_blocks``;
    - every active block has a ``thresholds.blocks`` entry, and no entry names an
      inactive block;
    - every ``manifest.cross_block_pairs()`` pair has a ``thresholds.cross_blocks``
      entry, and no entry names an inactive block;
    - every threshold's ``severity`` is ``enforce``/``report``, and ``min <= max``
      when both are given;
    - if ``lock_path`` is given and exists, the digest recomputed from its
      ``hashed_files`` (read fresh from disk) matches the digest it recorded.
    """
    errors: list[str] = []
    _check_conventions(prereg.raw, manifest, errors)

    if prereg.active_blocks != manifest.active_blocks:
        errors.append(
            f"prereg.active_blocks {prereg.active_blocks} != "
            f"manifest.active_blocks {manifest.active_blocks}"
        )

    for block in manifest.active_blocks:
        if block not in prereg.block_thresholds:
            errors.append(f"active block '{block}' has no thresholds.blocks entry")
    for block in prereg.block_thresholds:
        if not manifest.is_active(block):
            errors.append(f"thresholds.blocks references inactive block '{block}'")

    active_pairs = set(manifest.cross_block_pairs())
    for pair in active_pairs:
        if pair not in prereg.cross_block_thresholds:
            errors.append(f"active cross-block pair {pair} has no thresholds.cross_blocks entry")
    for pair in prereg.cross_block_thresholds:
        block_a, block_b = pair
        if not (manifest.is_active(block_a) and manifest.is_active(block_b)):
            errors.append(f"thresholds.cross_blocks references inactive block in pair {pair}")

    for block, entries in prereg.block_thresholds.items():
        for key, th in entries.items():
            _check_threshold_sanity(th, f"thresholds.blocks.{block}.{key}", errors)
    for pair, entries in prereg.cross_block_thresholds.items():
        for key, th in entries.items():
            _check_threshold_sanity(
                th, f"thresholds.cross_blocks.{pair[0]}|{pair[1]}.{key}", errors
            )

    if lock_path is not None and lock_path.exists():
        _verify_lock(lock_path, errors)

    if errors:
        raise PreRegError(
            "pre-registration verification failed:\n" + "\n".join(f"- {e}" for e in errors)
        )


# --------------------------------------------------------------------------- #
# seal()
# --------------------------------------------------------------------------- #


def _default_judged_sources() -> tuple[Path, ...]:
    """The enforce-tier metric modules that exist yet, plus ``ah/eval/g2.py``.

    Resolved lazily (called from :func:`seal`, not at import time) against *this
    repository's* real evaluation code -- fixed regardless of which
    ``pre-registration.yaml``/``factors.yaml`` pair is being sealed, because "the code
    that judges the thresholds" is a property of the codebase, not of a particular
    fixture. Most of the eight WP2.2 metric suites don't exist yet; nonexistent ones
    are skipped rather than erroring, so this task's dry-run seal doesn't block on
    files WP2.2 hasn't written.
    """
    candidates = [
        _REPO_ROOT / "src" / "ah" / "eval" / "metrics" / f"{name}.py"
        for name in _METRIC_SUITE_NAMES
    ]
    candidates.append(_REPO_ROOT / "src" / "ah" / "eval" / "g2.py")
    return tuple(p for p in candidates if p.exists())


def seal(
    prereg_path: Path,
    *,
    out_path: Path,
    judged_sources: Iterable[Path] | None = None,
    sealed_at: str,
    dry_run: bool = False,
) -> str:
    """Compute the pre-registration digest and, unless ``dry_run``, write ``out_path``.

    Hashes, canonically (:func:`_hash_files`): the ``prereg_path`` YAML bytes, the
    ``factors.yaml`` bytes it references (its ``factor_manifest`` field, resolved
    relative to ``prereg_path``'s directory), and the source text of every file in
    ``judged_sources`` (defaulting to :func:`_default_judged_sources`, resolved lazily
    so files WP2.2 hasn't added yet are silently skipped rather than erroring).

    ``sealed_at`` is a required, caller-supplied string -- never read from the clock
    (the repo's no-time-based-defaults invariant); it is recorded in the lock file but
    plays no part in the digest itself, so sealing the same inputs at two different
    ``sealed_at`` values gives the same digest (verified by
    ``tests/test_prereg.py::test_seal_is_deterministic``).

    The lock file, written only when ``dry_run`` is false, is JSON:
    ``{"digest": ..., "hashed_files": [...], "sealed_at": ...}`` -- ``hashed_files`` is
    the fully resolved list of every file that went into the digest, so a reader (and
    :func:`verify`) sees exactly what was hashed without re-deriving the default list.
    """
    prereg_path = Path(prereg_path)
    if not prereg_path.exists():
        raise PreRegError(f"{prereg_path}: not found")
    doc = yaml.safe_load(prereg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise PreRegError(f"{prereg_path}: top level must be a mapping")
    manifest_name = doc.get("factor_manifest", "factors.yaml")
    if not isinstance(manifest_name, str) or not manifest_name:
        raise PreRegError(f"{prereg_path}: 'factor_manifest' must be a non-empty string")
    factors_path = (prereg_path.parent / manifest_name).resolve()
    if not factors_path.exists():
        raise PreRegError(
            f"{prereg_path}: factor_manifest '{manifest_name}' resolves to missing "
            f"file {factors_path}"
        )

    resolved_judged = (
        tuple(judged_sources) if judged_sources is not None else _default_judged_sources()
    )
    all_paths = [prereg_path.resolve(), factors_path, *(Path(p) for p in resolved_judged)]
    digest, hashed_files = _hash_files(all_paths)

    if not dry_run:
        lock_doc = {"digest": digest, "hashed_files": hashed_files, "sealed_at": sealed_at}
        Path(out_path).write_text(
            json.dumps(lock_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return digest


# --------------------------------------------------------------------------- #
# amendment log
# --------------------------------------------------------------------------- #


def _parse_amendment(entry: object, source: Path) -> Amendment:
    entry_map = _require_mapping(entry, "amendment entry", source)
    unknown = sorted(k for k in entry_map if k not in _AMENDMENT_KEYS)
    if unknown:
        raise PreRegError(f"{source}: amendment has unknown key(s) {unknown}")

    amendment_id = entry_map.get("amendment_id")
    amendment_type = entry_map.get("type")
    date = entry_map.get("date")
    rationale = entry_map.get("rationale")
    post_hoc = entry_map.get("post_hoc")
    raw_payload = entry_map.get("payload") or {}

    if not isinstance(amendment_id, str) or not amendment_id:
        raise PreRegError(f"{source}: amendment 'amendment_id' must be a non-empty string")
    if amendment_type not in AMENDMENT_TYPES:
        raise PreRegError(
            f"{source}: amendment '{amendment_id}' type must be one of "
            f"{sorted(AMENDMENT_TYPES)}, got {amendment_type!r}"
        )
    if not isinstance(date, str) or not date:
        raise PreRegError(f"{source}: amendment '{amendment_id}' 'date' must be a non-empty string")
    if not isinstance(rationale, str) or not rationale:
        raise PreRegError(
            f"{source}: amendment '{amendment_id}' 'rationale' must be a non-empty string"
        )
    if not isinstance(post_hoc, bool):
        raise PreRegError(f"{source}: amendment '{amendment_id}' 'post_hoc' must be a boolean")
    if not isinstance(raw_payload, dict):
        raise PreRegError(f"{source}: amendment '{amendment_id}' 'payload' must be a mapping")

    return Amendment(
        amendment_id=amendment_id,
        type=amendment_type,
        date=date,
        rationale=rationale,
        post_hoc=post_hoc,
        payload=MappingProxyType(dict(raw_payload)),
    )


def load_amendments(path: Path) -> tuple[Amendment, ...]:
    """Parse every entry of ``governance/amendment-log.yaml`` (or ``path``), in file order."""
    path = Path(path)
    if not path.exists():
        raise PreRegError(f"{path}: not found")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise PreRegError(f"{path}: top level must be a mapping")
    raw_list = doc.get("amendments") or []
    if not isinstance(raw_list, list):
        raise PreRegError(f"{path}: 'amendments' must be a list")

    amendments: list[Amendment] = []
    seen_ids: set[str] = set()
    for entry in raw_list:
        amendment = _parse_amendment(entry, path)
        if amendment.amendment_id in seen_ids:
            raise PreRegError(f"{path}: duplicate amendment_id '{amendment.amendment_id}'")
        seen_ids.add(amendment.amendment_id)
        amendments.append(amendment)
    return tuple(amendments)


def append_amendment(path: Path, amendment: Amendment) -> None:
    """Append ``amendment`` to the log at ``path``, which must already exist.

    Append-only by construction: this opens ``path`` in file-append mode ('a') and
    writes only the new entry's bytes, so every byte already on disk is untouched --
    not merely unchanged in content, but literally never written to again. The new
    entry is one YAML block-sequence item (``yaml.safe_dump`` on a one-element list),
    valid appended directly after the log's ``amendments:`` key (a YAML block sequence
    may start at the same indentation as its parent key) or after a prior entry.
    """
    path = Path(path)
    if not path.exists():
        raise PreRegError(f"{path}: not found; create the amendment log before appending to it")

    entry: dict[str, Any] = {
        "amendment_id": amendment.amendment_id,
        "type": amendment.type,
        "date": amendment.date,
        "rationale": amendment.rationale,
        "post_hoc": amendment.post_hoc,
    }
    if amendment.payload:
        entry["payload"] = dict(amendment.payload)

    block = yaml.safe_dump([entry], default_flow_style=False, sort_keys=True, allow_unicode=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(block)


# --------------------------------------------------------------------------- #
# apply_block_addition()
# --------------------------------------------------------------------------- #


def apply_block_addition(
    prereg: PreRegistration, manifest_after: FactorManifest, amendment: Amendment
) -> PreRegistration:
    """Merge a ``block_addition`` amendment's new thresholds into ``prereg``.

    ``block_addition`` is additive by construction (see
    ``governance/amendment-log.yaml``'s header): it requires new per-block thresholds
    for exactly one newly-active block, plus new cross-block joint thresholds for
    every pair that block forms with each of ``prereg``'s pre-existing active blocks
    -- both supplied on ``amendment.payload`` (``"block"``, ``"block_thresholds"``,
    ``"cross_block_thresholds"``, shaped like ``pre-registration.yaml``'s own
    ``thresholds.blocks.*`` / ``thresholds.cross_blocks.*``). It does **not**
    invalidate any pre-existing block's or pair's thresholds: every value already in
    ``prereg.block_thresholds`` / ``prereg.cross_block_thresholds`` is carried over by
    reference (the same :class:`Threshold` objects, not rebuilt), so it is provably
    byte-identical -- via canonical-JSON serialization -- before and after, which is
    the patch's acceptance criterion for a block addition. This is why a block
    addition is not a re-seal.

    ``manifest_after`` must be exactly ``prereg``'s active blocks plus the one new
    block (i.e. the manifest state *after* activating it); the new cross-block pairs
    required are computed from ``manifest_after.cross_block_pairs()``, filtered to
    pairs containing the new block -- ``FactorManifest.cross_block_pairs()``
    deliberately covers only active blocks, and in ``manifest_after`` the new block
    *is* active, so this is already the correct set without widening that method.

    Returns a new :class:`PreRegistration` (``prereg`` is not mutated) whose
    ``active_blocks`` is ``manifest_after.active_blocks``, suitable for
    :func:`verify` against ``manifest_after``.
    """
    if amendment.type != "block_addition":
        raise PreRegError(
            f"apply_block_addition requires an amendment of type 'block_addition', "
            f"got '{amendment.type}'"
        )
    src = Path(f"<amendment {amendment.amendment_id}>")

    new_block = amendment.payload.get("block")
    if not isinstance(new_block, str) or not new_block:
        raise PreRegError(f"{src}: payload.block must be a non-empty string")
    if new_block in prereg.active_blocks:
        raise PreRegError(f"{src}: block '{new_block}' is already active in the pre-registration")
    if not manifest_after.is_active(new_block):
        raise PreRegError(f"{src}: block '{new_block}' is not active in manifest_after")
    expected_active = set(prereg.active_blocks) | {new_block}
    if set(manifest_after.active_blocks) != expected_active:
        raise PreRegError(
            f"{src}: manifest_after.active_blocks {manifest_after.active_blocks} must "
            f"equal prereg.active_blocks {prereg.active_blocks} plus exactly the new "
            f"block '{new_block}'"
        )

    raw_block_thresholds = amendment.payload.get("block_thresholds")
    if not isinstance(raw_block_thresholds, dict) or not raw_block_thresholds:
        raise PreRegError(f"{src}: payload.block_thresholds must be a non-empty mapping")
    new_block_thresholds = MappingProxyType(
        _parse_threshold_map(raw_block_thresholds, "payload.block_thresholds", src)
    )

    raw_cross_thresholds = amendment.payload.get("cross_block_thresholds")
    if not isinstance(raw_cross_thresholds, dict):
        raise PreRegError(f"{src}: payload.cross_block_thresholds must be a mapping")
    parsed_cross: dict[tuple[str, str], Mapping[str, Threshold]] = {}
    for pair_key, entries in raw_cross_thresholds.items():
        pair = _parse_pair_key(pair_key, src)
        parsed_cross[pair] = MappingProxyType(
            _parse_threshold_map(entries, f"payload.cross_block_thresholds.{pair_key}", src)
        )

    expected_new_pairs = {p for p in manifest_after.cross_block_pairs() if new_block in p}
    missing_pairs = expected_new_pairs - set(parsed_cross)
    if missing_pairs:
        raise PreRegError(
            f"{src}: missing cross-block thresholds for new pair(s) {sorted(missing_pairs)}"
        )
    extra_pairs = set(parsed_cross) - expected_new_pairs
    if extra_pairs:
        raise PreRegError(
            f"{src}: declares cross-block threshold(s) for pair(s) {sorted(extra_pairs)} "
            f"that are not a new pair formed by block '{new_block}'"
        )

    merged_block_thresholds = dict(prereg.block_thresholds)
    merged_block_thresholds[new_block] = new_block_thresholds

    merged_cross_thresholds = dict(prereg.cross_block_thresholds)
    merged_cross_thresholds.update(parsed_cross)

    new_raw = dict(prereg.raw)
    new_raw["active_blocks"] = list(manifest_after.active_blocks)

    return PreRegistration(
        sealed=prereg.sealed,
        active_blocks=manifest_after.active_blocks,
        block_thresholds=MappingProxyType(merged_block_thresholds),
        cross_block_thresholds=MappingProxyType(merged_cross_thresholds),
        decisions=prereg.decisions,
        raw=MappingProxyType(new_raw),
    )
