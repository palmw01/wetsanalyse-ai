"""Synchrone leesadapter voor de worker-thread; fouten zijn nooit lege zoekresultaten."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings
from .wetsanalyse_api import TIMEOUT


class AnnotatieReadApi:
    def __init__(self, settings: Settings, user_id: str = "", *, transport=None):
        self.settings = settings
        self.user_id = user_id
        self.transport = transport

    def _request(self, method: str, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.wetsanalyse_api_url or not self.settings.wetsanalyse_api_token:
            return {"status": "unavailable", "volledig": False, "reden": "annotatie_api_niet_ingesteld"}
        if not self.user_id:
            return {"status": "unavailable", "volledig": False, "reden": "annotatie_gebruikerscontext_ontbreekt"}
        try:
            with httpx.Client(timeout=TIMEOUT, transport=self.transport) as client:
                response = client.request(
                    method, self.settings.wetsanalyse_api_url.rstrip("/") + "/v1/annotatie" + path,
                    headers={"Authorization": f"Bearer {self.settings.wetsanalyse_api_token}",
                             "X-User-Id": self.user_id},
                    **({"json": data} if method == "POST" else {"params": data}),
                )
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("ongeldig annotatieantwoord")
                return result
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            return {"status": "invalid_request" if status in (400, 409, 422) else "unavailable", "volledig": False,
                    "reden": ("zoekresultaten_gewijzigd_begin_opnieuw" if status == 409 else
                              "ongeldige_zoekargumenten" if status in (400, 422) else
                              "annotatie_niet_toegestaan" if status in (401, 403) else f"annotatie_api_{status}"),
                    "http_status": status}
        except (httpx.HTTPError, ValueError):
            return {"status": "unavailable", "volledig": False, "reden": "annotatie_api_onbereikbaar"}

    def zoeken(self, filters: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/zoeken", filters)

    def element(self, element_id: str) -> dict[str, Any]:
        return self._request("GET", "/elementen/" + quote(element_id, safe=""), {})

    def dekking(self, doel: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", "/dekking", doel)

    def weergave(self, doel: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", "/weergave", doel)
