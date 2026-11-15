"""Bronnen naast de wet in een antwoord (ADR-008 + ADR-013): het blok `extern`, als subsjabloon en als eigen sjabloon.

Een antwoord met een Kamerstuk (of later een uitspraak, EU-recht) krijgt een vaste vorm in plaats van vrije tekst
waarin de wetsgeschiedenis door de uitleg loopt. Eén herbruikbaar blok, generiek per brontype:

- **Als subsjabloon.** De sjablonen van een specialist die een connector bedient (het profiel noemt hem: `Agentprofiel.connectors`)
  krijgen één extra veld, `extern`: een lijst platte objecten `{id, van_nr, tot_nr}`. Zonder union, zonder recursie en
  verplicht maar mag leeg zijn: binnen de grenzen die strict tools stellen. Het veld staat er alleen als er een
  connector aanstaat, dus zonder connector is het schema byte-gelijk aan vóór ADR-013 (open keuze 6, aanbeveling a).
- **Als eigen sjabloon** (`antwoord_extern`): een vraag die alleen over een bron naast de wet gaat. Een kort antwoord
  van Lex, dezelfde `extern`-aanwijzing en de twijfel.

Het model wijst alleen het stuk en de passages aan. De tekst, de vindplaats, het brontype en de kop komen uit de code:
de rijen van de leestool van de connector (contract: `stuk: {id, label, link, bron_hash, gewijzigd?}` en rijen `{nr, tekst, kop?}`) en de
beschrijving (`kop_in_antwoord`). Een id dat niet gelezen is, of een passage die er niet is, is `Onvulbaar`: het model
haalt dan eerst op, net als bij `van`/`tot` in de duiding.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any

from bronmodel.antwoord import (Antwoord, Extern, ExternePassage, ExterneVerwijzing, Leemte, Stuk, Stukken, Toelichting,
                                Twijfel)
from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving, van_id
from bronmodel.extern import externe_vindplaats

from ..tools.stuk_tekst import aangevuld
from .vullen import Onvulbaar, Trace, _data, resultaten

#: De maat van één aanwijzing: meer is een samenvatting, en die schrijft Lex in eigen woorden.
MAX_PASSAGES = 6
#: Zo veel stukken per antwoord.
MAX_STUKKEN = 4
#: Zo veel stukken in het rapport van een subagent: elk stuk dat hij samenvat, hoort er een passage te dragen, want daarop
#: toetst de centrale agent zijn samenvatting (meting bundel 122, D01: de grens van vier liet er twee weg, en de centrale
#: agent haalde hun juiste samenvatting weg).
MAX_STUKKEN_RAPPORT = 10
#: Hoeveel woorden een alinea minstens heeft om inhoud te dragen. Korter is een kopregel ("HOGE RAAD DER NEDERLANDEN",
#: "BELASTINGKAMER", "tegen"): die draagt geen duiding (meting bundel 122, D01: de citaten waren alleen kopregels).
MIN_WOORDEN_INHOUD = 6


def is_kopregel(tekst: str, kop: str = "") -> bool:
    """Draagt deze alinea geen inhoud? Minder dan `MIN_WOORDEN_INHOUD` woorden, of alleen hoofdletters. De
    inhoudsindicatie is nooit een kopregel: ze vat de uitspraak samen, ook in een paar woorden."""
    if kop.strip().lower().startswith("inhoudsindicatie"):
        return False
    woorden = re.findall(r"\w+", tekst or "")
    return len(woorden) < MIN_WOORDEN_INHOUD or not any(c.islower() for c in tekst or "")
#: Vaste formules zonder inhoud voor de vraag (A6 run 3): de aanhef en het slot van een besluit (S05: "Wij Beatrix, bij de
#: gratie Gods …", "Hebben goedgevonden en verstaan:") en het procesverloop van een uitspraak (P02: "De Staatssecretaris
#: van Financiën heeft een verweerschrift ingediend.").
_FORMULES = tuple(re.compile(p, re.I) for p in (
    r"^wij \w+,? bij de gratie gods", r"^op de voordracht van ", r"^hebben goedgevonden en verstaan",
    r"^lasten en bevelen dat", r"^gegeven te ", r"\bis belast met de uitvoering van (?:dit|deze) ",
    r"^gewezen op het (?:beroep|verzoek|hoger beroep)", r"\bheeft een verweerschrift ingediend",
    r"\b(?:beroep|hoger beroep|beroep in cassatie) ingesteld\.?$",
    r"\b(?:beroepschrift|verweerschrift)\b.{0,60}\b(?:gehecht|deel uit)",
    r"^in cassatie kan van het volgende worden uitgegaan", r"\bheeft een (?:conclusie|repliek|dupliek|schriftelijke "
    r"toelichting)\b.{0,40}\b(?:genomen|ingediend)"))


def is_formule(tekst: str, kop: str = "") -> bool:
    """Een vaste formule of een rij trefwoorden: tekst die er staat maar niets zegt over de vraag. Een inhoudsindicatie
    die alleen trefwoorden noemt ("Ontvanger, huurkoopovereenkomst, meldingsplicht, …", "- Successierecht"; P01, P02)
    telt ook, een die zinnen draagt niet."""
    t = " ".join((tekst or "").split())
    if any(f.search(t) for f in _FORMULES):
        return True
    if not kop.strip().lower().startswith("inhoudsindicatie"):
        return False
    delen = [d for d in re.split(r"[,;]|\s-\s|^-\s*", t) if d.strip()]
    if t.startswith("-") and len(re.findall(r"\w+", t)) <= 5:
        return True
    return len(delen) >= 3 and all(len(re.findall(r"\w+", d)) <= 4 for d in delen)


#: Zo veel alinea's citeert één antwoord hoogstens, over alle aanwijzingen samen. Een langere reeks splitst de code zelf,
#: en wat erboven valt kapt de code af, met een melding in het antwoord: een weigering liet het model zijn aanwijzingen
#: inkorten tot het er precies zoveel waren, en kostte zo twee rondes (iteratie bekendmakingen ronde 4, B21 en B22).
#: Een grens per aanwijzing liet het model in stappen splitsen, één weigering per stap (iteratie 11 nov 2026: Kamerstukken
#: K15 vijf keer, 450k tokens). Het aantal aanwijzingen heeft geen eigen grens: elke aanwijzing draagt minstens één alinea,
#: dus dit totaal begrenst ze al. Een grens van acht aanwijzingen weigerde losse alinea's verspreid over een stuk, zoals de
#: aanhef van zeventien artikelen van een verzamelwet (iteratie bekendmakingen ronde 3, B16: zeven rondes, 187k tokens).
MAX_ALINEAS = MAX_PASSAGES * MAX_STUKKEN * 2

VELD = "extern"
#: Het veld voor een lijst gevonden stukken (`Stukken`): alleen de ids, de rest komt uit de zoekrijen.
STUKKEN = "stukken"
#: Zo veel stukken per lijst; meer is geen antwoord maar een zoekresultaat.
MAX_LIJST = 25

def _connectors(namen: Any = None) -> list[ConnectorBeschrijving]:
    """De beschrijvingen van de connectors in de beurt (namen), of alle bekende; in de volgorde van `CONNECTORS`."""
    if namen is None or namen is True:
        return list(CONNECTORS.values())
    return [c for n, c in CONNECTORS.items() if n in set(namen)] or list(CONNECTORS.values())


def _of_opsomming(delen: list[str]) -> str:
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " of " + delen[-1]


def items(namen: Any = None) -> dict[str, Any]:
    """Het veld `extern`, met de voorbeelden van de connectors die aanstaan (`ConnectorBeschrijving.voorbeeld_id`)."""
    cs = _connectors(namen)
    return {
        "type": "array",
        "description": (
            f"Passages uit een bron naast de wet ({_of_opsomming([f'een {c.brontype}' for c in cs])}) die je in dit gesprek "
            "met de leestool ophaalde: per stuk het id en het eerste en laatste alineanummer. Schrijf de tekst niet uit, de "
            "code neemt hem uit de bron. Leeg als het antwoord zo'n bron niet gebruikt. Een bron naast de wet onderbouwt "
            "nooit wat de wet zegt."),
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Het id van het stuk uit het toolresultaat, bijvoorbeeld "
                       + _of_opsomming([f"'{c.voorbeeld_id}'" for c in cs]) + "."},
                "van_nr": {"type": "integer", "description": "Het nummer (nr) van de eerste alinea."},
                "tot_nr": {"type": "integer", "description": "Het nummer (nr) van de laatste alinea; gelijk aan van_nr voor één alinea."},
            },
            "required": ["id", "van_nr", "tot_nr"],
            "additionalProperties": False,
        },
    }


def stukken_items(namen: Any = None) -> dict[str, Any]:
    cs = _connectors(namen)
    vormen = ", ".join(f"{p}…" for c in cs for p in c.id_prefixen)
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Een lijst stukken die een zoektool van een bron naast de wet in dit gesprek vond, zoals 'de tien nieuwste "
            f"stukken' of 'het laatste stuk van een reeks': alleen hun ids ({vormen}), in de volgorde van het "
            f"zoekresultaat, hoogstens {MAX_LIJST} per bron (elke bron krijgt een eigen lijst). De code toont per stuk het label, soort, datum en titel uit de bron, "
            "met de zoekvraag en het totaal. Schrijf de lijst of hun datums niet zelf uit. Alleen als de vraag om een "
            "lijst stukken vraagt; leeg bij een telling, een opbouw of een uitleg, ook als de zoektool stukken gaf."),
    }


def schema(namen: Any = None) -> dict[str, Any]:
    """Het eigen sjabloon `antwoord_extern`, voor de connectors die aanstaan."""
    cs = _connectors(namen)
    return {
        "name": "antwoord_extern",
        "description": (
            f"Rond een vraag af die alleen over een bron naast de wet gaat ({_of_opsomming([c.label for c in cs])}): wat "
            "staat er in dit stuk, wat zegt het hierover. Roep deze tool aan nadat je het stuk hebt opgehaald, en schrijf "
            "geen antwoord ernaast. Jij schrijft het korte antwoord in eigen woorden en wijst de passages aan; de code "
            "toont ze letterlijk met hun vindplaats. Gaat de vraag (ook) over wat de wet zegt, gebruik dan het sjabloon "
            "voor de bepaling of de uitleg, met de passages in hun veld 'extern'."),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "kort_antwoord": {"type": "string", "description": "Het antwoord in twee tot vier zinnen, in eigen woorden en zonder citaten."},
                VELD: items(namen),
                STUKKEN: stukken_items(namen),
                "twijfel": {"type": "array", "items": {"type": "string"},
                            "description": "Aannames en wat de opgehaalde tekst open laat, elk als één punt. Leeg als die er niet zijn."},
            },
            "required": ["kort_antwoord", VELD, STUKKEN, "twijfel"],
            "additionalProperties": False,
        },
    }


#: Met alle bekende connectors; de schema's van een beurt bouwt `sjablonen.sjabloon_schemas` met de connectors die aanstaan.
ITEMS: dict[str, Any] = items()
STUKKEN_ITEMS: dict[str, Any] = stukken_items()
SCHEMA: dict[str, Any] = schema()


def met_veld(basis: dict[str, Any], namen: Any = None) -> dict[str, Any]:
    """Een sjabloonschema met het veld `extern` erbij: het subsjabloon, met de voorbeelden van de connectors die aanstaan
    (`namen`; zonder: alle). Het origineel blijft ongemoeid."""
    uit = copy.deepcopy(basis)
    invoer = uit["input_schema"]
    for veld, waarde in ((VELD, items(namen)), (STUKKEN, stukken_items(namen))):
        invoer["properties"][veld] = waarde
        if veld not in invoer["required"]:
            invoer["required"].append(veld)
    return uit


def _gelezen(trace: Trace, c: ConnectorBeschrijving, ident: str
             ) -> tuple[dict[str, Any], dict[int, dict[str, Any]], set[int], set[int]]:
    """Het stuk en zijn passages op nummer, uit de pagina's van de laatste lezing van dit id (dezelfde `bron_hash`), en
    de nummers die alleen in een eerdere lezing staan. Twee lezingen mengen kan niet: het register gaat over beurten
    heen, en een bron kan intussen een nieuwe versie publiceren (review ADR-013, punt 3)."""
    lezingen: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for data in resultaten(trace, [c.leestool]):
        s = data.get("stuk") or {}
        if s.get("id") == ident:
            # Een pagina laat de kop weg waar hij gelijk is aan die erboven (`stuk_tekst.tekstpagina`): eerst aanvullen.
            lezingen.append((s, [r for r in aangevuld(data)
                                 if isinstance(r.get("nr"), int) and isinstance(r.get("tekst"), str)]))
    if not lezingen:
        return {}, {}, set(), set()
    laatste = lezingen[-1][0]
    rijen: dict[int, dict[str, Any]] = {}
    eerder: set[int] = set()
    for s, rs in lezingen:
        if s.get("bron_hash") == laatste.get("bron_hash"):
            for r in rs:
                # De kop van een tabel staat op de tekstpagina (titel) en in de tabel zelf (titel en kolommen): de
                # rijkste wint, zodat de kolommen meekomen.
                if r["nr"] not in rijen or (r.get("cellen") and not rijen[r["nr"]].get("cellen")):
                    rijen[r["nr"]] = r
        else:
            eerder |= {r["nr"] for r in rs}
    # Een tabel die niet geopend is: haar rijen zijn niet gelezen, maar een passage mag eroverheen lopen (de titel staat
    # erin). `tot_nr` op de tabelrij zegt welke nummers bij de tabel horen.
    in_tabel = {n for r in rijen.values() if r.get("soort") == "tabel" and isinstance(r.get("tot_nr"), int)
                for n in range(r["nr"] + 1, r["tot_nr"] + 1)} - set(rijen)
    return laatste, rijen, eerder - set(rijen), in_tabel


def _verwijzingen(rij: dict[str, Any]) -> list[ExterneVerwijzing] | None:
    """De stukken waar een rij naar verwijst, met label en link uit de code (nooit uit het model)."""
    uit = [ExterneVerwijzing(id=vp.id, label=vp.label, link=vp.uri) for i in rij.get("verwijst_naar") or []
           if isinstance(i, str) and (vp := externe_vindplaats(i)) is not None]
    return uit or None


#: De velden over de tekst van de bepaling waarbij een stuk hoort (een uitspraak bij een eerdere versie van het artikel).
#: Ze staan in de zoekrij, niet in het gelezen stuk: de leestool kent het artikel niet.
TEKSTVELDEN = ("tekst_vanaf", "tekst_tot", "tekststand", "op_peildatum")


def status_velden(c: ConnectorBeschrijving, stuk: dict[str, Any]) -> dict[str, Any]:
    """De statusregel uit de beschrijving (met de datum van het stuk voluit) en de stand van het stuk bij de bron. Uit de
    code: het model schrijft niet wat een bron tegenover de wet is (plan-connector-kennisgroepen.md §2.5)."""
    uit: dict[str, Any] = {}
    if c.status_regel:
        uit["status_regel"] = c.status_regel.format(datum=_voluit(str(stuk.get("datum") or "")) or "onbekend")
    if stuk.get("status"):
        uit["status"] = str(stuk["status"])
    if isinstance(stuk.get("vervangen_door"), list):
        uit["vervangen_door"] = [str(x) for x in stuk["vervangen_door"]]
    return uit


def _tekst_bij(trace: Trace, c: ConnectorBeschrijving, ident: str) -> dict[str, Any]:
    """De tekstvelden uit de zoekrij van dit stuk, als het in een zoekresultaat van dit gesprek stond."""
    rij = _gevonden(trace, c).get(ident, ({}, None, 0))[0]
    return {k: rij[k] for k in TEKSTVELDEN if rij.get(k) not in ("", None)}


def _reeksen(nummers: Any) -> str:
    """Alineanummers als reeksen: [6, 7, 8, 12] wordt "6–8, 12". Een weigering met honderden losse nummers was langer dan
    het antwoord dat het model moest herstellen."""
    uit: list[str] = []
    for n in sorted(set(nummers)):
        if uit and isinstance(laatste := uit[-1], str) and laatste.split("–")[-1].isdigit() and int(
                laatste.split("–")[-1]) == n - 1:
            uit[-1] = f"{laatste.split('–')[0]}–{n}"
        else:
            uit.append(str(n))
    return ", ".join(uit)


#: Hoeveel alinea's de code hoogstens kiest bij een stuk dat het rapport samenvat zonder een passage met inhoud.
MAX_GEKOZEN = 2


def samenvatting(tekst: str, trace: Trace) -> dict[str, set[str]]:
    """Per gelezen stuk dat het rapport samenvat (een zin met meer dan `MAX_EIGEN_WOORDEN` woorden die het zoekresultaat
    niet al noemt) de stammen van alles wat het erover zegt, ook in de kortere zinnen. Daarmee kiest de code de passages
    van een stuk."""
    from ..gelezen import MAX_EIGEN_WOORDEN, _FUNCTIEWOORDEN, _WOORD, _context, _rijwoorden, _stammen, per_stuk

    paren = [(str(x[0]), str(x[1])) for x in trace]
    gelezen, labels = _context(paren)
    per_id: dict[str, set[str]] = {}
    samengevat: set[str] = set()
    for segment, ids in per_stuk(tekst or "", gelezen, labels):
        for ident in ids:
            if ident not in gelezen or van_id(ident) is None:
                continue
            bekend = _rijwoorden(paren, ident)
            eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
            per_id.setdefault(ident, set()).update(_stammen(eigen))
            if len(eigen) > MAX_EIGEN_WOORDEN:
                samengevat.add(ident)
    return {i: s for i, s in per_id.items() if i in samengevat}


def aanvulling(tekst: str, items: Any, trace: Trace) -> tuple[list[dict[str, Any]], list[str]]:
    """De aanwijzingen die de code toevoegt aan een rapport: bij elk gelezen stuk dat de bevindingen samenvatten zonder een
    alinea met inhoud in 'extern', de alinea's van dat stuk die het meest delen met wat erover gezegd wordt (hoogstens
    `MAX_GEKOZEN`, geen kopregel). Zo draagt elke samenvatting een passage waartegen de centrale agent haar toetst, zonder
    extra ronde (meting bundel 122, D01: vier juiste samenvattingen zonder passage, en de correctie haalde ze weg). De
    passages zijn letterlijk uit het stuk; wat ze dragen toetst `verify`, en de controle per stuk leest ze na.
    (de aanwijzingen, een regel voor 'Niet als citaat getoond' per stuk)."""
    from ..gelezen import MIN_STEUN, _WOORD, _stammen

    lijst = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    # Per stuk de tekst met inhoud die het model al aanwees (geen kopregel).
    aangewezen: dict[str, str] = {}
    for item in lijst:
        vp, c = externe_vindplaats(str(item.get("id") or "")), van_id(str(item.get("id") or ""))
        van, tot = item.get("van_nr"), item.get("tot_nr")
        if vp is None or c is None or not isinstance(van, int) or not isinstance(tot, int):
            continue
        _s, rijen, _e, _t = _gelezen(trace, c, vp.id)
        aangewezen[vp.id] = aangewezen.get(vp.id, "") + " " + " ".join(
            rijen[n].get("tekst", "") for n in range(van, tot + 1)
            if n in rijen and not is_kopregel(rijen[n].get("tekst", ""), str(rijen[n].get("kop") or "")))
    per_id = samenvatting(tekst, trace)
    extra, regels = [], []
    for ident, stammen in per_id.items():
        al = _stammen(_WOORD.findall((aangewezen.get(ident) or "").casefold()))
        if al and len(stammen & al) >= MIN_STEUN * len(stammen):
            continue  # wat het model aanwees, draagt de samenvatting al
        stuk, rijen, _e, _t = _gelezen(trace, van_id(ident), ident)
        score = sorted(((len(_stammen(_WOORD.findall(r.get("tekst", "").casefold())) & stammen), n)
                        for n, r in rijen.items() if not is_kopregel(r.get("tekst", ""), str(r.get("kop") or ""))),
                       reverse=True)
        gekozen = sorted(n for k, n in score[:MAX_GEKOZEN] if k > 0)
        if gekozen:
            extra += [{"id": ident, "van_nr": n, "tot_nr": n} for n in gekozen]
            regels.append(f"{str(stuk.get('label') or ident)}: de aangewezen passages dragen de samenvatting niet; de "
                          f"code koos er alinea {_reeksen(gekozen)} bij")
    return extra, regels


def blokken(items: Any, trace: Trace, *, overgeslagen: list[str] | None = None,
            max_stukken: int = MAX_STUKKEN, zonder_kopregels: bool = False,
            voorkeur: dict[str, set[str]] | None = None) -> list[Extern | Leemte]:
    """De blokken `extern` uit de aanwijzingen van het model; elk feit uit de trace. Wat niet klopt, staat in één
    weigering voor alle aanwijzingen samen: per fout een weigering kostte per fout een ronde waarin het model het hele
    antwoord opnieuw schreef (iteratie bekendmakingen ronde 1, 11 nov 2026: B16 vijf rondes, ~120k tokens). Meer dan
    `MAX_ALINEAS` is geen fout: de code kapt af en zegt het in een `Leemte` achter de blokken.

    Met `overgeslagen` (het rapport van een subagent) weigert de code niet: wat niet klopt of boven `MAX_STUKKEN` valt,
    laat ze weg en zet ze in die lijst, zodat het rapport het onder 'Open' noemt.

    Met `voorkeur` (per stuk de stammen van wat het rapport erover zegt, `samenvatting`) houdt het afkappen per stuk de
    alinea's die dat het best dragen, in plaats van de eerste."""
    if not items:
        return []
    if overgeslagen is not None and isinstance(items, list) and len(items) > MAX_ALINEAS:
        overgeslagen.append(f"meer dan {MAX_ALINEAS} aanwijzingen in '{VELD}': alleen de eerste {MAX_ALINEAS} getoond")
        items = items[:MAX_ALINEAS]
    if not isinstance(items, list) or len(items) > MAX_ALINEAS:
        raise Onvulbaar(f"'{VELD}' is een lijst van hoogstens {MAX_ALINEAS} aanwijzingen. Wijs alleen de alinea's aan die "
                        "het antwoord dragen, en vat de rest samen in het korte antwoord.")
    per_stuk: dict[str, Extern] = {}
    fouten: list[str] = []
    for item in items:
        ident = str((item or {}).get("id") or "").strip()
        vp = externe_vindplaats(ident)
        c = van_id(ident)
        if vp is None or c is None:
            fouten.append(f"'{ident}' is geen id van een bron naast de wet die hier aanstaat. Een stuk waar de tekst alleen "
                          f"naar verwijst, hoort niet in '{VELD}': noem het in je eigen woorden of in de twijfel.")
            continue
        stuk, rijen, alleen_eerder, in_tabel = _gelezen(trace, c, vp.id)
        if not stuk:
            fouten.append(f"{vp.label} is in dit gesprek niet gelezen: haal het stuk eerst op met {c.leestool} en wijs "
                          f"dan de passages aan, of laat het weg uit '{VELD}' en noem het in je eigen woorden of in de "
                          "twijfel (niet gelezen).")
            continue
        van, tot = item.get("van_nr"), item.get("tot_nr")
        if not isinstance(van, int) or not isinstance(tot, int) or van > tot:
            fouten.append(f"{vp.label}: van_nr en tot_nr zijn alineanummers, met van_nr ≤ tot_nr.")
            continue
        ontbreekt = [n for n in range(van, tot + 1) if n not in rijen and n not in in_tabel]
        if ontbreekt and set(ontbreekt) & alleen_eerder:
            fouten.append(f"{vp.label} is veranderd sinds alinea {_reeksen(set(ontbreekt) & alleen_eerder)} gelezen "
                          f"werd. Haal het stuk opnieuw op met {c.leestool}, en wijs de passages aan in de versie van nu.")
            continue
        if ontbreekt:
            fouten.append(f"{vp.label}: alinea {_reeksen(ontbreekt)} is niet opgehaald. Haal het vervolg op, of wijs "
                          f"alinea's aan die in het resultaat staan (gelezen: {_reeksen(rijen)}).")
            continue
        blok = per_stuk.setdefault(vp.id, Extern(
            brontype=vp.brontype, id=vp.id, label=str(stuk.get("label") or vp.label),
            link=str(stuk.get("link") or vp.uri), kop=c.kop_in_antwoord, passages=[],
            bron_hash=str(stuk.get("bron_hash") or ""), gewijzigd=str(stuk.get("gewijzigd") or ""),
            datum=str(stuk.get("datum") or ""), soort_stuk=str(stuk.get("soort") or ""),
            **_tekst_bij(trace, c, vp.id), **status_velden(c, stuk)))
        al = {p.nr for p in blok.passages}
        if (zonder_kopregels or vp.brontype == "uitspraak") and overgeslagen is not None:
            # In een rapport telt een kopregel niet als passage: hij draagt geen duiding, en de centrale agent toetst erop.
            # Bij een uitspraak ook niet in een antwoord: "Locatie Arnhem" en het zaaknummer zijn geen citaat (meting
            # bundel 123, D01); daar zonder melding, want de kop van het blok noemt het stuk al.
            kop = [n for n in range(van, tot + 1) if n in rijen and n not in al
                   and is_kopregel(rijen[n].get("tekst", ""), str(rijen[n].get("kop") or ""))]
            if kop:
                if zonder_kopregels:
                    overgeslagen.append(f"{vp.label}: alinea {_reeksen(kop)} is een kopregel zonder inhoud")
                al |= set(kop)
        if overgeslagen is not None:
            # Een formule binnen een reeks valt weg als er iets met inhoud overblijft; een aanwijzing van alleen de formule
            # blijft staan (wie om de aanhef vraagt, krijgt de aanhef).
            formule = {n for n in range(van, tot + 1) if n in rijen and n not in al
                       and is_formule(rijen[n].get("tekst", ""), str(rijen[n].get("kop") or ""))}
            if formule and any(n in rijen and n not in al and n not in formule for n in range(van, tot + 1)):
                al |= formule
        blok.passages += [ExternePassage(nr=n, tekst=rijen[n]["tekst"], kop=str(rijen[n].get("kop") or ""),
                                         soort=str(rijen[n].get("soort") or "alinea"),
                                         cellen=[str(x) for x in rijen[n]["cellen"]] if isinstance(rijen[n].get("cellen"), list)
                                         else None, verwijst_naar=_verwijzingen(rijen[n]),
                                         plek=str(rijen[n].get("plek") or ""))
                          for n in range(van, tot + 1) if n not in al and n in rijen]
    per_stuk = {k: v for k, v in per_stuk.items() if v.passages}
    if len(per_stuk) > max_stukken and overgeslagen is not None:
        weg = list(per_stuk)[max_stukken:]
        overgeslagen.append(f"{len(weg)} stukken boven de grens van {max_stukken} niet als citaat getoond: "
                            + ", ".join(per_stuk[i].label for i in weg))
        per_stuk = {k: v for k, v in per_stuk.items() if k not in weg}
    elif len(per_stuk) > max_stukken:
        fouten.append(f"Hoogstens {max_stukken} stukken per antwoord.")
    if overgeslagen is not None:
        overgeslagen.extend(fouten)
        fouten = []
    if len(fouten) == 1:
        raise Onvulbaar(fouten[0])
    if fouten:
        raise Onvulbaar(f"{len(fouten)} aanwijzingen in '{VELD}' kloppen niet; herstel ze allemaal in één aanroep:\n"
                        + "\n".join(f"- {f}" for f in fouten))
    for b in per_stuk.values():
        b.passages.sort(key=lambda p: p.nr)
    return [*per_stuk.values(), *_afgekapt(list(per_stuk.values()), voorkeur)]


