"""Synchrone leesadapter voor begrippen (fase F4): de api bevestigt wat Lex in de graaf vond.

Net als `annotatie_read.AnnotatieReadApi`: fouten zijn nooit lege resultaten, en de actor is de
rungebruiker (of `ANNOTATIE_READ_USER_ID` voor CLI/MCP), nooit een toolargument. `werkgebied_id` is
het werkgebied van waaruit de werkplek het gesprek opende; zijn begrippen staan vooraan.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .annotatie_read import _detail
from .config import Settings
from .wetsanalyse_api import TIMEOUT


class BegripReadApi:
    def __init__(self, settings: Settings, user_id: str = "", werkgebied_id: str = "", *, transport=None):
        self.settings = settings
        self.user_id = user_id
        self.werkgebied_id = werkgebied_id
        self.transport = transport

    def _request(self, method: str, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.wetsanalyse_api_url or not self.settings.wetsanalyse_api_token:
            return {"status": "unavailable", "volledig": False, "reden": "begrippen_api_niet_ingesteld"}
        if not self.user_id:
            return {"status": "unavailable", "volledig": False, "reden": "begrippen_gebruikerscontext_ontbreekt"}
        try:
            with httpx.Client(timeout=TIMEOUT, transport=self.transport) as client:
                response = client.request(
                    method, self.settings.wetsanalyse_api_url.rstrip("/") + "/v1/begrippen" + path,
                    headers={"Authorization": f"Bearer {self.settings.wetsanalyse_api_token}",
                             "X-User-Id": self.user_id},
                    **({"json": data} if method == "POST" else {"params": data}))
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("ongeldig begrippenantwoord")
                return {"status": "ok", **result}
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = _detail(exc.response) if status in (400, 422) else ""
            return {**({"detail": detail} if detail else {}),
                    "status": "invalid_request" if status in (400, 404, 422) else "unavailable", "volledig": False,
                    "reden": ("begrip_bestaat_niet" if status == 404 else
                              "ongeldige_zoekargumenten" if status in (400, 422) else
                              "begrippen_niet_toegestaan" if status in (401, 403) else f"begrippen_api_{status}"),
                    "http_status": status}
        except (httpx.HTTPError, ValueError):
            return {"status": "unavailable", "volledig": False, "reden": "begrippen_api_onbereikbaar"}

    def verifieer(self, ids: list[str], werkgebieden: list[str]) -> dict[str, Any]:
        return self._request("POST", "/verifieer", {"ids": ids[:50], "werkgebieden": werkgebieden[:50]})

    def begrip(self, begrip_id: str) -> dict[str, Any]:
        return self._request("GET", "/" + quote(begrip_id, safe=""), {})
