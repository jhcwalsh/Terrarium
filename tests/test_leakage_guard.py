"""WP2.1 acceptance: split access guard + the import-graph leakage proof."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from ah.eval.g2 import final_evaluation_token
from ah.splits import DataAccess, HoldoutAccessError

ROOT = Path(__file__).resolve().parents[1]
GEN_DIR = ROOT / "src" / "ah" / "gen"


def _reader(_series_id: str) -> pd.DataFrame:
    dates = pd.date_range("1900-01-01", "2026-07-01", freq="YS")
    return pd.DataFrame({"date": dates, "value": range(len(dates))})


def test_train_and_validation_are_open() -> None:
    da = DataAccess(_reader)
    tr = da.frame("x", "train")
    val = da.frame("x", "validation")
    assert tr["date"].max() < pd.Timestamp("2011-01-01")
    assert val["date"].min() >= pd.Timestamp("2011-01-01")
    assert val["date"].max() < pd.Timestamp("2021-01-01")


def test_train_val_excludes_holdout() -> None:
    da = DataAccess(_reader)
    tv = da.train_val("x")
    assert tv["date"].max() < pd.Timestamp("2021-01-01")  # holdout never in the reference surface


def test_holdout_requires_token() -> None:
    da = DataAccess(_reader)
    with pytest.raises(HoldoutAccessError):
        da.frame("x", "holdout")
    # the sanctioned token unlocks it
    got = da.frame("x", "holdout", token=final_evaluation_token())
    assert got["date"].min() >= pd.Timestamp("2021-01-01")


def test_unknown_split_errors() -> None:
    with pytest.raises(KeyError):
        DataAccess(_reader).frame("x", "nope")


# --------------------------------------------------------------------------- #
# import-graph proof: no generator/training module may import ah.eval.g2
# --------------------------------------------------------------------------- #

_G2_IMPORT = re.compile(
    r"import\s+ah\.eval\.g2|from\s+ah\.eval\.g2\b|from\s+ah\.eval\s+import\s+.*\bg2\b"
)


def test_gen_modules_never_import_g2() -> None:
    offenders = []
    for path in GEN_DIR.rglob("*.py"):
        if _G2_IMPORT.search(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, (
        f"generator modules must not import ah.eval.g2 (holdout mint): {offenders}"
    )
