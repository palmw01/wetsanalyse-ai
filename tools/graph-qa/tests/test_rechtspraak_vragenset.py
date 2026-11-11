"""De vragenset van de connector Rechtspraak (`tests/data/rechtspraak_vragenset_30.json`): de route en de argumenten.

Per vraag die de code zelf leest (`route`: lijstvraag of genoemd stuk) toetst dit dat `bron_lijst.lees` of
`genoemde_stukken` precies de argumenten uit de set geeft; een vraag voor het model mag de code niet zelf lezen. Een
vraag met `open` is een bekende afwijking (gedeelde code, gemeld): `xfail(strict=True)`, zodat een oplossing hier rood
wordt en de set dan bijgewerkt moet worden. Wat het antwoord van Lex op acceptatie doet, staat in de rondes in
`docs/architectuur/metingen/rechtspraak-iteratie-2026-11-11/`.

De regelingen bij naam komen hier uit een vaste lijst (`NAMEN`), zoals de graaf van acceptatie ze kent; elke naam die in
de vraag staat telt, net als `overzicht.regelingen_in_vraag`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agent.bron_lijst import lees as lijstvraag
from bronmodel.connectors import genoemde_stukken

SET = json.loads((Path(__file__).parent / "data" / "rechtspraak_vragenset_30.json").read_text(encoding="utf-8"))["vragen"]
AAN = frozenset({"rechtspraak", "kamerstukken", "bekendmakingen"})
NAMEN = {
    "BWBR0004770": {"Invorderingswet 1990", "Iw 1990"},
    "BWBR0002320": {"Algemene wet inzake rijksbelastingen", "AWR"},
    "BWBR0005537": {"Algemene wet bestuursrecht", "Awb"},
    "BWBR0018472": {"Algemene wet inkomensafhankelijke regelingen", "Awir"},
    "BWBR0004766": {"Uitvoeringsregeling Invorderingswet 1990"},
    "BWBR0024096": {"Leidraad Invordering 2008"},
}


def _regelingen(tekst: str) -> list[tuple[str, set[str]]]:
    return [(b, n) for b, n in NAMEN.items()
            if any(re.search(rf"(?<!\w){re.escape(x)}(?!\w)", tekst, re.IGNORECASE) for x in n)]


def _route(v: dict) -> tuple:
    if (l := lijstvraag(v["vraag"], AAN, _regelingen)) is not None:
        return ("lijstvraag", l.tool, l.args)
    if (g := [i for _, i in genoemde_stukken(v["vraag"])]):
        return ("genoemd stuk", "get_uitspraak", {"id": g[0]})
    return ("model",)


def _gevallen():
    for v in SET:
        marks = [pytest.mark.xfail(reason=v["open"], strict=True)] if v.get("open") else []
        yield pytest.param(v, id=v["id"], marks=marks)


@pytest.mark.parametrize("v", list(_gevallen()))
def test_de_route_leest_wat_de_set_zegt(v: dict):
    if v.get("gesprek") and v["route"] == "model":
        pytest.skip("een vervolgvraag leest de supervisor met het gesprek erbij")
    uit = _route(v)
    if v["route"] == "model":
        assert uit == ("model",), f"{v['id']}: de code las de vraag zelf: {uit}"
    else:
        assert uit == (v["route"], v["tool"], v["args"]), f"{v['id']}: de code las {uit}"


def test_de_set_dekt_het_geheel():
    """Dertig vragen (twee in twee beurten), elk met een verwachting, en de spreiding die de opdracht vraagt."""
    assert len({v["id"][:3] for v in SET}) == 30 and len({v["id"] for v in SET}) == len(SET)
    assert all(v.get("goed") and v.get("tool") and v.get("route") in ("lijstvraag", "genoemd stuk", "model") for v in SET)
    routes = {v["route"] for v in SET}
    assert routes == {"lijstvraag", "genoemd stuk", "model"}
    wetten = {v["args"].get("bwb_id") for v in SET if v["args"].get("bwb_id")}
    assert len(wetten) >= 7, wetten
