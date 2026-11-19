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
from bronmodel.antwoord import getal

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
    zoekterm = next((f"“{truncate(str(inp[k]).strip(), 60)}”" for k in ("query", "term", "zoekterm", "onderwerp")
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
    if bron.connector is not None and str(inp.get("bwb_id") or "").strip():
        # Ook bij een connector de naam van de regeling, als die in dit proces bekend is: "bij artikel 36 van
        # Invorderingswet 1990" in plaats van "van BWBR0004770" (nameting 10 nov 2026).
        waarden["bwb_id"] = _regeling(str(inp["bwb_id"]).strip())
    regel = (bron.werkwoord(naam, waarden) or "raadpleegt de kennisgraaf").strip()
    if bron.connector is not None:
        regel += _filters_erbij(bron.connector, inp, regel)
    elif naam in bron.zoektools:
        regel += _afbakening_erbij(inp, regel)
    return regel


#: De afbakening van een zoekactie in de graaf (`search_wetgeving`: `veld`, `soort`, `bwb_id`), in de woorden van een
#: jurist. Twee zoekacties op "derdenbeslag", één in de definities en één in alle tekst, heetten anders allebei "zoekt
#: “derdenbeslag”", met twee verschillende uitkomsten eronder (acceptatie 19 nov 2026). De regel van `_filters_erbij`.
_VELDEN = {
    "tekst": "in de tekst", "titel": "in de titels", "citeertitel": "op de naam van een regeling",
    "opschrift": "in de opschriften", "aanhef": "in de aanhef", "considerans": "in de considerans",
    "voetnoot": "in de voetnoten", "definieertBegrip": "in de definities", "label": "op het nummer",
}


def _afbakening_erbij(invoer: dict[str, Any], regel: str) -> str:
    delen: list[str] = []
    veld = str((invoer or {}).get("veld") or "").strip()
    if veld:
        delen.append(_VELDEN.get(veld, f"in het veld {veld}"))
    soort = str((invoer or {}).get("soort") or "").strip()
    if soort:
        delen.append(f"alleen {soort.casefold()}")
    bwb_id = str((invoer or {}).get("bwb_id") or "").strip()
    if bwb_id and (regeling := _regeling(bwb_id)) not in regel:
        delen.append(f"in {regeling}")
    return f" ({', '.join(delen)})" if delen else ""


#: Argumenten die geen afbakening zijn maar de vorm van het antwoord: die horen niet in de regel.
_GEEN_AFBAKENING = frozenset({"volgorde", "aantal", "offset", "limit", "inhoud", "doel"})


def _filters_erbij(c: _connectors.ConnectorBeschrijving, invoer: dict[str, Any], regel: str) -> str:
    """De filters van een aanroep die het werkwoord niet noemt, met het label uit de beschrijving: " (soort stuk memorie
    van toelichting)". Drie zoekacties op hetzelfde dossier met een ander soort stuk heetten anders drie keer hetzelfde
    (E2E Rekeningafspraken 16 nov 2026, D-8). Uit `ConnectorBeschrijving.filters`, dus voor elke connector."""
    delen: list[str] = []
    for arg, veld in c.filters.items():
        waarde = str((invoer or {}).get(arg) or "").strip()
        if not waarde or arg in _GEEN_AFBAKENING or arg in {"bwb_id", "artikel"} or waarde[:60] in regel:
            continue
        label = veld.label if len(veld.filters) == 1 else f"{veld.label} {'vanaf' if arg == veld.filters[0] else 'tot'}"
        delen.append(f"{label} {truncate(waarde, 60)}")
    return f" ({', '.join(dict.fromkeys(delen))})" if delen else ""


#: Waarom de code een aanroep van het model niet uitvoerde, als zin achter "niet uitgevoerd". Een reden die hier niet staat,
#: krijgt haar zin uit `resultaat.REDEN_ZIN`.
WEIGERING: dict[str, str] = {
    "na_subagent": "na de subagent leest Lex niet zelf opnieuw",
    "tool_buiten_profiel": "deze tool hoort niet bij de agent",
    "stukken_plafond": "meer stukken lezen doet een subagent",
}


def weigerregel(call: dict[str, Any], reden: str) -> str:
    """"leest artikel 7a, lid 4 (Wet X) – niet uitgevoerd: na de subagent leest Lex niet zelf opnieuw". Een stap die het
    model aankondigde en die de code weigerde, staat zo in het denkproces; anders las de jurist "Laat me eerst artikel 7a
    lid 4 ophalen" en daarna niets (E2E Rekeningafspraken 16 nov 2026, D-5)."""
    return f"{toolregel(call)} – niet uitgevoerd: {WEIGERING.get(reden) or REDEN_ZIN.get(reden, 'geweigerd')}"


# --- wat de bron opleverde ---------------------------------------------------------------------------------------

_getal = getal


def stuk_van(tool: str, invoer: dict[str, Any]) -> str:
    """Het stuk dat een leestool leest, in de woorden van het denkproces: het id bij een connector ("kst-33755-3"), de
    bepaling of de regeling bij de kennisgraaf ("artikel 9, lid 1 (Invorderingswet 1990)"), en leeg als de aanroep geen
    stuk aanwijst (de dekking van de annotaties, het schema van de graaf)."""
    bron = bron_van(tool)
    invoer = invoer or {}
    if bron is None or tool not in bron.leestools:
        return ""
    if bron.connector is not None or tool in bron.lees_id:
        arg = bron.lees_id.get(tool)
        return str(invoer.get(arg) or "").strip() if arg else ""
    if any(str(invoer.get(k) or "").strip() for k in ("artikel", "nummer", "bwb_id")):
        afgeleid = _afgeleid(invoer)
        return afgeleid["bepaling"] if (invoer.get("artikel") or invoer.get("nummer")) else afgeleid["regeling"]
    return ""


def zoekt_binnen(tool: str, invoer: dict[str, Any]) -> bool:
    """Zoekt deze aanroep van een leestool binnen één stuk ("zoekt in Kamerstuk kst-34002-3 naar “rente”")? Dat zegt het
    werkwoord dat de bron voor deze argumenten declareert; dan telt het aantal rijen als treffers, net als bij een zoektool
    (E2E Rekeningafspraken 16 nov 2026, D-2: van twee zoekacties in één stuk stond alleen de ene met een uitkomst er)."""
    bron = bron_van(tool)
    return bron is not None and tool in bron.leestools and toolregel({"name": tool, "input": invoer}).startswith("zoekt ")


def uitkomstregel(tool: str, invoer: dict[str, Any], eind: dict[str, Any], data: dict[str, Any] | None = None) -> str:
    """Wat de bron opleverde, voor de jurist. **Nooit leeg**: elke aanroep die draaide, heeft een uitkomst in het
    denkproces, zodat wie meeleest per stap ziet wat er gelezen en gevonden is (E2E Rekeningafspraken 16 nov 2026, D-2 en
    D-3: van 22 leesacties hadden er 17 een regel, en een gelezen stuk zonder iets bijzonders zweeg).

    - een fout: in woorden (`resultaat.REDEN_ZIN`), nooit de code;
    - een zoekaanroep: "niets gevonden", "16 gevonden", "10 van 1.218 gevonden"; met een `uitsplitsing` van de tool die
      delen ("2 met deze naam, 7 waarin de term voorkomt");
    - zoeken binnen één stuk (`zoekt_binnen`): "kst-34002-3: 6 gevonden", "kst-34002-G: niets gevonden";
    - een gelezen stuk: "kst-33755-3 gelezen", "artikel 9, lid 1 (Invorderingswet 1990) gelezen";
    - niet alles opgehaald: "er is meer dan dit", bij een leestool "kst-33755-3 deels gelezen, er is meer dan dit";
    - een stuk zonder tekst (`leesbaar: false`): "ECLI:NL:GHARL:2023:5000 heeft geen tekst om te lezen";
    - de inhoud van een stuk zonder koppen (`zonder_koppen`): "kst-30322-3 heeft geen koppen, 210 alinea’s".

    Een leestool krijgt geen aantal: dat telt rijen, geen inhoud. Het `peilmoment` van de annotatiedekking ook niet: dat
    is het moment van opvragen, dus "nu", en zei bij elke annotatie hetzelfde.
    """
    data = data or {}
    invoer = invoer or {}
    bron = bron_van(tool)
    if eind.get("status") not in ("ok", "partial"):
        return REDEN_ZIN.get(str(eind.get("foutcode") or data.get("reden") or ""), "gaf een fout")
    aantal, totaal = eind.get("aantal"), data.get("totaal")
    meer = bool(eind.get("has_more"))
    stuk = stuk_van(tool, invoer)
    voor = f"{stuk} " if stuk else ""
    leest = bron is not None and tool in bron.leestools
    binnen = leest and zoekt_binnen(tool, invoer)
    if (not leest or binnen) and isinstance(aantal, int):
        if aantal == 0 and not meer:
            telling = "niets gevonden"
        elif isinstance(totaal, int) and totaal > aantal:
            telling, meer = f"{_getal(aantal)} van {_getal(totaal)} gevonden", False
        else:
            telling = f"{_getal(aantal)} gevonden"
        # Een tool die zijn treffers zelf uitsplitst (`search_begrippen`: met deze naam, en waarin de term voorkomt):
        # de jurist leest wat er telt, niet alleen een totaal dat groter is dan wat het antwoord toont.
        if (delen := [(n, w) for n, w in (data.get("uitsplitsing") or []) if isinstance(n, int) and n >= 0 and w]
                ) and sum(n for n, _ in delen) == aantal:
            telling = ", ".join(f"{_getal(n)} {w}" for n, w in delen)
        return (f"{stuk}: " if binnen and stuk else "") + telling + (", er is meer dan dit" if meer else "")
    if not leest:
        return "opgehaald" + (", er is meer dan dit" if meer else "")
    if data.get("zonder_koppen") and aantal == 0:
        # Geen koppen is iets anders dan geen tekst: het stuk is gewoon te lezen (ronde 1 Kamerstukken, 11 nov 2026).
        n = data.get("alineas")
        return f"{voor}heeft geen koppen" + (f", {_getal(n)} {'alinea' if n == 1 else 'alinea’s'}"
                                              if isinstance(n, int) else "")
    if (data.get("stuk") or {}).get("leesbaar") is False and aantal == 0:
        # Een stuk zonder tekst bij de bron (een uitspraak met alleen metadata): anders zweeg het denkproces (meting
        # 10 nov). Alleen dan: nul rijen na een filter is nog geen stuk zonder tekst.
        return f"{voor}heeft geen tekst om te lezen"
    if meer:
        return f"{voor}deels gelezen, er is meer dan dit"
    if bron.connector is not None and aantal == 0 and not meer:
        # Nul rijen na een filter (een artikel, een regeling): het stuk is er, maar bij deze afbakening staat er niets.
        return f"{stuk + ': ' if stuk else ''}niets bij deze afbakening"
    return f"{voor}gelezen"


def voorleesregel(tool: str, invoer: dict[str, Any], paginas: int, volledig: bool) -> str:
    """Eén regel voor een stuk dat de code zelf doorlas (`nodes/bron_lezen.py`): "kst-33755-3 gelezen, 7 pagina’s". Elke
    pagina meldde zich eerst als "deels gelezen, er is meer dan dit", zes keer voor één stuk (iteratie bekendmakingen
    ronde 4, B21). Is het stuk na de laatste pagina nog niet uit, dan zegt de regel dat."""
    bron = bron_van(tool)
    arg = bron.lees_id.get(tool) if bron is not None else None
    stuk = str((invoer or {}).get(arg) or "").strip() if arg else ""
    voor = f"{stuk} " if stuk else ""
    wat = f"{_getal(paginas)} {'pagina' if paginas == 1 else 'pagina’s'}"
    return f"{voor}gelezen, {wat}" if volledig else f"{voor}deels gelezen ({wat}), er is meer dan dit"