def _rang(p: ExternePassage, stammen: set[str]) -> float:
    """Hoe goed een passage draagt wat het rapport over haar stuk zegt: de gedeelde stammen, en een rechtsoverweging
    telt zwaarder dan het procesverloop en de feiten (meting bundel 123, D01: bij HR:2023:1371 bleven r.o. 1–3.1 staan en
    vielen de dragende r.o. 3.3–3.8 weg). Een kopregel draagt niets."""
    from ..gelezen import _WOORD, _stammen

    if is_kopregel(p.tekst, p.kop):
        return 0.0
    gedeeld = len(_stammen(_WOORD.findall(p.tekst.casefold())) & stammen)
    return gedeeld * (1.5 if p.plek.strip().lower().startswith("r.o.") else 1.0)


def _afgekapt(blokken: list[Extern], voorkeur: dict[str, set[str]] | None = None) -> list[Leemte]:
    """Kap de passages af op `MAX_ALINEAS` en zeg welke alinea's eruit vielen: een melding in plaats van een weigering.
    Een lege lijst als alles past. Eerlijk verdeeld: om de beurt één alinea per stuk, in de volgorde van het antwoord,
    zodat een lange reeks bij het eerste stuk de andere niet leeg laat (meting bundel 122, D01: alinea 1–35 en 1–59 bij
    de eerste twee, en HR:2023:563 en :176 hielden geen passage)."""
    houd = [0] * len(blokken)
    ruimte = MAX_ALINEAS
    while ruimte > 0 and any(houd[i] < len(b.passages) for i, b in enumerate(blokken)):
        for i, b in enumerate(blokken):
            if ruimte and houd[i] < len(b.passages):
                houd[i] += 1
                ruimte -= 1
    weg = []
    for i, b in enumerate(blokken):
        if houd[i] < len(b.passages) and (voorkeur or {}).get(b.id):
            # De best dragende alinea's eerst (bij gelijke rang de eerste), daarna weer op nummer.
            beste = sorted(b.passages, key=lambda p: -_rang(p, voorkeur[b.id]))[:houd[i]]
            gehouden = {p.nr for p in beste}
            rest = [p for p in b.passages if p.nr not in gehouden]
            b.passages = [p for p in b.passages if p.nr in gehouden]
        else:
            rest, b.passages = b.passages[houd[i]:], b.passages[:houd[i]]
        if rest:
            weg.append(f"{b.label} (alinea {_reeksen([p.nr for p in rest])})")
    if not weg:
        return []
    return [Leemte(tekst=f"Dit antwoord citeert hoogstens {MAX_ALINEAS} alinea's. Niet geciteerd: {_en_opsomming(weg)}. Lees "
                         "die tekst via de link bij het stuk.")]


