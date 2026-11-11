"""De tekst van een bepaling zonder modelronde: laag 2 van ADR-010 (de eerste vaste workflow, D1).

"Wat staat er in artikel 9, eerste lid, van de Invorderingswet 1990?" kostte vier modelaanroepen en 42k tokens: de
supervisor, het BWB-id zoeken dat in de vraag stond, het lid ophalen, en afronden met het sjabloon, waarbij het model de
IRI aanwees die de code al kende (acceptatie, 7 nov 2026). Hier doet de code dat werk: de vraag lezen, ophalen, en het
sjabloon `bepaling` vullen. Het model schrijft hoogstens een korte toelichting; dat zit niet in deze module.

Alleen bij één eenduidige lezing: een tekstvraag, precies één regeling bij naam of afkorting, precies één artikel en
hoogstens één lid. Anders `None`, en de vraag gaat de gewone weg. Deze module gokt nooit en zoekt niet.

**Wettekst van overheid.nl** (connector `wetgeving_live`, ADR-013 fase 1e) loopt langs dezelfde weg (`live`): een artikel
van een regeling buiten de kennisgraaf (`lees_buiten`, met de herkenning uit `buiten_graaf`), of een eerdere of
toekomstige tekst van een regeling in de graaf, als de peildatum van de vraag buiten de graaftoestand valt (`lees`). De
code leest het hele artikel met `get_wettekst` (alle pagina's) en toont het in het blok `extern`; het model schrijft
alleen de toelichting. Zonder deze route bladerde het model zelf door het artikel, zonder sjabloon en dus zonder
controle: 131k en 144k tokens, en "Klaar · 0 bronnen" (meting 11 nov 2026, W07 en W15).
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from bronmodel.antwoord import Antwoord

from .aanwijzing import lees_aanwijzing
from .graph import queries
from .hoeveelheden import buiten as hoeveelheden_buiten
from .llm_stap import Rol, Stopreden, aanroep
from .overzicht import regelingen_in_vraag
from .ports import GraphPort, LLMPort
from .sjablonen import Onvulbaar
from .sjablonen import vul as vul_sjabloon
from .tools import dispatch

logger = logging.getLogger(__name__)

# Een vraag naar de tekst zelf. Uitleg ("wat betekent", "wat houdt … in", "waarom", "hoe verhoudt") is duiding en valt
# hier bewust buiten: die gaat naar de open laag.
_TEKSTVRAAG = re.compile(
    r"^\s*(?:wat\s+(?:staat|stond)\s+er\s+(?:[^?]{0,40}?\s)?in|wat\s+(?:zegt|zei)|wat\s+is\s+de\s+(?:letterlijke\s+)?tekst\s+van"
    r"|geef\s+(?:me\s+|mij\s+)?(?:de\s+(?:letterlijke\s+)?tekst\s+van|letterlijk)|citeer|toon\s+(?:me\s+|mij\s+)?(?:de\s+tekst\s+van)?)\b",
    re.IGNORECASE,
)
#: Een datum in de vraag ("op 1 januari 2020", "2020-01-01"): de peildatum. Meer dan één datum is geen eenduidige vraag.
_DATUM_NL = re.compile(r"(?<!\d)(\d{1,2})\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|"
                       r"november|december)\s+(\d{4})(?!\d)", re.IGNORECASE)
_DATUM_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_MAAND = {m: i for i, m in enumerate(("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                                      "september", "oktober", "november", "december"), start=1)}
_UITLEG = re.compile(r"\b(?:betekent|betekenis|houdt\b.*\bin\b|waarom|verhoudt|uitleg|leg\s+uit|bedoeld|toepass)", re.IGNORECASE)

#: Zoveel pagina's per aanroep haalt de workflow hoogstens op; daarboven is hij niet zeker van een hele tekst.
MAX_PAGINAS = 8


@dataclass(frozen=True)
class Bepalingsvraag:
    """Wat de vraag eenduidig aanwijst. `lid` is leeg voor het hele artikel."""

    bwb_id: str
    artikel: str
    lid: str = ""
    #: De tekst komt van overheid.nl (`get_wettekst`), niet uit de graaf; `peildatum` is dan de gevraagde datum (leeg:
    #: vandaag).
    live: bool = False
    peildatum: str = ""

    @property
    def iri(self) -> str:
        if self.lid:
            return queries.lid_iri(self.bwb_id, self.artikel, self.lid)
        return queries.artikel_iri(self.bwb_id, self.artikel)


def peildatum_in(vraag: str) -> str | None:
    """De ene datum die de vraag noemt, als JJJJ-MM-DD; `None` zonder datum, "" bij meer dan één (niet eenduidig)."""
    datums = {f"{int(j):04d}-{_MAAND[m.lower()]:02d}-{int(d):02d}" for d, m, j in _DATUM_NL.findall(vraag or "")}
    datums |= {f"{j}-{m}-{d}" for j, m, d in _DATUM_ISO.findall(vraag or "")}
    if not datums:
        return None
    return next(iter(datums)) if len(datums) == 1 else ""


#: Woorden voor een stuk naast de wet. "Wat zegt het arrest over artikel 36" vraagt naar het arrest, niet naar de wettekst.
_STUKWOORD = re.compile(r"\b(?:arrest(?:en)?|uitspra(?:ak|ken)|vonnis(?:sen)?|kamerstuk(?:ken)?|kamerbrie(?:f|ven)|memorie|"
                        r"staatsblad(?:en)?|staatscourant(?:en)?|bekendmaking(?:en)?|ecli)\b", re.IGNORECASE)


def wijst_stuk_aan(vraag: str) -> bool:
    """Wijst de vraag een stuk naast de wet aan? Een genoemd id of citeervorm (`genoemde_stukken`), een signaal van een
    connector die geen wettekst levert, of een stukwoord. Dan is het geen vraag naar de tekst van een bepaling, ook als er
    een artikel in staat (R28b, rechtspraak 11 nov 2026: "wat zegt de nieuwste daarvan" na een lijst arresten bij art. 36
    Iw las art. 36 live in plaats van het arrest)."""
    from bronmodel.connectors import CONNECTORS, genoemde_stukken

    if _STUKWOORD.search(vraag or ""):
        return True
    if any(c.brontype != "wettekst_live" for c, _ in genoemde_stukken(vraag or "")):
        return True
    return any(c.brontype != "wettekst_live" and c.herkent(vraag or "") for c in CONNECTORS.values())


def _is_tekstvraag(vraag: str) -> bool:
    return bool(_TEKSTVRAAG.search(vraag)) and not _UITLEG.search(vraag) and not wijst_stuk_aan(vraag)


def lees(vraag: str, graph: GraphPort, *, live_aan: bool = False, getypt: str | None = None) -> Bepalingsvraag | None:
    """De bepaling die de vraag eenduidig aanwijst, of `None`. Leest de regelingnamen uit de graaf (gecachet).

    Noemt de vraag een peildatum buiten de toestand van de graaf ("wat zei artikel 9 Iw op 1 januari 2020?"), dan is de
    graaftekst niet de gevraagde tekst: met de connector aan (`live_aan`) leest de code de tekst van die datum bij
    overheid.nl, anders `None` (de agent zegt wat de graaf heeft). Een peildatum binnen de graaftoestand is gewoon de graaf.

    `getypt` is wat de jurist zelf typte, als `vraag` een herschreven vervolgvraag is. Een datum telt alleen als peildatum
    als de jurist hem typte: een herschrijving neemt ook de datum van een stuk uit de vorige beurt over (de uitspraak van
    10 april 2026), en dat is geen vraag naar de tekst op die dag (R28b). Zo'n vraag gaat de gewone weg."""
    if not _is_tekstvraag(vraag):
        return None
    aanwijzing = lees_aanwijzing(vraag)
    if len(aanwijzing.artikelen) != 1 or len(aanwijzing.leden) > 1:
        return None
    artikel = aanwijzing.artikelen[0]
    # Een divisie van een beleidsregel ("25.1") loopt via `get_bepaling`: geen artikel. Die vorm volgt later.
    if not queries.is_artikelnummer(artikel):
        return None
    regelingen = regelingen_in_vraag(graph, vraag)
    if len(regelingen) != 1:
        return None
    v = Bepalingsvraag(bwb_id=regelingen[0], artikel=artikel, lid=aanwijzing.leden[0] if aanwijzing.leden else "")
    peil = peildatum_in(vraag)
    if peil is None:
        return v
    if not peil or (getypt is not None and peildatum_in(getypt) != peil):
        return None
    from .tools.wetgeving_tools import GraafOnbekend, graaftoestanden

    try:
        periode = graaftoestanden(graph, [v.bwb_id]).get(v.bwb_id)
    except GraafOnbekend:
        return None
    if periode and periode[0] and periode[0] <= peil <= periode[1]:
        return v
    return replace(v, live=True, peildatum=peil) if live_aan else None


