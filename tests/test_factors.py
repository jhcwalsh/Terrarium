"""WP2.1b Task 1 acceptance: factor manifest with a block layer.

The block layer (STEP2-GENERATOR-PLAN / Instructions/WP2.1b-PRE-SEAL-PATCH.md Item 2)
makes a later jurisdiction addition (e.g. `uk`) an additive `block_addition` amendment
rather than a wholesale re-seal: existing per-block thresholds stay byte-identical.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from ah.factors import FactorManifest, ManifestError, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_load_manifest_active_blocks_and_factors() -> None:
    manifest = load_manifest()
    # campaign-2 block additions (fx, valuation) -- amendments AM-2026-08-02-*
    assert manifest.active_blocks == ("global", "us", "fx", "valuation")
    factors = manifest.active_factors()
    for f in (
        "equity_mkt",
        "smb",
        "hml",
        "mom",
        "equity_vol",
        "commodities",
        "ig_spread",
        "hy_spread",
    ):
        assert f in factors
    for f in ("policy_rate", "ust_2y", "ust_10y", "cpi", "hqm_curve", "funding_spread"):
        assert f in factors
    for f in ("fx_usd", "cape_v"):
        assert f in factors
    for f in ("bank_rate", "gilt_nominal_10y", "gilt_real_10y", "rpi", "cpi_uk"):
        assert f not in factors


def test_load_manifest_is_cached_by_identity() -> None:
    a = load_manifest()
    b = load_manifest()
    assert a is b


def test_block_of_known_and_unknown_factor() -> None:
    manifest = load_manifest()
    assert manifest.block_of("ust_2y") == "us"
    with pytest.raises(KeyError):
        manifest.block_of("nope")


def test_cross_block_pairs_on_real_manifest() -> None:
    manifest = load_manifest()
    # sorted-pair order over the four campaign-2 active blocks
    assert manifest.cross_block_pairs() == (
        ("fx", "global"),
        ("fx", "us"),
        ("fx", "valuation"),
        ("global", "us"),
        ("global", "valuation"),
        ("us", "valuation"),
    )


def test_is_active() -> None:
    manifest = load_manifest()
    assert manifest.is_active("global") is True
    assert manifest.is_active("us") is True
    assert manifest.is_active("fx") is True
    assert manifest.is_active("valuation") is True
    assert manifest.is_active("uk") is False


def test_active_block_absent_from_factor_blocks_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global, nonexistent]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_factor_duplicated_across_blocks_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n"
        "  global: [equity_mkt, cpi]\n"
        "  us: [cpi, ust_2y]\n"
        "active_blocks: [global, us]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_three_block_active_manifest_yields_deterministic_cross_pairs(tmp_path: Path) -> None:
    cfg = tmp_path / "factors.yaml"
    cfg.write_text(
        "factor_blocks:\n"
        "  global: [equity_mkt]\n"
        "  us: [ust_2y]\n"
        "  uk: [gilt_nominal_10y]\n"
        "active_blocks: [global, us, uk]\n"
        "factor_sources:\n"
        "  equity_mkt: {kind: series, series_id: french.mkt_rf, units: ret}\n"
        "  ust_2y: {kind: series, series_id: fred.DGS2, units: pct}\n"
        "  gilt_nominal_10y: {kind: unavailable, reason: fixture}\n",
        encoding="utf-8",
    )
    manifest = load_manifest(cfg)
    assert manifest.cross_block_pairs() == (
        ("global", "uk"),
        ("global", "us"),
        ("uk", "us"),
    )


def test_empty_block_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: []\n  us: [ust_2y]\nactive_blocks: [global, us]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_active_factors_deterministic_order(tmp_path: Path) -> None:
    cfg = tmp_path / "factors.yaml"
    cfg.write_text(
        "factor_blocks:\n"
        "  global: [b_factor, a_factor]\n"
        "  us: [z_factor]\n"
        "active_blocks: [global, us]\n"
        "factor_sources:\n"
        "  b_factor: {kind: unavailable, reason: fixture}\n"
        "  a_factor: {kind: unavailable, reason: fixture}\n"
        "  z_factor: {kind: unavailable, reason: fixture}\n",
        encoding="utf-8",
    )
    manifest = load_manifest(cfg)
    # block order (as declared in active_blocks), then declaration order within block.
    assert manifest.active_factors() == ("b_factor", "a_factor", "z_factor")


def test_manifest_is_frozen_dataclass() -> None:
    manifest = load_manifest()
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError, dataclass-generated
        manifest.active_blocks = ("global",)  # type: ignore[misc]


def test_load_manifest_default_path_is_repo_root_factors_yaml() -> None:
    manifest = load_manifest()
    assert isinstance(manifest, FactorManifest)
    assert (ROOT / "factors.yaml").exists()


def test_blocks_mapping_is_immutable() -> None:
    # load_manifest() is memoized by object identity (test_load_manifest_is_cached_by_identity),
    # and downstream work relies on that identity holding for the process lifetime. A plain
    # dict on a frozen dataclass is still mutable through its contents (frozen only blocks
    # attribute *reassignment*), so an accidental `manifest.blocks["x"] = (...)` anywhere would
    # silently corrupt the single shared manifest. Assert that mutation is rejected outright.
    manifest = load_manifest()
    with pytest.raises(TypeError):
        manifest.blocks["us"] = ("hacked",)  # type: ignore[index]


def test_block_with_empty_string_factor_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt, '']\nactive_blocks: [global]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_block_with_non_string_factor_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt, 5]\nactive_blocks: [global]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_active_blocks_entry_empty_string_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: ['']\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_active_blocks_entry_error_message_includes_offending_value(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: ['']\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match=re.escape(repr(""))):
        load_manifest(bad)


# --------------------------------------------------------------------------- #
# WP2.2 Task 1: factor_sources -- the factor -> Step-1 catalog series mapping.
#
# The mapping this project lacked entirely before: reference statistics and the
# panel reader cannot honestly be computed without it, and it must land before
# WP2.3 seals because it determines what every sealed band is a band *of*.
# --------------------------------------------------------------------------- #


def test_every_declared_factor_has_a_factor_source() -> None:
    manifest = load_manifest()
    all_factors = {f for factors in manifest.blocks.values() for f in factors}
    assert set(manifest.sources) == all_factors


def test_commodities_is_sourced_with_its_provenance_stated() -> None:
    """INVERTED at campaign-3 (AM-2026-08-10-001). Through campaign-2 this
    asserted kind == "unavailable" with a stated reason (RFR-8); ruling K2
    closed the gap via the REG-licensed AQR intake, so the new truth is a
    derived total return whose notes carry the licence discipline."""
    manifest = load_manifest()
    source = manifest.sources["commodities"]
    assert source.kind == "derived"
    assert source.expr == "add"
    assert source.inputs == ("aqr.cmdty_ew_excess", "french.rf")
    assert "REG licence" in (source.notes or "")


def test_uk_block_factors_are_all_unavailable() -> None:
    """uk is declared but inactive; every one of its factors is honestly unsourced."""
    manifest = load_manifest()
    for factor in manifest.blocks["uk"]:
        assert manifest.sources[factor].kind == "unavailable"
        assert manifest.sources[factor].reason


def test_is_available_matches_source_kind() -> None:
    manifest = load_manifest()
    for factor, source in manifest.sources.items():
        assert manifest.is_available(factor) == (source.kind != "unavailable")


def test_is_available_unknown_factor_raises_key_error() -> None:
    manifest = load_manifest()
    with pytest.raises(KeyError):
        manifest.is_available("not_a_factor")


def test_series_id_for_returns_the_declared_series() -> None:
    manifest = load_manifest()
    # `equity_mkt` used to be asserted here; the fix pass made it `kind: derived`
    # (mkt_rf + rf -- see test_equity_mkt_is_a_total_return_not_a_bare_excess_return),
    # so it now belongs to the rejection test below instead. `ust_10y` followed it
    # at the campaign-3 wiring (AM-2026-08-09-003: ust_10y_extended).
    assert manifest.series_id_for("smb") == "french.smb"
    assert manifest.series_id_for("cpi") == "fred.CPI"


def test_series_id_for_rejects_derived_factor() -> None:
    manifest = load_manifest()
    with pytest.raises(ValueError, match="ig_spread"):
        manifest.series_id_for("ig_spread")
    with pytest.raises(ValueError, match="equity_mkt"):
        manifest.series_id_for("equity_mkt")
    # campaign-3 wiring: the extended factors joined the derived side.
    with pytest.raises(ValueError, match="ust_10y"):
        manifest.series_id_for("ust_10y")
    with pytest.raises(ValueError, match="equity_vol"):
        manifest.series_id_for("equity_vol")


def test_series_id_for_rejects_unavailable_factor() -> None:
    manifest = load_manifest()
    with pytest.raises(ValueError, match="commodities"):
        manifest.series_id_for("commodities")


def test_series_id_for_unknown_factor_raises_key_error() -> None:
    manifest = load_manifest()
    with pytest.raises(KeyError):
        manifest.series_id_for("not_a_factor")


def test_factor_sources_units_agree_with_prereg_return_level_classification() -> None:
    """The units-consistency test the WP2.2 Task 1 brief requires: factor_sources'
    ``units`` and pre-registration.yaml's ``conventions.return_bearing_factors`` /
    ``conventions.level_factors`` classification must never disagree -- a return-
    bearing factor's source units must be exactly ``ret``; a level factor's source
    units must never be ``ret``. These two files are sealed together, and a
    divergence between them is exactly the defect class this project keeps finding.
    """
    manifest = load_manifest()
    prereg_doc = yaml.safe_load((ROOT / "pre-registration.yaml").read_text(encoding="utf-8"))
    conventions = prereg_doc["conventions"]
    return_bearing = set(conventions["return_bearing_factors"])
    level = set(conventions["level_factors"])
    assert return_bearing & level == set()  # sealed disjointness, sanity-checked here too

    checked = 0
    for factor in return_bearing | level:
        source = manifest.sources[factor]
        if source.kind == "unavailable":
            continue  # nothing to check units against (e.g. commodities)
        assert source.units is not None, f"factor '{factor}' has no units"
        if factor in return_bearing:
            assert source.units == "ret", (
                f"'{factor}' is return-bearing in pre-registration.yaml but "
                f"factor_sources declares units={source.units!r}, not 'ret'"
            )
        else:
            assert source.units != "ret", (
                f"'{factor}' is a level factor in pre-registration.yaml but "
                f"factor_sources declares units='ret'"
            )
        checked += 1
    assert checked == len({f for f in (return_bearing | level) if manifest.is_available(f)})


def test_factor_sources_series_units_agree_with_requirements_yaml() -> None:
    """A ``kind: series`` entry's units must match requirements.yaml's units for that
    exact series id -- a typo here would silently misdescribe what a sealed band is a
    band of.
    """
    manifest = load_manifest()
    requirements_doc = yaml.safe_load((ROOT / "requirements.yaml").read_text(encoding="utf-8"))
    series_registry = requirements_doc["series"]

    checked = 0
    for factor, source in manifest.sources.items():
        if source.kind != "series":
            continue
        assert source.series_id in series_registry, (
            f"factor '{factor}' names series_id '{source.series_id}', not registered "
            f"in requirements.yaml"
        )
        registered_units = series_registry[source.series_id]["units"]
        assert source.units == registered_units, (
            f"factor '{factor}' (series '{source.series_id}') declares "
            f"units={source.units!r} but requirements.yaml registers "
            f"units={registered_units!r}"
        )
        checked += 1
    assert checked > 0


def test_factor_sources_derived_inputs_are_registered_series() -> None:
    manifest = load_manifest()
    requirements_doc = yaml.safe_load((ROOT / "requirements.yaml").read_text(encoding="utf-8"))
    series_registry = requirements_doc["series"]

    checked = 0
    for factor, source in manifest.sources.items():
        if source.kind != "derived":
            continue
        for series_id in source.inputs:
            assert series_id in series_registry, (
                f"factor '{factor}''s derived input '{series_id}' is not registered "
                f"in requirements.yaml"
            )
        checked += 1
    assert checked > 0


# --------------------------------------------------------------------------- #
# factor_sources structural validation (synthetic fixtures)
# --------------------------------------------------------------------------- #


def test_factor_sources_missing_entry_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt, smb]\nactive_blocks: [global]\n"
        "factor_sources:\n  equity_mkt: {kind: unavailable, reason: fixture}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="smb"):
        load_manifest(bad)


def test_factor_sources_unknown_factor_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n"
        "  equity_mkt: {kind: unavailable, reason: fixture}\n"
        "  ghost_factor: {kind: unavailable, reason: fixture}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="ghost_factor"):
        load_manifest(bad)


def test_factor_sources_missing_section_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="factor_sources"):
        load_manifest(bad)


def test_factor_sources_invalid_kind_raises(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n  equity_mkt: {kind: bogus}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="kind"):
        load_manifest(bad)


def test_factor_sources_series_kind_requires_series_id_and_units(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n  equity_mkt: {kind: series}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="series_id"):
        load_manifest(bad)


def test_factor_sources_series_kind_rejects_reason(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n"
        "  equity_mkt: {kind: series, series_id: french.mkt_rf, units: ret, reason: nope}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="must not set"):
        load_manifest(bad)


def test_factor_sources_derived_kind_requires_expr_and_inputs(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [ig_spread]\nactive_blocks: [global]\n"
        "factor_sources:\n  ig_spread: {kind: derived, units: pct}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="expr"):
        load_manifest(bad)


def test_factor_sources_unavailable_kind_requires_reason(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [commodities]\nactive_blocks: [global]\n"
        "factor_sources:\n  commodities: {kind: unavailable}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="reason"):
        load_manifest(bad)


def test_factor_sources_unavailable_kind_rejects_series_id(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [commodities]\nactive_blocks: [global]\n"
        "factor_sources:\n"
        "  commodities: {kind: unavailable, reason: fixture, series_id: nope}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="must not set"):
        load_manifest(bad)


# --------------------------------------------------------------------------- #
# WP2.2 Task 1 fix pass -- Critical 2 (policy rate) and Critical 3 (numeraire),
# plus the machine-visible proxy flag.
# --------------------------------------------------------------------------- #


def test_policy_rate_maps_to_the_effective_funds_rate_not_a_bill() -> None:
    """Critical 2: `policy_rate` is an ADMINISTERED policy rate.

    A 3-month bill is a market yield -- term premium, policy expectations, and
    flight-to-quality -- and it decouples from the funds rate in exactly the episodes
    the tail and severe tiers judge. Worse, `funding_spread` is TED = 3m LIBOR minus
    the 3m bill, so sourcing `policy_rate` from the same bill would give the policy-rate
    factor and the funding-stress factor a shared, construction-driven stress component
    and seal the cross-block correlation bands over an artifact of the mapping.
    """
    manifest = load_manifest()
    source = manifest.sources["policy_rate"]
    # campaign-3 wiring (AM-2026-08-09-003): the entry moved to `kind: derived`
    # (policy_rate_extended applies the fedfunds_pre1954 splice at read time),
    # but Critical 2's substance is unchanged and still asserted: the PRIMARY
    # series is the administered funds rate, never a bill.
    assert source.kind == "derived"
    assert source.expr == "policy_rate_extended"
    assert source.inputs[0] == "fred.FEDFUNDS"
    # the pre-1954 backfill is machine-visible, not free text in `notes`
    assert source.proxy is True
    assert source.proxy_for and "fred.TB3MS" in source.proxy_for


def test_policy_rate_and_funding_spread_share_only_the_bounded_pre1954_donor() -> None:
    """The contamination the mapping must not create, asserted directly.

    AMENDED 2026-08-09 (campaign-3 wiring, AM-2026-08-09-003). As written this
    test asserted full disjointness, and for the factors' PRIMARY/observed
    constructions it still does: FEDFUNDS vs TEDRATE + the CP/bill donor legs
    share nothing, so no observed month of either factor is built from the
    other's inputs. What the wiring adds is one BOUNDED donor overlap:
    fred.TB3MS enters policy_rate only before 1954-07 (the fedfunds_pre1954
    splice) and enters funding_spread's bill leg only before 1954-01 (where
    TB3M_SEC takes over), so the shared-construction months are exactly
    1953-04..1953-12 of the ratified span -- nine months, deepest history,
    disclosed here and in both factors' proxy_for entries rather than sealed
    over silently. Any second shared series, or TB3MS appearing outside these
    donor roles, fails this test exactly as full disjointness would have.
    """
    manifest = load_manifest()
    policy = manifest.sources["policy_rate"]
    funding = manifest.sources["funding_spread"]
    policy_inputs = {policy.series_id} if policy.series_id else set(policy.inputs)
    funding_inputs = {funding.series_id} if funding.series_id else set(funding.inputs)
    assert policy_inputs & funding_inputs == {"fred.TB3MS"}
    # the primary constructions stay fully disjoint
    assert policy.inputs[0] not in funding_inputs
    assert "fred.TEDRATE" not in policy_inputs


def test_equity_mkt_is_a_total_return_not_a_bare_excess_return() -> None:
    """Critical 3: the sealed numeraire is total return.

    `french.mkt_rf` is Mkt-RF, an excess return over the one-month bill. Weighting it
    beside `govt_tr_10y` (a total return) inside `sixty_forty` and `endowment_proxy`
    mixes numeraires inside a fully-invested portfolio. `french.rf` is registered, so
    the factor is `mkt_rf + rf` -- a genuine total return.
    """
    manifest = load_manifest()
    source = manifest.sources["equity_mkt"]
    assert source.kind == "derived"
    assert source.expr == "add"
    assert source.inputs == ("french.mkt_rf", "french.rf")
    assert source.units == "ret"
    assert source.numeraire == "total_return"


def test_every_available_return_bearing_factor_declares_a_numeraire() -> None:
    manifest = load_manifest()
    prereg_doc = yaml.safe_load((ROOT / "pre-registration.yaml").read_text(encoding="utf-8"))
    for factor in prereg_doc["conventions"]["return_bearing_factors"]:
        source = manifest.sources[factor]
        assert source.numeraire, f"return-bearing factor '{factor}' declares no numeraire"
        assert source.numeraire in {"total_return", "zero_cost", "excess_return"}


def test_level_factors_declare_no_numeraire() -> None:
    """A level is not a return, so it has no numeraire to declare."""
    manifest = load_manifest()
    prereg_doc = yaml.safe_load((ROOT / "pre-registration.yaml").read_text(encoding="utf-8"))
    for factor in prereg_doc["conventions"]["level_factors"]:
        assert manifest.sources[factor].numeraire is None


def test_hy_spread_records_its_splice_backed_backfill_as_a_proxy() -> None:
    manifest = load_manifest()
    source = manifest.sources["hy_spread"]
    assert source.proxy is True
    assert source.proxy_for


def test_factor_sources_derived_units_agree_with_their_inputs_units() -> None:
    """Minor: a derived factor's declared `units` was never checked against its inputs.

    `ig_spread: units: idx` would have passed everything. The units algebra lives in
    ``ah.eval.panel._DERIVED_EXPRS`` (a sealed judged source), applied here to the
    committed manifest against ``requirements.yaml``'s own registered units.
    """
    from ah.eval.panel import expected_derived_units

    manifest = load_manifest()
    requirements_doc = yaml.safe_load((ROOT / "requirements.yaml").read_text(encoding="utf-8"))
    series_registry = requirements_doc["series"]

    checked = 0
    for factor, source in manifest.sources.items():
        if source.kind != "derived":
            continue
        input_units = tuple(series_registry[sid]["units"] for sid in source.inputs)
        assert source.units == expected_derived_units(source.expr or "", input_units), (
            f"factor '{factor}' declares units={source.units!r}, which its inputs' "
            f"units {input_units} and expr '{source.expr}' do not produce"
        )
        checked += 1
    assert checked > 0


def test_factor_sources_rejects_proxy_for_without_proxy(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n"
        "  equity_mkt: {kind: series, series_id: french.mkt_rf, units: ret, "
        "proxy_for: fred.TB3MS}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="proxy"):
        load_manifest(bad)


def test_factor_sources_rejects_proxy_without_proxy_for(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n"
        "  equity_mkt: {kind: series, series_id: french.mkt_rf, units: ret, proxy: true}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="proxy_for"):
        load_manifest(bad)


def test_factor_sources_rejects_unknown_numeraire(tmp_path: Path) -> None:
    bad = tmp_path / "factors.yaml"
    bad.write_text(
        "factor_blocks:\n  global: [equity_mkt]\nactive_blocks: [global]\n"
        "factor_sources:\n"
        "  equity_mkt: {kind: series, series_id: french.mkt_rf, units: ret, "
        "numeraire: gold_standard}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="numeraire"):
        load_manifest(bad)


def test_factor_and_strategy_numeraire_vocabularies_agree() -> None:
    """`ah.factors` and `ah.strategies` must not drift into different vocabularies.

    A D4 leg's numeraire comes from `factor_sources.<factor>.numeraire` for a factor
    and from `derived_series.<id>.numeraire` for a derived series; the two are
    validated by different modules and compared to each other by the loader, so their
    accepted value sets have to be identical.
    """
    from ah.factors import _NUMERAIRES
    from ah.strategies import _LEG_NUMERAIRES

    assert _NUMERAIRES == _LEG_NUMERAIRES