def heel_stuk(trace: Trace, ident: str) -> Extern | None:
    """Het blok `extern` met álle rijen van de laatste lezing van één stuk, door de code aangewezen (geen grens van
    `MAX_PASSAGES`: die begrenst wat het model aanwijst). Voor de tekst van een artikel van overheid.nl in de
    bepalingsworkflow (`bepaling_workflow`): een artikel is één geheel, en de jurist ziet het zoals de graaf een artikel
    toont. `None` als het stuk niet (helemaal) gelezen is: een gat in de nummers is een ontbrekende pagina."""
    vp, c = externe_vindplaats(ident), van_id(ident)
    if vp is None or c is None:
        return None
    stuk, rijen, _, _ = _gelezen(trace, c, vp.id)
    if not stuk or not rijen or sorted(rijen) != list(range(1, len(rijen) + 1)):
        return None
    tekstvelden = {k: stuk[k] for k in TEKSTVELDEN if stuk.get(k) not in ("", None)}
    return Extern(
        brontype=vp.brontype, id=vp.id, label=str(stuk.get("label") or vp.label), link=str(stuk.get("link") or vp.uri),
        kop=c.kop_in_antwoord, bron_hash=str(stuk.get("bron_hash") or ""), gewijzigd=str(stuk.get("gewijzigd") or ""),
        datum=str(stuk.get("datum") or ""), soort_stuk=str(stuk.get("soort") or ""),
        **{**tekstvelden, **_tekst_bij(trace, c, vp.id)}, **status_velden(c, stuk),
        passages=[ExternePassage(nr=n, tekst=r["tekst"], kop=str(r.get("kop") or ""), soort=str(r.get("soort") or "alinea"),
                                 verwijst_naar=_verwijzingen(r), plek=str(r.get("plek") or ""))
                  for n, r in sorted(rijen.items())])


