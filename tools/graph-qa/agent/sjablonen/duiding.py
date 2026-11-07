"""Het sjabloon voor uitleg ("hoe werkt X", "hoe verhoudt Y zich tot Z"): de ene plek waar het model veel schrijft.

Het model schrijft het korte antwoord, de reden per passage en de twijfel, en wijst de passages aan: per passage de
bepaling en de eerste en laatste woorden. De tekst ertussen neemt de code uit de bron (D5, ADR-010). Het model schreef
eerst elk citaat voluit, teken voor teken: dat was de meeste uitvoer van een duidingsbeurt, en een citaat dat net niet
klopte kostte een hele correctieronde. De code toetst
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
from bronmodel.vindplaats import vindplaats

from ..annotatie import _normaliseer, komt_letterlijk_voor
from ..grounding import _bekende_artikelen, herstel_citaten
from ..overzicht import vermeldingen
from .vullen import Onvulbaar, Trace, artikel_in_trace, bron_rijen, iri_van_jci, ouders, vindplaats_van

SCHEMA: dict[str, Any] = {
    "name": "antwoord_duiding",
    "description": (
        "Rond een vraag om uitleg af: hoe iets werkt, hoe bepalingen zich verhouden, wat ze voor een geval betekenen. Roep deze "
        "tool aan nadat je de bepalingen hebt opgehaald, en schrijf geen antwoord ernaast. Jij schrijft de uitleg in eigen woorden "
        "en wijst de passages aan die haar dragen, met hun eerste en laatste woorden: schrijf het citaat niet uit, de code neemt "
        "de tekst ertussen uit wat de tools teruggaven en de werkplek toont hem met zijn vindplaats. Vind je geen bepaling die de vraag draagt, gebruik deze tool dan niet en zeg dat in tekst."),
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
                        "van": {"type": "string", "description": "De eerste drie tot acht woorden van de passage, letterlijk uit de tekst van één lid of onderdeel. Leeg: vanaf het begin van die tekst."},
                        "tot": {"type": "string", "description": "De laatste drie tot acht woorden van de passage, letterlijk, in dezelfde tekst na `van`. Leeg: tot het eind van die tekst."},
                        "waarom": {"type": "string", "description": "Eén zin: wat deze passage bijdraagt aan het antwoord."},
                    },
                    "required": ["bepaling", "van", "tot", "waarom"],
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


#: Zo lang mag een passage zonder `van` en `tot` zijn: een heel lid of onderdeel. Daarboven wijst het model een stuk aan.
MAX_HELE_TEKST = 600


# Typografische tekens die het model als hun gewone vorm schrijft: de wet heeft "personenauto’s", het model
# "personenauto's" (Iw 9 lid 8, vier weigeringen in de eval van 7 nov 2026). Eén teken voor één teken, dus een plek in de
# zoekvorm is dezelfde plek in de brontekst: de jurist ziet de bron, niet de zoekvorm.
_ZOEKVORM = str.maketrans({"’": "'", "‘": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "„": '"', "‟": '"',
                           "–": "-", "—": "-", "‑": "-", "\u00a0": " "})


def _ankers(anker: str, tekst: str) -> list[tuple[int, int]]:
    """Waar het anker in de (genormaliseerde) tekst staat, als (begin, eind). Gezocht wordt in de zoekvorm (`_ZOEKVORM`).
    Bijna-letterlijk herstelt `herstel_citaten`; die leest aanhalingstekens, dus een anker dat er zelf een bevat kan alleen
    letterlijk."""
    tekst, vorm = tekst.translate(_ZOEKVORM), _normaliseer(anker).translate(_ZOEKVORM)
    if not komt_letterlijk_voor(tekst, vorm) and '"' not in vorm:
        _, hersteld = herstel_citaten(f'"{vorm}"', [("", tekst)])
        vorm = hersteld[0][1] if hersteld else ""
    uit, i = [], tekst.find(vorm) if vorm else -1
    while i >= 0:
        uit.append((i, i + len(vorm)))
        i = tekst.find(vorm, i + 1)
    return uit


def _passage(van: str, tot: str, tekst: str) -> str:
    """De passage van `van` tot en met `tot`, zoals ze in deze tekst staat, of leeg. Staat `van` er vaker, dan telt de
    eerste plek waarna `tot` volgt."""
    tekst = _normaliseer(tekst)
    if not van and not tot:
        return tekst if len(tekst) <= MAX_HELE_TEKST else ""
    begins = _ankers(van, tekst) if van else [(0, 0)]
    for begin, _ in begins:
        if not tot:
            return tekst[begin:]
        eind = next((e for b, e in _ankers(tot, tekst) if b >= begin), None)
        if eind is not None:
            return tekst[begin:eind]
    return ""


def _binnen(node: str, iri: str) -> bool:
    return bool(node) and (node == iri or node.startswith(iri + ":"))


def _citaat(stuk: dict[str, Any], rijen: dict[str, dict[str, Any]], trace: Trace, fouten: list[str]) -> Citaat | None:
    iri = str(stuk.get("bepaling") or "").strip()
    if iri.startswith("jci"):
        # Eerst de rij die deze jci draagt; draagt geen rij hem (de leden van `get_artikel` hebben vaak geen eigen jci,
        # eval 7 nov 2026), dan het graafadres uit de jci zelf, met dezelfde regels als de importer.
        vp = vindplaats(iri)
        iri = (jcis := iri_van_jci(trace)).get(iri) or jcis.get(iri.split("&z=", 1)[0]) or (vp.bron_iri if vp else iri)
    van, tot = str(stuk.get("van") or "").strip(), str(stuk.get("tot") or "").strip()
    # Per rij de plek die de jurist ziet: de rij zelf, of het lid van een slotzin met een eigen `:id:`-iri.
    lid_van = ouders(trace)
    onder = {k: (k if _binnen(k, iri) else lid_van[k], r) for k, r in rijen.items()
             if _binnen(k, iri) or _binnen(lid_van.get(k, ""), iri)} if iri else {}
    if not onder:
        fouten.append(f"{iri or 'een passage zonder bepaling'}: de tekst is niet (helemaal) opgehaald. Gebruik een iri uit een "
                      "toolresultaat, en haal de bepaling op met get_artikel, get_lid of get_bepaling")
        return None
    treffers = {k: (plek, t) for k, (plek, r) in onder.items() if (t := _passage(van, tot, r["tekst"]))}
    if not treffers:
        if not van and not tot:
            fouten.append(f"{vindplaats_van(iri).label} is te lang om heel te tonen. Wijs met `van` en `tot` de passage aan "
                          "die de uitleg draagt")
        else:
            aangewezen = " … ".join(_kort(x) for x in (van, tot) if x)
            fouten.append(f"„{aangewezen}” staat niet in {vindplaats_van(iri).label}. Geef de eerste en de laatste woorden van "
                          "een passage uit één lid of onderdeel, letterlijk, en wijs de bepaling aan waar ze staan")
        return None
    # De vindplaats is de diepste node met deze tekst. Staat de passage in meer leden, dan klopt alleen wat het model aanwees.
    plekken = {plek for plek, _ in treffers.values()}
    diepste = [p for p in plekken if not any(a.startswith(p + ":") for a in plekken)]
    plek = diepste[0] if len(diepste) == 1 else iri
    tekst = next(t for p, t in treffers.values() if p in diepste)
    rij = rijen.get(plek, {})
    return Citaat(tekst=tekst, waarom=_lex(stuk.get("waarom"), trace),
                  vindplaats=vindplaats_van(plek, jci=rij.get("jci", ""), regeling=rij.get("citeertitel", ""),
                                            label=rij.get("inLabel") or rij.get("label", "")))


def _kort(tekst: str) -> str:
    return tekst[:60] + ("…" if len(tekst) > 60 else "")


def _niet_onderbouwd(uitleg: str, citaten: list[Citaat]) -> list[str]:
    """De artikelen die de uitleg noemt en die geen enkele passage draagt of vermeldt."""
    bekend = _bekende_artikelen([("", f"{c.vindplaats.iri} {c.vindplaats.label} {c.tekst}") for c in citaten])
    return [v for v in vermeldingen(uitleg) if v.startswith("artikel ") and v.removeprefix("artikel ").casefold() not in bekend]


#: Zoveel artikelen haalt de code in één weigering zelf op; de rest moet het model ophalen of weglaten.
MAX_OPHALEN = 2


def _genoemd_is_gelezen(los: list[str], rijen: dict[str, dict[str, Any]], trace: Trace) -> Onvulbaar:
    """Wat het antwoord noemt, moet gelezen zijn (D, besluit gebruiker 7 nov 2026). Per artikel zonder passage:

    - de tekst is opgehaald maar niet aangewezen: wijs een passage aan of laat het weg;
    - de opgehaalde resultaten wijzen het aan zonder tekst (een verwijzing in `get_context`): de code haalt het op, en
      het model kiest daarna een passage of laat het weg;
    - het staat nergens in wat er is opgehaald: dan komt het uit het geheugen van het model. Ophalen of weglaten.

    Een markering "niet opgehaald" bestaat niet: een artikel staat in beeld met een passage, of niet."""
    gelezen, ophalen, onbekend = [], [], []
    for vermelding in los:
        nummer = vermelding.removeprefix("artikel ")
        iri = artikel_in_trace(nummer, trace)
        if iri and any(_binnen(k, iri) for k in rijen):
            gelezen.append(vermelding)
        elif iri and len(ophalen) < MAX_OPHALEN:
            ophalen.append({"bwb_id": iri.split(":")[2], "artikel": nummer, "vermelding": vermelding})
        else:
            onbekend.append(vermelding)
    zinnen = []
    if gelezen:
        zinnen.append(f"Je noemt {', '.join(gelezen)} zonder passage, terwijl de tekst al is opgehaald. Wijs er een passage uit "
                      "aan, of laat de vermelding weg.")
    if ophalen:
        zinnen.append(f"Je noemt {', '.join(o['vermelding'] for o in ophalen)} zonder passage. Wat je noemt, moet gelezen zijn: "
                      "de tekst staat hieronder. Wijs er een passage uit aan met `bepaling`, `van` en `tot`, of laat de "
                      "vermelding weg als het artikel er na lezing niet toe doet.")
    if onbekend:
        zinnen.append(f"Je noemt {', '.join(onbekend)} zonder passage, en de tekst daarvan heb je niet opgehaald. Haal het op "
                      "met get_artikel als het ertoe doet en wijs dan een passage aan, of laat de vermelding weg.")
    return Onvulbaar(" ".join([*zinnen, "Rond daarna opnieuw af."]),
                     ophalen=[{"bwb_id": o["bwb_id"], "artikel": o["artikel"]} for o in ophalen])


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
        raise _genoemd_is_gelezen(los, rijen, trace)
    blokken: list[Any] = [Toelichting(kop="Kort antwoord", tekst=kort), Citaten(items=citaten)]
    if twijfel:
        blokken.append(Twijfel(punten=twijfel))
    return Antwoord(sjabloon="duiding", blokken=blokken, doelen=list({c.vindplaats.iri: c.vindplaats for c in citaten}.values()))
