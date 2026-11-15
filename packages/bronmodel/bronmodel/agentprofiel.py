"""Het agentprofiel en zijn grenzen (ADR-016 §A2; poort 1 van §B2).

Een profiel is configuratie die een Python-agent laadt, nooit een agent op zichzelf: het kiest uit wat de code
aanbiedt. Het is wat een Claude Code-subagent ook is: een beschrijving, een instructie en een lijst onderdelen. Op
schijf is het een Markdown-bestand `<naam>.md` met YAML-frontmatter en de instructie als tekst eronder; de veldnamen
zijn die van een Claude Code-subagent waar ze overeenkomen (`VELDEN`).

Eén validator voor de generator die de profielen in het image bundelt en voor de werkplaats, die een profiel bij elke
opslag toetst. De vorm toetst `Agentprofiel` zelf. De grenzen hangen af van wat er bestaat (de tools van de open laag,
de skills in de catalogus, de connectors, de sjablonen): die geeft de aanroeper mee als `Grenzen`, want graph-qa kent
ze en dit pakket niet.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .validatie import Bevinding, ValidatieFout, frontmatter, uniek

#: Een profielnaam is ook de bestandsnaam. De onderstreep mag, omdat de specialisten van nu hem dragen
#: (`annotaties_lezen`) en hun naam in de routering staat.
NAAM = r"[a-z][a-z0-9_-]*"
MAX_NAAM = 64
MAX_BESCHRIJVING = 1024
#: De instructie staat in het vaste voorvoegsel van elke aanroep met dit profiel.
MAX_INSTRUCTIE = 12_000

#: Wat geen profiel mag hebben, wat de aanroeper ook aanbiedt: een subagent stelt zelf geen subagents op (één laag).
NOOIT = frozenset({"subagent"})

#: Het veld `model` van een Claude Code-subagent. Lex leest het niet: het model van een profiel kiest de beheerder
#: (`agent:<profiel>`, `bronmodel.modelkeuzes`). In een concept uit de werkplaats is het een voorstel aan de beheerder;
#: in een vast profiel (`.claude/lex-agents/`) hoort het niet, want daar zou het lijken alsof het iets doet.
MODEL = "model"
MAX_MODEL = 64

#: Van het veld in de frontmatter naar het veld van het profiel. De eerste namen zijn die van een Claude
#: Code-subagent; de rest kent alleen Lex. De instructie is de tekst onder de frontmatter. `model` staat er niet in:
#: zie `MODEL`.
VELDEN: dict[str, str] = {
    "name": "naam",
    "description": "beschrijving",
    "tools": "tools",
    "skills": "skills",
    "maxTurns": "max_rondes",
    "mcpServers": "mcp",
    "kiesbaar": "kiesbaar",
    "connectors": "connectors",
    "sjablonen": "sjablonen",
    "budget": "budget",
    "methoderol": "methoderol",
}


class Agentprofiel(BaseModel):
    """De velden van ADR-016 §A2. Onveranderlijk: een agent wordt uit een gevalideerd profiel opgebouwd."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    naam: str = Field(pattern=rf"^{NAAM}$", max_length=MAX_NAAM)
    #: Wanneer de centrale agent dit profiel kiest.
    beschrijving: str = Field(min_length=1, max_length=MAX_BESCHRIJVING)
    #: Of de centrale agent het mag kiezen. `False` voor een profiel dat een stap van een route in code is.
    kiesbaar: bool = True
    #: De systeemtekst, bovenop de identiteit van Lex.
    instructie: str = Field(min_length=1, max_length=MAX_INSTRUCTIE)
    #: De skills die hij vooraf krijgt.
    skills: tuple[str, ...] = ()
    #: De tools. `None` (het veld ontbreekt) betekent alle tools van de open laag, zoals bij een Claude Code-subagent.
    tools: tuple[str, ...] | None = None
    connectors: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    #: De sjablonen waarmee hij afrondt (ADR-008).
    sjablonen: tuple[str, ...] = ()
    #: Hoe lang (modelrondes) en hoe duur (tokens, ruw: zoals het budget van de gebruiker telt) als subagent; `None` is
    #: de standaard van het platform. Als specialist van de supervisor gelden ze niet.
    max_rondes: int | None = Field(default=None, ge=1)
    budget: int | None = Field(default=None, ge=1)
    #: De methoderol waarvan hij de tekst uit de skill krijgt; `None` is de rol met zijn eigen naam. Een profiel maakt
    #: geen rol: het leent er een die bestaat (ADR-014 §5).
    methoderol: str | None = None

    @property
    def rol(self) -> str:
        return self.methoderol or self.naam