#: De volgordes in de woorden van de jurist: een eigen zin onder de lijst.
_VOLGORDE_TEKST = {"nieuwste": "Nieuwste eerst.", "oudste": "Oudste eerst.", "nummer": "Op nummer.",
                   "relevantie": "Meest relevante eerst."}


_AANHALING = re.compile(r'["„”]')


def _voluit(datum: str) -> str:
    """'2024-01-01' → '1 januari 2024', '2024-03' → 'maart 2024'; iets anders blijft staan."""
    from ..hoeveelheden import _MAANDEN

    if (m := re.fullmatch(r"(\d{4})-(\d{2})", str(datum))) and 1 <= int(m.group(2)) <= 12:
        return f"{_MAANDEN[int(m.group(2)) - 1]} {m.group(1)}"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(datum))
    return f"{int(m.group(3))} {_MAANDEN[int(m.group(2)) - 1]} {m.group(1)}" if m and 1 <= int(m.group(2)) <= 12 else str(datum)


def _en_opsomming(delen: list[str]) -> str:
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " en " + delen[-1]


#: Het eerste woord van een naam dat "het" krijgt: "van het College van Beroep", "van het Ministerie van Financiën"
#: (metingen Rechtspraak R25 en Staatsblad B10, 11 nov 2026: "van de College", "van de Ministerie").
_HET = frozenset({"college", "ministerie", "parket", "gerechtshof", "hof", "openbaar", "instituut", "comité", "agentschap",
                  "bureau", "centraal", "europees", "kabinet", "uwv", "cbs"})


