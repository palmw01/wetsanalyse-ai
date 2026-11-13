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

from ..annotatie import TYPOGRAFISCH, _normaliseer, komt_letterlijk_voor
from ..grounding import _bekende_artikelen, herstel_citaten
from ..overzicht import vermeldingen
from .vullen import Onvulbaar, Trace, artikel_in_trace, bron_rijen, iri_van_jci, met_toestand, ouders, toestanden, vindplaats_van

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


def _ankers(anker: str, tekst: str) -> list[tuple[int, int]]:
    """Waar het anker in de (genormaliseerde) tekst staat, als (begin, eind). Gezocht wordt in de zoekvorm (`TYPOGRAFISCH`).
    Bijna-letterlijk herstelt `herstel_citaten`; die leest aanhalingstekens, dus een anker dat er zelf een bevat kan alleen
    letterlijk."""
    tekst, vorm = tekst.translate(TYPOGRAFISCH), _normaliseer(anker).translate(TYPOGRAFISCH)
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
        if live := _live_van(str(stuk.get("bepaling") or ""), trace):
            # Wettekst van overheid.nl is gelezen, maar hoort in 'extern'. "Haal de bepaling op met get_artikel" liet het
            # model dezelfde tekst opnieuw lezen en het antwoord opnieuw schrijven (ronde 3, I13 en I28: 9 en 18 rondes).
            fouten.append(f"{stuk.get('bepaling')} is wettekst van overheid.nl, en die staat al in het gesprek: wijs haar "
                          f"niet in 'onderbouwing' aan maar in 'extern', met het id ({', '.join(live)}) en de "
                          "alineanummers. Lees haar niet opnieuw")
            return None
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
            fouten.append(f"„{aangewezen}” staat niet in {vindplaats_van(iri).label}. "
                          + _waar_wel(van, tot, onder, rijen) + " Geef de eerste en de laatste woorden van een passage uit "
                          "één lid of onderdeel, letterlijk, en wijs de bepaling aan waar ze staan")
        return None
    # De vindplaats is de diepste node met deze tekst. Staat de passage in meer leden, dan klopt alleen wat het model aanwees.
    plekken = {plek for plek, _ in treffers.values()}
    diepste = [p for p in plekken if not any(a.startswith(p + ":") for a in plekken)]
    plek = diepste[0] if len(diepste) == 1 else iri
    tekst = next(t for p, t in treffers.values() if p in diepste)
    rij = rijen.get(plek, {})
    return Citaat(tekst=tekst, waarom=_lex(stuk.get("waarom"), trace),
                  vindplaats=vindplaats_van(plek, jci=met_toestand(rij.get("jci", ""), toestanden(trace)), regeling=rij.get("citeertitel", ""),
                                            label=rij.get("inLabel") or rij.get("label", "")))


def _waar_wel(van: str, tot: str, onder: dict[str, tuple[str, dict[str, Any]]], rijen: dict[str, dict[str, Any]]) -> str:
    """Wat de weigering erbij zegt om de tweede poging te laten slagen (wetgeving_live ronde 6, I28 en L-R1: twee weigeringen
    van een passage, daarna tekst zonder de vorm van de duiding): waar `van` en `tot` wél staan, of hoe de aangewezen
    tekst begint. Alleen wat in de opgehaalde rijen staat, nooit een raad."""
    def staat(anker: str, tekst: str) -> bool:
        return bool(anker) and bool(_ankers(anker, _normaliseer(tekst)))

    eigen = [(k, r) for k, (_, r) in onder.items()]
    if van and any(staat(van, r["tekst"]) for _, r in eigen):
        plek = next(k for k, r in eigen if staat(van, r["tekst"]))
        if tot and staat(tot, rijen[plek]["tekst"]):
            return (f"„{_kort(van)}” en „{_kort(tot)}” staan allebei in {vindplaats_van(plek).label}, maar „{_kort(tot)}” "
                    "niet ná „" + _kort(van) + "”: draai ze om of kies het einde uit dezelfde zin.")
        return (f"„{_kort(van)}” staat in {vindplaats_van(plek).label}, „{_kort(tot)}” daar niet: kies het einde uit "
                "hetzelfde lid of onderdeel.")
    elders = [k for k, r in rijen.items() if k not in onder and van and staat(van, r.get("tekst", ""))]
    if len(elders) == 1:
        return f"„{_kort(van)}” staat wel in {vindplaats_van(elders[0]).label} ({elders[0]}): wijs die bepaling aan."
    begin = [f"{vindplaats_van(k).label}: „{_kort(_normaliseer(r['tekst']))}”" for k, r in eigen[:3]]
    return ("Zo begint de tekst die je aanwees: " + "; ".join(begin) + ".") if begin else ""


