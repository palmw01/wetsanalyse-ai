"""De catalogus (ADR-014): één beschrijving per onderdeel van Lex.

Een onderdeel is alles wat bepaalt hoe Lex werkt:
- een methode (een skill) en de rollen die zijn tekst krijgen;
- een specialist, taakagent of vaste workflow, en de route die hem kiest;
- een bronconnector, een antwoordsjabloon of een regelset.

De beschrijving wordt **afgeleid** uit het register dat er al is. Graph-qa doet dat in `agent/catalogus.py`, met
`CONNECTORS`, `SPECIALISTS`, `SJABLONEN` en `PAKKET`. Wat dat register niet weet, staat ernaast: doel, twijfel en
herkomst. Dit bestand bevat alleen de vorm. Die staat in het bronmodel omdat api, graph-qa en de spiegel in de werkplek
hem alle drie lezen, net als `connectors.py`.

De velden volgen de zeven contractpunten van ADR-010: doel, ingang, context, tools, uitvoer, twijfel en eval. Daarbij
komen herkomst en licentie, want de repo is publiek. Ook staat erbij of er een model aan te pas komt; dat wordt
afgeleid en nooit met de hand gezet.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Soort = Literal["methode", "rol", "regelset", "tool", "connector", "sjabloon", "workflow", "agentprofiel", "agent",
                "route", "controle"]

#: De soorten in de volgorde van de werkplek.
SOORTEN: tuple[str, ...] = Soort.__args__  # type: ignore[attr-defined]

#: Komt er een model aan te pas?
#: - `geen`: alleen code;
#: - `strict`: één modelstap met een strikte tool en validatie in code (ADR-005/010);
#: - `agent`: een open lus met tools.
Model = Literal["geen", "strict", "agent"]

#: Het concept uit Claude Code waar een soort bij hoort (ADR-014 §7). De samenwerking wordt per concept geregeld:
#: - `skill`: kennis die zelf niets uitvoert en in de context van een agent of workflow geladen wordt;
#: - `tool`: één getypte handeling met het resultaatcontract;
#: - `workflow`: een vaste keten in code, een model alleen in een strict stap;
#: - `agent`: een modellus met eigen context, tools en contract (de subagent);
#: - `ingang`: kiest zonder model één onderdeel (route, commando);
#: - `hook`: een deterministische controle op een vast moment.
Concept = Literal["skill", "tool", "workflow", "agent", "ingang", "hook"]
CONCEPTEN: tuple[str, ...] = Concept.__args__  # type: ignore[attr-defined]

CONCEPT: dict[str, str] = {
    "methode": "skill", "rol": "skill", "regelset": "skill",
    "tool": "tool", "connector": "tool", "sjabloon": "tool",
    "workflow": "workflow",
    "agentprofiel": "agent", "agent": "agent",
    "route": "ingang",
    "controle": "hook",
}


#: Een onderdeel dat van geen methode is: de graaftools, de bronconnectors, de controles.
NEUTRAAL = "neutraal"


def concept_van(soort: str, model: str) -> str:
    """Het concept volgt het gedrag: een taak onder de supervisor zonder enige modelstap is een vaste keten, geen
    agent (de annotatie-agent annoteert een werkgebied als reeks, zonder model)."""
    if soort == "agent" and model == "geen":
        return "workflow"
    return CONCEPT[soort]


#: Wat een concept mag gebruiken (`hangt_af_van` = "A gebruikt B"). `tests/test_catalogus.py` maakt elke andere rand
#: rood. Een connector bundelt tools, zoals een MCP-server: daarom mag een tool een tool gebruiken.
MAG_GEBRUIKEN: dict[str, frozenset[str]] = {
    "skill": frozenset(),
    "tool": frozenset({"tool"}),
    "workflow": frozenset({"tool", "skill", "hook", "workflow"}),
    "agent": frozenset({"tool", "skill", "hook", "workflow"}),
    "ingang": frozenset({"workflow", "agent"}),
    "hook": frozenset({"skill"}),
}

#: Welk model een concept mag hebben. Een workflow kent nooit een open lus; een skill, ingang of hook nooit een model.
MAG_MODEL: dict[str, frozenset[str]] = {
    "skill": frozenset({"geen"}),
    "tool": frozenset({"geen", "strict"}),
    "workflow": frozenset({"geen", "strict"}),
    "agent": frozenset({"agent", "strict"}),
    "ingang": frozenset({"geen"}),
    "hook": frozenset({"geen"}),
}

#: Laag uit ADR-010.
Laag = Literal["routering", "workflow", "taakagent", "open"]

_ID = re.compile(r"(?P<soort>[a-z]+)/(?P<naam>[a-z0-9_.-]+)")


@dataclass(frozen=True)
class Herkomst:
    """Waar de inhoud vandaan komt. `letterlijk` zegt of tekst van een bron van derden letterlijk in de repo mag staan.
    Dat mag bij de W3C-licentie van BZK-bronnen, mét de notice in een `BRON.md`. Bij het boek en de BRM-readers mag
    het niet; daar alleen eigen woorden."""

    bron: str
    licentie: str
    letterlijk: bool = False
    #: Broncodes (M/P uit `references/bronnen.md`, H2:NN uit H2-JAS) of repo-paden van de bron.
    verwijzing: tuple[str, ...] = ()


#: Eigen werk van dit platform: code of tekst die hier is geschreven.
EIGEN = Herkomst(bron="eigen werk van dit platform", licentie="repo")


@dataclass(frozen=True)
class Stap:
    """Eén stap van een workflow, in uitvoeringsvolgorde, met het onderdeel dat hem zet (als dat er een eigen heeft)."""

    naam: str
    model: Model
    onderdeel: str | None = None
    #: Bij een strict stap: de `llm_stap.Rol` die de modelaanroep draagt (ADR-014 §7).
    rol: str | None = None


@dataclass(frozen=True)
class Onderdeel:
    #: `"<soort>/<naam>"`, stabiel: een commando, een link in het denkproces en een voorstel verwijzen ernaar.
    id: str
    soort: Soort
    label: str
    #: Eén zin, met wat er níét bij hoort (contractpunt 1).
    doel: str
    model: Model
    herkomst: Herkomst
    #: Waar je het in de repo leest en bewerkt.
    bestand: tuple[str, ...]
    #: Een hash van de inhoud. Die verandert als het gedrag verandert.
    versie: str
    #: De hash van de bronbestanden van dit onderdeel in het image (`bronmodel.werkplaats.hash_van`), als het die heeft:
    #: een skill of een agentprofiel. Een versie in de werkplaats met dezelfde hash is *actief* (ADR-016 §B1). Iets anders
    #: dan `versie`: commentaar in een bestand verandert het gedrag niet, de bronbestanden wel.
    bronhash: str = ""
    #: Van welke methode dit onderdeel is: de naam van één methode-skill, of `NEUTRAAL`. De annotatieketen, de
    #: annotatie-UI en de JAS-tools zijn van wetsanalyse; een andere methode krijgt er geen toegang toe (ADR-014 §5,
    #: plan methodes scheiden). Leeg bestaat alleen onderweg: de catalogus vult het voor elk onderdeel in.
    methode: str = ""
    #: Acties, routes of tools die het kiezen (contractpunt 2).
    ingang: tuple[str, ...] = ()
    #: Benodigde context en de bovengrens ervan (contractpunt 3).
    context: str = ""
    #: Tools of queries (contractpunt 4).
    tools: tuple[str, ...] = ()
    #: Sjabloon of artefact (contractpunt 5).
    uitvoer: str = ""
    #: Wat er bij twijfel gebeurt (contractpunt 6).
    twijfel: str = ""
    #: Tests en eval-sets, als repo-paden (contractpunt 7).
    tests: tuple[str, ...] = ()
    #: Ids van onderdelen waar dit op leunt. Een specialist leunt bijvoorbeeld op zijn rol, en die rol op de methode.
    hangt_af_van: tuple[str, ...] = ()
    #: Waar dit een deel van is (een rol is een deel van zijn skill). Iets anders dan gebruiken: een skill gebruikt niets,
    #: maar bestaat wel uit delen.
    deel_van: str | None = None
    #: De straatvlag die het aan- of uitzet (`CONNECTOR_KAMERSTUKKEN`, `RELATIE_VOORSTELLEN`); None = altijd aan.
    straat: str | None = None
    #: Welke delen een beheerder via de app als wijziging mag voorstellen. Dat zijn sectie-ids of veldnamen. Zo'n
    #: voorstel wordt een concept-PR, nooit een directe wijziging.
    bewerkbaar: tuple[str, ...] = ()
    #: Alleen bij een workflow: de laag en de stappen.
    laag: Laag | None = None
    stappen: tuple[Stap, ...] = ()
    #: De inhoud die de werkplek toont, zoals methodetekst, regels met hun testzinnen of een connectorbeschrijving.
    #: Het is vrije JSON per soort; de lijst laat hem weg.
    inhoud: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        m = _ID.fullmatch(self.id)
        if not m or m["soort"] != self.soort:
            raise ValueError(f"ongeldig onderdeel-id {self.id!r} voor soort {self.soort}")
        if (self.soort == "workflow") != bool(self.laag):
            raise ValueError(f"{self.id}: alleen een workflow heeft een laag")

    @property
    def naam(self) -> str:
        return self.id.split("/", 1)[1]

    @property
    def concept(self) -> str:
        return concept_van(self.soort, self.model)

    def als_dict(self, *, met_inhoud: bool = False) -> dict[str, Any]:
        d = asdict(self) | {"concept": self.concept}
        if not met_inhoud:
            d.pop("inhoud")
        return d


def oid(soort: str, naam: str) -> str:
    return f"{soort}/{naam}"


def versie(*delen: Any) -> str:
    """Een korte hash van de inhoud, deterministisch over JSON-serialiseerbare delen."""
    tekst = json.dumps(delen, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(tekst.encode()).hexdigest()[:12]


def zwaarste(modellen: list[str] | tuple[str, ...]) -> Model:
    """Het model van een geheel is het zwaarste van zijn delen: agent > strict > geen."""
    for m in ("agent", "strict"):
        if m in modellen:
            return m  # type: ignore[return-value]
    return "geen"