def van_orgaan(naam: str) -> str:
    """'van de Hoge Raad', 'van het College van Beroep voor het bedrijfsleven'; een soort in kleine letters (een
    categorie, geen naam) in het meervoud: 'van gerechtshoven' (meting Rechtspraak ronde 2, R06: "van een
    gerechtshoven")."""
    from bronmodel.connectors import INSTANTIE_MEERVOUD

    naam = " ".join(str(naam).split())
    eerste = naam.split(" ", 1)[0] if naam else ""
    if eerste[:1].islower():
        meervoud = next((m for m, e in INSTANTIE_MEERVOUD.items() if e == naam.lower()), "")
        return f"van {naam}" if naam.lower() in INSTANTIE_MEERVOUD else f"van {meervoud}" if meervoud else f"van een {naam}"
    return f"van {'het' if eerste.lower() in _HET else 'de'} {naam}"


def _bepaling_in_woorden(zoekvraag: dict[str, Any]) -> str:
    """"artikel 36 van de Invorderingswet 1990", of de regeling als geheel, als de tool zelf geen `bepaling` gaf. De
    naam als dit proces hem kent, anders het id. Zonder artikel geen lege plek: "Gezocht bij artikel  van BWBR0004770"
    (meting Staatsblad ronde 5, B03)."""
    from ..spoorbronnen import _regeling
    bwb_id, artikel = str(zoekvraag.get("bwb_id") or "").strip(), str(zoekvraag.get("artikel") or "").strip()
    regeling = _regeling(bwb_id) if bwb_id else "de regeling"
    return f"artikel {artikel} van {regeling}" if artikel else regeling


