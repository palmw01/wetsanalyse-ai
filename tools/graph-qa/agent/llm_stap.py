"""Eén stap voor elke modelaanroep (H5).

De aanroepen in graph-qa hadden dezelfde vorm, maar liepen uiteen in herhalen, loggen en tellen. Vijf kopieën lazen de
tool-aanroep elk net anders, de ene plek logde de stopreden en de andere niet, en een methoderol kon bestaan zonder dat
een model hem ooit kreeg. Hier staat het één keer.

Twee lagen:

- **`aanroep`**: elke modelaanroep. De kwargs gaan **ongewijzigd** door naar `llm.create` (het verzoek blijft byte-gelijk;
  `tests/test_modelverzoeken.py` bewaakt dat). Daarbij komen een stopreden, de duur, één logregel `model_aanroep` en de
  controle dat de methodetekst van de rol in de systeemprompt staat. Hij probeert niets opnieuw en vangt niets af: de SDK
  herhaalt zelf bij transportfouten (`llm_max_retries`), de adapter doet de cache-terugval, en een fout is van de aanroeper.
- **`vraag_tool`**: de aanroepen met één strict tool (classifier, reviewer, begrippen, kaartacties, deelvragen, intake). Het
  aantal pogingen is verplicht en expliciet, en de tellers houden hun bestaande namen (`llm_calls`, `review_calls`,
  `afgekapt`), zodat metingen vergelijkbaar blijven. Wat de items zijn en of ze kloppen, blijft bij de module: dat is het
  contract van die stap, niet van de aanroep.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

logger = logging.getLogger("graph_qa.llm")


class Stopreden(StrEnum):
    """Waarom het model stopte (`stop_reason`). Een onbekende waarde wordt `ANDERS`, nooit een fout."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    REFUSAL = "refusal"
    PAUSE_TURN = "pause_turn"
    STOP_SEQUENCE = "stop_sequence"
    ANDERS = "anders"

    @classmethod
    def van(cls, resp: Any) -> "Stopreden":
        try:
            return cls(str(getattr(resp, "stop_reason", "") or ""))
        except ValueError:
            return cls.ANDERS


class Rol(Enum):
    """Wie het model aanroept: een gesloten lijst, met de methoderol uit de skill die de systeemprompt moet dragen.

    `None` als de rol zijn methode niet uit `methode.instructies` haalt: de classifier en de reviewer krijgen de
    JAS-klassen uit `jas_klassen.py`, en de begrippenrol is vervallen (besluit 6, 7 nov 2026)."""

    SUPERVISOR = ("supervisor", "supervisor")
    # De antwoordlus draait twee rollen: de ophaal-agent van de annotatieroute en de QA-specialisten. Die laatste krijgen
    # de methoderol van hun specialist (`specialists.methoderol`), dus die geeft de aanroeper mee.
    OPHAAL = ("ophaal", "retrieval")
    ANTWOORD = ("antwoord", None)
    BEPALING_TOELICHTING = ("bepaling_toelichting", None)
    JAS_CLASSIFIER = ("jas_classifier", None)
    JAS_REVIEWER = ("jas_reviewer", None)
    BEGRIP_VERGELIJK = ("begrip_vergelijk", None)
    BEGRIP_KAART = ("begrip_kaart", None)
    KAARTACTIE = ("kaartactie", None)
    DEELVRAGEN_VOORSTEL = ("deelvragen_voorstel", "deelvragen")
    DEELVRAAG_VERBETER = ("deelvraag_verbeter", "deelvragen")
    INTAKE = ("intake", None)

    def __init__(self, naam: str, methoderol: str | None) -> None:
        self.naam = naam
        self.methoderol = methoderol


@dataclass(frozen=True)
class Antwoord:
    resp: Any
    stopreden: Stopreden
    duur_ms: int


def _systeemtekst(system: Any) -> str:
    if isinstance(system, str):
        return system
    delen = []
    for d in system or []:
        delen.append(d.get("text", "") if isinstance(d, dict) else str(d or ""))
    return "\n\n".join(delen)


def _controleer_rol(rol: Rol, system: Any, methoderol: str | None = None) -> None:
    """De methodetekst van de rol moet in de systeemprompt staan (`methode.instructies` zet die kop). Een rol zonder
    haar methode is een stille drift: de skill zegt dan iets wat geen model leest (bevinding S-01)."""
    methode = methoderol or rol.methoderol
    if methode and f"— rol {methode}\n\n" not in _systeemtekst(system):
        raise ValueError(f"de systeemprompt van {rol.naam} mist de methoderol '{methode}'")


def _gebruik(resp: Any) -> dict[str, int]:
    u = getattr(resp, "usage", None)
    return {"invoer": int(getattr(u, "input_tokens", 0) or 0),
            "uitvoer": int(getattr(u, "output_tokens", 0) or 0),
            "cache_lees": int(getattr(u, "cache_read_input_tokens", 0) or 0),
            "cache_schrijf": int(getattr(u, "cache_creation_input_tokens", 0) or 0)}


