"""Synchrone leesadapter voor afleidingsregels (ADR-018; regels herleidbaar, 20 nov 2026, stap 7).

Lex leest de regels bij de api, niet in de graaf: Postgres is de waarheid, en de poort, de gaten en de toets van de
voorbeelden rekent alleen de api. Net als `begrip_read.BegripReadApi`: fouten zijn nooit lege resultaten, en de actor
is de rungebruiker, nooit een toolargument. Alleen lezen: het agent-token mag op een regel niets wijzigen
(`api/app/agent_toegang.py`).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .annotatie_read import _detail
from .config import Settings
from .wetsanalyse_api import TIMEOUT


class RegelReadApi:
    def __init__(self, settings: Settings, user_id: str = "", werkgebied_id: str = "", *, transport=None):
        self.settings = settings
        self.user_id = user_id
        self.werkgebied_id = werkgebied_id
        self.transport = transport

    def _request(self, method: str, path: str, data: dict[str, Any], sleutel: str = "") -> dict[str, Any]:
        """`sleutel`: zet het antwoord onder die sleutel, als het zelf een `status` draagt (een regel)."""
        if not self.settings.wetsanalyse_api_url or not self.settings.wetsanalyse_api_token:
            return {"status": "unavailable", "volledig": False, "reden": "regels_api_niet_ingesteld"}
        if not self.user_id:
            return {"status": "unavailable", "volledig": False, "reden": "regels_gebruikerscontext_ontbreekt"}
        try:
            with httpx.Client(timeout=TIMEOUT, transport=self.transport) as client:
                response = client.request(
                    method, self.settings.wetsanalyse_api_url.rstrip("/") + "/v1" + path,
                    headers={"Authorization": f"Bearer {self.settings.wetsanalyse_api_token}",
                             "X-User-Id": self.user_id}, params=data)
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError("ongeldig regelantwoord")
                return {"status": "ok", sleutel: result} if sleutel else {"status": "ok", **result}
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = _detail(exc.response) if status in (400, 422) else ""
            return {**({"detail": detail} if detail else {}),
                    "status": "invalid_request" if status in (400, 404, 422) else "unavailable", "volledig": False,
                    "reden": ("regel_bestaat_niet" if status == 404 else
                              "ongeldige_zoekargumenten" if status in (400, 422) else
                              "regels_niet_toegestaan" if status in (401, 403) else f"regels_api_{status}"),
                    "http_status": status}
        except (httpx.HTTPError, ValueError):
            return {"status": "unavailable", "volledig": False, "reden": "regels_api_onbereikbaar"}

    def zoek(self, q: str, status: list[str], werkgebied_id: str) -> dict[str, Any]:
        data: dict[str, Any] = {"q": q[:200], "status": status}
        if werkgebied_id:
            data["werkgebied_id"] = werkgebied_id
        return self._request("GET", "/regels", data)

    def regel(self, werkgebied_id: str, regel_id: str) -> dict[str, Any]:
        return self._request("GET", "/werkgebieden/" + quote(werkgebied_id, safe="") + "/regels/"
                             + quote(regel_id, safe=""), {}, "regel")
