"""Het sjabloon voor een begripsvraag: wat de wet zegt en wat juristen vastlegden, los van elkaar.

Een vastgelegd begrip is een analyse-uitkomst met een status, geen wettelijke definitie. Daarom twee blokken,
en een leemte als de wet niets zegt. "In de graaf bij deze term": dat de graaf niets vond, zegt niet dat de wet
niets zegt.

Twee vormen. Met een `begrip` gaat het om één term en is `zoek_definitie` op die term verplicht: het resultaat
draagt de gezochte term, dus een zoekactie uit een eerdere beurt of op een andere term telt niet. Zonder `begrip`
is het de leesroute: wat `search_begrippen` vond, zonder enige uitspraak over de wet.
"""
from __future__ import annotations

from typing import Any

import re

from bronmodel.antwoord import (Antwoord, Begrippen, Bepaling, Definitie, Definities, Leemte, Toelichting, VastgelegdBegrip,
                                Wettekst)
from bronmodel.definities import Geldigheid, geldigheid_uit, losse_termen, term_vindplaats

from ..tools.begrip_tools import (BEGRIPPEN_NIET_GEZOCHT, BEGRIPPEN_ONVOLLEDIG, begrippen_stand, met_deze_naam, normaal,
                                  zelfde_term)
from .vullen import Onvulbaar, Trace, resultaten, rijen, vindplaats_van, volledige_tekst

SCHEMA: dict[str, Any] = {
    "name": "antwoord_begrip",
    "description": (
        "Rond een vraag naar de betekenis van een begrip, of naar wat juristen als begrip vastlegden, af. Roep deze tool aan "
        "nadat je zoek_definitie hebt gebruikt, en schrijf geen antwoord ernaast. De vastgelegde begrippen bij de term zoekt de code zelf. De werkplek toont "
        "de wettelijke definities met hun vindplaats en de vastgelegde begrippen zelf, uit wat de tools teruggaven: herhaal die "
        "niet. Jij levert het begrip en een korte toelichting in eigen woorden, zonder citaten en zonder vindplaatsen die je "
        "niet hebt opgehaald. Vond je geen definitie, schrijf dan nooit dat er geen definitie bestaat: dat de graaf niets vond "
        "zegt de werkplek zelf, in die woorden, en een gelezen bepaling die de term gebruikt toont ze zelf, met de vindplaats. "
        "Zeg dan in de toelichting alleen wat die bepaling of het vastgelegde begrip zegt, of laat haar leeg; uitleg uit "
        "eigen kennis hoort er niet in. Zet er geen tegenstelling of uitzondering in ('niet wie …', 'ongeacht …', 'behalve "
        "…') die de getoonde tekst niet zelf maakt: dat is een interpretatie, en de werkplek markeert zo'n zin. Gaat de vraag alleen over wat er is vastgelegd, laat begrip dan leeg: de werkplek toont dan wat "
        "search_begrippen vond en zegt niets over de wet."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "begrip": {"type": "string", "description": "De term waarnaar gevraagd is, zoals de wet hem schrijft. Leeg als de vraag alleen gaat over wat er is vastgelegd."},
            "toelichting": {"type": "string", "description": "Twee of drie zinnen over wat de getoonde wettekst zegt, in eigen woorden. Over vastgelegde begrippen alleen wat je zelf met search_begrippen las (zoals de opvolger van een vervangen begrip): wat de code erbij zoekt, zie jij niet. Leeg als er niets te zeggen valt."},
        },
        "required": ["begrip", "toelichting"],
        "additionalProperties": False,
    },
}


def _zelfde_term(a: str, b: str) -> bool:
    """Dezelfde term, ook in het meervoud (`begrip_tools.zelfde_term`, dezelfde maat als de telling van de zoektool).
    `zoek_definitie` zoekt op een deel van het woord, dus "aanslag" levert ook "belastingaanslag": die hoort hier niet."""
    return zelfde_term(a, b)


def _bereik(rij: dict[str, Any], tekst: str, trace: Trace) -> Geldigheid:
    """De geldingsformule. De aanhef eerst, zoals de api (`samenhang_antwoord._aanhef_en_geldigheid`): daar staat ze, en
    in de definitie zelf kan "deze wet" over iets anders gaan. Naast de rij uit de tool ook wat er verder is opgehaald."""
    houders, plek = [rij.get("aanhef", "")], rij.get("node", "")
    while ":o:" in plek:
        plek = plek.rsplit(":o:", 1)[0]
        houders.append(volledige_tekst(plek, trace))
    return next((g for t in (*houders, tekst) if (g := geldigheid_uit(t)).formule), Geldigheid(""))


