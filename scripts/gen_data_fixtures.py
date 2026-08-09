"""Generate offline connector fixtures in each source's on-the-wire format.

Run:  uv run python scripts/gen_data_fixtures.py

These are small, format-faithful stand-ins for the recorded fixtures the ``--record``
dev flag would capture from the live sources (unavailable offline). Golden parse
tests read them; no network is ever touched (STEP1-DATA-PLAN §WP1.2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures" / "data"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build() -> None:
    # --- FRED (observations JSON) ---
    _write(
        FX / "fred" / "dgs10.json",
        json.dumps(
            {
                "observations": [
                    {"date": "2020-01-01", "value": "."},
                    {"date": "2020-01-02", "value": "2.0"},
                    {"date": "2020-01-03", "value": "4.0"},
                    {"date": "2020-02-03", "value": "3.0"},
                    {"date": "2020-02-04", "value": "5.0"},
                ]
            }
        ),
    )
    _write(
        FX / "fred" / "vix.json",
        json.dumps(
            {
                "observations": [
                    {"date": "2020-01-02", "value": "2.0"},
                    {"date": "2020-01-03", "value": "4.0"},
                    {"date": "2020-02-03", "value": "3.0"},
                    {"date": "2020-02-04", "value": "5.0"},
                ]
            }
        ),
    )
    _write(
        FX / "fred" / "vxo.json",
        json.dumps(
            {
                "observations": [
                    {"date": "2020-01-02", "value": "2.4"},
                    {"date": "2020-01-03", "value": "4.8"},
                    {"date": "2020-02-03", "value": "."},
                    {"date": "2020-02-04", "value": "6.0"},
                ]
            }
        ),
    )
    _write(
        FX / "fred" / "tb3ms.json",
        json.dumps(
            {
                "observations": [
                    {"date": "2020-01-01", "value": "1.5"},
                    {"date": "2020-02-01", "value": "1.6"},
                ]
            }
        ),
    )

    # Effective federal funds rate: the administered policy rate `policy_rate` maps to
    # (WP2.2 Task 1). FRED's first observation is 1954-07; the pre-1954 campaign
    # pre-history is spliced from fred.TB3MS via ah.data.splice's `fedfunds_pre1954`
    # rule, flagged is_proxy. The three values below are the real FRED FEDFUNDS
    # observations for 1954-07..09, so the fixture is format- *and* value-faithful.
    _write(
        FX / "fred" / "fedfunds.json",
        json.dumps(
            {
                "observations": [
                    {"date": "1954-07-01", "value": "0.80"},
                    {"date": "1954-08-01", "value": "1.22"},
                    {"date": "1954-09-01", "value": "1.07"},
                ]
            }
        ),
    )

    # --- Ken French research factors + momentum (CSV) ---
    _write(
        FX / "french" / "factors.csv",
        "This file was created by CMPT_ME_BEME_RETS using the 202412 CRSP database.\n"
        "\n"
        ",Mkt-RF,SMB,HML,RF\n"
        "202001, 2.00, -1.00,  0.50, 0.10\n"
        "202002,-3.00,  1.50, -0.25, 0.10\n"
        "\n"
        "  Annual Factors: January-December\n"
        ",Mkt-RF,SMB,HML,RF\n"
        "2020, 5.00, 1.00, 2.00, 1.20\n",
    )
    _write(
        FX / "french" / "momentum.csv",
        "This file was created ...\n"
        "\n"
        ",Mom\n"
        "202001, 1.00\n"
        "202002,-2.00\n"
        "\n"
        "  Annual Factors: January-December\n"
        ",Mom\n"
        "2020, 3.00\n",
    )

    # --- Shiller ie_data (xlsx) ---
    shiller = pd.DataFrame(
        {
            "Date": [1871.01, 1871.02, 1871.03],
            "P": [4.44, 4.50, 4.61],
            "D": [0.26, 0.26, 0.26],
            "E": [0.40, 0.40, 0.40],
            "CPI": [12.0, 12.0, 12.1],
            "CAPE": [None, None, None],
        }
    )
    (FX / "shiller").mkdir(parents=True, exist_ok=True)
    shiller.to_excel(FX / "shiller" / "ie_data.xlsx", index=False)

    # --- JST macrohistory (.dta), USA + a second country ---
    jst = pd.DataFrame(
        {
            "year": [1870, 1871, 1872, 1870, 1871, 1872],
            "iso": ["USA", "USA", "USA", "GBR", "GBR", "GBR"],
            "ltrate": [5.32, 5.11, 5.00, 3.2, 3.1, 3.0],
            "stir": [6.0, 5.5, 5.2, 2.5, 2.4, 2.3],
        }
    )
    (FX / "jst").mkdir(parents=True, exist_ok=True)
    jst.to_stata(FX / "jst" / "jst.dta", write_index=False)

    # --- BIS credit-to-GDP gap (long CSV) ---
    _write(
        FX / "bis" / "credit_gap.csv",
        "date,value\n1961-03-01,2.5\n1961-06-01,2.7\n1961-09-01,2.6\n",
    )

    # --- Treasury HQM (xlsx) ---
    hqm = pd.DataFrame(
        {
            "Date": ["2020-01-01", "2020-02-01", "2020-03-01"],
            "5.0": [2.1, 2.2, 2.0],
            "10.0": [3.1, 3.2, 3.0],
        }
    )
    (FX / "treasury_hqm").mkdir(parents=True, exist_ok=True)
    hqm.to_excel(FX / "treasury_hqm" / "hqm.xlsx", index=False)

    print(f"wrote connector fixtures under {FX}")


if __name__ == "__main__":
    build()