def _log(rol: Rol, model: str, resp: Any, begin: float) -> Antwoord:
    duur = round((time.perf_counter() - begin) * 1000)
    stop = Stopreden.van(resp)
    logger.info("model_aanroep", extra={"categorie": "technisch", "rol": rol.naam, "model": model,
                                        "stopreden": str(stop), "duur_ms": duur, **_gebruik(resp)})
    return Antwoord(resp, stop, duur)


def aanroep(llm: Any, rol: Rol, *, methoderol: str | None = None, **verzoek: Any) -> Antwoord:
    """Eén `llm.create`, met de kwargs zoals ze binnenkomen. Logt `model_aanroep`: geen inhoud, geen veldnaam met
    "token" (de redactie in `observability` kijkt daarnaar). `methoderol` gaat vóór die van de rol."""
    _controleer_rol(rol, verzoek.get("system"), methoderol)
    begin = time.perf_counter()
    return _log(rol, verzoek.get("model", ""), llm.create(**verzoek), begin)


class Stroom:
    """Om de stream van de adapter heen: `final_message()` geeft het volledige antwoord, zoals de adapter, en legt de
    stopreden en de logregel vast. Eén keer aanroepen, net als bij de adapter (de meter telt anders dubbel)."""

    def __init__(self, stream: Any, rol: Rol, model: str, begin: float) -> None:
        self._stream, self._rol, self._model, self._begin = stream, rol, model, begin
        self.antwoord: Antwoord | None = None

    @property
    def text_deltas(self) -> Any:
        return self._stream.text_deltas

    def final_message(self) -> Any:
        self.antwoord = _log(self._rol, self._model, self._stream.final_message(), self._begin)
        return self.antwoord.resp


@contextmanager
def stroom(llm: Any, rol: Rol, *, methoderol: str | None = None, **verzoek: Any) -> Iterator[Stroom]:
    """Eén `llm.stream`, met de kwargs zoals ze binnenkomen (ook `historie_cache`)."""
    _controleer_rol(rol, verzoek.get("system"), methoderol)
    begin = time.perf_counter()
    with llm.stream(**verzoek) as s:
        yield Stroom(s, rol, verzoek.get("model", ""), begin)


def lees_tool(resp: Any, naam: str) -> dict[str, Any] | None:
    """De invoer van de eerste aanroep van tool `naam`, als object. Onleesbare JSON of geen object: `None`."""
    for blok in getattr(resp, "content", []) or []:
        if getattr(blok, "type", "") == "tool_use" and getattr(blok, "name", "") == naam:
            try:
                invoer = blok.input if isinstance(blok.input, dict) else json.loads(blok.input)
            except (TypeError, ValueError):
                return None
            return invoer if isinstance(invoer, dict) else None
    return None


def lijst(sleutel: str) -> Callable[[dict[str, Any]], list[Any] | None]:
    """Een `haal` voor `vraag_tool`: de lijst onder `sleutel`, of `None` als die er niet als lijst staat."""
    def haal(invoer: dict[str, Any]) -> list[Any] | None:
        items = invoer.get(sleutel)
        return items if isinstance(items, list) else None
    return haal


@dataclass(frozen=True)
class ToolUitkomst:
    """`waarde` is wat `haal` uit de tool-aanroep haalde, of `None` als geen poging iets bruikbaars gaf."""

    waarde: Any
    stopreden: Stopreden
    pogingen: int


def _tel(meting: dict[str, Any] | None, sleutel: str | None) -> None:
    if meting is not None and sleutel:
        meting[sleutel] = meting.get(sleutel, 0) + 1


def vraag_tool(llm: Any, rol: Rol, *, verzoek: dict[str, Any], pogingen: int,
               haal: Callable[[dict[str, Any]], Any] = lambda invoer: invoer,
               meting: dict[str, Any] | None = None, teller: str = "llm_calls",
               afgekapt_teller: str | None = None) -> ToolUitkomst:
    """Vraag het model om de ene tool in `verzoek`, hoogstens `pogingen` keer.

    Een poging is bruikbaar als de tool-aanroep leesbaar is en `haal` er iets anders dan `None` uit haalt. Elke poging
    telt in `meting[teller]`, een afgekapte (`max_tokens`) ook in `meting[afgekapt_teller]`. Een onbruikbare poging
    logt één regel met de stopreden."""
    if pogingen < 1:
        raise ValueError("pogingen moet minstens 1 zijn")
    naam = verzoek["tools"][0]["name"]
    stop = Stopreden.ANDERS
    for poging in range(1, pogingen + 1):
        antwoord = aanroep(llm, rol, **verzoek)
        stop = antwoord.stopreden
        _tel(meting, teller)
        if stop is Stopreden.MAX_TOKENS:
            _tel(meting, afgekapt_teller)
        invoer = lees_tool(antwoord.resp, naam)
        waarde = haal(invoer) if invoer is not None else None
        if waarde is not None:
            return ToolUitkomst(waarde, stop, poging)
        logger.info("geen bruikbare tool-aanroep", extra={"categorie": "functioneel", "rol": rol.naam, "tool": naam,
                                                          "stopreden": str(stop), "poging": poging})
    return ToolUitkomst(None, stop, pogingen)
