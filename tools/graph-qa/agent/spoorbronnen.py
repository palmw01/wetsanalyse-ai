"""Waar Lex kijkt, voor het denkproces: één register van spoorbronnen, intern en via een connector (ADR-013).

Het denkproces zegt per aanroep wat Lex doet ("Lex · leest Kamerstuk kst-33755-3") en daarna, als er iets te melden is,
wat de bron opleverde ("Kamerstukken · 16 gevonden", "Begrippen · niets gevonden", "Kamerstukken · niet bereikbaar").
Dat stond eerst in een tweede blok onder het antwoord, "Graaf geraadpleegd · N aanroepen", met toolnamen, ruwe JSON en
milliseconden; het heette "graaf" ook als Lex een Kamerstuk las (9 nov 2026).

Elke bron heeft dezelfde vorm (`Spoorbron`): een label, per tool de werkwoorden, en welke tools zoeken (treffers tellen)
en welke lezen (de tekst van één stuk; een aantal rijen zegt daar niets: een artikel zonder leden gaf "0 resultaten").
De interne bronnen staan hier; een connector wordt uit zijn beschrijving afgeleid (`uit_connector`), dus een nieuwe
connector staat in het denkproces zonder één regel in dit bestand. `tests/test_spoorbronnen.py` bewaakt dat.

Pure functies: zonder graaf te testen, en `narratie` en `tool_execution` delen ze.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bronmodel import connectors as _connectors

from .agent_common import truncate
from .resultaat import REDEN_ZIN


@dataclass(frozen=True)
class Spoorbron:
    #: De sleutel: in het `tool_execution`-event en op de statusregel (`bron`).
    naam: str
    #: Zoals de jurist hem in het denkproces leest ("Wetgeving", "Kamerstukken"); "Wetgeving" is ook het woord van het
    #: connectormenu.
    label: str
    #: Per tool een of meer vormen met `{argument}`; de eerste waarvan alle argumenten er zijn, telt. Dezelfde regel als
    #: `ConnectorBeschrijving.werkwoord`.
    werkwoorden: dict[str, tuple[str, ...]]
    #: Tools die treffers leveren: het aantal zegt hoe breed het antwoord rust.
    zoektools: frozenset[str]
    #: Tools die de tekst van één stuk leveren: geen aantal, wel "deels gelezen" als niet alles er is.
    leestools: frozenset[str]
    #: Per leestool het argument dat het stuk aanwijst ("kst-33755-3 deels gelezen").
    lees_id: dict[str, str] = field(default_factory=dict)
    #: De beschrijving waaruit hij is afgeleid; dan geldt haar `werkwoord`, niet een kopie ervan.
    connector: _connectors.ConnectorBeschrijving | None = None

    @property
    def tools(self) -> frozenset[str]:
        return self.zoektools | self.leestools

    def werkwoord(self, tool: str, waarden: dict[str, str]) -> str | None:
        if self.connector is not None:
            return self.connector.werkwoord(tool, waarden)
        vormen = self.werkwoorden.get(tool)
        return kies_vorm(vormen, waarden) if vormen else None


def kies_vorm(vormen: tuple[str, ...], invoer: dict[str, Any]) -> str:
    """De eerste vorm waarvan alle argumenten er zijn; anders de laatste zonder zijn gaten. De regel van
    `ConnectorBeschrijving.werkwoord` (een test zet ze naast elkaar)."""
    waarden = {k: str(v).strip() for k, v in (invoer or {}).items() if str(v).strip()}
    for vorm in vormen:
        nodig = re.findall(r"\{(\w+)\}", vorm)
        if all(n in waarden for n in nodig):
            return vorm.format(**{n: waarden[n] for n in nodig})
    return re.sub(r"\s*\{\w+\}", "", vormen[-1]).strip()


# De graaftools in de woorden van een jurist: "get_lid(BWBR0004770, 9, 1)" zei hem niets (acceptatie 7 nov 2026).
# `{bepaling}`, `{regeling}` en `{zoekterm}` vult `toolregel` altijd, met een terugval.
WETGEVING = Spoorbron(
    naam="wetgeving", label="Wetgeving",
    werkwoorden={
        "get_artikel": ("leest {bepaling}",), "get_lid": ("leest {bepaling}",), "get_bepaling": ("leest {bepaling}",),
        "get_bronnode": ("leest {bepaling}",),
        "get_context": ("bekijkt de samenhang rond {bepaling}",),
        "follow_verwijzingen": ("volgt de verwijzingen in {bepaling}",),
        "verwijst_naar_deze": ("zoekt wat naar {bepaling} verwijst",),
        "referenced_by": ("zoekt wat naar {bepaling} verwijst",),
        "geldigheid": ("kijkt sinds wanneer {bepaling} geldt",), "grondslagen": ("zoekt de grondslag van {bepaling}",),
        "search_wetgeving": ("zoekt {zoekterm}",), "semantic_search": ("zoekt {zoekterm}",),
        "zoek_opbouw": ("zoekt in de opbouw naar {zoekterm}",),
        "zoek_definitie": ("zoekt de definitie van {zoekterm}",), "resolve_begrip": ("zoekt het begrip {zoekterm}",),
        "list_regelingen": ("bekijkt welke regelingen er zijn",),
        "get_regeling_info": ("leest de gegevens van {regeling}",),
        "inhoudsopgave": ("bekijkt de opbouw van {regeling}",), "bijlagen": ("bekijkt de bijlagen van {regeling}",),
        "overzicht_onderwerp": ("maakt een overzicht van {zoekterm}",),
        "raw_sparql": ("raadpleegt de kennisgraaf met een eigen zoekvraag",),
        "graph_schema": ("bekijkt hoe de kennisgraaf is opgebouwd",),
    },
    zoektools=frozenset({"search_wetgeving", "semantic_search", "zoek_opbouw", "zoek_definitie", "resolve_begrip",
                         "list_regelingen", "overzicht_onderwerp", "verwijst_naar_deze", "referenced_by",
                         "follow_verwijzingen", "grondslagen", "bijlagen", "raw_sparql"}),
    leestools=frozenset({"get_artikel", "get_lid", "get_bepaling", "get_bronnode", "get_context", "geldigheid",
                         "get_regeling_info", "inhoudsopgave", "graph_schema"}),
)

ANNOTATIES = Spoorbron(
    naam="annotaties", label="Annotaties",
    werkwoorden={
        "search_annotaties": ("zoekt in de annotaties naar {klasse}", "zoekt in de annotaties"),
        "overzicht_annotaties": ("zet de annotaties van {klasse} op een rij", "zet de annotaties op een rij"),
        "get_annotatie": ("leest een annotatie",),
        "get_annotatiedekking": ("bekijkt wat er al geannoteerd is",),
        "get_annotatieweergave": ("leest de annotaties bij {bepaling}",),
    },
    zoektools=frozenset({"search_annotaties", "overzicht_annotaties"}),
    leestools=frozenset({"get_annotatie", "get_annotatiedekking", "get_annotatieweergave"}),
)

BEGRIPPEN = Spoorbron(
    naam="begrippen", label="Begrippen",
    werkwoorden={"search_begrippen": ("zoekt in de vastgelegde begrippen",), "get_begrip": ("leest een begrip",)},
    zoektools=frozenset({"search_begrippen"}), leestools=frozenset({"get_begrip"}),
)

METHODE = Spoorbron(
    naam="methode", label="Methode",
    werkwoorden={"jas_klasse_opvragen": ("leest de omschrijving van de JAS-klasse {klasse}",
                                         "leest de omschrijving van een JAS-klasse")},
    zoektools=frozenset(), leestools=frozenset({"jas_klasse_opvragen"}),
)

INTERN: tuple[Spoorbron, ...] = (WETGEVING, ANNOTATIES, BEGRIPPEN, METHODE)


def uit_connector(c: _connectors.ConnectorBeschrijving) -> Spoorbron:
    """De spoorbron van een connector, uit zijn beschrijving: wat hij leest is zijn leestool, de rest zoekt."""
    return Spoorbron(naam=c.naam, label=c.label, werkwoorden=dict(c.werkwoorden),
                     zoektools=frozenset(c.tools - {c.leestool}), leestools=frozenset({c.leestool}),
                     lees_id={c.leestool: c.lees_argument}, connector=c)


def bronnen() -> tuple[Spoorbron, ...]:
    """Alle spoorbronnen, de connectoren vers uit hun register (een nieuwe connector, ook in een test, telt meteen)."""
    return INTERN + tuple(uit_connector(c) for c in _connectors.CONNECTORS.values())


def bron_van(tool: str) -> Spoorbron | None:
    return next((b for b in bronnen() if tool in b.tools), None)


# --- wat Lex doet ------------------------------------------------------------------------------------------------

def _regeling(bwb_id: str) -> str:
    """De citeertitel als die al bekend is in dit proces (de namenlijst van het overzicht); anders het BWB-id."""
    from .overzicht import _REGELINGEN_CACHE
    return next((r["citeertitel"] for r in _REGELINGEN_CACHE if r.get("bwb_id") == bwb_id and r.get("citeertitel")), bwb_id)


def _afgeleid(inp: dict[str, Any]) -> dict[str, str]:
    """De velden die de interne werkwoorden gebruiken, altijd gevuld: "artikel 9, lid 1 (Invorderingswet 1990)"."""
    regeling = _regeling(str(inp.get("bwb_id") or "").strip()) if inp.get("bwb_id") else ""
    nummer = str(inp.get("artikel") or inp.get("nummer") or "").strip()
    bepaling = " ".join(x for x in (f"artikel {nummer}" if nummer else "", f"lid {inp['lid']}" if inp.get("lid") else "") if x)
    bepaling = (bepaling.replace(" lid", ", lid") + (f" ({regeling})" if regeling else "")) if bepaling else (regeling or "de bepaling")
    zoekterm = next((f"„{truncate(str(inp[k]).strip(), 60)}”" for k in ("query", "term", "zoekterm", "onderwerp")
                     if str(inp.get(k, "")).strip()), "")
    klassen = inp.get("jas_klassen")
    klasse = str(inp.get("klasse") or (", ".join(map(str, klassen)) if isinstance(klassen, list) else "")).strip()
    return {"bepaling": bepaling, "regeling": regeling or "de regeling", "zoekterm": zoekterm or "in de wetgeving",
            **({"klasse": klasse} if klasse else {})}


def toolregel(call: dict[str, Any]) -> str:
    """"leest artikel 9, lid 1 (Invorderingswet 1990)" – wat Lex doet, en waarnaar hij kijkt. Een tool die geen bron
    kent, heet "raadpleegt de kennisgraaf"; `tests/test_spoorbronnen.py` zorgt dat dat niet voorkomt."""
    naam = str(call.get("name", ""))
    inp = call.get("input") or {}
    bron = bron_van(naam)
    if bron is None:
        return "raadpleegt de kennisgraaf"
    waarden = dict(inp) if bron.connector is not None else {**inp, **_afgeleid(inp)}
    return (bron.werkwoord(naam, waarden) or "raadpleegt de kennisgraaf").strip()


# --- wat de bron opleverde ---------------------------------------------------------------------------------------

def _getal(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def uitkomstregel(tool: str, invoer: dict[str, Any], eind: dict[str, Any], data: dict[str, Any] | None = None) -> str:
    """Wat de bron opleverde, voor de jurist; leeg als er niets te melden is.

    - een fout: in woorden (`resultaat.REDEN_ZIN`), nooit de code;
    - een zoekaanroep: "niets gevonden", "16 gevonden", "10 van 1.218 gevonden";
    - niet alles opgehaald: "er is meer dan dit", bij een leestool "kst-33755-3 deels gelezen, er is meer dan dit".

    Een leestool krijgt geen aantal: dat telt rijen, geen inhoud. Het `peilmoment` van de annotatiedekking ook niet: dat
    is het moment van opvragen, dus "nu", en zei bij elke annotatie hetzelfde.
    """
    data = data or {}
    bron = bron_van(tool)
    if eind.get("status") not in ("ok", "partial"):
        return REDEN_ZIN.get(str(eind.get("foutcode") or data.get("reden") or ""), "gaf een fout")
    delen: list[str] = []
    zoekt = bron is not None and tool in bron.zoektools
    aantal, totaal = eind.get("aantal"), data.get("totaal")
    meer = bool(eind.get("has_more"))
    if zoekt and isinstance(aantal, int):
        if aantal == 0 and not meer:
            delen.append("niets gevonden")
        elif isinstance(totaal, int) and totaal > aantal:
            delen.append(f"{_getal(aantal)} van {_getal(totaal)} gevonden")
            meer = False
        else:
            delen.append(f"{_getal(aantal)} gevonden")
    if meer:
        arg = bron.lees_id.get(tool) if bron is not None and not zoekt else None
        stuk = str((invoer or {}).get(arg) or "").strip() if arg else ""
        delen.append("er is meer dan dit" if zoekt else f"{stuk + ' ' if stuk else ''}deels gelezen, er is meer dan dit")
    return ", ".join(delen)