def _houder(node: str) -> str:
    """De bepaling waarin een definitie staat: het lid boven een onderdeel, het artikel boven een lid. Leeg bij een
    definitie die een heel artikel is (daarboven staat geen definitieartikel)."""
    for scheiding in (":o:", ":lid:"):
        if scheiding in node:
            return node.rsplit(scheiding, 1)[0]
    return ""


#: Zoveel begrippen uit hetzelfde definitieartikel toont een definitie hoogstens bij zich.
MAX_GEBRUIKT = 5


def _rij_tekst(rij: dict[str, Any], trace: Trace) -> str:
    return rij.get("tekst", "") if rij.get("tekst_volledig") is not False else volledige_tekst(rij.get("node", ""), trace)


def _gebruikt(node: str, tekst: str, term: str, trace: Trace) -> list[Definitie]:
    """De begrippen die deze definitie zelf gebruikt en die in dezelfde bepaling gedefinieerd zijn (`zoek_definitie`
    met `binnen`, gezocht door `vooraf`): "belastingschuldige: degene te wiens naam de belastingaanslag is gesteld" rust op
    "belastingaanslag" (IW 1990 art. 2 lid 1 onder m), en die definitie zegt welke aanslagen dat zijn (acceptatie
    19 nov 2026). Op woordgrens, zonder de term zelf; een gebruikt begrip zonder volledige tekst valt weg."""
    houder = _houder(node)
    if not houder:
        return []
    romp = tekst.split(":", 1)[1] if ":" in tekst else tekst
    eigen = {t.casefold() for t in losse_termen(term)}
    uit: dict[str, Definitie] = {}
    for data in resultaten(trace, ["zoek_definitie"]):
        if data.get("binnen") != houder:
            continue
        for rij in data.get("resultaten") or []:
            andere, ruw = rij.get("node", ""), rij.get("begrip", "")
            termen = [t for t in losse_termen(ruw) if t.casefold() not in eigen]
            if not andere or andere == node or andere in uit or not any(term_vindplaats(t, romp) for t in termen):
                continue
            if (gebruikte := _rij_tekst(rij, trace)):
                uit[andere] = Definitie(term=ruw, tekst=gebruikte, vindplaats=vindplaats_van(
                    andere, jci=rij.get("jci", ""), regeling=rij.get("citeertitel", ""), label=rij.get("inLabel", "")))
    return list(uit.values())[:MAX_GEBRUIKT]


def _definities(begrip: str, trace: Trace) -> list[Definitie]:
    uit: dict[str, Definitie] = {}
    for rij in rijen(trace, ["zoek_definitie"]):
        node, ruw = rij.get("node", ""), rij.get("begrip", "")
        if not node or node in uit or not any(_zelfde_term(begrip, t) for t in losse_termen(ruw)):
            continue
        tekst = _rij_tekst(rij, trace)
        if not tekst:
            raise Onvulbaar(f"De tekst van {node} is niet volledig opgehaald. Haal de bepaling op met get_lid en rond dan af.")
        g = _bereik(rij, tekst, trace)
        uit[node] = Definitie(term=ruw, tekst=tekst, bereik=g.formule, bereik_soort=g.soort, bereik_waarde=g.waarde,
                              gebruikt=_gebruikt(node, tekst, ruw, trace),
                              vindplaats=vindplaats_van(node, jci=rij.get("jci", ""), regeling=rij.get("citeertitel", ""), label=rij.get("inLabel", "")))
    return list(uit.values())


