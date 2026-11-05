"""Welk begrip bedoelt de analist? Een naam lost op of wordt een keuzekaart; nooit stil een ander begrip (S1)."""
from __future__ import annotations

import asyncio

import pytest

from agent.agents import register
from agent.agents.begrippen import Invoer, Taak, _begrippen, voer_uit
from agent.kaart_beurt import keuzekaart, naaste, samenvatting, uit_keuze
from fakes import agent_ctx

WG = "wg1"


def rij(i, naam, **kw):
    return {"id": i, "naam": naam, "status": "concept", "werkgebied_id": WG, "werkgebied_naam": "Proef",
            "alternatieve_termen": [], "definitie": "", **kw}


AWR = rij("a", "akte (regeling A)")
BW = rij("b", "akte (regeling B)")
SOM = rij("c", "bestemming van een rekening")
BOVEN = rij("d", "aangifte")


class Api:
    def __init__(self, *rijen):
        self.rijen = {r["id"]: r for r in rijen}

    async def zoek_begrippen(self, q, eerst="", limit=20):
        w = q.casefold().split()
        return {"resultaten": [r for r in self.rijen.values() if all(x in r["naam"].casefold() for x in w)]}

    async def haal_begrip(self, wid, bid):
        r = self.rijen[bid]
        return {"status": r["status"], "inhoud": {"naam": r["naam"]}}

    async def haal_werkgebied(self, wid):
        return {"naam": "Proef"}


def keuze(api, **kw):
    invoer = Invoer(taak=kw.pop("taak", Taak.BETEKENISVERSCHIL), werkgebied_id=WG, **kw)
    return asyncio.run(_begrippen(agent_ctx(api), invoer))


def test_de_kern_van_de_naam_lost_op_met_het_haakje_erbij():
    assert [r["id"] for r in naaste("akte uit de regeling a", [AWR, BW])] == ["a"]
    assert {r["id"] for r in naaste("akte", [AWR, BW])} == {"a", "b"}
    assert naaste("rekening", [rij("x", "akte")]) == []


def test_een_vervangen_begrip_telt_niet_mee():
    assert naaste("akte", [rij("x", "akte (oud)", status="vervangen")]) == []


def test_het_aangewezen_begrip_is_niet_zijn_eigen_vergelijking():
    """De e2e-test: gevraagd op het ene begrip naar het tweede met dezelfde kernnaam."""
    k = keuze(Api(AWR, BW, SOM), begrip_id="a", termen=["akte"])
    assert (k.begrip["id"], k.ander["id"]) == ("a", "b") and k.kaart is None


def test_de_vraag_gaat_voor_op_het_aangewezen_begrip():
    k = keuze(Api(AWR, SOM, BOVEN), begrip_id="d", termen=["akte", "bestemming van een rekening"])
    assert (k.begrip["id"], k.ander["id"]) == ("a", "c")


def test_twijfel_wordt_een_kaart_met_de_begrippen():
    k = keuze(Api(AWR, BW, BOVEN), begrip_id="d", termen=["akte"])
    assert k.begrip is None and k.kaart["stap"] == "begrip_kiezen" and k.kaart["modus"] == "begrip"
    assert k.kaart["intake_id"] == "bk-wg1" and "aangifte" in k.kaart["vraag"]
    assert {o["label"] for o in k.kaart["opties"]} == {AWR["naam"], BW["naam"]}
    assert uit_keuze(k.kaart["opties"][0]["waarde"]) == {"taak": "betekenisverschil", "begrip_id": "d", "ander_id": "a"}


def test_een_onbekende_term_wordt_niet_vervangen_door_het_onderwerp():
    k = keuze(Api(AWR, BOVEN), begrip_id="d", termen=["kaas"])
    assert k.begrip is None and "kaas" in k.zin


def test_de_kaart_komt_als_uitkomst_mee():
    uit = asyncio.run(voer_uit(Invoer(taak=Taak.BETEKENISVERSCHIL, werkgebied_id=WG, begrip_id="d", termen=["akte"]),
                               agent_ctx(Api(AWR, BW, BOVEN))))
    assert uit.vraagkaart and uit.gesprekstekst == uit.vraagkaart["vraag"]


def test_de_kaart_past_op_het_contract_van_de_api():
    import json
    import re
    from pathlib import Path

    bron = (Path(__file__).resolve().parents[3] / "api" / "app" / "gesprek_contracts.py").read_text()
    assert '"begrip_kiezen"' in bron and re.search(r'modus: Literal\[.*"begrip"', bron)
    kaart = keuzekaart("betekenisverschil", WG, "akte", [AWR, BW], BOVEN)
    assert len(json.dumps(kaart)) < 4000 and all(len(o["waarde"]) < 4000 for o in kaart["opties"])


def test_het_antwoord_noemt_altijd_beide_begrippen():
    t = samenvatting("betekenisverschil", "akte", "Proef", 2, "", False, "aangifte")
    assert "*akte*" in t and "*aangifte*" in t


@pytest.mark.parametrize("vraag, herschreven, verwacht", [
    ("wat is het verschil met de akte?", "wat is het betekenisverschil tussen 'een' en 'twee'?", ["akte"]),
    ("en nu?", "wat is het betekenisverschil tussen 'een' en 'twee'?", ["een", "twee"]),
])
def test_de_termen_komen_uit_de_woorden_van_de_analist(vraag, herschreven, verwacht):
    p = register.parameters("begrippen", "betekenisverschil", vraag=vraag, herschreven=herschreven)
    assert p["termen"] == verwacht
