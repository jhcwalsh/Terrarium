"""Albourne PriMaRS Public Dataservice client (sync, httpx).

Verified contract (see also session.md §3, reference memory):

- Base URL: https://dataservice-us.albourne.com/dataservice
- Auth: Bearer access token; refresh via GET /auth/refreshToken with
  the refresh token as Bearer. Response: {"token": "<new>"}. A 401 on
  any data call triggers exactly one refresh-and-retry.
- Mandatory header on every request: `endpoint: SWAGGER`.
- PriMaRS endpoints under /public/data/rest/.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from primars.config import ALBOURNE_BASE_URL


class PrimarsAPIError(Exception):
    """Raised on a non-2xx response from the Albourne API."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Albourne API error {status}: {message[:300]}")
        self.status = status
        self.message = message


class PrimarsClient:
    """Sync HTTP client for the four PriMaRS routes."""

    def __init__(
        self,
        token: str,
        refresh_token: str = "",
        base_url: str = ALBOURNE_BASE_URL,
        timeout: float = 60.0,
        retry_max: int = 3,
        retry_sleep: float = 2.0,
    ) -> None:
        self._token = token
        self._refresh_token = refresh_token
        self.base_url = base_url.rstrip("/")
        self.retry_max = retry_max
        self.retry_sleep = retry_sleep
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Accept": "application/json", "endpoint": "SWAGGER"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PrimarsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal: auth + request

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            raise PrimarsAPIError(401, "access token expired and no refresh token configured")
        resp = self._client.get(
            f"{self.base_url}/auth/refreshToken",
            headers={"Authorization": f"Bearer {self._refresh_token}"},
        )
        if resp.status_code != 200:
            raise PrimarsAPIError(resp.status_code, f"refresh failed: {resp.text}")
        new_token = resp.json().get("token")
        if not new_token:
            raise PrimarsAPIError(500, "refresh response missing 'token' field")
        self._token = new_token

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        _retried_auth: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        last_5xx: httpx.Response | None = None
        for attempt in range(self.retry_max):
            if method == "GET":
                resp = self._client.get(url, headers=self._auth_headers())
            else:
                resp = self._client.post(url, headers=self._auth_headers(), json=json_body)
            if resp.status_code == 401 and not _retried_auth and self._refresh_token:
                self._refresh_access_token()
                return self._request(method, path, json_body, _retried_auth=True)
            if 500 <= resp.status_code < 600:
                last_5xx = resp
                if attempt < self.retry_max - 1:
                    time.sleep(self.retry_sleep * (2 ** attempt))
                    continue
                raise PrimarsAPIError(resp.status_code, resp.text)
            if resp.status_code != 200:
                raise PrimarsAPIError(resp.status_code, resp.text)
            return resp.json()
        # Unreachable, but satisfy the type checker.
        assert last_5xx is not None
        raise PrimarsAPIError(last_5xx.status_code, last_5xx.text)

    # ------------------------------------------------------------------
    # PriMaRS endpoints

    def index_list(self, primars_type: str, vintage: int | None = None) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"primarsType": primars_type}
        if vintage is not None:
            body["vintage"] = vintage
        result: list[dict[str, Any]] = self._request(
            "POST", "/public/data/rest/primarsIndexList", body
        )
        return result

    def index_data(
        self,
        index_ids: list[int],
        field_names: list[str],
        start_quarter: str | None = None,
        end_quarter: str | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"indexIds": index_ids, "fieldNames": list(field_names)}
        if start_quarter:
            body["startQuarter"] = start_quarter
        if end_quarter:
            body["endQuarter"] = end_quarter
        result: list[dict[str, Any]] = self._request(
            "POST", "/public/data/rest/primarsIndexData", body
        )
        return result

    def last_quarter(self) -> Any:
        return self._request("GET", "/public/data/rest/primarsLastQuarter")

    def data_field_names(self) -> list[str]:
        result: list[str] = self._request(
            "GET", "/public/data/rest/primarsIndexDataFieldNames"
        )
        return result
