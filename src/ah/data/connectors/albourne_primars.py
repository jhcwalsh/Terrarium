"""Albourne PriMaRS downloader for the registered private-markets series.

NOT a refresh connector: ``requirements.yaml`` keeps the albourne source at
``intake: manual`` (COMM license), and this module feeds that existing manual
path — it produces the ``albourne_pm_returns`` drop the intake pipeline
already validates, QCs and vintages. ``scripts/download_primars.py`` is the
entry point. Raw payloads and drops live under gitignored ``data/``; licensed
values are never committed.

API contract (vendored client at ``docs/data/client.py``; verified live
2026-08-08 — see the probe evidence in the WP commit):

- Base ``https://dataservice-us.albourne.com/dataservice``; Bearer access
  token (``ALBOURNE_TOKEN``), refresh via ``GET /auth/refreshToken`` with the
  refresh token (``ALBOURNE_REFRESH_TOKEN``) as Bearer, one retry on 401;
  mandatory header ``endpoint: SWAGGER`` on every request.
- ``POST /public/data/rest/primarsIndexData`` with
  ``{"indexIds": [...], "fieldNames": ["TWR"]}`` (optional
  ``startQuarter``/``endQuarter`` as ISO DATES — ``"2023Q1"`` is rejected).
- Response: one object per index —
  ``{"indexId": 547791, "published": bool, "asOfDate": epoch_ms,
  "indexData": [{"QUARTER": "Fri Mar 31 00:00:00 UTC 2023",
  "TWR": "0.0326..."}, ...]}`` — TWR is a DECIMAL FRACTION in a string,
  which is exactly the intake schema's ``ret`` unit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ah.data.connectors.base import ConnectorError

BASE_URL = "https://dataservice-us.albourne.com/dataservice"

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

#: Registered series suffix -> (PriMaRS index id, index title, proxy note).
#: Ids from docs/data/primars_ids.md. Owner decisions 2026-08-08: pm_dl maps
#: to Senior Debt; pm_mezz has NO mezzanine index in the 49-index universe and
#: uses broad Private Credit as a declared proxy. Both proxies are recorded in
#: requirements.yaml notes as well — a substitution must never be silent.
PM_INDEX_MAP: dict[str, tuple[int, str, str | None]] = {
    "pm_buyout_ret_q": (547791, "Albourne AW Buy-Outs/Growth Index (USD)", None),
    "pm_growth_ret_q": (553469, "Albourne AW Growth (PE) Index (USD)", None),
    "pm_vc_ret_q": (547813, "Albourne AW Venture Capital Index (USD)", None),
    "pm_secondaries_ret_q": (553463, "Albourne AW Secondaries Index (USD)", None),
    "pm_dl_ret_q": (
        553475,
        "Albourne AW Senior Debt Index (USD)",
        "direct lending proxied by the senior-debt index (owner decision 2026-08-08)",
    ),
    "pm_mezz_ret_q": (
        547807,
        "Albourne AW Private Credit Index (USD)",
        "NO mezzanine index exists in the PriMaRS universe; broad private credit "
        "is a declared proxy (owner decision 2026-08-08)",
    ),
    "pm_distressed_ret_q": (
        547805,
        "Albourne AW Distressed, Stressed & Special Situations Index (USD)",
        None,
    ),
    "pm_re_va_ret_q": (
        558969,
        "Albourne AW Real Estate Equity Value-Added Index (USD)",
        None,
    ),
}

_ID_TO_STRATEGY = {pid: strat for strat, (pid, _, _) in PM_INDEX_MAP.items()}


def parse_java_date_quarter(text: str) -> str:
    """``"Fri Mar 31 00:00:00 UTC 2023"`` -> ``"2023Q1"`` (deterministic, tz-free)."""
    parts = text.split()
    if len(parts) != 6 or parts[1] not in _MONTHS:
        raise ConnectorError(f"unparseable PriMaRS QUARTER date: {text!r}")
    month, year = _MONTHS[parts[1]], int(parts[5])
    return f"{year}Q{(month - 1) // 3 + 1}"


def payload_to_intake_frame(payload: list[dict[str, Any]]) -> pd.DataFrame:
    """PriMaRS ``primarsIndexData`` payload -> ``albourne_pm_returns`` drop frame.

    Pure and offline-testable. Columns ``(period, strategy, ret)``; one row per
    quarter per mapped index; unknown index ids are an error, not a skip —
    receiving data this module did not ask for means the request went wrong.
    """
    rows: list[dict[str, Any]] = []
    for entry in payload:
        pid = entry.get("indexId")
        strategy = _ID_TO_STRATEGY.get(pid)
        if strategy is None:
            raise ConnectorError(f"payload carries unmapped PriMaRS index id {pid!r}")
        for obs in entry.get("indexData", []):
            if "QUARTER" not in obs or "TWR" not in obs:
                raise ConnectorError(f"index {pid}: observation missing QUARTER/TWR: {obs!r}")
            rows.append(
                {
                    "period": parse_java_date_quarter(str(obs["QUARTER"])),
                    "strategy": strategy,
                    "ret": float(obs["TWR"]),
                }
            )
    if not rows:
        raise ConnectorError("PriMaRS payload contained no observations")
    frame = pd.DataFrame(rows, columns=["period", "strategy", "ret"])
    return frame.sort_values(by=["strategy", "period"], ignore_index=True)


# --------------------------------------------------------------------------- #
# live path (never exercised in tests; pytest-socket would block it anyway)
# --------------------------------------------------------------------------- #


def _load_tokens() -> tuple[str, str]:  # pragma: no cover - live only
    """ALBOURNE_TOKEN / ALBOURNE_REFRESH_TOKEN from env, falling back to the
    repo-root ``.env`` (same stdlib pattern as the FRED and Anthropic keys)."""
    import os

    names = ("ALBOURNE_TOKEN", "ALBOURNE_REFRESH_TOKEN")
    if not all(os.environ.get(n) for n in names):
        env = Path(__file__).resolve().parents[4] / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                for n in names:
                    if line.startswith(f"{n}=") and not os.environ.get(n):
                        os.environ[n] = line.split("=", 1)[1].strip()
    token = os.environ.get("ALBOURNE_TOKEN", "")
    if not token:
        raise ConnectorError("ALBOURNE_TOKEN not set (env or .env)")
    return token, os.environ.get("ALBOURNE_REFRESH_TOKEN", "")


def fetch_pm_payload() -> list[dict[str, Any]]:  # pragma: no cover - live only
    """One live call: full TWR history for the eight mapped indices."""
    import httpx

    token, refresh = _load_tokens()
    ids = sorted(pid for pid, _, _ in PM_INDEX_MAP.values())
    with httpx.Client(
        timeout=120,
        headers={"Accept": "application/json", "endpoint": "SWAGGER"},
        follow_redirects=True,
    ) as client:

        def post(access: str) -> httpx.Response:
            return client.post(
                f"{BASE_URL}/public/data/rest/primarsIndexData",
                headers={"Authorization": f"Bearer {access}"},
                json={"indexIds": ids, "fieldNames": ["TWR"]},
            )

        resp = post(token)
        if resp.status_code == 401 and refresh:
            r = client.get(
                f"{BASE_URL}/auth/refreshToken",
                headers={"Authorization": f"Bearer {refresh}"},
            )
            if r.status_code != 200:
                raise ConnectorError(
                    f"Albourne token refresh failed: {r.status_code} {r.text[:200]}"
                )
            resp = post(r.json()["token"])
        if resp.status_code != 200:
            raise ConnectorError(f"PriMaRS indexData failed: {resp.status_code} {resp.text[:300]}")
        payload: list[dict[str, Any]] = resp.json()
        return payload