def lees_buiten(vraag: str, genoemde: list[Any]) -> Bepalingsvraag | None:
    """Een tekstvraag naar één artikel van één regeling buiten de kennisgraaf (`buiten_graaf.genoemd`): die leest de code
    bij overheid.nl. `None` als de vraag geen tekstvraag is of niet eenduidig één artikel noemt."""
    if not _is_tekstvraag(vraag):
        return None
    eenduidig = [g for g in genoemde if g.bwb_id]
    if len(eenduidig) != 1 or not eenduidig[0].artikel or any(g.dubbelzinnig for g in genoemde):
        return None
    peil = peildatum_in(vraag)
    if peil == "":
        return None
    g = eenduidig[0]
    return Bepalingsvraag(bwb_id=g.bwb_id, artikel=g.artikel, lid=g.lid, live=True, peildatum=peil or "")


Uitvoerder = Callable[[str, dict[str, Any]], str]


def _alle_paginas(voer_uit: Uitvoerder, tool: str, args: dict[str, Any]) -> list[tuple[str, str]] | None:
    """De aanroep met al zijn pagina's, zoals het model `vervolg` zou volgen. `None` bij een fout of te veel pagina's."""
    uit: list[tuple[str, str]] = []
    for _ in range(MAX_PAGINAS):
        tekst = voer_uit(tool, args)
        try:
            data = json.loads(tekst)
        except ValueError:
            return None
        if data.get("status") not in ("ok", "partial"):
            return None
        uit.append((tool, tekst))
        vervolg = data.get("vervolg")
        if not vervolg:
            return uit
        tool, args = vervolg["tool"], vervolg["args"]
    return None


