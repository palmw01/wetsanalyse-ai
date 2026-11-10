"""Bronnen naast de wet in een antwoord (ADR-008 + ADR-013): het blok `extern`, als subsjabloon en als eigen sjabloon.

Een antwoord met een Kamerstuk (of later een uitspraak, EU-recht) krijgt een vaste vorm in plaats van vrije tekst
waarin de wetsgeschiedenis door de uitleg loopt. Eén herbruikbaar blok, generiek per brontype:

- **Als subsjabloon.** De sjablonen van een specialist die een connector bedient (`ConnectorBeschrijving.specialisten`)
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
import re
from typing import Any

from bronmodel.antwoord import Antwoord, Extern, ExternePassage, ExterneVerwijzing, Stuk, Stukken, Toelichting, Twijfel
from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving, van_id
from bronmodel.extern import externe_vindplaats

from .vullen import Onvulbaar, Trace, _data, resultaten

#: Zo veel passages mag één aanwijzing omvatten: meer is een samenvatting, en die schrijft Lex in eigen woorden.
MAX_PASSAGES = 6
#: Zo veel stukken per antwoord.
MAX_STUKKEN = 4

VELD = "extern"
#: Het veld voor een lijst gevonden stukken (`Stukken`): alleen de ids, de rest komt uit de zoekrijen.
STUKKEN = "stukken"
#: Zo veel stukken per lijst; meer is geen antwoord maar een zoekresultaat.
MAX_LIJST = 25

ITEMS: dict[str, Any] = {
    "type": "array",
    "description": (
        "Passages uit een bron naast de wet (een Kamerstuk, later een uitspraak) die je in dit gesprek met de leestool "
        "ophaalde: per stuk het id en het eerste en laatste alineanummer. Schrijf de tekst niet uit, de code neemt hem "
        "uit de bron. Leeg als het antwoord zo'n bron niet gebruikt. Een bron naast de wet onderbouwt nooit wat de wet zegt."),
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Het id van het stuk uit het toolresultaat, bijvoorbeeld 'kst-33755-3'."},
            "van_nr": {"type": "integer", "description": "Het nummer (nr) van de eerste alinea."},
            "tot_nr": {"type": "integer", "description": "Het nummer (nr) van de laatste alinea; gelijk aan van_nr voor één alinea."},
        },
        "required": ["id", "van_nr", "tot_nr"],
        "additionalProperties": False,
    },
}

STUKKEN_ITEMS: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string"},
    "description": (
        "Een lijst stukken die een zoektool van een bron naast de wet in dit gesprek vond, zoals 'de tien nieuwste "
        "Kamerstukken' of 'het laatste stuk van dossier 32140': alleen hun ids (kst-…), in de volgorde van het "
        f"zoekresultaat, hoogstens {MAX_LIJST}. De code toont per stuk het label, soort, datum en titel uit de bron, met "
        "de zoekvraag en het totaal. Schrijf de lijst of hun datums niet zelf uit. Leeg als het antwoord geen lijst geeft."),
}

SCHEMA: dict[str, Any] = {
    "name": "antwoord_extern",
    "description": (
        "Rond een vraag af die alleen over een bron naast de wet gaat (wetsgeschiedenis, later rechtspraak): wat staat er in "
        "dit stuk, wat zegt de memorie van toelichting hierover. Roep deze tool aan nadat je het stuk hebt opgehaald, en "
        "schrijf geen antwoord ernaast. Jij schrijft het korte antwoord in eigen woorden en wijst de passages aan; de code "
        "toont ze letterlijk met hun vindplaats. Gaat de vraag (ook) over wat de wet zegt, gebruik dan het sjabloon voor "
        "de bepaling of de uitleg, met de passages in hun veld 'extern'."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "kort_antwoord": {"type": "string", "description": "Het antwoord in twee tot vier zinnen, in eigen woorden en zonder citaten."},
            VELD: ITEMS,
            STUKKEN: STUKKEN_ITEMS,
            "twijfel": {"type": "array", "items": {"type": "string"},
                        "description": "Aannames en wat de opgehaalde tekst open laat, elk als één punt. Leeg als die er niet zijn."},
        },
        "required": ["kort_antwoord", VELD, STUKKEN, "twijfel"],
        "additionalProperties": False,
    },
}


def met_veld(schema: dict[str, Any]) -> dict[str, Any]:
    """Een sjabloonschema met het veld `extern` erbij: het subsjabloon. Het origineel blijft ongemoeid."""
    uit = copy.deepcopy(schema)
    invoer = uit["input_schema"]
    for veld, items in ((VELD, ITEMS), (STUKKEN, STUKKEN_ITEMS)):
        invoer["properties"][veld] = copy.deepcopy(items)
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
            lezingen.append((s, [r for r in data.get("resultaten") or []
                                 if isinstance(r, dict) and isinstance(r.get("nr"), int) and isinstance(r.get("tekst"), str)]))
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


def blokken(items: Any, trace: Trace) -> list[Extern]:
    """De blokken `extern` uit de aanwijzingen van het model; elk feit uit de trace."""
    if not items:
        return []
    if not isinstance(items, list) or len(items) > MAX_STUKKEN * 2:
        raise Onvulbaar(f"'{VELD}' is een lijst van hoogstens {MAX_STUKKEN * 2} aanwijzingen.")
    per_stuk: dict[str, Extern] = {}
    for item in items:
        ident = str((item or {}).get("id") or "").strip()
        vp = externe_vindplaats(ident)
        c = van_id(ident)
        if vp is None or c is None:
            raise Onvulbaar(f"'{ident}' is geen id van een bron naast de wet die hier aanstaat.")
        stuk, rijen, alleen_eerder, in_tabel = _gelezen(trace, c, vp.id)
        if not stuk:
            raise Onvulbaar(f"{vp.label} is in dit gesprek niet gelezen: haal het stuk eerst op met {c.leestool}, en wijs "
                            "dan de passages aan.")
        van, tot = item.get("van_nr"), item.get("tot_nr")
        if not isinstance(van, int) or not isinstance(tot, int) or van > tot:
            raise Onvulbaar(f"{vp.label}: van_nr en tot_nr zijn alineanummers, met van_nr ≤ tot_nr.")
        if sum(1 for n in range(van, tot + 1) if n not in in_tabel) > MAX_PASSAGES:
            raise Onvulbaar(f"{vp.label}: hoogstens {MAX_PASSAGES} alinea's per aanwijzing; vat de rest in eigen woorden samen.")
        ontbreekt = [n for n in range(van, tot + 1) if n not in rijen and n not in in_tabel]
        if ontbreekt and set(ontbreekt) & alleen_eerder:
            raise Onvulbaar(f"{vp.label} is veranderd sinds alinea {', '.join(map(str, sorted(set(ontbreekt) & alleen_eerder)))} "
                            f"gelezen werd. Haal het stuk opnieuw op met {c.leestool}, en wijs de passages aan in de "
                            "versie van nu.")
        if ontbreekt:
            raise Onvulbaar(f"{vp.label}: alinea {', '.join(map(str, ontbreekt))} is niet opgehaald. Haal het vervolg op, "
                            "of wijs alinea's aan die in het resultaat staan.")
        blok = per_stuk.setdefault(vp.id, Extern(
            brontype=vp.brontype, id=vp.id, label=str(stuk.get("label") or vp.label),
            link=str(stuk.get("link") or vp.uri), kop=c.kop_in_antwoord, passages=[],
            bron_hash=str(stuk.get("bron_hash") or ""), gewijzigd=str(stuk.get("gewijzigd") or ""),
            datum=str(stuk.get("datum") or ""), soort_stuk=str(stuk.get("soort") or "")))
        al = {p.nr for p in blok.passages}
        blok.passages += [ExternePassage(nr=n, tekst=rijen[n]["tekst"], kop=str(rijen[n].get("kop") or ""),
                                         soort=str(rijen[n].get("soort") or "alinea"),
                                         cellen=[str(x) for x in rijen[n]["cellen"]] if isinstance(rijen[n].get("cellen"), list)
                                         else None, verwijst_naar=_verwijzingen(rijen[n]))
                          for n in range(van, tot + 1) if n not in al and n in rijen]
    if len(per_stuk) > MAX_STUKKEN:
        raise Onvulbaar(f"Hoogstens {MAX_STUKKEN} stukken per antwoord.")
    for b in per_stuk.values():
        b.passages.sort(key=lambda p: p.nr)
    return list(per_stuk.values())


#: De volgordes in de woorden van de jurist: een eigen zin onder de lijst.
_VOLGORDE_TEKST = {"nieuwste": "Nieuwste eerst.", "oudste": "Oudste eerst.", "nummer": "Op nummer.",
                   "relevantie": "Meest relevante eerst."}


_AANHALING = re.compile(r'["„”]')


def _voluit(datum: str) -> str:
    """'2024-01-01' → '1 januari 2024'; iets anders blijft staan."""
    from ..hoeveelheden import _MAANDEN

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(datum))
    return f"{int(m.group(3))} {_MAANDEN[int(m.group(2)) - 1]} {m.group(1)}" if m and 1 <= int(m.group(2)) <= 12 else str(datum)


def _opsomming(delen: list[str]) -> str:
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " en " + delen[-1]


def zoekvraag_tekst(c: ConnectorBeschrijving, zoekvraag: dict[str, Any]) -> str:
    """De zoekvraag onder een lijst, in gewone zinnen: "Gezocht op „invorderingsrente” in de tekst, vergaderjaar
    2025-2026 en van de Eerste Kamer. Meest relevante eerst." Uit de code, met de labels uit de metadata van de
    beschrijving (`ConnectorBeschrijving.filters`); de vorm per soort veld (`MetadataVeld.sleutel`), dus voor elke
    connector. Een waarde die al zegt wat ze is ("Eerste Kamer") krijgt geen label ervoor (acceptatie 9 nov 2026:
    "Kamer Eerste Kamer")."""
    delen: list[str] = []
    periode: dict[str, str] = {}
    for arg, waarde in zoekvraag.items():
        if arg in {"volgorde", "aantal", "offset"} or waarde in ("", None):
            continue
        veld = c.filters.get(arg)
        sleutel = veld.sleutel if veld else ""
        if arg == "tekst":
            kaal = " ".join(_AANHALING.sub(" ", str(waarde)).split())
            delen.append(f"„{kaal}” in de tekst")
        elif sleutel == "titel":
            delen.append(f"„{waarde}” in de titel")
        elif veld is not None and veld.type == "datum":
            periode["vanaf" if arg == veld.filters[0] else "tot"] = _voluit(str(waarde))
        elif sleutel == "orgaan":
            delen.append(f"van de {waarde}")
        elif sleutel == "soort":
            delen.append(f"{veld.label} „{waarde}”")
        elif veld is not None:
            delen.append(f"{veld.label} {waarde}")
        else:
            delen.append(f"{arg} {waarde}")
    if periode.get("vanaf") and periode.get("tot"):
        delen.append(f"van {periode['vanaf']} tot en met {periode['tot']}")
    elif periode.get("vanaf"):
        delen.append(f"vanaf {periode['vanaf']}")
    elif periode.get("tot"):
        delen.append(f"tot en met {periode['tot']}")
    zinnen = [f"Gezocht op {_opsomming(delen)}." if delen else "",
              _VOLGORDE_TEKST.get(str(zoekvraag.get("volgorde") or ""), "")]
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
            uit[data["stuk"]["id"]] = (data["stuk"], None, plek * 1000)
    return uit


def lijsten(items: Any, trace: Trace) -> list[Stukken]:
    """De lijsten `stukken` uit de ids die het model aanwees, één per connector. Elk feit uit de zoekrijen, in hun
    volgorde; een id dat niet gevonden is, is `Onvulbaar` (zoek het eerst)."""
    if not items:
        return []
    if not isinstance(items, list) or len(items) > MAX_LIJST:
        raise Onvulbaar(f"'{STUKKEN}' is een lijst van hoogstens {MAX_LIJST} ids.")
    per: dict[str, list[tuple[int, dict[str, Any], dict[str, Any] | None]]] = {}
    gevonden: dict[str, dict[str, tuple[dict[str, Any], dict[str, Any] | None, int]]] = {}
    for item in items:
        ident = str(item or "").strip()
        vp, c = externe_vindplaats(ident), van_id(ident)
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
    uit: list[Stukken] = []
    for naam, rijen in per.items():
        c = CONNECTORS[naam]
        rijen.sort(key=lambda x: x[0])
        bronnen = {id(d) for _, _, d in rijen}
        data = rijen[0][2] if len(bronnen) == 1 else None
        zoekvraag = data.get("zoekvraag") if data and isinstance(data.get("zoekvraag"), dict) else {}
        totaal = data.get("totaal") if data and isinstance(data.get("totaal"), int) else None
        velden = set(Stuk.model_fields)
        uit.append(Stukken(
            brontype=c.brontype, kop=f"Gevonden {c.label}",
            items=[Stuk(**{k: v for k, v in r.items() if k in velden}) for _, r, _ in rijen],
            zoekvraag=zoekvraag_tekst(c, zoekvraag), totaal=totaal))
    return uit


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    """Het sjabloon `antwoord_extern`: kort antwoord, de lijst en de passages, en de twijfel."""
    lijst = lijsten(invoer.get(STUKKEN), trace)
    gevonden = blokken(invoer.get(VELD), trace)
    if not gevonden and not lijst:
        raise Onvulbaar("Wijs minstens één passage of één gevonden stuk aan, of antwoord in tekst als je niets vond.")
    kort = str(invoer.get("kort_antwoord") or "").strip()
    if not kort:
        raise Onvulbaar("Schrijf een kort antwoord in eigen woorden.")
    punten = [str(p).strip() for p in invoer.get("twijfel") or [] if str(p).strip()]
    return Antwoord(sjabloon="extern", blokken=[Toelichting(tekst=kort), *lijst, *gevonden,
                                                 *([Twijfel(punten=punten)] if punten else [])])