def _live_van(bepaling: str, trace: Trace) -> list[str]:
    """De gelezen stukken van overheid.nl (`get_wettekst`) van dezelfde regeling als `bepaling` (een stuk-id, jci of iri),
    of leeg: daarmee wijst de weigering naar 'extern' in plaats van naar get_artikel."""
    import re as _re

    bwb = _re.search(r"BWB[RV]\d{7}", bepaling)
    if not bwb:
        return []
    return sorted(i for i in live_stukken(trace) if bwb.group(0) in i)[:6]


def _kort(tekst: str) -> str:
    return tekst[:60] + ("…" if len(tekst) > 60 else "")


def live_artikelen(trace: Trace) -> dict[str, tuple[str, ...]]:
    """De artikelen die in dit gesprek met `get_wettekst` (wettekst van overheid.nl) gelezen zijn: hun nummer ("9", en bij
    een boek van het BW ook "2:9") naar de ids van de stukken. Eén artikel kan meer stukken hebben: het hele artikel, of
    elk apart gelezen lid (`…:artikel:9:lid:2`)."""
    import json
    import re as _re

    uit: dict[str, tuple[str, ...]] = {}
    for naam, tekst in trace:
        if naam != "get_wettekst":
            continue
        try:
            stuk = json.loads(tekst).get("stuk") or {}
        except (ValueError, AttributeError):
            continue
        ident = str(stuk.get("id") or "")
        if not (m := _re.search(r":artikel:([^:]+)(?::lid:[^:]+)?(?::o:[^:]+)?$", ident)):
            continue
        nummers = [m.group(1).casefold()]
        if boek := _re.search(r"\bBoek\s+(\d+)\b", str(stuk.get("label") or "")):
            nummers.append(f"{boek.group(1)}:{nummers[0]}")
        for nummer in nummers:
            if ident not in uit.get(nummer, ()):
                uit[nummer] = (*uit.get(nummer, ()), ident)
    return uit


def live_stukken(trace: Trace) -> set[str]:
    """De ids van alle stukken die in dit gesprek met `get_wettekst` (wettekst van overheid.nl) gelezen zijn: een
    artikel, een lid, of een paragraaf van een beleidsregel (`…:id:…`)."""
    import json

    uit: set[str] = set()
    for naam, tekst in trace:
        if naam != "get_wettekst":
            continue
        try:
            ident = str((json.loads(tekst).get("stuk") or {}).get("id") or "")
        except (ValueError, AttributeError):
            continue
        if ident:
            uit.add(ident)
    return uit


def live_opbouw(trace: Trace) -> set[str]:
    """De artikelnummers die de opbouw van een regeling van overheid.nl in dit gesprek noemt (`zoek_artikelen`: de rijen
    en per deel het eerste en laatste artikel). Daarmee noemt de uitleg de indeling van de regeling uit de bron ("hoofdstuk
    3, artikel 3.1 tot en met 3.157"); wat een artikel inhoudelijk zegt, vraagt nog steeds een gelezen passage. Zonder
    dit weigerde het sjabloon vier keer het overzicht van de Wet IB 2001 (meting ronde 2, I13)."""
    import json
    import re as _re

    uit: set[str] = set()
    for naam, tekst in trace:
        if naam != "zoek_artikelen":
            continue
        try:
            data = json.loads(tekst)
        except ValueError:
            continue
        if not isinstance(data, dict) or data.get("status") not in ("ok", "partial"):
            continue
        labels = [r.get("label") for r in data.get("resultaten") or [] if isinstance(r, dict)]
        labels += [d.get(k) for d in data.get("opbouw") or [] if isinstance(d, dict) for k in ("van", "tot")]
        uit |= {m.group(1).casefold() for x in labels if isinstance(x, str)
                and (m := _re.fullmatch(r"Artikel\s+(\S+)", x.strip()))}
    return uit


