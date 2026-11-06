"""Het sjabloon voor uitleg ("hoe werkt X", "hoe verhoudt Y zich tot Z"): de ene plek waar het model veel schrijft.

Het model schrijft het korte antwoord, de reden per passage en de twijfel, en wijst de passages aan. De code toetst
elke passage tegen de tekst van de aangewezen bepaling, niet tegen alles wat is opgehaald: een echte zin bij het
verkeerde artikel haalt anders de controle en staat er met een onjuiste vindplaats. De tekst die het model schreef
gaat als antwoordtekst door `verify`; aan die controle verandert hier niets.

Wat een vrij antwoord niet kent: de werkplek toont bij een sjabloon met doelen geen bronnenlijst, want de blokken
dragen de vindplaatsen. Een bepaling die de uitleg noemt zonder passage zou dus nergens herleidbaar zijn; die
gaat terug naar het model.
"""
from __future__ import annotations

from typing import Any

from bronmodel.antwoord import Antwoord, Citaat, Citaten, Toelichting, Twijfel

from ..annotatie import _normaliseer, komt_letterlijk_voor
from ..grounding import _bekende_artikelen, herstel_citaten
from ..overzicht import vermeldingen
from .vullen import Onvulbaar, Trace, bron_rijen, vindplaats_van

SCHEMA: dict[str, Any] = {
    "name": "antwoord_duiding",
    "description": (
        "Rond een vraag om uitleg af: hoe iets werkt, hoe bepalingen zich verhouden, wat ze voor een geval betekenen. Roep deze "
        "tool aan nadat je de bepalingen hebt opgehaald, en schrijf geen antwoord ernaast. Jij schrijft de uitleg in eigen woorden "
        "en wijst de passages aan die haar dragen; de werkplek toont die passages met hun vindplaats, uit wat de tools "
        "teruggaven. Vind je geen bepaling die de vraag draagt, gebruik deze tool dan niet en zeg dat in tekst."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "kort_antwoord": {"type": "string", "description": "Het antwoord op de vraag in twee tot vier zinnen, in eigen woorden en zonder citaten."},
            "onderbouwing": {
                "type": "array",
                "description": "De passages die het antwoord dragen, ten minste één. Elke bepaling die je noemt staat hierin.",
                "items": {
                    "type": "object",
                    "properties": {
                        "bepaling": {"type": "string", "description": "De iri van de bepaling uit het toolresultaat."},
                        "fragment": {"type": "string", "description": "Een aaneengesloten stuk uit de tekst van één lid of onderdeel, teken voor teken gekopieerd, zonder weglatingen."},
                        "waarom": {"type": "string", "description": "Eén zin: wat deze passage bijdraagt aan het antwoord."},
                    },
                    "required": ["bepaling", "fragment", "waarom"],
                    "additionalProperties": False,
                },
            },
            "twijfel": {"type": "array", "items": {"type": "string"},
                        "description": "Aannames, interpretatiekeuzes en wat de opgehaalde tekst open laat, elk als één punt. Leeg als die er niet zijn."},
        },
        "required": ["kort_antwoord", "onderbouwing", "twijfel"],
        "additionalProperties": False,
    },
}


def _lex(tekst: Any, trace: Trace) -> str:
    """Tekst van het model. Een bijna-letterlijk citaat erin wordt letterlijk, net als in een vrij antwoord: anders
    kost dat een hele correctieronde. De rest blijft van `verify`."""
    return herstel_citaten(str(tekst or "").strip(), trace)[0]


def _uit_bron(fragment: str, tekst: str) -> str:
    """Het fragment zoals het in deze tekst staat, of leeg. Bijna-letterlijk herstelt `herstel_citaten`; die leest
    aanhalingstekens, dus een fragment dat er zelf een bevat kan alleen letterlijk."""
    if komt_letterlijk_voor(tekst, fragment):
        return _normaliseer(fragment)
    if '"' in fragment:
        return ""
    _, hersteld = herstel_citaten(f'"{fragment}"', [("", tekst)])
    return hersteld[0][1] if hersteld else ""