@dataclass(frozen=True)
class Grenzen:
    """Waaruit een profiel mag kiezen. De aanroeper leidt ze af uit zijn eigen registers."""

    #: De tools van de open laag.
    tools: frozenset[str]
    #: De skills in de catalogus (in de proef ook een conceptversie).
    skills: frozenset[str]
    connectors: frozenset[str]
    sjablonen: frozenset[str]
    mcp: frozenset[str] = frozenset()
    #: De methoderollen die bestaan; `None` toetst ze niet.
    methoderollen: frozenset[str] | None = None
    #: Tools die een besluit van de jurist nemen, of anderszins niet aan een profiel horen. `NOOIT` geldt altijd.
    verboden_tools: frozenset[str] = frozenset()
    #: methode-skill → de tools die alleen van die methode zijn (de annotatieleestools en de JAS-tools van
    #: wetsanalyse). Een profiel van een andere methode krijgt ze niet (plan methodes scheiden, S3).
    methode_tools: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: methoderol → de methode-skills waarvan hij secties draagt; `None` toetst de methode niet.
    rol_methodes: Mapping[str, frozenset[str]] | None = None
    max_rondes: int | None = None
    budget: int | None = None


def _vorm(fout: ValidationError) -> list[Bevinding]:
    return [Bevinding("vorm", f"{'.'.join(str(d) for d in f['loc']) or 'profiel'}: {f['msg']}") for f in fout.errors()]


def uit_markdown(naam: str, tekst: str, *, vast: bool = False) -> Agentprofiel:
    """Het profiel uit `<naam>.md`. Gooit `ValidatieFout` als de vorm niet klopt; de grenzen toetst `toets`. Met `vast`
    (de profielen in de repo) is `model` een fout; anders een voorstel dat het profiel niet draagt (`modelvoorstel`)."""
    try:
        kop, instructie = frontmatter(tekst)
    except ValueError as f:
        raise ValidatieFout(naam, [Bevinding("frontmatter", str(f))]) from None
    toegestaan = set(VELDEN) | (set() if vast else {MODEL})
    if vreemd := sorted(set(kop) - toegestaan):
        uitleg = (" `model` kiest de beheerder (Instellingen › Aanpassingen › Agents), niet het profiel."
                  if MODEL in vreemd and vast else "")
        raise ValidatieFout(naam, [Bevinding("frontmatter", f"onbekende velden {vreemd}; toegestaan zijn "
                                                            f"{sorted(toegestaan)}.{uitleg}".rstrip("."))])
    if MODEL in kop and not (isinstance(kop[MODEL], str) and 0 < len(kop[MODEL]) <= MAX_MODEL):
        raise ValidatieFout(naam, [Bevinding("vorm", f"model: een naam van hoogstens {MAX_MODEL} tekens")])
    velden: dict[str, Any] = {VELDEN[k]: tuple(v) if isinstance(v, list) else v for k, v in kop.items() if k != MODEL}
    try:
        profiel = Agentprofiel(**velden, instructie=instructie)
    except ValidationError as f:
        raise ValidatieFout(naam, _vorm(f)) from None
    if profiel.naam != naam:
        raise ValidatieFout(naam, [Bevinding("naam", f"name is {profiel.naam!r}, maar het bestand heet {naam!r}")])
    return profiel


def modelvoorstel(tekst: str) -> str | None:
    """Het model dat een concept voorstelt (`model:` in de frontmatter), of `None`. Alleen een voorstel aan de beheerder."""
    try:
        kop, _ = frontmatter(tekst)
    except ValueError:
        return None
    waarde = kop.get(MODEL)
    return waarde if isinstance(waarde, str) and waarde else None


