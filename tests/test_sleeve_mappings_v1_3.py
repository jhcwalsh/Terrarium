"""pe-chosen-01 -- the chosen-PE artifact (D-ER16-1, AM-2026-08-19-001).

`mappings/sleeve-mappings-v1.3.yaml` moves the generated plane's `pm_buyout`
row to CHOSEN coefficients -- equity beta 1.2 (DN-5 levered-beta prior
1.1-1.3, mid-range) and alpha 3%/yr (0.007399 quarterly under the sealed
alpha/3-per-month convention) -- replacing values fitted on an appraisal
index whose GFC was never recorded (ER-16; the Route-C measurement,
docs/superpowers/specs/2026-08-19-pe-desmooth-c-measurement.md).

The contract these tests hold:
* regenerating v1.3 from sealed v1.2 via scripts/make_sleeve_mappings_v1_3.py
  is byte-identical to the committed artifact;
* the diff between the two documents is EXACTLY the declared field set --
  nothing else moved, silently or otherwise;
* every sleeve other than pm_buyout is identical to v1.2.

TDD note: written before the generator or the artifact existed and watched
failing (ModuleNotFound/FileNotFound) before either was created.

The expected values below are copied from the D-ER16-1 ruling (the task
brief), NOT re-derived from the generator -- the test judges the script, it
does not restate it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
V12 = ROOT / "mappings" / "sleeve-mappings-v1.2.yaml"
V13 = ROOT / "mappings" / "sleeve-mappings-v1.3.yaml"


def _load_generator():
    """Import scripts/make_sleeve_mappings_v1_3.py (not a package) -- the
    house pattern (test_campaign_r1_generator.py)."""
    spec = importlib.util.spec_from_file_location(
        "_make_sleeve_mappings_v1_3", ROOT / "scripts" / "make_sleeve_mappings_v1_3.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _walk_diff(a: object, b: object, path: str = "") -> dict[str, tuple[object, object]]:
    """The test's OWN recursive diff (independent of the generator's), so the
    exactly-these-fields claim is not the script grading its own homework."""
    diffs: dict[str, tuple[object, object]] = {}
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            sub = f"{path}.{key}" if path else str(key)
            if key not in a:
                diffs[sub] = ("<absent>", b[key])
            elif key not in b:
                diffs[sub] = (a[key], "<absent>")
            else:
                diffs.update(_walk_diff(a[key], b[key], sub))
    elif a != b:
        diffs[path] = (a, b)
    return diffs


class TestRegeneration:
    def test_regenerating_from_v12_is_byte_identical_to_the_committed_artifact(self):
        mod = _load_generator()
        assert V13.exists(), "committed artifact mappings/sleeve-mappings-v1.3.yaml missing"
        assert mod.build().encode("utf-8") == V13.read_bytes()

    def test_v12_is_untouched_by_a_regeneration(self):
        before = V12.read_bytes()
        _load_generator().build()
        assert V12.read_bytes() == before


class TestDeclaredDiff:
    def _docs(self) -> tuple[dict, dict]:
        return (
            yaml.safe_load(V12.read_text(encoding="utf-8")),
            yaml.safe_load(V13.read_text(encoding="utf-8")),
        )

    def test_the_diff_set_is_exactly_the_declared_fields(self):
        v12, v13 = self._docs()
        diffs = _walk_diff(v12, v13)
        assert set(diffs) == {
            "pm_sleeves.pm_buyout.alpha_quarterly",
            "pm_sleeves.pm_buyout.loadings.equity_mkt",
            "pm_sleeves.pm_buyout.r2_train_val",
            "pm_sleeves.pm_buyout.r2_note",
            "pm_sleeves.pm_buyout.chosen",
        }
        assert diffs["pm_sleeves.pm_buyout.alpha_quarterly"] == (0.019441, 0.007399)
        assert diffs["pm_sleeves.pm_buyout.loadings.equity_mkt"] == (0.8362, 1.2)
        assert diffs["pm_sleeves.pm_buyout.r2_train_val"] == (0.269, None)
        assert diffs["pm_sleeves.pm_buyout.r2_note"][0] == "<absent>"
        assert diffs["pm_sleeves.pm_buyout.chosen"][0] == "<absent>"

    def test_every_other_sleeve_and_block_is_identical_to_v12(self):
        v12, v13 = self._docs()
        v12.get("pm_sleeves", {}).pop("pm_buyout", None)
        v13.get("pm_sleeves", {}).pop("pm_buyout", None)
        assert v12 == v13

    def test_alpha_is_the_declared_derivation_not_an_invention(self):
        """3%/yr under the sealed convention (alpha_quarterly/3 per month):
        3 * (1.03**(1/12) - 1) = 0.00739881, six-decimal artifact style."""
        assert round(3.0 * (1.03 ** (1.0 / 12.0) - 1.0), 6) == 0.007399
        _, v13 = self._docs()
        assert v13["pm_sleeves"]["pm_buyout"]["alpha_quarterly"] == 0.007399


class TestChosenRow:
    def _row(self) -> dict:
        return yaml.safe_load(V13.read_text(encoding="utf-8"))["pm_sleeves"]["pm_buyout"]

    def test_the_chosen_coefficients(self):
        row = self._row()
        assert row["loadings"]["equity_mkt"] == 1.2
        assert row["alpha_quarterly"] == 0.007399
        assert row["r2_train_val"] is None  # a chosen row has no fit R2
        assert "chosen coefficients (D-ER16-1)" in row["r2_note"]

    def test_the_chosen_provenance_block(self):
        chosen = self._row()["chosen"]
        assert chosen["ratification"] == "D-ER16-1"
        assert chosen["date"] == "2026-08-19"
        assert chosen["replaced"] == {"alpha_quarterly": 0.019441, "equity_mkt": 0.8362}
        assert "1.1-1.3" in chosen["anchors"]["beta"]  # the DN-5 levered-beta prior
        assert "2-4%/yr" in chosen["anchors"]["alpha"]  # marks-free cashflow/PME range
        assert "ER-16" in chosen["trigger"]
        assert "no internal refit is supportable" in chosen["trigger"]

    def test_route_and_application_semantics_are_unchanged(self):
        """1.2 is the SUM the adapter applies (whole Dimson sum, contemporaneous,
        monthly) -- the route string must not silently change meaning."""
        row = self._row()
        assert row["route"] == "sum-beta(4)"
        assert "SUM the adapter applies" in row["chosen"]["route_note"]

    def test_nothing_else_in_the_row_moved(self):
        row = self._row()
        assert row["loadings"]["d_ig"] == -0.0279
        assert row["residual_sigma_annual"] == 0.1225
        assert row["inflation_passthrough"]["b_infl"] == 0.35
        assert row["inflation_passthrough"]["k_quarters"] == 8
        assert row["inflation_passthrough"]["c_anchor"] == 0.03068
        assert row["n_quarters"] == 125
        assert row["family"] == "glm"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
