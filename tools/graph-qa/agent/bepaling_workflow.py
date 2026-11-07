"""De tekst van een bepaling zonder modelronde: laag 2 van ADR-010 (de eerste vaste workflow, D1).

"Wat staat er in artikel 9, eerste lid, van de Invorderingswet 1990?" kostte vier modelaanroepen en 42k tokens: de
supervisor, het BWB-id zoeken dat in de vraag stond, het lid ophalen, en afronden met het sjabloon, waarbij het model de
IRI aanwees die de code al kende (acceptatie, 7 nov 2026). Hier doet de code dat werk: de vraag lezen, ophalen, en het
sjabloon `bepaling` vullen. Het model schrijft hoogstens een korte toelichting; dat zit niet in deze module.

Alleen bij één eenduidige lezing: een tekstvraag, precies één regeling bij naam of afkorting, precies één artikel en
hoogstens één lid. Anders `None`, en de vraag gaat de gewone weg. Deze module gokt nooit en zoekt niet.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
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
    r"^\s*(?:wat\s+(?:staat|stond)\s+er\s+(?:precies\s+|letterlijk\s+)?in|wat\s+zegt|wat\s+is\s+de\s+(?:letterlijke\s+)?tekst\s+van"
    r"|geef\s+(?:me\s+|mij\s+)?(?:de\s+(?:letterlijke\s+)?tekst\s+van|letterlijk)|citeer|toon\s+(?:me\s+|mij\s+)?(?:de\s+tekst\s+van)?)\b",
    re.IGNORECASE,
)
_UITLEG = re.compile(r"\b(?:betekent|betekenis|houdt\b.*\bin\b|waarom|verhoudt|uitleg|leg\s+uit|bedoeld|toepass)", re.IGNORECASE)

#: Zoveel pagina's per aanroep haalt de workflow hoogstens op; daarboven is hij niet zeker van een hele tekst.
MAX_PAGINAS = 8


@dataclass(frozen=True)
class Bepalingsvraag:
    """Wat de vraag eenduidig aanwijst. `lid` is leeg voor het hele artikel."""

    bwb_id: str
    artikel: str
    lid: str = ""

    @property
    def iri(self) -> str:
        if self.lid:
            return queries.lid_iri(self.bwb_id, self.artikel, self.lid)
        return queries.artikel_iri(self.bwb_id, self.artikel)


def lees(vraag: str, graph: GraphPort) -> Bepalingsvraag | None:
    """De bepaling die de vraag eenduidig aanwijst, of `None`. Leest de regelingnamen uit de graaf (gecachet)."""
    if not _TEKSTVRAAG.search(vraag) or _UITLEG.search(vraag):
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
    return Bepalingsvraag(bwb_id=regelingen[0], artikel=artikel, lid=aanwijzing.leden[0] if aanwijzing.leden else "")


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


def antwoord(v: Bepalingsvraag, trace: list[tuple[str, str]], toelichting: str = "") -> Antwoord | None:
    """Het sjabloon `bepaling`, door de code aangewezen. `None` als het sjabloon niet compleet te vullen is."""
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
