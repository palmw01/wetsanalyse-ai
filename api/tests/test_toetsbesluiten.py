"""De besluiten over een contenttoets (plan contenttoets, C7): op het bericht, per bevinding, alleen door de mens.

Lex stelt voor; de redacteur of jurist zegt per bevinding of hij het eens is en wat er met het voorstel gebeurt. De toets
bestaat alleen in het bericht, dus daar staat ook het besluit, geadresseerd met de run die het bericht schreef.
"""
from __future__ import annotations

import pytest

from conftest import api_client

_A = {"X-User-Id": "gebruiker-a"}
_B = {"X-User-Id": "gebruiker-b"}

_VP = {"iri": "urn:bwb:BWBR0024096:x", "label": "Artikel 25.3a.1", "jci": "", "regeling": "Leidraad Invordering 2008"}
_TOETS = {
    "soort": "contenttoets", "door": "lex", "content": "U betaalt in maximaal 24 maanden. Of in 12 maanden.",
    "peildatum": "2026-11-25", "getoetst_tegen": ["Leidraad Invordering 2008"], "voor_redacteur": [], "niet_getoetst": [],
    "ontbreekt": [],
    "bevindingen": [
        {"nr": 1, "citaat": "maximaal 24 maanden", "begin": 13, "eind": 32, "oordeel": "mogelijk_onjuist", "criterium": "J1",
         "bronnen": [{"tekst": "maximaal twaalf maanden", "vindplaats": _VP}], "toelichting": "", "twijfel": "",
         "voorstel": "U betaalt in maximaal 12 maanden."},
        {"nr": 2, "citaat": "in 12 maanden", "begin": 37, "eind": 50, "oordeel": "juist", "criterium": "",
         "bronnen": [{"tekst": "maximaal twaalf maanden", "vindplaats": _VP}], "toelichting": "", "twijfel": "",
         "voorstel": ""},
    ],
}


@pytest.fixture
async def client(monkeypatch):
    async with api_client(monkeypatch, env={"WETSANALYSE_AUTH_REQUIRED": "0"}, reconcile=True,
                          gebruikers=("gebruiker-a", "gebruiker-b")) as ac:
        yield ac


async def _gesprek_met_toets(client, run_id="r1", blokken=None) -> str:
    g = (await client.post("/v1/gesprekken", headers=_A, json={"titel": "t"})).json()["id"]
    antwoord = {"sjabloon": "contenttoets", "versie": 1, "doelen": [], "blokken": blokken if blokken is not None else [_TOETS]}
    r = await client.post(f"/v1/gesprekken/{g}/berichten", headers=_A,
                          json={"rol": "assistant", "tekst": "Het rapport.", "run_id": run_id, "antwoord": antwoord})
    assert r.status_code == 201, r.text
    return g


async def test_een_besluit_staat_op_het_bericht_en_overleeft_herladen(client):
    g = await _gesprek_met_toets(client)
    assert (await client.get(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten", headers=_A)).json() == []
    r = await client.put(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten/1", headers=_A,
                         json={"oordeel": "eens", "voorstel": "aangepast", "tekst": "U betaalt in hoogstens 12 maanden."})
    assert r.status_code == 200, r.text
    [b] = r.json()
    assert (b["nr"], b["oordeel"], b["voorstel"], b["door"]) == (1, "eens", "aangepast", "gebruiker-a")
    await client.put(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten/2", headers=_A, json={"oordeel": "eens"})
    bericht = (await client.get(f"/v1/gesprekken/{g}", headers=_A)).json()["berichten"][-1]
    assert [(b["nr"], b["oordeel"], b["voorstel"]) for b in bericht["toetsbesluiten"]] == [(1, "eens", "aangepast"),
                                                                                         (2, "eens", None)]


async def test_een_nieuw_besluit_vervangt_het_vorige_en_leeg_wist(client):
    g = await _gesprek_met_toets(client)
    pad = f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten/1"
    await client.put(pad, headers=_A, json={"oordeel": "eens", "voorstel": "overgenomen"})
    r = await client.put(pad, headers=_A, json={"oordeel": "oneens", "voorstel": "afgewezen", "reden": "De 24 klopt hier."})
    assert [(b["oordeel"], b["voorstel"], b["reden"]) for b in r.json()] == [("oneens", "afgewezen", "De 24 klopt hier.")]
    assert (await client.put(pad, headers=_A, json={})).json() == []


@pytest.mark.parametrize("body", [{"voorstel": "aangepast"}, {"voorstel": "overgenomen", "tekst": "x"},
                                  {"oordeel": "misschien"}, {"oordeel": "eens", "onbekend": 1}])
async def test_een_besluit_dat_niet_klopt_is_een_422(client, body):
    g = await _gesprek_met_toets(client)
    assert (await client.put(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten/1", headers=_A, json=body)).status_code == 422


async def test_een_onbekende_bevinding_of_een_bericht_zonder_toets(client):
    g = await _gesprek_met_toets(client)
    r = await client.put(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten/9", headers=_A, json={"oordeel": "eens"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "onbekende_bevinding"
    assert (await client.put(f"/v1/gesprekken/{g}/runs/onbekend/toetsbesluiten/1", headers=_A,
                             json={"oordeel": "eens"})).status_code == 404
    zonder = await _gesprek_met_toets(client, run_id="r2", blokken=[{"soort": "toelichting", "door": "lex", "kop": "Kort antwoord",
                                                                      "tekst": "Geen toets."}])
    r = await client.get(f"/v1/gesprekken/{zonder}/runs/r2/toetsbesluiten", headers=_A)
    assert r.status_code == 404 and r.json()["detail"]["fout"] == "geen_contenttoets"


async def test_andermans_gesprek_bestaat_niet(client):
    g = await _gesprek_met_toets(client)
    assert (await client.get(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten", headers=_B)).status_code == 404
    assert (await client.put(f"/v1/gesprekken/{g}/runs/r1/toetsbesluiten/1", headers=_B,
                             json={"oordeel": "eens"})).status_code == 404
