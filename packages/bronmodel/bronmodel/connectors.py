"""De bronconnectors (ADR-013): één beschrijving per connector, de enige bron voor de hele keten.

Een bronconnector is code (getypeerde tools in graph-qa, `agent/tools/`), maar wát hij is, staat hier: naam en label,
het soort vindplaats, wat hij dekt, welke tools erbij horen, hoe je eruit citeert en waar hij in een antwoord voor
staat. Daaruit leiden de api (het register, de toegestane namen) en graph-qa (toollaag, specialisten, routering,
scope, prompt en verificatie) alles af. Een nieuwe connector is dus: een beschrijving hier, zijn tools in graph-qa en
een straatvlag (`CONNECTOR_<NAAM>`). De poorttest `tests/poort/test_connectorbeschrijving.py` maakt een onvolledige
beschrijving rood.

Wetgeving (de BWB-graaf) is geen connector: die staat altijd aan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extern import externe_verwijzingen


@dataclass(frozen=True)
class ConnectorBeschrijving:
    #: De sleutel: in het register, in `ChatRequest.bronnen`, in `Settings.connector_<naam>`.
    naam: str
    #: Leesbaar, voor het menu en de meldingen ("Kamerstukken").
    label: str
    #: Het soort vindplaats (`extern.BRONTYPEN`, nooit `wettekst`).
    brontype: str
    #: De kop in de bronnenlijst van de werkplek ("Parlementaire stukken").
    groep: str
    #: Wat de bron dekt, in één zin voor de router en de scope ("wetsgeschiedenis: …").
    dekt: str
    #: Patronen (hoofdletterongevoelig) waaraan een vraag naar deze bron herkenbaar is.
    signalen: tuple[str, ...]
    #: De tools van de connector in graph-qa.
    tools: frozenset[str]
    #: De tool waarvan het resultaat de citeerbare tekst draagt; een zoekresultaat draagt alleen titels.
    leestool: str
    #: De vorm van het id dat het antwoord noemt (`extern.externe_vindplaats` leest het).
    id_prefixen: tuple[str, ...]
    #: De rollen (specialisten) die de tools krijgen, als de connector aanstaat.
    specialisten: frozenset[str]
    #: Waar de bron in een antwoord voor staat, en waarvoor niet.
    rol_in_antwoord: str
    #: Wat de connector niet kan: de jurist moet het weten voor hij op een stilte vertrouwt.
    grenzen: str
    #: De beschrijving in de beheertab.
    beheer: str
    #: Vragen die binnen scope vallen en deze bron raken; routering, tests en de meting gebruiken ze.
    voorbeeldvragen: tuple[str, ...]
    _patronen: tuple[re.Pattern[str], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_patronen", tuple(re.compile(s, re.IGNORECASE) for s in self.signalen))

    @property
    def env(self) -> str:
        """De straatvlag die de connector aanbiedt."""
        return f"CONNECTOR_{self.naam.upper()}"

    def herkent(self, tekst: str) -> bool:
        """Gaat deze tekst (ook) over deze bron? Een signaalwoord, of een id van zijn soort."""
        if any(p.search(tekst or "") for p in self._patronen):
            return True
        return any(e.brontype == self.brontype and e.id.startswith(self.id_prefixen)
                   for e in externe_verwijzingen(tekst or ""))


KAMERSTUKKEN = ConnectorBeschrijving(
    naam="kamerstukken",
    label="Kamerstukken",
    brontype="kamerstuk",
    groep="Parlementaire stukken",
    dekt=("wetsgeschiedenis uit de officiële publicaties: het voorstel van wet, de memorie van toelichting, nota's, "
          "verslagen, het advies van de Raad van State en het nader rapport"),
    signalen=(r"\bkamerstuk", r"\bmemorie\s+van\s+toelichting\b", r"\bmvt\b", r"\bwetsgeschiedenis\b",
              r"\bparlementaire\s+(?:stukken|geschiedenis|behandeling)\b", r"\bnota\s+naar\s+aanleiding\b",
              r"\bnader\s+rapport\b", r"\badvies\s+van\s+de\s+raad\s+van\s+state\b",
              r"\bbedoel(?:de|ing\s+van)\s+de\s+wetgever\b"),
    tools=frozenset({"zoek_kamerstukken", "get_kamerstuk"}),
    leestool="get_kamerstuk",
    id_prefixen=("kst-",),
    specialisten=frozenset({"definitie", "duiding", "algemeen"}),
    rol_in_antwoord=("een Kamerstuk laat zien wat de wetgever bedoelde; het onderbouwt nooit wat de wet zegt – dat "
                     "doet alleen de opgehaalde bepaling"),
    grenzen=("zoeken gaat op dossiernummer of op woorden uit de titel, niet in de volle tekst; tabellen, illustraties "
             "en voetnoten staan niet in de opgehaalde tekst"),
    beheer=("Wetsgeschiedenis uit de officiële publicaties: memorie van toelichting, nota's, verslagen en het advies "
            "van de Raad van State. Openbaar, zonder sleutel."),
    voorbeeldvragen=(
        "Wat kun je vinden in de Kamerstukken?",
        "Wat staat er in de memorie van toelichting bij Kamerstuk 33755, nummer 3?",
        "Welke Kamerstukken horen bij de Invorderingswet 1990?",
        "Wat zegt kst-33755-3 over de bestuurdersaansprakelijkheid?",
        "Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?",
    ),
)

#: De bronconnectors, in de volgorde van het menu en de beheertab.
CONNECTORS: dict[str, ConnectorBeschrijving] = {c.naam: c for c in (KAMERSTUKKEN,)}

#: De namen, als tuple voor een `Literal[NAMEN]` in de contracten.
NAMEN: tuple[str, ...] = tuple(CONNECTORS)

def herkende(tekst: str) -> tuple[str, ...]:
    """De connectors waar deze tekst (ook) over gaat, in de volgorde van `CONNECTORS`."""
    return tuple(n for n, c in CONNECTORS.items() if c.herkent(tekst))