def zoekvraag_tekst(c: ConnectorBeschrijving, zoekvraag: dict[str, Any], *, volgorde: bool = True) -> str:
    """De zoekvraag onder een lijst, in gewone zinnen: "Gezocht op „invorderingsrente” in de tekst, vergaderjaar
    2025-2026 en van de Eerste Kamer. Meest relevante eerst." Uit de code, met de labels uit de metadata van de
    beschrijving (`ConnectorBeschrijving.filters`); de vorm per soort veld (`MetadataVeld.sleutel`), dus voor elke
    connector. Een waarde die al zegt wat ze is ("Eerste Kamer") krijgt geen label ervoor (acceptatie 9 nov 2026:
    "Kamer Eerste Kamer")."""
    delen: list[str] = []
    periode: dict[str, str] = {}
    bepaling = ""
    for arg, waarde in zoekvraag.items():
        if arg in {"volgorde", "aantal", "offset", "bepaling"} or waarde in ("", None):
            continue
        veld = c.filters.get(arg)
        sleutel = veld.sleutel if veld else ""
        if sleutel == "wetsverwijzing":
            # Eén bepaling, ook al zijn het twee argumenten (regeling en artikel): in woorden, zoals de tool haar noemt.
            bepaling = str(zoekvraag.get("bepaling") or _bepaling_in_woorden(zoekvraag))
            continue
        if arg == "tekst":
            kaal = " ".join(_AANHALING.sub(" ", str(waarde)).split())
            delen.append(f"„{kaal}” in de tekst")
        elif sleutel == "titel":
            delen.append(f"„{waarde}” in de titel")
        elif sleutel == "reekstitel":
            delen.append(f"„{waarde}” in de titel van het dossier")
        elif veld is not None and veld.type == "datum":
            periode["vanaf" if arg == veld.filters[0] else "tot"] = _voluit(str(waarde))
        elif sleutel == "orgaan":
            delen.append(van_orgaan(str(waarde)))
        elif sleutel == "op_peildatum":
            delen.append(f"peildatum {_voluit(str(waarde))}")
        elif sleutel == "tekststand":
            delen.append({"huidige tekst": "de huidige tekst", "eerdere tekst": "een eerdere tekst",
                          "op peildatum": "de tekst op de peildatum"}.get(str(waarde), str(waarde)))
        elif sleutel == "soort":
            delen.append(f"{veld.label} „{waarde}”")
        elif veld is not None:
            delen.append(f"{veld.label} {waarde}")
        else:
            delen.append(f"{arg} {waarde}")
    if periode.get("vanaf") and periode.get("tot") and periode["vanaf"] == periode["tot"]:
        # Eén maand of één jaar: "in maart 2025", niet "van 2025-03 tot en met 2025-03" (meting Rechtspraak ronde 2, R04).
        delen.append(f"in {periode['vanaf']}")
    elif periode.get("vanaf") and periode.get("tot"):
        delen.append(f"van {periode['vanaf']} tot en met {periode['tot']}")
    elif periode.get("vanaf"):
        delen.append(f"vanaf {periode['vanaf']}")
    elif periode.get("tot"):
        delen.append(f"tot en met {periode['tot']}")
    # Wat met "van" begint (een orgaan, een periode) staat achteraan: "Gezocht op van de Hoge Raad" liep niet (nameting
    # 10 nov 2026). Is er verder niets, dan is het "Gezocht naar stukken van de Hoge Raad".
    delen.sort(key=lambda d: d.startswith(("van ", "vanaf ", "tot en met ", "in ")))
    alleen_van = bool(delen) and all(d.startswith(("van ", "vanaf ", "tot en met ", "in ")) for d in delen)
    # Delen die met een voorzetsel beginnen, lopen zonder "en" door: "van de Centrale Raad van Beroep in maart 2025"
    # (meting Rechtspraak ronde 2, R04: "… en in maart 2025").
    if bepaling:
        begin = f"Gezocht bij {bepaling}" + (f", {' '.join(delen)}" if alleen_van else
                                              f", op {_en_opsomming(delen)}" if delen else "") + "."
    elif alleen_van:
        begin = f"Gezocht naar stukken {' '.join(delen)}."
    else:
        begin = f"Gezocht op {_en_opsomming(delen)}." if delen else ""
    # Bij niets gevonden zegt een volgorde niets ("Meest relevante eerst." onder 0 treffers, meting Staatsblad B14).
    zinnen = [begin,
              _VOLGORDE_TEKST.get(str(zoekvraag.get("volgorde") or ""), "") if volgorde else ""]
    return " ".join(z for z in zinnen if z)