def _niet_onderbouwd(uitleg: str, citaten: list[Citaat], extern: frozenset[str] = frozenset(),
                     trace: Trace = ()) -> list[str]:
    """De artikelen die de uitleg noemt en die geen enkele passage draagt of vermeldt. Een artikel van overheid.nl
    (`wettekst_live`) dat het blok `extern` aanwijst, is onderbouwd (iteratie ronde 1, I28: "artikel 2:9 BW" werd zes keer
    geweigerd, terwijl het gelezen en aangewezen was), en zo ook een artikel dat de opbouw van zo'n regeling noemt
    (`live_opbouw`)."""
    live = {n for n, ids in live_artikelen(trace).items() if any(i in extern for i in ids)} | live_opbouw(trace)
    bekend = _bekende_artikelen([("", f"{c.vindplaats.iri} {c.vindplaats.label} {c.tekst}") for c in citaten]) | live
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
    gelezen, ophalen, onbekend, live = [], [], [], []
    live_ids = live_artikelen(trace)
    for vermelding in los:
        nummer = vermelding.removeprefix("artikel ")
        iri = artikel_in_trace(nummer, trace)
        if nummer.casefold() in live_ids:
            live.append((vermelding, live_ids[nummer.casefold()]))
        elif iri and any(_binnen(k, iri) for k in rijen):
            gelezen.append(vermelding)
        elif iri and len(ophalen) < MAX_OPHALEN:
            ophalen.append({"bwb_id": iri.split(":")[2], "artikel": nummer, "vermelding": vermelding})
        else:
            onbekend.append(vermelding)
    zinnen = []
    if live:
        zinnen.append("Je noemt " + ", ".join(v for v, _ in live) + " zonder passage. Die tekst is van overheid.nl gelezen: "
                      "wijs de passages aan in 'extern' met het id (" + ", ".join(i for _, ids in live for i in ids) +
                      "), of laat de "
                      "vermelding weg.")
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
    # De code zegt welke soorten vermelding zonder passage er waren: daaraan is te zien wat een ronde kostte.
    soorten = [naam for naam, lijst in (("live", live), ("gelezen", gelezen), ("op_te_halen", ophalen), ("onbekend", onbekend))
               if lijst]
    return Onvulbaar(" ".join([*zinnen, "Rond daarna opnieuw af."]),
                     ophalen=[{"bwb_id": o["bwb_id"], "artikel": o["artikel"]} for o in ophalen],
                     code="genoemd_" + "+".join(soorten))


#: De ids die het subsjabloon `extern` in dezelfde aanroep aanwees (`sjablonen.vul` geeft ze mee): een artikel van
#: overheid.nl daaruit telt als onderbouwd.
EXTERN_IDS = "_extern_ids"


def _geen_passage(live: set[str]) -> str:
    """De weigering zonder aangewezen passage. Is er wettekst van overheid.nl gelezen, dan is die de onderbouwing, in
    'extern': 'onderbouwing' kent alleen wettekst uit de kennisgraaf (ronde 3, I12 en I13: het model schreef het antwoord
    acht keer opnieuw, omdat 'onderbouwing' voor een regeling buiten de graaf niet te vullen is)."""
    if live:
        return ("Wijs de passages aan in 'extern', met het id van het gelezen stuk (" + ", ".join(sorted(live)[:6]) +
                ") en de alineanummers: 'onderbouwing' is alleen voor wettekst uit de kennisgraaf, en die staat hier niet.")
    return "Wijs ten minste één passage aan. Vond je geen bepaling die de vraag draagt, zeg dat dan in tekst."


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    kort = _lex(invoer.get("kort_antwoord"), trace)
    if not kort:
        raise Onvulbaar("Schrijf het korte antwoord.", code="kort_antwoord")
    stukken = invoer.get("onderbouwing") or []
    extern = frozenset(str(i) for i in invoer.get(EXTERN_IDS) or [])
    live = live_stukken(trace)
    if not stukken and not (extern & live):
        raise Onvulbaar(_geen_passage(live), code="geen_passage_live" if live else "geen_passage")
    rijen, fouten = bron_rijen(trace), []
    citaten = [c for stuk in stukken if (c := _citaat(stuk, rijen, trace, fouten))]
    if fouten:
        raise Onvulbaar("Niet te tonen, dus er wordt niets getoond. " + "; ".join(fouten) + ". Rond daarna opnieuw af.",
                        code="passage_niet_te_tonen")
    twijfel = list(dict.fromkeys(t for x in invoer.get("twijfel") or [] if (t := _lex(x, trace))))
    if los := _niet_onderbouwd("\n".join([kort, *(c.waarom for c in citaten), *twijfel]), citaten, extern, trace):
        raise _genoemd_is_gelezen(los, rijen, trace)
    blokken: list[Any] = [Toelichting(kop="Kort antwoord", tekst=kort), *([Citaten(items=citaten)] if citaten else [])]
    if twijfel:
        blokken.append(Twijfel(punten=twijfel))
    return Antwoord(sjabloon="duiding", blokken=blokken, doelen=list({c.vindplaats.iri: c.vindplaats for c in citaten}.values()))
