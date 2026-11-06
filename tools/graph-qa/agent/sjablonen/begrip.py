"""Het sjabloon voor een begripsvraag: wat de wet zegt en wat juristen vastlegden, los van elkaar.

Een vastgelegd begrip is een analyse-uitkomst met een status, geen wettelijke definitie. Daarom twee blokken,
en een leemte als de wet niets zegt. "In de graaf bij deze term": dat de graaf niets vond, zegt niet dat de wet
niets zegt.
"""
from __future__ import annotations

from typing import Any

from bronmodel.antwoord import Antwoord, Begrippen, Definitie, Definities, Leemte, Toelichting, VastgelegdBegrip
from bronmodel.definities import geldigheid_uit, losse_termen, term_vindplaats

from .vullen import Onvulbaar, Trace, resultaten, rijen, vindplaats_van, volledige_tekst

SCHEMA: dict[str, Any] = {
    "name": "antwoord_begrip",
    "description": (
        "Rond een vraag naar de betekenis van een begrip af. Roep deze tool aan nadat je zoek_definitie en zo nodig "
        "search_begrippen hebt gebruikt, en schrijf geen antwoord ernaast. De werkplek toont de wettelijke definities met "
        "hun vindplaats en de vastgelegde begrippen zelf, uit wat de tools teruggaven: herhaal die niet. Jij levert het begrip "
        "en een korte toelichting in eigen woorden, zonder citaten en zonder vindplaatsen die je niet hebt opgehaald."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "begrip": {"type": "string", "description": "De term waarnaar gevraagd is, zoals de wet hem schrijft."},
            "toelichting": {"type": "string", "description": "Twee of drie zinnen: wat de definitie betekent. Leeg als er niets te zeggen valt."},
        },
        "required": ["begrip", "toelichting"],
        "additionalProperties": False,
    },
}


def _zelfde_term(a: str, b: str) -> bool:
    """Dezelfde term, ook in het meervoud. `zoek_definitie` zoekt op een deel van het woord, dus "aanslag" levert
    ook "belastingaanslag": die hoort hier niet."""
    a, b = a.strip(), b.strip()
    return any(g.casefold() == o.casefold() for x, y in ((a, b), (b, a)) if (g := term_vindplaats(x, y)) for o in (y,))


def _definities(begrip: str, trace: Trace) -> list[Definitie]:
    uit: dict[str, Definitie] = {}
    for rij in rijen(trace, ["zoek_definitie"]):
        node, ruw = rij.get("node", ""), rij.get("begrip", "")
        if not node or node in uit or not any(_zelfde_term(begrip, t) for t in losse_termen(ruw)):
            continue
        tekst = rij.get("tekst", "") if rij.get("tekst_volledig") is not False else volledige_tekst(node, trace)
        if not tekst:
            raise Onvulbaar(f"De tekst van {node} is niet volledig opgehaald. Haal de bepaling op met get_lid en rond dan af.")
        g = geldigheid_uit(tekst)
        uit[node] = Definitie(term=ruw, tekst=tekst, bereik=g.formule,
                              vindplaats=vindplaats_van(node, jci=rij.get("jci", ""), regeling=rij.get("citeertitel", ""), label=rij.get("inLabel", "")))
    return list(uit.values())


def _vastgelegd(begrip: str, trace: Trace) -> list[VastgelegdBegrip]:
    uit: dict[str, VastgelegdBegrip] = {}
    for rij in rijen(trace, ["search_begrippen"]):
        if rij.get("id") and any(_zelfde_term(begrip, t) for t in [rij.get("naam", ""), *(rij.get("alternatieve_termen") or [])]):
            uit[rij["id"]] = VastgelegdBegrip(
                id=rij["id"], naam=rij.get("naam", ""), status=rij.get("status", ""), definitie=rij.get("definitie", ""),
                werkgebied=rij.get("werkgebied", ""), werkgebied_id=rij.get("werkgebied_id", ""), herbeoordelen=bool(rij.get("herbeoordelen")))
    # `get_begrip` draagt de hele definitie; de zoekrij een ingekorte.
    for data in resultaten(trace, ["get_begrip"]):
        if (b := uit.get(data.get("id", ""))) and data.get("definitie"):
            b.definitie = data["definitie"]
    return list(uit.values())


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    begrip = str(invoer.get("begrip") or "").strip()
    if not begrip:
        raise Onvulbaar("Noem het begrip.")
    if not any(True for _ in resultaten(trace, ["zoek_definitie"])):
        raise Onvulbaar("Zoek eerst de wettelijke definitie met zoek_definitie.")
    definities = _definities(begrip, trace)
    vastgelegd = _vastgelegd(begrip, trace)
    blokken: list[Any] = [Definities(items=definities) if definities
                          else Leemte(tekst=f"Geen wettelijke definitie in de graaf bij de term „{begrip}”.")]
    if vastgelegd:
        blokken.append(Begrippen(items=vastgelegd))
    if toelichting := str(invoer.get("toelichting") or "").strip():
        blokken.append(Toelichting(tekst=toelichting))
    return Antwoord(sjabloon="begrip", blokken=blokken, doelen=[d.vindplaats for d in definities])
