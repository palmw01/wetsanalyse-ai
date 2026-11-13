"""Graph-qa meldt de api wat zijn image bevat (ADR-016 §B1): idempotent, zonder inhoud in de logs, nooit in de weg."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from agent import bronpakket, imagemelding, wetsanalyse_api
from fakes import make_settings

PAKKET = bronpakket.pakket()


def _api(monkeypatch, antwoord):
    """Zet een nep-api onder de echte client. `antwoord(body) -> httpx.Response`; geeft de gezien verzoeken terug."""
    monkeypatch.setattr(wetsanalyse_api, "HERHAAL_NA_S", 0)
    gezien: list[tuple[str, str, dict, dict]] = []

    def transport(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        gezien.append((request.method, request.url.path, body, dict(request.headers)))
        return antwoord(body)

    echte = httpx.AsyncClient
    monkeypatch.setattr(wetsanalyse_api.httpx, "AsyncClient",
                        lambda **_k: echte(transport=httpx.MockTransport(transport)))
    return gezien


def _settings(**extra):
    return make_settings(wetsanalyse_api_url="http://api:3000", wetsanalyse_api_token="t", revisie="abc1234", **extra)


def test_een_bekend_pakket_kost_alleen_de_hash(monkeypatch):
    gezien = _api(monkeypatch, lambda body: httpx.Response(200, json={"bekend": True, "geschreven": False}))
    assert asyncio.run(imagemelding.meld(_settings())) == "bekend"
    [(methode, pad, body, headers)] = gezien
    assert (methode, pad) == ("PUT", "/v1/werkplaats/image")
    assert body == {"pakket_hash": PAKKET["sha256"], "revisie": "abc1234"}
    assert headers["authorization"] == "Bearer t"


def test_een_onbekend_pakket_gaat_daarna_in_zijn_geheel(monkeypatch):
    gezien = _api(monkeypatch, lambda body: httpx.Response(
        200, json={"bekend": True, "geschreven": True} if "onderdelen" in body else {"bekend": False}))
    assert asyncio.run(imagemelding.meld(_settings())) == "geschreven"
    assert [set(b) for _, _, b, _ in gezien] == [{"pakket_hash", "revisie"}, {"pakket_hash", "revisie", "onderdelen"}]
    assert gezien[1][2]["onderdelen"] == PAKKET["onderdelen"]


def test_zonder_api_of_zonder_werkplaats_gebeurt_er_niets(monkeypatch, caplog):
    gezien = _api(monkeypatch, lambda body: httpx.Response(404, json={"detail": "De werkplaats staat niet aan."}))
    assert asyncio.run(imagemelding.meld(make_settings())) == "uit" and gezien == []
    with caplog.at_level(logging.INFO):
        assert asyncio.run(imagemelding.meld_met_herhaling(_settings())) == "werkplaats_uit"
    # Een omgeving zonder werkplaats is geen fout: één verzoek, geen foutregel.
    assert len(gezien) == 1 and not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_een_storing_wordt_later_herhaald_en_houdt_de_dienst_niet_op(monkeypatch, caplog):
    antwoorden = [503, 503, 503, 503, 200]
    gezien = _api(monkeypatch, lambda body: httpx.Response(antwoorden.pop(0), json={"bekend": True}))
    # Elke poging is één verzoek plus de ene herhaling van de client; de tweede poging slaagt bij het vijfde antwoord.
    assert asyncio.run(imagemelding.meld_met_herhaling(_settings(), wacht=(0, 0, 0))) == "bekend"
    assert len(gezien) == 5


def test_blijft_de_api_weg_dan_geeft_de_melding_het_op_met_een_waarschuwing(monkeypatch, caplog):
    _api(monkeypatch, lambda body: httpx.Response(500, json={}))
    with caplog.at_level(logging.INFO):
        assert asyncio.run(imagemelding.meld_met_herhaling(_settings(), wacht=(0,))) == "mislukt"
    [regel] = [r for r in caplog.records if r.getMessage() == "image melden mislukt"]
    assert regel.poging == 2 and regel.pakket_hash == PAKKET["sha256"]


def test_de_logregels_dragen_geen_inhoud(monkeypatch, caplog):
    _api(monkeypatch, lambda body: httpx.Response(200, json={"bekend": "onderdelen" in body, "geschreven": True}))
    with caplog.at_level(logging.DEBUG):
        assert asyncio.run(imagemelding.meld_met_herhaling(_settings())) == "geschreven"
    [regel] = [r for r in caplog.records if r.name == "graph_qa.imagemelding"]
    extra = {k: v for k, v in vars(regel).items() if k in ("pakket_hash", "revisie", "uitkomst", "poging", "categorie")}
    assert extra == {"pakket_hash": PAKKET["sha256"], "revisie": "abc1234", "uitkomst": "geschreven", "poging": 1,
                     "categorie": "technisch"}
    tekst = json.dumps({k: str(v) for k, v in vars(regel).items()})
    assert "Juridisch Analyseschema" not in tekst and "onderdelen" not in tekst


def test_de_dienst_start_de_melding_op_de_achtergrond():
    import inspect

    from api import main
    bron = inspect.getsource(main._lifespan)
    assert "asyncio.create_task(imagemelding.meld_met_herhaling(settings)" in bron and "melding.cancel()" in bron
    assert bron.index("create_task(imagemelding") < bron.index("yield")