def haal(graph: GraphPort, v: Bepalingsvraag, voer_uit: Uitvoerder | None = None) -> list[tuple[str, str]] | None:
    """De trace die het sjabloon nodig heeft: het lid, of het artikel met elk lid dat onderdelen heeft. `None` als de
    bepaling niet (helemaal) op te halen is. `voer_uit` laat de node de aanroepen als `tool_execution` tonen."""
    voer_uit = voer_uit or (lambda tool, args: dispatch(tool, graph, args))
    if v.live:
        # Het hele artikel (of lid) in één keer, alle pagina's: een weigering (`in_graaf`) of fout is `None`.
        return _alle_paginas(voer_uit, "get_wettekst", {"bwb_id": v.bwb_id, "artikel": v.artikel,
                                                         **({"lid": v.lid} if v.lid else {}),
                                                         **({"peildatum": v.peildatum} if v.peildatum else {})})
    if v.lid:
        return _alle_paginas(voer_uit, "get_lid", {"bwb_id": v.bwb_id, "artikel": v.artikel, "lid": v.lid})
    trace = _alle_paginas(voer_uit, "get_artikel", {"bwb_id": v.bwb_id, "artikel": v.artikel})
    if trace is None:
        return None
    leden = [rij for _, tekst in trace for rij in json.loads(tekst).get("resultaten") or [] if rij.get("heeft_onderdelen")]
    for rij in leden:
        deel = _alle_paginas(voer_uit, "get_lid", {"bwb_id": v.bwb_id, "artikel": v.artikel, "lid": rij.get("nummer", "")})
        if deel is None:
            return None
        trace += deel
    return trace


def gelezen_stuk(trace: list[tuple[str, str]]) -> dict[str, Any]:
    """Het `stuk` van de laatste lezing met `get_wettekst` in de trace, of {}."""
    for tool, tekst in reversed(trace):
        if tool == "get_wettekst":
            try:
                stuk = json.loads(tekst).get("stuk")
            except (ValueError, AttributeError):
                return {}
            return stuk if isinstance(stuk, dict) else {}
    return {}