def _vastgelegd(begrip: str, trace: Trace) -> list[VastgelegdBegrip]:
    uit: dict[str, VastgelegdBegrip] = {}
    # Zonder term geldt de laatste zoekopdracht: de zoekterm zat daar al in, een rij kan op zijn definitie gevonden zijn,
    # en een eerdere, ruimere zoekopdracht hoort niet meer bij de vraag.
    laatste = list(resultaten(trace, ["search_begrippen"]))[-1:]
    gevonden = rijen(trace, ["search_begrippen"]) if begrip else [r for d in laatste for r in d.get("resultaten") or []]
    for rij in gevonden:
        # Een begrip rust altijd op een annotatie: zonder dragende passage is het geen vastgelegd begrip (een wees van
        # een gewist werkgebied, acceptatie 19 nov 2026; de graafcontrole van de api meldt het). Een vervangen begrip is
        # historie en heeft zijn passages aan zijn opvolger gegeven.
        if rij.get("status") != "vervangen" and rij.get("aantal_dragend") == 0:
            continue
        if rij.get("id") and (not begrip or met_deze_naam(begrip, rij)):
            uit[rij["id"]] = VastgelegdBegrip(
                id=rij["id"], naam=rij.get("naam", ""), status=rij.get("status", ""), definitie=rij.get("definitie", ""),
                werkgebied=rij.get("werkgebied", ""), werkgebied_id=rij.get("werkgebied_id", ""), herbeoordelen=bool(rij.get("herbeoordelen")),
                generiek=bool(rij.get("generiek")))
    # `get_begrip` draagt de hele definitie; de zoekrij een ingekorte.
    for data in resultaten(trace, ["get_begrip"]):
        if (b := uit.get(data.get("id", ""))) and data.get("definitie"):
            b.definitie = data["definitie"]
    return list(uit.values())


#: Zoveel gelezen bepalingen die de term gebruiken, toont een begripsantwoord zonder definitie hoogstens.
MAX_GEBRUIK = 3


def _gebruik(begrip: str, trace: Trace) -> list[Bepaling]:
    """De bepalingen die deze beurt las (`get_artikel`, `get_lid`, `get_bepaling`) en die de term in hun tekst gebruiken.

    Zonder wettelijke definitie zei het antwoord alleen "Geen wettelijke definitie in de graaf", en de toelichting van
    het model deed de rest: een gelezen bepaling die de term wél gebruikte (Leidraad 14.4.1 bij "derdenbeslag") stond er
    niet in, en wat het model erbij zei kwam deels uit eigen kennis (acceptatie 19 nov 2026). Nu toont de code die tekst
    zelf, met de vindplaats, zoals bij een definitie. Alleen een bepaling die compleet gelezen is (`bepaling._bepalingen`
    zonder melding); een deel onder een andere gevonden bepaling niet nog eens."""
    from .bepaling import _bepalingen, _stukken, _tekst
    from .vullen import toestanden

    term = re.compile(rf"(?<!\w){re.escape(begrip.strip())}", re.IGNORECASE)
    stukken, staarten = _stukken(trace), toestanden(trace)
    gevonden = [iri for iri in stukken if term.search(_tekst(iri, stukken))]
    boven = [iri for iri in gevonden if not any(iri != o and iri.startswith(o + ":") for o in gevonden)]
    uit: dict[str, Bepaling] = {}
    for iri in boven:
        ontbreekt: list[str] = []
        items = _bepalingen(iri, stukken, ontbreekt, staarten)
        if ontbreekt:
            continue
        for b in items:
            if term.search(b.tekst):
                uit.setdefault(b.vindplaats.iri, b)
    return list(uit.values())[:MAX_GEBRUIK]


def _gezocht(begrip: str, trace: Trace) -> list[dict[str, Any]]:
    """De zoekacties die deze term dekken. `zoek_definitie` zoekt op een deel van het woord, dus "aanslag" dekt ook
    "belastingaanslag", maar niet andersom."""
    return [d for d in resultaten(trace, ["zoek_definitie"])
            if not d.get("binnen") and (t := str(d.get("term") or "")) and (normaal(t) in normaal(begrip) or _zelfde_term(begrip, t))]


def _toelichting(invoer: dict[str, Any]) -> list[Toelichting]:
    tekst = str(invoer.get("toelichting") or "").strip()
    return [Toelichting(tekst=tekst)] if tekst else []