def _citaat(stuk: dict[str, Any], rijen: dict[str, dict[str, Any]], trace: Trace, fouten: list[str]) -> Citaat | None:
    iri, fragment = str(stuk.get("bepaling") or "").strip(), str(stuk.get("fragment") or "").strip()
    onder = {k: r for k, r in rijen.items() if k == iri or k.startswith(iri + ":")} if iri else {}
    if not onder:
        fouten.append(f"{iri or 'een passage zonder bepaling'}: de tekst is niet (helemaal) opgehaald. Gebruik een iri uit een "
                      "toolresultaat, en haal de bepaling op met get_artikel, get_lid of get_bepaling")
        return None
    treffers = {k: t for k, r in onder.items() if (t := _uit_bron(fragment, r["tekst"]))}
    if not treffers:
        begin = fragment[:80] + ("…" if len(fragment) > 80 else "")
        fouten.append(f"„{begin}” staat niet in {vindplaats_van(iri).label}. Kopieer een aaneengesloten stuk uit één lid of "
                      "onderdeel, teken voor teken en zonder weglatingen, en wijs de bepaling aan waar het staat")
        return None
    # De vindplaats is de diepste node met deze tekst. Staat de passage in meer leden, dan klopt alleen wat het model aanwees.
    diepste = [k for k in treffers if not any(a.startswith(k + ":") for a in treffers)]
    plek = diepste[0] if len(diepste) == 1 else iri
    rij = rijen.get(plek, {})
    return Citaat(tekst=treffers[diepste[0]], waarom=_lex(stuk.get("waarom"), trace),
                  vindplaats=vindplaats_van(plek, jci=rij.get("jci", ""), regeling=rij.get("citeertitel", ""),
                                            label=rij.get("inLabel") or rij.get("label", "")))


def _niet_onderbouwd(uitleg: str, citaten: list[Citaat]) -> list[str]:
    """De artikelen die de uitleg noemt en die geen enkele passage draagt of vermeldt."""
    bekend = _bekende_artikelen([("", f"{c.vindplaats.iri} {c.vindplaats.label} {c.tekst}") for c in citaten])
    return [v for v in vermeldingen(uitleg) if v.startswith("artikel ") and v.removeprefix("artikel ").casefold() not in bekend]


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    kort = _lex(invoer.get("kort_antwoord"), trace)
    if not kort:
        raise Onvulbaar("Schrijf het korte antwoord.")
    stukken = invoer.get("onderbouwing") or []
    if not stukken:
        raise Onvulbaar("Wijs ten minste één passage aan. Vond je geen bepaling die de vraag draagt, zeg dat dan in tekst.")
    rijen, fouten = bron_rijen(trace), []
    citaten = [c for stuk in stukken if (c := _citaat(stuk, rijen, trace, fouten))]
    if fouten:
        raise Onvulbaar("Niet te tonen, dus er wordt niets getoond. " + "; ".join(fouten) + ". Rond daarna opnieuw af.")
    twijfel = list(dict.fromkeys(t for x in invoer.get("twijfel") or [] if (t := _lex(x, trace))))
    if los := _niet_onderbouwd("\n".join([kort, *(c.waarom for c in citaten), *twijfel]), citaten):
        raise Onvulbaar(f"Je noemt {', '.join(los)} zonder passage, dus de jurist kan het niet naslaan. Wijs er een passage uit "
                        "aan, en haal de bepaling zo nodig op, of laat de vermelding weg. Rond daarna opnieuw af.")
    blokken: list[Any] = [Toelichting(kop="Kort antwoord", tekst=kort), Citaten(items=citaten)]
    if twijfel:
        blokken.append(Twijfel(punten=twijfel))
    return Antwoord(sjabloon="duiding", blokken=blokken, doelen=list({c.vindplaats.iri: c.vindplaats for c in citaten}.values()))