def tools_van_andere_methode(profiel: Agentprofiel, grenzen: Grenzen) -> frozenset[str]:
    """De tools die van een methode zijn waarvan de rol van dit profiel geen sectie draagt. Zonder `rol_methodes` is er
    niets te toetsen."""
    if grenzen.rol_methodes is None:
        return frozenset()
    eigen = grenzen.rol_methodes.get(profiel.rol, frozenset())
    return frozenset().union(*(tools for methode, tools in grenzen.methode_tools.items() if methode not in eigen))


def toets(profiel: Agentprofiel, grenzen: Grenzen) -> list[Bevinding]:
    """Het profiel tegen de grenzen van §A2. Een lege lijst betekent: dit profiel mag een agent opbouwen."""
    uit = []

    def kies(veld: str, waarden: tuple[str, ...], uit_wat: frozenset[str]) -> None:
        if not uniek(waarden):
            uit.append(Bevinding(veld, f"{veld}: een waarde staat er dubbel"))
        if onbekend := sorted(set(waarden) - uit_wat):
            uit.append(Bevinding(veld, f"{veld}: {onbekend} bestaat niet of staat niet open voor een profiel"))

    verboden = NOOIT | grenzen.verboden_tools
    if profiel.tools is not None:
        if mag_niet := sorted(set(profiel.tools) & verboden):
            uit.append(Bevinding("tools", f"tools: {mag_niet} hoort nooit bij een profiel"))
        kies("tools", tuple(t for t in profiel.tools if t not in verboden), grenzen.tools)
        # Een rol die niet bestaat, meldt de toets op de methoderol al.
        kent_rol = grenzen.rol_methodes is None or profiel.rol in grenzen.rol_methodes
        if kent_rol and (vreemd := sorted(set(profiel.tools) & tools_van_andere_methode(profiel, grenzen))):
            uit.append(Bevinding("tools", f"tools: {vreemd} is van een andere methode dan de rol {profiel.rol!r}; de "
                                          "annotatieketen en de JAS-tools zijn alleen van wetsanalyse"))
    kies("skills", profiel.skills, grenzen.skills)
    # Een skill vooraf is methodetekst. Die moet van de methode zijn waarvan de rol van het profiel zijn secties draagt:
    # anders mengt het profiel twee methodes (plan methodes scheiden). Een skill van een methode zonder rol kan pas
    # vooraf, als een meting zijn secties aan een rol koppelt (ADR-014 §7).
    if grenzen.rol_methodes is not None and profiel.rol in grenzen.rol_methodes:
        eigen = grenzen.rol_methodes[profiel.rol]
        if vreemd := sorted(s for s in set(profiel.skills) & grenzen.skills if s not in eigen):
            uit.append(Bevinding("skills", f"skills: {vreemd} is van een andere methode dan de rol {profiel.rol!r} "
                                           f"({', '.join(sorted(eigen)) or 'geen methode'})"))
    kies("connectors", profiel.connectors, grenzen.connectors)
    kies("mcp", profiel.mcp, grenzen.mcp)
    kies("sjablonen", profiel.sjablonen, grenzen.sjablonen)
    if grenzen.methoderollen is not None and profiel.rol not in grenzen.methoderollen:
        uit.append(Bevinding("methoderol", f"methoderol: de rol {profiel.rol!r} bestaat niet"))
    for veld, grens in (("max_rondes", grenzen.max_rondes), ("budget", grenzen.budget)):
        waarde = getattr(profiel, veld)
        if waarde is not None and grens is not None and waarde > grens:
            uit.append(Bevinding(veld, f"{veld}: {waarde} is meer dan de grens van {grens}"))
    return uit


def toegestane_tools(profiel: Agentprofiel, grenzen: Grenzen) -> frozenset[str]:
    """De tools die een agent met dit profiel krijgt. Ook een profiel met alle tools (`tools` is `None`) krijgt nooit
    wat verboden is."""
    alle = grenzen.tools - NOOIT - grenzen.verboden_tools - tools_van_andere_methode(profiel, grenzen)
    return alle if profiel.tools is None else frozenset(profiel.tools) & alle


def valideer(profiel: Agentprofiel, grenzen: Grenzen) -> Agentprofiel:
    """Zoals `toets`, maar gooit `ValidatieFout` met alle bevindingen."""
    if bevindingen := toets(profiel, grenzen):
        raise ValidatieFout(profiel.naam, bevindingen)
    return profiel