def _gevonden(trace: Trace, c: ConnectorBeschrijving) -> dict[str, tuple[dict[str, Any], dict[str, Any] | None, int]]:
    """Per id de rij met haar metadata, het resultaat waar ze in stond (voor de zoekvraag en het totaal) en haar plek
    in de trace. Uit de zoektools, en uit het `stuk` van de leestool, ook bij een stuk dat alleen als PDF bestaat
    (`alleen_pdf`): dat is gevonden, met zijn metadata. De laatste vermelding wint."""
    uit: dict[str, tuple[dict[str, Any], dict[str, Any] | None, int]] = {}
    zoeken = c.tools - {c.leestool}
    for plek, (naam, tekst) in enumerate(trace):
        if naam not in c.tools or (data := _data(tekst)) is None:
            continue
        if naam in zoeken and data.get("status") in ("ok", "partial"):
            for i, r in enumerate(data.get("resultaten") or []):
                if isinstance(r, dict) and isinstance(r.get("id"), str):
                    uit[r["id"]] = (r, data, plek * 1000 + i)
        elif naam == c.leestool and isinstance(data.get("stuk"), dict) and isinstance(data["stuk"].get("id"), str):
            # Wat alleen de zoekrij weet (de tekst van het artikel waarbij een uitspraak hoort) blijft staan.
            # Gevonden in een zoekvraag en daarna gelezen: het blijft bij die zoekvraag, op zijn plek in de lijst
            # (meting Rechtspraak R27: een gelezen arrest maakte de zoekvraag en het totaal van het blok leeg).
            eerder, bij, waar = uit.get(data["stuk"]["id"], ({}, None, plek * 1000))
            uit[data["stuk"]["id"]] = ({**{k: eerder[k] for k in TEKSTVELDEN if k in eerder}, **data["stuk"]}, bij,
                                       waar if bij is not None else plek * 1000)
    return uit


def lijsten(items: Any, trace: Trace) -> list[Stukken]:
    """De lijsten `stukken` uit de ids die het model aanwees, één per connector. Elk feit uit de zoekrijen, in hun
    volgorde; een id dat niet gevonden is, is `Onvulbaar` (zoek het eerst)."""
    if not items:
        return []
    # Hoogstens `MAX_LIJST` per bron, niet over alle bronnen samen: elke bron krijgt een eigen lijst (meting Rechtspraak
    # ronde 2, R30: 25 uitspraken lieten geen ruimte voor de gezochte Kamerstukken).
    if not isinstance(items, list) or len(items) > MAX_LIJST * max(1, len(CONNECTORS)):
        raise Onvulbaar(f"'{STUKKEN}' is een lijst van hoogstens {MAX_LIJST} ids per bron.")
    per_bron: dict[str, int] = {}
    for item in items:
        if (c0 := van_id(str(item or "").strip())) is not None:
            per_bron[c0.naam] = per_bron.get(c0.naam, 0) + 1
    if (te_veel := next((n for n, k in per_bron.items() if k > MAX_LIJST), None)) is not None:
        raise Onvulbaar(f"'{STUKKEN}' draagt hoogstens {MAX_LIJST} stukken van {CONNECTORS[te_veel].label}.")
    per: dict[str, list[tuple[int, dict[str, Any], dict[str, Any] | None]]] = {}
    gevonden: dict[str, dict[str, tuple[dict[str, Any], dict[str, Any] | None, int]]] = {}
    for item in items:
        ident = str(item or "").strip()
        vp, c = externe_vindplaats(ident), van_id(ident)
        if vp is not None and c is None:
            # Een stuk dat de zoektool van een connector vond maar dat buiten zijn id-vorm valt (een uitspraak van het
            # EHRM in de koppelingen van LiDO, `ECLI:CE:…`): het hoort bij die connector, als niet leesbaar stuk. Anders
            # weigerde één zo'n id het hele blok (meting 10 nov 2026).
            c = next((k for k in CONNECTORS.values() if k.brontype == vp.brontype
                      and vp.id in gevonden.setdefault(k.naam, _gevonden(trace, k))), None)
        if vp is None or c is None:
            raise Onvulbaar(f"'{ident}' is geen id van een bron naast de wet die hier aanstaat.")
        bij = gevonden.setdefault(c.naam, _gevonden(trace, c))
        if vp.id not in bij:
            zoektool = next(iter(sorted(c.tools - {c.leestool})), c.leestool)
            raise Onvulbaar(f"{vp.label} staat in geen zoekresultaat van dit gesprek: zoek het eerst met {zoektool}, en "
                            "wijs dan de ids uit het resultaat aan.")
        rij, data, plek = bij[vp.id]
        if all(p != plek for p, _, _ in per.get(c.naam, [])):
            per.setdefault(c.naam, []).append((plek, rij, data))
    if (te_veel := next((n for n, r in per.items() if len(r) > MAX_LIJST), None)) is not None:
        raise Onvulbaar(f"'{STUKKEN}' draagt hoogstens {MAX_LIJST} stukken van {CONNECTORS[te_veel].label}.")
    uit: list[Stukken] = []
    for naam, rijen in per.items():
        c = CONNECTORS[naam]
        rijen.sort(key=lambda x: x[0])
        # Pagina's van dezelfde zoekvraag (alleen `offset` verschilt, en die staat niet in `zoekvraag`) zijn één lijst
        # (metingen Rechtspraak R04/R30 en Kamerstukken K10, 11 nov 2026: zoekvraag leeg en totaal null).
        vragen = {_zoeksleutel(d) for _, _, d in rijen}
        data = rijen[0][2] if len(vragen) == 1 and None not in vragen else None
        zoekvraag = data.get("zoekvraag") if data and isinstance(data.get("zoekvraag"), dict) else {}
        totaal = data.get("totaal") if data and isinstance(data.get("totaal"), int) else None
        kanttekening = " ".join(dict.fromkeys(
            str(d["kanttekening"]).strip() for _, _, d in rijen
            if d and isinstance(d.get("kanttekening"), str) and d["kanttekening"].strip()))
        velden = set(Stuk.model_fields)
        uit.append(Stukken(
            brontype=c.brontype, kop=f"Gevonden {c.label}",
            items=[Stuk(**{k: v for k, v in r.items() if k in velden},
                        **({"zonder_tekst": c.zonder_tekst} if r.get("leesbaar") is False else {}))
                   for _, r, _ in rijen],
            zoekvraag=" ".join(filter(None, [zoekvraag_tekst(c, zoekvraag) if data else _per_zoekvraag(c, rijen),
                                             kanttekening])), totaal=totaal))
    return uit