def werking_zin(stuk: dict[str, Any]) -> str:
    """De zin over een bepaling die vervallen of nog niet in werking is (uit de bron), of ""."""
    status = str(stuk.get("status") or "")
    if status.startswith(("vervallen", "nog niet")):
        from .sjablonen.extern import _voluit

        naam = str(stuk.get("label") or "Deze bepaling").split(" (tekst geldig")[0]
        status = re.sub(r"\d{4}-\d{2}-\d{2}", lambda m: _voluit(m.group(0)), status)
        return f"{naam} is {status}: " + ("er geldt geen tekst meer." if status.startswith("vervallen")
                                           else "deze tekst geldt nog niet.")
    return ""


def _live_antwoord(trace: list[tuple[str, str]], toelichting: str) -> Antwoord | None:
    from bronmodel.antwoord import Leemte, Toelichting

    from .sjablonen.extern import heel_stuk

    stuk = gelezen_stuk(trace)
    blok = heel_stuk(trace, str(stuk.get("id") or ""))
    if blok is None:
        return None
    zin = werking_zin(stuk)
    return Antwoord(sjabloon="extern", blokken=[blok, *([Leemte(tekst=zin)] if zin else []),
                                                *([Toelichting(tekst=toelichting)] if toelichting else [])])


def antwoord(v: Bepalingsvraag, trace: list[tuple[str, str]], toelichting: str = "") -> Antwoord | None:
    """Het sjabloon `bepaling`, door de code aangewezen (bij wettekst van overheid.nl het blok `extern` met het hele
    artikel). `None` als het sjabloon niet compleet te vullen is."""
    if v.live:
        return _live_antwoord(trace, toelichting)
    try:
        return vul_sjabloon("antwoord_bepaling", {"bepalingen": [v.iri], "toelichting": toelichting}, trace)
    except Onvulbaar:
        return None


TOELICHTING_SYSTEM = (
    "Je bent Lex, een hulpmiddel voor wetsanalyse. Schrijf in twee of drie korte zinnen, in de je-vorm en op B1-niveau, "
    "wat de bepaling hieronder regelt. Gebruik alleen deze tekst: geen kennis van buiten, geen praktijk, geen andere "
    "artikelen. Noem een termijn, bedrag of datum zoals de tekst hem noemt (\"zes weken\", niet \"een bepaalde periode\"), "
    "en geen andere. Staat er een uitzondering (\"behoudens\", \"tenzij\", \"in afwijking van\", \"met uitzondering "
    "van\"), zeg dan voor wie of wat die geldt in de woorden van de tekst, en draai haar niet om. Geen citaten, geen koppen, "
    "geen opsomming. Vertel de tekst niet na; de jurist ziet hem er al boven."
)


def schrijf_toelichting(llm: LLMPort, model: str, bepaling: str) -> str:
    """De enige modelaanroep van deze workflow: een korte toelichting bij de opgehaalde tekst. Zonder tools, hoogstens
    300 tokens. Een storing kost alleen de toelichting; de wettekst staat er dan toch."""
    try:
        antwoord = aanroep(llm, Rol.BEPALING_TOELICHTING, model=model, max_tokens=300, system=TOELICHTING_SYSTEM,
                           tools=[], messages=[{"role": "user", "content": bepaling}])
    except Exception:  # noqa: BLE001 – de wettekst komt uit de graaf, de toelichting is een extra
        logger.warning("toelichting bij een bepaling niet geschreven", exc_info=True)
        return ""
    if antwoord.stopreden is not Stopreden.END_TURN:
        return ""
    tekst = "".join(b.text for b in antwoord.resp.content if getattr(b, "type", "") == "text").strip()
    # De tekst is de enige bron, dus een termijn, bedrag of datum die hij niet noemt, is verzonnen: dan geen toelichting.
    if extra := hoeveelheden_buiten(tekst, bepaling):
        logger.warning("toelichting noemt wat de bepaling niet noemt", extra={"categorie": "functioneel", "buiten": extra})
        return ""
    return tekst
