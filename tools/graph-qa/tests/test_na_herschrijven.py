"""De regels na het herschrijven (ADR-016 A2-3c): de supervisor blijft byte-gelijk, en een overdracht van de centrale
agent draait één regel uit dezelfde keten.

`data/na_herschrijven.json` is de momentopname van de supervisor vóór `na_herschrijven` bestond (master e1532e29): voor
elke herschreven vraag de volledige state-update én de stappen in de stroom. Een verschil is een gedragswijziging.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakes import FakeGraph, make_settings, response, text_block

from agent import overzicht
from agent.nodes import supervisie
from agent.nodes.context import Bouw

MOMENTOPNAME = Path(__file__).parent / "data" / "na_herschrijven.json"
NAMEN = ("?regeling\t?citeertitel\t?soort\t?afkortingen\n"
         "<urn:bwb:BWBR0004770>\t\"Invorderingswet 1990\"\t\"wet\"\t\"IW | Iw 1990\"\n")
KAMERSTUKKEN_AAN = {"kamerstukken": {"aan": True, "label": "Kamerstukken", "reden": ""}}

#: Per regel een herschreven vraag die hem raakt, plus vragen die er langs gaan. De getypte vraag is telkens een kale
#: vervolgvraag die vóór het model niets raakt.
GEVALLEN = [
    {"id": "begrippen", "getypt": "En welke nog meer?",
     "herschreven": "Welke begrippen hebben we al vastgelegd over de belastingschuldige?"},
    {"id": "annotaties", "getypt": "En bij lid 2?",
     "herschreven": "Welke annotaties zijn er al bij artikel 9 lid 2 van de Invorderingswet 1990?"},
    {"id": "overzicht", "getypt": "En over verrekening?",
     "herschreven": "Welke artikelen gaan over verrekening?"},
    {"id": "bepaling", "getypt": "En artikel 9?",
     "herschreven": "Wat staat er in artikel 9 van de Invorderingswet 1990?"},
    {"id": "dekking", "getypt": "En die?", "werkgebied_id": "wg1",
     "herschreven": "Welke bronnen horen bij de deelvraag die het minst is uitgewerkt?"},
    {"id": "lijst", "getypt": "Wat is het laatste?", "bronstand": KAMERSTUKKEN_AAN,
     "herschreven": "Wat is het laatste Kamerstuk in dossier 32140?"},
    {"id": "lijst_uit", "getypt": "Wat is het laatste?",
     "herschreven": "Wat is het laatste Kamerstuk in dossier 32140?"},
    {"id": "uitleg", "getypt": "En wat betekent dat?",
     "herschreven": "Wat betekent artikel 9 van de Invorderingswet 1990?"},
    {"id": "zonder_herschrijven", "getypt": "Hoe zit het met de termijn?", "herschreven": ""},
]


class _Supervisor:
    def __init__(self, tekst: str):
        self.tekst = tekst

    def create(self, **_):
        return response([text_block(self.tekst)], "end_turn")


def _bouw(tekst: str) -> Bouw:
    graaf = FakeGraph(results=lambda q: NAMEN if "bwb:Regeling" in q else "")
    return Bouw(settings=make_settings(), llm=_Supervisor(tekst), graph=graaf, stop_check=None, model="m",
                model_router="m", model_ophaal="m", memory_context=lambda _s: "", advies_context=lambda _s: "")


def uitkomst(geval: dict) -> dict:
    """De state-update van de supervisor en de events in de stroom, voor één herschreven vervolgvraag."""
    events: list = []
    oud = supervisie.get_stream_writer
    supervisie.get_stream_writer = lambda: events.append
    overzicht._REGELINGEN_CACHE.clear()
    try:
        tekst = (f"VRAAG: {geval['herschreven']}\n" if geval["herschreven"] else "") + \
            "WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: p"
        state = {"question": geval["getypt"], "modus": "auto", "werkgebied_id": geval.get("werkgebied_id", ""),
                 "focus": {}, "bronstand": geval.get("bronstand") or {},
                 "messages": [{"role": "user", "content": "Wat regelt artikel 9 van de Invorderingswet 1990?"},
                              {"role": "assistant", "content": "…"},
                              {"role": "user", "content": geval["getypt"]}]}
        upd = supervisie._kies(_bouw(tekst), state)
    finally:
        supervisie.get_stream_writer = oud
        overzicht._REGELINGEN_CACHE.clear()
    return json.loads(json.dumps({"upd": upd, "events": events}, default=repr))


@pytest.mark.parametrize("geval", GEVALLEN, ids=[g["id"] for g in GEVALLEN])
def test_de_supervisor_is_byte_gelijk_aan_voor_de_refactor(geval):
    assert uitkomst(geval) == json.loads(MOMENTOPNAME.read_text(encoding="utf-8"))[geval["id"]]
