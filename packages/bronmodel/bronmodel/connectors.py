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

from .extern import externe_verwijzingen, externe_vindplaats


def _opsomming(delen: tuple[str, ...]) -> str:
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " en " + delen[-1]


def bronnen_tekst(labels: list[str] | tuple[str, ...]) -> str:
    """Waar Lex zoekt, voor de algemene stappen in het denkproces: "de kennisgraaf" zonder connector, anders "de
    wetgeving en Kamerstukken"."""
    return "de kennisgraaf" if not labels else "de wetgeving en " + _opsomming(tuple(labels))


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
    #: De tool waarvan het resultaat de citeerbare tekst draagt; een zoekresultaat draagt alleen titels. Het contract van
    #: een leestool: het resultaat draagt `stuk: {id, label, link, bron_hash, gewijzigd?}` en per rij `{nr, tekst, kop?}`
    #: (genummerde passages in documentvolgorde), zodat het blok `extern` (ADR-008) voor elke connector met dezelfde code
    #: wordt gevuld. `bron_hash` is de hash van het gelezen document: de passages van één blok komen uit één lezing.
    #: Een rij mag `soort` dragen (`alinea`, `voetnoot`, `tabel`, `tabelrij`); een `tabel` draagt `openen` naar deze
    #: leestool (de tabel zelf, met de kolommen als `cellen` op de kop), een `tabelrij` haar `cellen`.
    leestool: str
    #: Het argument van de leestool dat het id draagt: een vraag die een id noemt, leest de code direct
    #: (`nodes/bron_lezen.py`), zonder dat het model eerst gaat zoeken.
    lees_argument: str
    #: De vorm van het id dat het antwoord noemt (`extern.externe_vindplaats` leest het).
    id_prefixen: tuple[str, ...]
    #: De rollen (specialisten) die de tools krijgen, als de connector aanstaat.
    specialisten: frozenset[str]
    #: Waar de bron in een antwoord voor staat, en waarvoor niet.
    rol_in_antwoord: str
    #: De kop boven het blok `extern` in een antwoord ("Uit de parlementaire geschiedenis").
    kop_in_antwoord: str
    #: Wat de connector niet kan bij het zoeken: de jurist moet het weten voor hij op een stilte vertrouwt.
    grenzen: str
    #: Wat de leestool levert, als rijsoorten in de woorden van de jurist (`alinea` → "alinea's"); en wat er niet in de
    #: opgehaalde tekst staat. Daaruit komt `capaciteit`, zodat Lex niet zegt dat iets ontbreekt wat de tool wel geeft
    #: (bundel 22: tabellen en voetnoten kwamen erbij, de vaste tekst bleef "staan er niet in"). Een test toetst het
    #: tegen wat de leestool echt teruggeeft.
    levert: tuple[str, ...]
    niet_in_tekst: tuple[str, ...]
    #: Per tool wat Lex doet, in de woorden van de jurist, voor het denkproces (`narratie._toolregel`). Per tool een of
    #: meer vormen met `{argument}`; de eerste waarvan alle argumenten in de aanroep staan, telt. Een tool zonder
    #: werkwoord heette "raadpleegt de kennisgraaf", ook als Lex een Kamerstuk las (acceptatie 8 nov 2026).
    werkwoorden: dict[str, tuple[str, ...]]
    #: De beschrijving in de beheertab.
    beheer: str
    #: Vragen die binnen scope vallen en deze bron raken; routering, tests en de meting gebruiken ze.
    voorbeeldvragen: tuple[str, ...]
    _patronen: tuple[re.Pattern[str], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_patronen", tuple(re.compile(s, re.IGNORECASE) for s in self.signalen))

    @property
    def capaciteit(self) -> str:
        """"levert alinea's, voetnoten en tabellen; illustraties staan niet in de opgehaalde tekst"."""
        zin = f"de tekst komt per stuk met {_opsomming(self.levert)}"
        return zin + (f"; {_opsomming(self.niet_in_tekst)} staan niet in de opgehaalde tekst" if self.niet_in_tekst else "")

    def werkwoord(self, tool: str, invoer: dict) -> str | None:
        """Wat Lex doet met deze aanroep, of None als de tool niet van deze connector is."""
        vormen = self.werkwoorden.get(tool)
        if not vormen:
            return None
        waarden = {k: str(v).strip() for k, v in (invoer or {}).items() if str(v).strip()}
        for vorm in vormen:
            nodig = re.findall(r"\{(\w+)\}", vorm)
            if all(n in waarden for n in nodig):
                return vorm.format(**{n: waarden[n][:60] for n in nodig})
        return re.sub(r"\s*\{\w+\}", "", vormen[-1]).strip()

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
    lees_argument="id",
    id_prefixen=("kst-",),
    specialisten=frozenset({"definitie", "duiding", "algemeen"}),
    rol_in_antwoord=("een Kamerstuk laat zien wat de wetgever bedoelde; het onderbouwt nooit wat de wet zegt – dat "
                     "doet alleen de opgehaalde bepaling"),
    kop_in_antwoord="Uit de parlementaire geschiedenis",
    grenzen="zoeken gaat op dossiernummer of op woorden uit de titel, niet in de volle tekst",
    levert=("alinea's", "voetnoten", "tabellen (op te halen met hun rijen)"),
    niet_in_tekst=("illustraties",),
    werkwoorden={
        "zoek_kamerstukken": ("zoekt de Kamerstukken van dossier {dossier}", "zoekt Kamerstukken over „{woorden}”",
                              "zoekt Kamerstukken"),
        "get_kamerstuk": ("leest tabel {tabel} van Kamerstuk {id}", "leest Kamerstuk {id}", "leest een Kamerstuk"),
    },
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


def van_id(ident: str) -> ConnectorBeschrijving | None:
    """De connector die een extern id levert: zijn brontype en de vorm van zijn id. None als geen connector het levert
    (een ECLI zonder connector voor rechtspraak, of geen extern id)."""
    vp = externe_vindplaats(ident)
    if vp is None:
        return None
    return next((c for c in CONNECTORS.values() if c.brontype == vp.brontype and vp.id.startswith(c.id_prefixen)), None)


def leestools() -> frozenset[str]:
    """De tools waarvan het resultaat citeerbare tekst van een bron naast de wet draagt."""
    return frozenset(c.leestool for c in CONNECTORS.values())


def genoemde_stukken(tekst: str) -> list[tuple[ConnectorBeschrijving, str]]:
    """De ids van een connector die de tekst letterlijk noemt (`kst-35496-F`), in de volgorde van de tekst."""
    uit: list[tuple[ConnectorBeschrijving, str]] = []
    for e in externe_verwijzingen(tekst or ""):
        if (c := van_id(e.id)) is not None:
            uit.append((c, e.id))
    return uit
