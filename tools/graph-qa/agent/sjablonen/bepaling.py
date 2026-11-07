"""Het sjabloon voor een vraag naar de tekst van een bepaling: de wettekst zelf, met de vindplaats per lid.

Het model wijst aan, de code toont. Compleetheid is hier de hele opgave: `get_artikel` levert de onderdelen onder
een lid niet mee, en de eigen tekst van zo'n lid is vaak alleen de aanhef. Een lid dat hier als compleet langskomt
zonder zijn onderdelen is een stil onjuiste wettekst, dus dan gaat er een fout naar het model met wat het moet ophalen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bronmodel.antwoord import Antwoord, Bepaling, Toelichting, Wettekst

from .vullen import Onvulbaar, Trace, resultaten, vindplaats_van

SCHEMA: dict[str, Any] = {
    "name": "antwoord_bepaling",
    "description": (
        "Rond een vraag naar de tekst van een bepaling af. Roep deze tool aan nadat je de bepaling hebt opgehaald, en schrijf "
        "geen antwoord ernaast. De werkplek toont de wettekst en de vindplaats zelf, uit wat de tools teruggaven: herhaal "
        "die niet. Jij wijst de bepalingen aan met hun iri uit het toolresultaat en levert een korte toelichting in eigen "
        "woorden, zonder citaten. Vond je de bepaling niet, gebruik deze tool dan niet en zeg dat in tekst."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "bepalingen": {"type": "array", "items": {"type": "string"},
                           "description": "De iri's van de bepalingen waarnaar gevraagd is: het artikel, lid of onderdeel zelf, niet meer dan gevraagd."},
            "toelichting": {"type": "string", "description": "Twee of drie zinnen: wat de bepaling regelt. Leeg als er niets te zeggen valt."},
        },
        "required": ["bepalingen", "toelichting"],
        "additionalProperties": False,
    },
}


@dataclass
class _Stuk:
    """Wat de trace van één bronnode weet. `delen` staan op iri, zodat pagina's van dezelfde tool samenvallen."""

    tekst: str = ""
    nummer: str = ""
    delen: dict[str, dict[str, Any]] = field(default_factory=dict)
    verwacht: int | None = None  # zoveel delen zegt de tool dat er zijn
    onderdelen_elders: bool = False  # een lid uit `get_artikel`: zijn onderdelen staan daar niet in
    subdivisies: int = 0  # een bepaling uit `get_bepaling`: daar staat alleen het begin van
    nog_niet_in_werking: bool = False


def _stukken(trace: Trace) -> dict[str, _Stuk]:
    uit: dict[str, _Stuk] = {}

    def stuk(iri: str, rij: dict[str, Any]) -> _Stuk:
        s = uit.setdefault(iri, _Stuk())
        s.tekst, s.nummer = rij.get("tekst") or s.tekst, rij.get("nummer") or s.nummer
        s.nog_niet_in_werking = s.nog_niet_in_werking or bool(rij.get("nog_niet_in_werking"))
        return s

    for data in resultaten(trace, ["get_artikel"]):
        artikel = stuk((data.get("artikel") or {}).get("iri", ""), data.get("artikel") or {})
        artikel.verwacht = (data.get("artikel") or {}).get("delen", artikel.verwacht)
        for rij in data.get("resultaten") or []:
            iri = rij.get("lid") or rij.get("onderdeel", "")
            artikel.delen[iri] = rij
            if rij.get("lid"):
                stuk(iri, rij).onderdelen_elders = bool(rij.get("heeft_onderdelen"))
    for data in resultaten(trace, ["get_lid"]):
        lid = stuk((data.get("lid") or {}).get("iri", ""), data.get("lid") or {})
        lid.verwacht = (data.get("lid") or {}).get("onderdelen", lid.verwacht)
        for rij in data.get("resultaten") or []:
            lid.delen[rij.get("onderdeel", "")] = rij
            stuk(rij.get("onderdeel", ""), rij)
    for data in resultaten(trace, ["get_bepaling"]):
        b = data.get("bepaling") or {}
        stuk(b.get("iri", ""), b).subdivisies = b.get("subdivisies", 0)
    uit.pop("", None)
    return uit


def _regel(rij: dict[str, Any]) -> str:
    return " ".join(x for x in (rij.get("nummer", ""), rij.get("tekst", "")) if x)


def _tekst(iri: str, stukken: dict[str, _Stuk]) -> str:
    s = stukken[iri]
    onder = [d for d in s.delen.values() if not d.get("lid")]
    if ":o:" in iri:  # een onderdeel heeft geen eigen resultaat: zijn subonderdelen staan op de iri eronder
        onder = [{"nummer": x.nummer, "tekst": x.tekst} for k, x in stukken.items() if k.startswith(iri + ":o:")]
    return "\n".join(t for t in (s.tekst, *map(_regel, onder)) if t)


def _bepalingen(iri: str, stukken: dict[str, _Stuk], ontbreekt: list[str], nog_niet: bool = False) -> list[Bepaling]:
    s = stukken.get(iri)
    label = vindplaats_van(iri).label
    if s is None:
        ontbreekt.append(f"{label}: niet opgehaald in dit gesprek. Gebruik de iri uit een toolresultaat, en haal de bepaling zo nodig op")
        return []
    if s.subdivisies:
        ontbreekt.append(f"{label}: heeft {s.subdivisies} subdivisies waarvan get_bepaling alleen het begin geeft. Haal de subdivisies op die de vraag raakt en wijs die aan")
        return []
    if s.verwacht is not None and len(s.delen) < s.verwacht:
        ontbreekt.append(f"{label}: nog niet helemaal opgehaald. Volg `vervolg` in het toolresultaat")
        return []
    if s.onderdelen_elders and not s.delen:
        ontbreekt.append(f"{label}: de onderdelen ontbreken. Haal ze op met get_lid")
        return []
    nog_niet = nog_niet or s.nog_niet_in_werking  # een lid erft het van zijn artikel
    uit: list[Bepaling] = []
    if tekst := _tekst(iri, stukken):
        uit.append(Bepaling(tekst=tekst, vindplaats=vindplaats_van(iri), nog_niet_in_werking=nog_niet))
    for lid in (k for k, d in s.delen.items() if d.get("lid")):
        uit += _bepalingen(lid, stukken, ontbreekt, nog_niet)
    if not uit and not ontbreekt:
        ontbreekt.append(f"{label}: geen tekst in het resultaat. Haal de bepaling op met get_artikel of get_lid")
    return uit


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    iris = list(dict.fromkeys(str(i).strip() for i in invoer.get("bepalingen") or [] if str(i).strip()))
    if not iris:
        raise Onvulbaar("Wijs de bepalingen aan met hun iri.")
    stukken, ontbreekt = _stukken(trace), []
    items = [b for iri in iris for b in _bepalingen(iri, stukken, ontbreekt)]
    if ontbreekt:
        raise Onvulbaar("Nog niet compleet, dus er wordt niets getoond. " + "; ".join(ontbreekt) + ". Rond daarna opnieuw af.")
    blokken: list[Any] = [Wettekst(items=items)]
    if toelichting := str(invoer.get("toelichting") or "").strip():
        blokken.append(Toelichting(tekst=toelichting))
    return Antwoord(sjabloon="bepaling", blokken=blokken, doelen=[vindplaats_van(iri) for iri in iris])
