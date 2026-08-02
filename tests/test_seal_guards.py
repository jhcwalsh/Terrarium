"""WP2R.8 — the three mechanical seal guards.

Seven governance defects in three days shared one shape: *the seal asserts or
assumes something that nothing mechanically verifies* (RFR-76, -77, -78, -81,
-82, -83, -84). Each guard here closes one route by which that shape recurs:

1. **Import closure** (RFR-82's route): every module reachable from the judging
   entry points is either inside the seal or on an explicit exclusion list with
   a reason. A new module joining the judgment path unsealed and unclassified
   fails the suite the day it is added — the two-day `ablation.py` hole becomes
   impossible to open silently.
2. **Sealed-name resolution** (RFR-76/-77/-78's route): structured names the
   sealed document uses — threshold names, strategy weights, factor lists —
   must resolve against the registries that define them. The one *known*
   unresolvable phrase is pinned as such, so fixing it forces this file to be
   updated in the same change.
3. **Citation integrity** (RFR-84's route): `file::test` references and
   repo-path citations in the governance documents must point at things that
   exist — including the bare-filename form the RFR-84 checker missed.

None of these seals anything new. They make the *boundary* of the seal a
checked fact instead of an assumption; widening the seal itself remains a
dated amendment.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

JUDGING_ENTRY_POINTS = ("ah.eval.g2", "ah.battery.report")

#: Reachable-but-unsealed modules, each with the reason it is outside the seal.
#: An entry here is a *recorded boundary decision*, not a free pass: test
#: ``test_no_stale_exclusions`` deletes-or-fails any entry that stops being
#: reachable or becomes sealed, and adding a new entry requires writing the
#: reason a reviewer can dispute. Boundary decisions recorded at WP2R.8
#: (2026-07-31); re-examine when the next campaign's seal is authored.
EXCLUDED_FROM_SEAL: dict[str, str] = {
    "src/ah/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/battery/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/core/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/data/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/eval/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/eval/metrics/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/gen/__init__.py": "package plumbing; def/class-free (asserted below)",
    "src/ah/core/digest.py": (
        "Step-0 rails under gate G0; canonical rounding + hashing for RunRecords. "
        "No sealed band or verdict statistic is computed from a digest."
    ),
    "src/ah/core/engine.py": (
        "the toy-v0 engine, Step-0 rails under gate G0 (golden snapshot). Reachable via "
        "the Step-0 battery report; the sealed enforce arithmetic (monthly/1_5yr on the "
        "factor panel) does not pass through it."
    ),
    "src/ah/core/loader.py": (
        "WorldSpec dual validation, Step-0 rails under gate G0 (jsonschema/pydantic "
        "agreement property test). Feeds the conditional suite's fixture worlds, whose "
        "every threshold is severity: report (non-gating per the sealed NC5 decision)."
    ),
    "src/ah/core/numericworld.py": (
        "the narrative-blind projection, Step-0 rails under gate G0; same conditional-"
        "suite-only judgment path as loader.py."
    ),
    "src/ah/core/worldspec.py": (
        "the WorldSpec pydantic contract, Step-0 rails under gate G0; same conditional-"
        "suite-only judgment path as loader.py."
    ),
    "src/ah/data/catalog.py": (
        "the vintage-store IO layer: decides what data CAN be read, never what a band "
        "is. Content is pinned by the sealed campaign_vintage_id over an immutable "
        "vintage store; a failure here is loud (missing factors, quarantine), not a "
        "silent verdict move."
    ),
    "src/ah/data/manifest.py": (
        "requirements.yaml loader — series registry IO, same availability-not-"
        "arithmetic argument as catalog.py."
    ),
    "src/ah/gen/base.py": (
        "the judged, not the judge: Ensemble/EnsembleMeta lineage (generator, "
        "checkpoint, config, vintage, seed) travels on every ensemble, so editing the "
        "judged object changes what is measured — visibly — not how it is judged."
    ),
    "src/ah/gen/bootstrap.py": (
        "the benchmark generator — judged, not judge (same argument as base.py); its "
        "numeric path is additionally pinned by bit-identical per-seed tests."
    ),
    "src/ah/gen/registry.py": (
        "generator id -> factory resolution; selects the judged system by its sealed "
        "id, computes nothing about it."
    ),
}


def _module_to_path(mod: str) -> Path | None:
    parts = mod.split(".")
    pkg = SRC.joinpath(*parts)
    if (pkg / "__init__.py").exists():
        return pkg / "__init__.py"
    py = SRC.joinpath(*parts[:-1], parts[-1] + ".py")
    if py.exists():
        return py
    return None


def _imports_of(path: Path, mod: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "ah" or alias.name.startswith("ah."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = mod.split(".")
                if path.name != "__init__.py":
                    base = base[:-1]
                if node.level > 1:
                    base = base[: -(node.level - 1)]
                prefix = ".".join(base)
                if node.module:
                    found.add(f"{prefix}.{node.module}")
                else:
                    for alias in node.names:
                        found.add(f"{prefix}.{alias.name}")
            elif node.module and (node.module == "ah" or node.module.startswith("ah.")):
                found.add(node.module)
                # `from ah.x import y` where y may itself be a submodule
                for alias in node.names:
                    found.add(f"{node.module}.{alias.name}")
    return found


def judging_closure(entry_points: tuple[str, ...] = JUDGING_ENTRY_POINTS) -> dict[str, Path]:
    """Static import closure of the judging entry points, ``ah``-package only.

    ``ah.eval.battery`` loads its metric suites through ``import_module`` (a
    dynamic import a static walk cannot see), so every module under
    ``src/ah/eval/metrics/`` is added to the closure unconditionally — they are
    judging code by construction.
    """
    seen: dict[str, Path] = {}
    queue: list[str] = list(entry_points)
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        path = _module_to_path(mod)
        if path is None:
            continue  # a from-import of a name, not a module
        seen[mod] = path
        for dep in _imports_of(path, mod):
            if dep not in seen:
                queue.append(dep)
        parts = mod.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            if parent not in seen:
                queue.append(parent)
    for metrics_file in sorted((SRC / "ah" / "eval" / "metrics").glob("*.py")):
        mod = (
            f"ah.eval.metrics.{metrics_file.stem}"
            if metrics_file.stem != "__init__"
            else "ah.eval.metrics"
        )
        seen.setdefault(mod, metrics_file)
    return seen


def sealed_files() -> set[str]:
    lock = json.loads((ROOT / "pre-registration.lock").read_text(encoding="utf-8"))
    return set(lock["hashed_files"])


class TestJudgingImportClosure:
    """Guard 1 — RFR-82's route: no module joins the judgment path unclassified."""

    def test_every_reachable_module_is_sealed_or_excluded_with_a_reason(self):
        sealed = sealed_files()
        unclassified = []
        for mod, path in judging_closure().items():
            rel = path.relative_to(ROOT).as_posix()
            if rel in sealed or rel in EXCLUDED_FROM_SEAL:
                continue
            unclassified.append(f"{rel} (imported as {mod})")
        assert not unclassified, (
            "modules reachable from the judging entry points are neither sealed nor "
            f"excluded-with-a-reason: {sorted(unclassified)}. Either add the file to "
            "the seal (a dated amendment via ah.eval.prereg) or add an exclusion entry "
            "in tests/test_seal_guards.py WITH the reason a reviewer can dispute. "
            "This is the guard RFR-82 asked for: ablation.py sat exactly here, "
            "unsealed and unnoticed, for two days."
        )

    def test_no_stale_exclusions(self):
        """An exclusion for a module that is sealed or unreachable is a lie in waiting."""
        sealed = sealed_files()
        reachable = {p.relative_to(ROOT).as_posix() for p in judging_closure().values()}
        stale = [rel for rel in EXCLUDED_FROM_SEAL if rel not in reachable or rel in sealed]
        assert not stale, (
            f"exclusion entries no longer needed (unreachable or now sealed): {stale}; "
            "delete them so the list states only live boundary decisions"
        )

    def test_excluded_init_files_carry_no_logic(self):
        """The 'package plumbing' reason is checked, not assumed."""
        for rel, reason in EXCLUDED_FROM_SEAL.items():
            if not rel.endswith("__init__.py"):
                continue
            assert "plumbing" in reason
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
            defs = [
                n
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            assert not defs, (
                f"{rel} is excluded as plumbing but defines "
                f"{[d.name for d in defs]}; classify it honestly"
            )

    def test_every_metric_suite_module_is_sealed(self):
        """battery.py imports suites dynamically; the closure walk cannot see it,
        so the invariant is asserted directly: all metric modules are sealed."""
        sealed = sealed_files()
        for path in sorted((SRC / "ah" / "eval" / "metrics").glob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if path.name == "__init__.py":
                assert rel in EXCLUDED_FROM_SEAL
                continue
            assert rel in sealed, (
                f"{rel} is a metric suite module (dynamically imported by "
                "ah.eval.battery) and must be sealed"
            )


class TestG3SealBoundary:
    """The same closure guard, over the G3-pre surface (wp3-00) — binding from
    the DRAFT onward, so the first G3 lock is minted with its boundary already
    checked rather than guarded retroactively."""

    G3_ENTRY_POINTS = ("ah.eval.sleevetails", "ah.eval.g3seal", "ah.eval.episode2022")

    def test_g3_reachable_modules_are_declared_or_excluded(self):
        declared = set(
            yaml.safe_load((ROOT / "pre-registration-g3.yaml").read_text("utf-8"))["seal_scope"][
                "hashed_files"
            ]
        )
        g2_sealed = sealed_files()
        unclassified = []
        for mod, path in judging_closure(self.G3_ENTRY_POINTS).items():
            rel = path.relative_to(ROOT).as_posix()
            if rel in declared or rel in g2_sealed or rel in EXCLUDED_FROM_SEAL:
                continue
            unclassified.append(f"{rel} (imported as {mod})")
        assert not unclassified, (
            "modules reachable from the G3 judged entry points are neither in "
            "pre-registration-g3.yaml's seal_scope, nor G2-sealed, nor excluded-"
            f"with-a-reason: {sorted(unclassified)}"
        )

    def test_g3_declared_list_has_no_stale_source_entries(self):
        """Declared .py entries under src/ must be reachable — a sealed list
        carrying dead code misstates what the seal defends."""
        declared = yaml.safe_load((ROOT / "pre-registration-g3.yaml").read_text("utf-8"))[
            "seal_scope"
        ]["hashed_files"]
        reachable = {
            p.relative_to(ROOT).as_posix() for p in judging_closure(self.G3_ENTRY_POINTS).values()
        }
        stale = [
            rel
            for rel in declared
            if rel.startswith("src/") and rel.endswith(".py") and rel not in reachable
        ]
        assert not stale, f"declared but unreachable from the G3 entry points: {stale}"


def _prereg() -> dict:
    return yaml.safe_load((ROOT / "pre-registration.yaml").read_text(encoding="utf-8"))


class TestSealedNameResolution:
    """Guard 2 — RFR-76/-77/-78's route: sealed structured names must resolve."""

    def test_threshold_names_resolve_to_declared_factors(self):
        from ah.factors import load_manifest

        doc = _prereg()
        manifest = load_manifest()
        factors = {name for names in manifest.blocks.values() for name in names}
        derived = set(doc.get("derived_series", {}))
        known_sections = set(manifest.blocks) | {"cross_block", "cross"}
        bad: list[str] = []
        for section, entries in doc["thresholds"]["blocks"].items():
            if section not in known_sections:
                bad.append(f"section '{section}' is not a declared factor block")
                continue
            for name in entries:
                # "a~b.correlation"-family or "factor.stat"
                head = name.split(".", 1)[0]
                parts = head.split("~") if "~" in head else [head]
                for factor in parts:
                    if factor not in factors and factor not in derived:
                        bad.append(f"threshold '{name}': '{factor}' resolves to no factor")
        assert not bad, bad

    def test_strategy_weights_resolve(self):
        from ah.factors import load_manifest

        doc = _prereg()
        manifest = load_manifest()
        factors = {name for names in manifest.blocks.values() for name in names}
        derived = set(doc.get("derived_series", {}))
        bad = [
            f"{strategy}: weight key '{key}' resolves to no factor or derived series"
            for strategy, spec in doc["d4_strategies"].items()
            for key in (spec.get("weights") or {})
            if key not in factors and key not in derived
        ]
        assert not bad, bad

    def test_reference_run_lists_resolve(self):
        from ah.factors import load_manifest

        doc = _prereg()
        manifest = load_manifest()
        factors = {name for names in manifest.blocks.values() for name in names}
        for factor in doc["reference_run"]["missing_factors"]:
            assert factor in factors, f"missing_factors names unknown factor '{factor}'"
        strategies = set(doc["d4_strategies"])
        for s in doc["reference_run"]["uncomputable_d4_strategies"]:
            assert s in strategies, f"uncomputable_d4_strategies names unknown strategy '{s}'"

    def test_decision_rule_tiers_and_suite_builders_resolve(self):
        from ah.eval import battery

        # The executable rule's regression tiers are real battery tiers.
        from ah.eval.g2 import REGRESSION_TIERS
        from ah.eval.metrics import tails

        for tier in REGRESSION_TIERS:
            assert tier in battery.TIERS
        # tail_tier_definition names build_tails_suite; it must exist and be callable.
        assert callable(tails.build_tails_suite)

    def test_factor_manifest_path_resolves(self):
        doc = _prereg()
        assert (ROOT / doc["factor_manifest"]).exists()

    def test_known_unresolved_phrases_are_exactly_the_sealed_state(self):
        """S2-HORIZON-TIER: severe_test_protocol says "the horizon tier"; TIERS has no
        such tier, both readings are reported, and narrowing awaits a pre-campaign
        amendment. This test pins that state: if the phrase is amended away, this
        assertion fails and the KNOWN entry must be removed in the same change —
        an unresolvable phrase can be sealed, but never silent."""
        from ah.eval import battery

        doc = _prereg()
        # str(), not yaml.dump(): loading already folded the >- scalars, so the
        # phrase is contiguous in the loaded strings; re-dumping re-wraps lines
        # and can split it.
        protocol = str(doc["severe_test_protocol"])
        assert "horizon tier" in protocol, (
            "severe_test_protocol no longer says 'horizon tier' — delete this "
            "known-unresolved entry (and check S2-HORIZON-TIER's register row)"
        )
        assert "horizon" not in battery.TIERS  # the day this exists, the phrase resolves


GOVERNANCE_DOCS = (
    "governance/decision-register.md",
    "governance/retrofit-register.md",
    "governance/G2-REVIEWER-PACKET.md",
    "governance/evidence/README.md",
    "G2-EVIDENCE.md",
    "ABLATION.md",
)

#: Citations the checker flags that are correct anyway, each with the reason.
#: RFR-84's corrected spec, verbatim: "exclude spans quoted as known-bad" — a
#: register documenting a bad citation must be able to quote it without the
#: checker re-reporting the defect the register exists to record.
CITATION_ALLOWLIST: dict[str, str] = {
    "DESMOOTHING.md": "cited as ABSENT, deliberately (WP2R.8 closure note on D1)",
    "DN-5-decision-alpha-and-twin.md": (
        "cited by RFR-89 as NOT IN REPO, deliberately — the retrofit task named it "
        "as optional background and the row records that it was absent at execution"
    ),
    "retrofit-R1-decision-alpha.md": (
        "cited by RFR-89 as NOT IN REPO, deliberately — same task, same absence, "
        "recorded rather than implied"
    ),
    "MASTER-ROADMAP.md": "cited as MISSING from the repo, deliberately (2R plan source)",
    "tier1-synthesis-and-decisions.md": "cited as missing per CLAUDE.md's standing note",
    "progress.md": "session-tool artifact name, not a repo citation",
    "GAPS.md": "generated gap register living in gitignored data/; unverifiable on a fresh clone",
    "test_splits.py": (
        "does not exist and never did — quoted as KNOWN-BAD by RFR-82 (which invented "
        "it) and RFR-84 (which documents the invention); the quotations are the record"
    ),
    "test_finding_the_monthly_tier_cannot_separate_nc3_from_the_undistorted_bootstrap": (
        "RFR-34's citation, stale since WP2.2c renamed the test to "
        "test_closed_the_monthly_tier_separates_nc3_from_the_undistorted_bootstrap; "
        "the correction is already on record as RFR-75, which quotes the dangling "
        "name while documenting it — append-only preserves both instances"
    ),
    "test_mc_error_is_well_defined_and_finite_for_a_conditional_metric": (
        "RFR-31's citation, dangling since the test was renamed (the real tests are "
        "test_conditional_mc_error_* in tests/test_conditional.py); the register is "
        "append-only so the row stands, corrected by RFR-85, and RFR-84 quotes the "
        "dangling name in its prototype results"
    ),
}

_FILE_TEST_RE = re.compile(r"`?([\w/.-]+\.py)::(test_\w+)`?")
_PATH_RE = re.compile(
    r"`((?:src|tests|scripts|governance|Instructions|schemas|docs|fixtures|artifacts)"
    r"/[\w./-]+\.(?:py|md|yaml|yml|json|lock))`"
)
_BARE_RE = re.compile(r"`([A-Za-z][\w.-]*\.(?:md|yaml|yml|json|lock))`")


def _tracked_files() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return set(out.splitlines())


class TestGovernanceCitations:
    """Guard 3 — RFR-84's route: governance citations must point at real things."""

    def test_file_and_test_citations_resolve(self):
        tracked = _tracked_files()
        bad: list[str] = []
        for doc in GOVERNANCE_DOCS:
            text = (ROOT / doc).read_text(encoding="utf-8")
            for match in _FILE_TEST_RE.finditer(text):
                rel, test_name = match.groups()
                if rel.split("/", 1)[0] in {"experiments", "data"}:
                    continue  # gitignored roots; unverifiable on a fresh clone
                if test_name in CITATION_ALLOWLIST or Path(rel).name in CITATION_ALLOWLIST:
                    continue  # quoted-as-known-bad, per RFR-84's corrected spec
                if rel not in tracked and not (ROOT / rel).exists():
                    bad.append(f"{doc}: cites {rel}::{test_name} but {rel} does not exist")
                    continue
                body = (ROOT / rel).read_text(encoding="utf-8")
                if f"def {test_name}" not in body:
                    bad.append(f"{doc}: cites {rel}::{test_name} but no such test exists")
        assert not bad, bad

    def test_repo_path_citations_resolve(self):
        tracked = _tracked_files()
        bad: list[str] = []
        for doc in GOVERNANCE_DOCS:
            text = (ROOT / doc).read_text(encoding="utf-8")
            for match in _PATH_RE.finditer(text):
                rel = match.group(1)
                if rel.split("/", 1)[0] in {"experiments", "data"}:
                    continue
                if Path(rel).name in CITATION_ALLOWLIST:
                    continue
                if rel not in tracked and not (ROOT / rel).exists():
                    bad.append(f"{doc}: cites `{rel}` which does not exist")
        assert not bad, bad

    def test_bare_filename_citations_resolve(self):
        """The form RFR-84's checker missed: `SOMEFILE.md` with no path. Resolved
        against the basenames of tracked files; unknown basenames need either the
        file or an allowlist entry with a reason."""
        tracked_basenames = {Path(p).name for p in _tracked_files()}
        bad: list[str] = []
        for doc in GOVERNANCE_DOCS:
            text = (ROOT / doc).read_text(encoding="utf-8")
            for match in _BARE_RE.finditer(text):
                name = match.group(1)
                if name in CITATION_ALLOWLIST or name in tracked_basenames:
                    continue
                bad.append(f"{doc}: bare citation `{name}` matches no tracked file")
        assert not bad, bad