def _alleen_vastgelegd(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    """De leesroute. Is er een storing of niets gevonden, dan spreekt de code en vervalt de toelichting: die zou de
    leegte zelf kunnen duiden, en "er zijn geen begrippen" is niet bewezen."""
    melding, onvolledig = begrippen_stand(trace)
    if melding == BEGRIPPEN_NIET_GEZOCHT:
        raise Onvulbaar("Zoek eerst met search_begrippen, of noem het begrip.")
    if melding:
        return Antwoord(sjabloon="begrip", blokken=[Leemte(tekst=melding)])
    vastgelegd = _vastgelegd("", trace)
    if not vastgelegd:  # een eerdere zoekopdracht vond wel iets, of de laatste is onvolledig en leeg
        laatste = list(resultaten(trace, ["search_begrippen"]))[-1:]
        return Antwoord(sjabloon="begrip", blokken=[Leemte(tekst=(laatste[0].get("geen_treffers") if laatste else "") or BEGRIPPEN_ONVOLLEDIG)])
    return Antwoord(sjabloon="begrip", blokken=[Begrippen(items=vastgelegd), *([Leemte(tekst=BEGRIPPEN_ONVOLLEDIG)] if onvolledig else []),
                                                *_toelichting(invoer)])


def vooraf(invoer: dict[str, Any], trace: Trace) -> list[dict[str, Any]]:
    """Wat de code zelf opzoekt vóór het vullen (`Sjabloon.vooraf`).

    - Wat juristen als begrip vastlegden, ook een generiek begrip (ADR-006). Dat hangt niet af van of het model, of zijn
      profiel, `search_begrippen` kent: is er in de trace niet op deze term gezocht, dan zoekt de code het zelf.
    - De andere definities in de bepaling van een gevonden definitie (`zoek_definitie` met `binnen`): een definitie die
      zelf een gedefinieerd begrip gebruikt, toont dat erbij (`_gebruikt`)."""
    begrip = str(invoer.get("begrip") or "").strip()
    if not begrip:
        return []
    aanroepen: list[dict[str, Any]] = []
    if not _vastgelegd(begrip, trace) and not any(_zelfde_term(begrip, str(d.get("zoekterm") or ""))
                                                  for d in resultaten(trace, ["search_begrippen"])):
        aanroepen.append({"name": "search_begrippen", "input": {"zoekterm": begrip}})
    al = {str(d.get("binnen")) for d in resultaten(trace, ["zoek_definitie"]) if d.get("binnen")}
    houders = {h for rij in rijen(trace, ["zoek_definitie"])
               if any(_zelfde_term(begrip, t) for t in losse_termen(rij.get("begrip", "")))
               and (h := _houder(rij.get("node", ""))) and h not in al}
    aanroepen += [{"name": "zoek_definitie", "input": {"term": "", "binnen": h, "limit": 100}} for h in sorted(houders)]
    return aanroepen


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    begrip = str(invoer.get("begrip") or "").strip()
    if not begrip:
        return _alleen_vastgelegd(invoer, trace)
    gezocht = _gezocht(begrip, trace)
    if not gezocht:
        raise Onvulbaar(f"Zoek eerst de wettelijke definitie van “{begrip}” met zoek_definitie. Gaat de vraag alleen over wat "
                        "juristen vastlegden, laat begrip dan leeg.")
    definities = _definities(begrip, trace)
    onvolledig = gezocht[-1].get("volledig") is False
    if onvolledig and not definities:
        raise Onvulbaar(f"Er zijn nog meer treffers voor “{begrip}”, dus de definitie kan er nog tussen zitten. Volg `vervolg` in het toolresultaat.")
    plek = "in de graaf" if any(not d.get("bwb_id") for d in gezocht) else "in de gezochte regeling"
    gebruik = [] if definities else _gebruik(begrip, trace)
    leemte = f"Geen wettelijke definitie {plek} bij de term “{begrip}”."
    if gebruik:
        leemte += (" De gelezen bepaling hieronder gebruikt de term wel." if len(gebruik) == 1
                   else " De gelezen bepalingen hieronder gebruiken de term wel.")
    blokken: list[Any] = [Definities(items=definities) if definities else Leemte(tekst=leemte),
                          *([Wettekst(items=gebruik)] if gebruik else [])]
    if onvolledig:
        blokken.append(Leemte(tekst="Er kunnen meer wettelijke definities zijn: de zoekuitkomst is onvolledig."))
    if vastgelegd := _vastgelegd(begrip, trace):
        blokken.append(Begrippen(items=vastgelegd))
    # Wie de vastgelegde begrippen niet kon lezen, zwijgt daar niet over: geen blok zou klinken als geen begrip.
    melding, begrippen_onvolledig = begrippen_stand(trace)
    if melding and melding != BEGRIPPEN_NIET_GEZOCHT and not any(True for _ in resultaten(trace, ["search_begrippen"])):
        blokken.append(Leemte(tekst=melding))
    elif begrippen_onvolledig:
        blokken.append(Leemte(tekst=BEGRIPPEN_ONVOLLEDIG))
    return Antwoord(sjabloon="begrip", blokken=[*blokken, *_toelichting(invoer)], doelen=[v for d in definities for v in (d.vindplaats, *(g.vindplaats for g in d.gebruikt))])