def _per_zoekvraag(c: ConnectorBeschrijving, rijen: list[tuple[int, dict[str, Any], dict[str, Any] | None]]) -> str:
    """Een lijst uit meer zoekvragen: per zoekvraag een zin met haar totaal, in de volgorde waarin ze gesteld zijn. Het
    blok zelf draagt dan geen totaal: dat is er niet (meting Kamerstukken ronde 3, K17: de jurist zag niet waarop gezocht
    was). Een stuk dat alleen gelezen is, heeft geen zoekvraag en geen zin."""
    zinnen: list[str] = []
    gezien: set[str] = set()
    for _, _, d in rijen:
        if (sleutel := _zoeksleutel(d)) is None or sleutel in gezien or d is None:
            continue
        gezien.add(sleutel)
        totaal = d.get("totaal") if isinstance(d.get("totaal"), int) else None
        zin = zoekvraag_tekst(c, d["zoekvraag"])
        zinnen.append(f"{zin} Totaal {totaal}." if zin and totaal is not None else zin)
    return " ".join(z for z in zinnen if z)


def _zoeksleutel(data: dict[str, Any] | None) -> str | None:
    """Wat een zoekvraag is, los van de pagina: de zoekvraag van het resultaat (zonder `offset`) en het totaal. None voor
    een rij zonder zoekvraag (alleen gelezen)."""
    if not data or not isinstance(data.get("zoekvraag"), dict):
        return None
    return json.dumps([data["zoekvraag"], data.get("totaal")], sort_keys=True, ensure_ascii=False, default=str)


def leemte_tekst(c: ConnectorBeschrijving, data: dict[str, Any]) -> str:
    """De zin bij niets gevonden: de zoekvraag zonder volgorde, de kanttekening van de tool (waar de zoekvraag minder
    kon, meting Rechtspraak R07: een onvolledige lijst bleef "geen jurisprudentie gevonden") en dat niets gevonden geen
    bewijs is."""
    stukken = c.verzamelnamen[0] if c.verzamelnamen else "stukken"
    zoekvraag = zoekvraag_tekst(c, data.get("zoekvraag") or {}, volgorde=False)
    kant = str(data.get("kanttekening") or "").strip()
    return " ".join(filter(None, [f"Bij deze zoekvraag vond ik geen {stukken}.", zoekvraag, kant,
                                  "Dat ik niets vond, betekent niet dat het niet bestaat."]))


def niet_getoond_tekst(overgeslagen: list[str]) -> str:
    """De leemte voor wat de code in een antwoord wegliet, uit code: alleen hoeveel. De meldingen voor het model ("haal het
    vervolg op") horen niet in het antwoord."""
    aantal = len(overgeslagen)
    return (("Een aanwijzing in een bron naast de wet klopte" if aantal == 1 else
             f"{aantal} aanwijzingen in een bron naast de wet klopten")
            + " niet met wat er gelezen is en " + ("is" if aantal == 1 else "zijn") + " daarom niet als citaat getoond.")


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    """Het sjabloon `antwoord_extern`: kort antwoord, de lijst en de passages, en de twijfel. Een aanwijzing die niet
    klopt, laat de code weg als er iets anders te tonen is; anders weigert ze (meting bundel 114)."""
    lijst = lijsten(invoer.get(STUKKEN), trace)
    overgeslagen: list[str] = []
    gevonden = blokken(invoer.get(VELD), trace, overgeslagen=overgeslagen)
    if overgeslagen and not any(b.soort == "extern" for b in gevonden) and not lijst:
        blokken(invoer.get(VELD), trace)   # niets anders te tonen: de weigering zoals altijd
    if overgeslagen:
        gevonden = [*gevonden, Leemte(tekst=niet_getoond_tekst(overgeslagen))]
    if not gevonden and not lijst:
        raise Onvulbaar("Wijs minstens één passage of één gevonden stuk aan, of antwoord in tekst als je niets vond.")
    kort = str(invoer.get("kort_antwoord") or "").strip()
    if not kort:
        raise Onvulbaar("Schrijf een kort antwoord in eigen woorden.")
    punten = [str(p).strip() for p in invoer.get("twijfel") or [] if str(p).strip()]
    return Antwoord(sjabloon="extern", blokken=[Toelichting(tekst=kort), *lijst, *gevonden,
                                                 *([Twijfel(punten=punten)] if punten else [])])
