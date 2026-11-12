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

from dataclasses import dataclass
from typing import Any, Literal

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

Modelklasse = Literal["licht", "zwaar"]

#: Van het veld in de frontmatter naar het veld van het profiel. De eerste zes zijn de namen van een Claude
#: Code-subagent; de rest kent alleen Lex. De instructie is de tekst onder de frontmatter.
VELDEN: dict[str, str] = {
    "name": "naam",
    "description": "beschrijving",
    "tools": "tools",
    "skills": "skills",
    "model": "modelklasse",
    "maxTurns": "max_rondes",
    "mcpServers": "mcp",
    "kiesbaar": "kiesbaar",
    "connectors": "connectors",
    "sjablonen": "sjablonen",
    "budget": "budget",
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
    #: Verwijst naar de modelprofielen in het beheer.
    modelklasse: Modelklasse = "zwaar"
    #: Hoe lang en hoe duur; `None` is de grens van het platform.
    max_rondes: int | None = Field(default=None, ge=1)
    budget: int | None = Field(default=None, ge=1)


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
    #: Tools die een besluit van de jurist nemen, of anderszins niet aan een profiel horen. `NOOIT` geldt altijd.
    verboden_tools: frozenset[str] = frozenset()
    max_rondes: int | None = None
    budget: int | None = None


def _vorm(fout: ValidationError) -> list[Bevinding]:
    return [Bevinding("vorm", f"{'.'.join(str(d) for d in f['loc']) or 'profiel'}: {f['msg']}") for f in fout.errors()]


def uit_markdown(naam: str, tekst: str) -> Agentprofiel:
    """Het profiel uit `<naam>.md`. Gooit `ValidatieFout` als de vorm niet klopt; de grenzen toetst `toets`."""
    try:
        kop, instructie = frontmatter(tekst)
    except ValueError as f:
        raise ValidatieFout(naam, [Bevinding("frontmatter", str(f))]) from None
    if vreemd := sorted(set(kop) - set(VELDEN)):
        raise ValidatieFout(naam, [Bevinding("frontmatter", f"onbekende velden {vreemd}; toegestaan zijn {sorted(VELDEN)}")])
    velden: dict[str, Any] = {VELDEN[k]: tuple(v) if isinstance(v, list) else v for k, v in kop.items()}
    try:
        profiel = Agentprofiel(**velden, instructie=instructie)
    except ValidationError as f:
        raise ValidatieFout(naam, _vorm(f)) from None
    if profiel.naam != naam:
        raise ValidatieFout(naam, [Bevinding("naam", f"name is {profiel.naam!r}, maar het bestand heet {naam!r}")])
    return profiel


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
    kies("skills", profiel.skills, grenzen.skills)
    kies("connectors", profiel.connectors, grenzen.connectors)
    kies("mcp", profiel.mcp, grenzen.mcp)
    kies("sjablonen", profiel.sjablonen, grenzen.sjablonen)
    for veld, grens in (("max_rondes", grenzen.max_rondes), ("budget", grenzen.budget)):
        waarde = getattr(profiel, veld)
        if waarde is not None and grens is not None and waarde > grens:
            uit.append(Bevinding(veld, f"{veld}: {waarde} is meer dan de grens van {grens}"))
    return uit


def toegestane_tools(profiel: Agentprofiel, grenzen: Grenzen) -> frozenset[str]:
    """De tools die een agent met dit profiel krijgt. Ook een profiel met alle tools (`tools` is `None`) krijgt nooit
    wat verboden is."""
    alle = grenzen.tools - NOOIT - grenzen.verboden_tools
    return alle if profiel.tools is None else frozenset(profiel.tools) & alle


def valideer(profiel: Agentprofiel, grenzen: Grenzen) -> Agentprofiel:
    """Zoals `toets`, maar gooit `ValidatieFout` met alle bevindingen."""
    if bevindingen := toets(profiel, grenzen):
        raise ValidatieFout(profiel.naam, bevindingen)
    return profiel
