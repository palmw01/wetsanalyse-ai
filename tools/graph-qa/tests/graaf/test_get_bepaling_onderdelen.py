"""`get_bepaling` leest de onderdelen van de bepaling zelf mee (meting contenttoets C5, 26 nov 2026).

Bij Leidraad 25.3a.1 staat de uitzondering in de opsomming na de aanhef ("– aanslagen waartegen … bezwaar …"). Die hangt
aan `heeftOnderdeel`, en `get_bepaling` gaf alleen de aanhef en de subdivisies: de contenttoets miste haar.
"""
from __future__ import annotations

import json

from agent.sjablonen.vullen import bron_rijen, ouders
from agent.tools import dispatch
from tests.fakes import FakeGraph

NODE = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.3a%2FCirculaire.divisie25.3a.1"
O = NODE + "%2FTekst%2FOnderdeel._"


def _tsv(kop: list[str], *rijen: list[str]) -> str:
    regels = ["\t".join(f"?{k}" for k in kop)] + ["\t".join(f'"{w}"' if w else "" for w in r) for r in rijen]
    return json.dumps("\n".join(regels))


def _graaf(query: str) -> str:
    if "heeftOnderdeel+" in query:
        return _tsv(["o", "onummer", "otekst", "ovolg"],
                    [O + "2", "–", "conserverende aanslagen, en", "2"],
                    [O + "1", "–", "voorlopige aanslagen inkomstenbelasting over het lopende jaar,", "1"],
                    [O + "3", "–", "aanslagen waartegen een verzoek om uitstel in verband met bezwaar in behandeling is.", "3"])
    return _tsv(["node", "nummer", "tekst", "label"],
                [NODE, "25.3a.1", "De standaardbetalingsregeling geldt niet voor:", "Standaardbetalingsregeling"])


def test_de_onderdelen_van_de_bepaling_komen_mee_in_documentvolgorde():
    uit = json.loads(dispatch("get_bepaling", FakeGraph(results=_graaf), {"bwb_id": "BWBR0024096", "nummer": "25.3a.1"}))
    assert [r["onderdeel"] for r in uit["resultaten"]] == [O + "1", O + "2", O + "3"]
    assert uit["bepaling"]["onderdelen"] == 3 and "onderdelen" in uit["toelichting"]


def test_een_onderdeel_hoort_bij_de_bepaling_voor_het_citeren():
    tekst = dispatch("get_bepaling", FakeGraph(results=_graaf), {"bwb_id": "BWBR0024096", "nummer": "25.3a.1"})
    trace = [("get_bepaling", tekst)]
    assert ouders(trace)[O + "3"] == NODE
    assert "bezwaar" in bron_rijen(trace)[O + "3"]["tekst"]
