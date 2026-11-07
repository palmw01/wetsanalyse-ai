"""Eén herhaling voor een schrijfactie die de api ontdubbelt, en geen voor de rest (ROB-06)."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from agent import wetsanalyse_api
from agent.wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout
from fakes import make_settings


def _client(antwoorden: list[int], monkeypatch) -> tuple[WetsanalyseApi, list[str]]:
    monkeypatch.setattr(wetsanalyse_api, "HERHAAL_NA_S", 0)
    gezien: list[str] = []

    def api(request: httpx.Request) -> httpx.Response:
        gezien.append(request.url.path)
        return httpx.Response(antwoorden.pop(0), json={"ok": True})

    c = WetsanalyseApi(make_settings(wetsanalyse_api_url="http://api:3000", wetsanalyse_api_token="t"), "jurist")
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(api))
    return c, gezien


def test_een_bericht_met_run_id_overleeft_een_tijdelijke_503(monkeypatch):
    c, gezien = _client([503, 200], monkeypatch)
    assert asyncio.run(c.voeg_bericht_toe("g1", {"rol": "assistant", "run_id": "r1", "tekst": ""})) == {"ok": True}
    assert len(gezien) == 2


def test_zonder_sleutel_geen_herhaling(monkeypatch):
    c, gezien = _client([503, 200], monkeypatch)
    with pytest.raises(WetsanalyseApiFout):
        asyncio.run(c.voeg_bericht_toe("g1", {"rol": "assistant", "tekst": ""}))
    assert len(gezien) == 1


def test_een_inhoudelijke_fout_wordt_niet_herhaald(monkeypatch):
    c, gezien = _client([409, 200], monkeypatch)
    with pytest.raises(WetsanalyseApiFout):
        asyncio.run(c.boek_verbruik({"invoer": 1}, run_id="r1"))
    assert len(gezien) == 1
